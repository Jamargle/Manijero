"""The image definition in ``backend/container/``: static checks and in-process behavior, no Docker.

* the Dockerfile pins its base by digest, runs as a non-root user, sets the same service
  environment as ``--local-rag-start`` with image paths, installs the pinned requirements
  with torch from the CPU index, and never mentions a drafting runtime, reload, or a pilot key;
* that environment passes the real hybrid-retrieval and local-provider gates;
* ``Dockerfile.dockerignore`` is an allowlist (evaluated here with Docker's matching rules);
* the entry point's server settings are fixed, and the Ollama relay forwards bytes both ways
  between two ephemeral loopback sockets and only to its constant target;
* a staged-layout smoke copies exactly the allowlisted files into an ``/opt/manijero``-shaped
  temporary tree with a fixture release and starts the service there (BM25, extractive).
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import pytest

import test_local_rag_bootstrap as boot
from app import knowledge_release as kr
from app import local_rag_service as svc
from app.local_generation import PROVIDER_LOCAL, resolve_local_provider
from app.retrieval_backend import Bm25Backend, backend_from_environment

REPO_ROOT = boot.REPO_ROOT
CONTAINER = REPO_ROOT / "backend" / "container"
DOCKERFILE = CONTAINER / "Dockerfile"
IGNORE = CONTAINER / "Dockerfile.dockerignore"
RELEASE_ID = "0123456789abcdef"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


relay = _load("ollama_relay_under_test", CONTAINER / "ollama_relay.py")
entrypoint = _load("container_entrypoint_under_test", CONTAINER / "entrypoint.py")


def instructions() -> List[Tuple[str, str]]:
    """``(INSTRUCTION, arguments)`` pairs with comments dropped and continuations joined."""

    joined: List[str] = []
    current = ""
    for raw in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not current and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            current += line[:-1] + " "
            continue
        joined.append(current + line)
        current = ""
    return [(text.split(None, 1)[0].upper(), text.split(None, 1)[1] if " " in text else "") for text in joined]


def image_environment() -> Dict[str, str]:
    values: Dict[str, str] = {}
    for name, arguments in instructions():
        if name == "ENV":
            for key, value in re.findall(r"([A-Z_][A-Z0-9_]*)=(\S+)", arguments):
                values[key] = value
    return values


# --- Dockerfile ----------------------------------------------------------------------------


def test_the_base_image_is_pinned_by_tag_and_index_digest() -> None:
    steps = instructions()
    assert steps[0] == ("ARG", "BASE_IMAGE")
    assert [arguments for name, arguments in steps if name == "FROM"] == ["${BASE_IMAGE}"]
    pin = json.loads((CONTAINER / "base-image.json").read_text(encoding="utf-8"))
    assert set(pin) == {"image", "digest", "reviewed_on", "reason"}
    assert pin["image"] == "python:3.12-slim-bookworm"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", pin["digest"]), "a developer must record the reviewed index digest"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", pin["reviewed_on"]) and pin["reason"].strip()


def test_the_image_runs_as_a_non_root_user() -> None:
    users = [arguments for name, arguments in instructions() if name == "USER"]
    assert users == ["10001:10001"]
    assert [name for name, _ in instructions()][-4:] == ["USER", "WORKDIR", "EXPOSE", "ENTRYPOINT"]
    assert ("ENTRYPOINT", '["python", "/opt/manijero/backend/container/entrypoint.py"]') in instructions()
    assert ("EXPOSE", "8000") in instructions()


def test_the_service_environment_is_the_local_rag_one_with_image_paths() -> None:
    service_keys = {key for key in svc_launch_keys() if key.startswith("MANIJERO_")}
    environment = {key: value for key, value in image_environment().items() if key.startswith("MANIJERO_")}
    assert set(environment) == service_keys - {"MANIJERO_ACTIVE_CAMPAIGN"}
    assert environment == {
        "MANIJERO_KNOWLEDGE_RELEASE_ROOT": "/opt/manijero/knowledge-releases",
        "MANIJERO_RETRIEVAL_MODE": "hybrid",
        "MANIJERO_VECTOR_STORE": "/opt/manijero/knowledge-releases/releases/${RELEASE_ID}/vector-store",
        "MANIJERO_EMBEDDING_ARTIFACT": "/opt/manijero/models/bge-m3",
        "MANIJERO_GENERATION_PROVIDER": "local",
        "MANIJERO_LOCAL_MODEL": "${LOCAL_MODEL}",
    }


def svc_launch_keys() -> List[str]:
    """The keys ``--local-rag-start`` gives the service (no file is read or written)."""

    ctx = boot.lrb.Context(
        repo_root=REPO_ROOT,
        paths=boot.lrb.local_paths(Path("/home-for-keys")),
        knowledge_dir=boot.KNOWLEDGE,
        embedding_config=boot.FIXTURE_SPEC,
        generation_record=boot.RECORD_PATH,
        dev_python=boot.DEV_PYTHON,
        hybrid_python=boot.HYBRID_PYTHON,
        ollama_models=Path("/models"),
    )
    _, record = boot.lrb.load_pins(ctx, boot.NOW.date())
    return list(svc.launch_environment(ctx, boot.lrb.Settings("2026"), record, RELEASE_ID, {}))


def test_the_image_environment_passes_the_real_hybrid_and_local_provider_gates() -> None:
    environment = {
        key: value.replace("${RELEASE_ID}", RELEASE_ID).replace("${LOCAL_MODEL}", boot.RECORD["model"])
        for key, value in image_environment().items()
    }
    environment["MANIJERO_ACTIVE_CAMPAIGN"] = "2026"

    assert not isinstance(backend_from_environment(environment), Bm25Backend)  # built lazily, nothing loaded
    resolution = resolve_local_provider(
        environment, record_document=boot.RECORD, transport=object(), as_of=boot.NOW.date(), pilot=False, review_record=None
    )
    assert resolution.provider == PROVIDER_LOCAL and not resolution.blockers


def test_requirements_are_the_pinned_files_with_torch_from_the_cpu_index() -> None:
    runs = " ".join(arguments for name, arguments in instructions() if name == "RUN")
    assert "pip install --index-url https://download.pytorch.org/whl/cpu --requirement requirements-torch.txt" in runs
    assert "grep -E '^torch==' requirements-embeddings.txt" in runs
    assert "pip install --requirement requirements-hybrid.txt --requirement requirements-production.txt" in runs
    assert "pip freeze > /opt/manijero/pip-freeze.txt" in runs
    copies = [arguments for name, arguments in instructions() if name == "COPY"]
    assert "backend/deploy/requirements-production.txt ./requirements-production.txt" in copies


def test_the_dockerfile_never_mentions_a_drafting_runtime_reload_or_a_pilot_key() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8").lower()
    for word in ("ollama", "--reload", "pilot", "deployment_profile", "retention", "gemini", "token", ".env", "settings.env"):
        assert word not in text, word


def test_release_and_model_come_only_from_the_named_build_contexts() -> None:
    copies = [arguments for name, arguments in instructions() if name == "COPY"]
    assert "--from=knowledge-release --chown=10001:10001 . /opt/manijero/knowledge-releases/releases/${RELEASE_ID}/" in copies
    assert "--from=embedding-model . /opt/manijero/models/bge-m3/" in copies
    assert all(arguments.startswith(("backend/", "--from=")) for arguments in copies)


# --- Allowlist -----------------------------------------------------------------------------


def ignore_patterns() -> List[str]:
    lines = [line.strip() for line in IGNORE.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def _pattern_regex(pattern: str) -> "re.Pattern[str]":
    out = ""
    position = 0
    while position < len(pattern):
        if pattern.startswith("**/", position):
            out += "(?:.*/)?"
            position += 3
            continue
        if pattern.startswith("**", position):
            out += ".*"
            position += 2
            continue
        char = pattern[position]
        out += "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
        position += 1
    return re.compile(out + r"\Z")


def included(relative: str, patterns: List[str]) -> bool:
    """Docker's rule: the last matching pattern wins; a pattern matching a parent applies to children."""

    parts = relative.split("/")
    candidates = ["/".join(parts[: count + 1]) for count in range(len(parts))]
    keep = True
    for pattern in patterns:
        negate = pattern.startswith("!")
        body = pattern[1:] if negate else pattern
        regex = _pattern_regex(body.rstrip("/"))
        if any(regex.match(candidate) for candidate in candidates):
            keep = negate
    return keep


def context_files() -> List[str]:
    """Every file the build context would send (from the working tree under backend/)."""

    patterns = ignore_patterns()
    files: List[str] = []
    for current, directories, names in os.walk(REPO_ROOT / "backend"):
        directories[:] = [name for name in directories if not name.startswith(".venv") and name != "__pycache__"]
        for name in names:
            relative = str((Path(current) / name).relative_to(REPO_ROOT))
            if included(relative, patterns):
                files.append(relative)
    for name in os.listdir(REPO_ROOT):
        if (REPO_ROOT / name).is_file() and included(name, patterns):
            files.append(name)
    return sorted(files)


def test_the_dockerignore_is_an_allowlist_without_tests_virtualenvs_settings_or_examples() -> None:
    patterns = ignore_patterns()
    assert patterns[0] == "*"
    assert [pattern for pattern in patterns if pattern.startswith("!")] == [
        "!backend/app",
        "!backend/config",
        "!backend/requirements.txt",
        "!backend/requirements-embeddings.txt",
        "!backend/requirements-hybrid.txt",
        "!backend/deploy/requirements-production.txt",
        "!backend/container",
    ]
    for name in ("backend/tests/test_local_container.py", "backend/.venv/bin/python", "settings.env", "backend/app/x.env",
                 "backend/deploy/pilot.env.example", "backend/README.md", "knowledge/passages.json", ".env", "local.properties",
                 "backend/app/__pycache__/main.cpython-312.pyc", "backend/requirements-dev.txt", "backend/scripts/local_rag.py"):
        assert not included(name, patterns), name
    files = context_files()
    assert "backend/app/main.py" in files and "backend/container/ollama_relay.py" in files
    assert all(file.startswith(("backend/app/", "backend/config/", "backend/container/", "backend/requirements", "backend/deploy/requirements-production.txt")) for file in files)
    assert not [file for file in files if "/tests/" in file or file.endswith((".env", ".example", ".pyc"))]


# --- Entry point and relay -----------------------------------------------------------------


def test_the_entrypoint_server_settings_are_fixed() -> None:
    assert entrypoint.uvicorn_config() == {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": False,
        "access_log": False,
        "proxy_headers": False,
        "server_header": False,
    }


def test_the_relay_addresses_are_constants() -> None:
    assert relay.LISTEN == ("127.0.0.1", 11434)
    assert relay.TARGET == ("host.docker.internal", 11434)
    source = (CONTAINER / "ollama_relay.py").read_text(encoding="utf-8")
    assert "os.environ" not in source and "getenv" not in source and "import os" not in source


def _listener() -> socket.socket:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    return server


def _running_relay(target: Tuple[str, int]) -> Iterator[Tuple[str, int]]:
    server = relay.bind(("127.0.0.1", 0))
    stop = threading.Event()
    thread = threading.Thread(target=relay.serve, args=(server, target, stop), daemon=True)
    thread.start()
    try:
        yield server.getsockname()
    finally:
        stop.set()
        thread.join(timeout=5)
        server.close()


def test_the_relay_forwards_bytes_both_ways_and_closes_when_the_client_closes() -> None:
    upstream = _listener()
    seen: List[bytes] = []

    def echo() -> None:
        connection, _ = upstream.accept()
        with connection:
            while True:
                chunk = connection.recv(1024)
                if not chunk:
                    seen.append(b"<closed>")
                    break
                seen.append(chunk)
                connection.sendall(chunk.upper())

    worker = threading.Thread(target=echo, daemon=True)
    worker.start()
    for address in _running_relay(upstream.getsockname()):
        with socket.create_connection(address, timeout=5) as client:
            client.sendall(b"get /api/tags")
            assert client.recv(1024) == b"GET /API/TAGS"
        worker.join(timeout=5)
    upstream.close()
    assert seen == [b"get /api/tags", b"<closed>"]


def test_the_relay_closes_the_client_when_the_target_closes_or_is_absent() -> None:
    upstream = _listener()

    def say_bye() -> None:
        connection, _ = upstream.accept()
        connection.sendall(b"bye")
        connection.close()

    threading.Thread(target=say_bye, daemon=True).start()
    for address in _running_relay(upstream.getsockname()):
        with socket.create_connection(address, timeout=5) as client:
            received = b""
            while True:
                chunk = client.recv(1024)
                if not chunk:
                    break
                received += chunk
            assert received == b"bye"
    absent = upstream.getsockname()
    upstream.close()
    for address in _running_relay(absent):
        with socket.create_connection(address, timeout=5) as client:
            assert client.recv(1024) == b""


class _Tags(http.server.BaseHTTPRequestHandler):
    status = 200
    body = b'{"models": []}'

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args: Any) -> None:
        return None


@pytest.mark.parametrize("status, body, expected", [(200, b'{"models": []}', 0), (500, b"{}", 1), (200, b"not json", 1)])
def test_the_relay_check_reports_whether_tags_answer(status: int, body: bytes, expected: int) -> None:
    handler = type("Handler", (_Tags,), {"status": status, "body": body})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert relay.main(["--check"], listen=server.server_address[:2]) == expected
    finally:
        server.shutdown()
        server.server_close()
    closed = _listener()
    address = closed.getsockname()
    closed.close()
    assert relay.main(["--check"], listen=address) == 1
    assert relay.main(["--what"], listen=address) == 2


# --- Staged-layout smoke -------------------------------------------------------------------


COPY_MAP = (("backend/app/", "backend/app/"), ("backend/config/", "backend/config/"), ("backend/container/", "backend/container/"))

SMOKE = r"""
import json, sys
from datetime import date
from fastapi.testclient import TestClient
import app
from app.ask_api import get_as_of_date
from app.main import create_app
application = create_app()
application.dependency_overrides[get_as_of_date] = lambda: date(2026, 11, 1)
client = TestClient(application)
health, ready = client.get("/health"), client.get("/ready")
print(json.dumps({"app": app.__file__, "health": [health.status_code, health.json()], "ready": [ready.status_code, ready.json()]}))
"""


def test_the_allowlisted_files_start_the_service_in_the_image_layout(tmp_path: Path) -> None:
    (tmp_path / "setup").mkdir()
    env = boot.Env(tmp_path / "setup")
    assert env.setup("yes") == 0, env.output
    release_id = kr.current_release_id(env.paths.releases)
    opt = tmp_path / "opt" / "manijero"
    for file in context_files():
        for source, target in COPY_MAP:
            if file.startswith(source):
                destination = opt / target / file[len(source):]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / file, destination)
    releases = opt / "knowledge-releases"
    shutil.copytree(env.paths.releases / "releases" / release_id, releases / "releases" / release_id)
    (releases / "current").symlink_to(Path("releases") / release_id)
    backend = opt / "backend"
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "MANIJERO_ACTIVE_CAMPAIGN": "2026",
        "MANIJERO_KNOWLEDGE_RELEASE_ROOT": str(releases),
    }

    completed = subprocess.run(
        [sys.executable, "-c", SMOKE], cwd=backend, env=environment, capture_output=True, text=True, timeout=120, check=False
    )

    assert completed.returncode == 0, completed.stderr[-2000:]
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert Path(result["app"]).resolve().is_relative_to(backend.resolve())
    assert result["health"] == [200, {"status": "ok", "service": "manijero-backend"}]
    assert result["ready"] == [200, {"status": "ready", "service": "manijero-backend"}]
    assert not (opt / "knowledge").exists() and not (backend / "tests").exists()
