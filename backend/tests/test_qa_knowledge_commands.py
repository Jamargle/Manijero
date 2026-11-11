"""The QA knowledge owner commands through ``./scripts/init.sh`` (the automated owner walkthrough).

The owner guide (``docs/owner-guide/qa.md``, "Send approved knowledge to QA") is covered by this test
instead of a manual walkthrough (owner decision 2026-11-11): every documented command runs through
``scripts/init.sh`` exactly as the guide writes it, with the owner's ``yes`` typed on a pseudo-terminal.

Each run uses temporary QA and local homes; a local bare ``origin`` and a clone whose ``main`` holds fake
builder scripts plus fixture knowledge; fake ``docker`` and ``tailscale`` programs that keep their state in
files; a loopback HTTP server that plays the QA service; and fake tokens. Nothing real is built, run,
shared, or fetched, and no real token is read or printed.
"""

from __future__ import annotations

import json
import os
import pty
import re
import shutil
import socket
import subprocess
import sys
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from app import environment_profiles as profiles
from app import knowledge_release as kr

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"
GUIDE = REPO_ROOT / "docs" / "owner-guide" / "qa.md"
VENV_PYTHON = BACKEND_ROOT / ".venv" / "bin" / "python"
KNOWLEDGE = REPO_ROOT / "knowledge"
FILES = ("source_catalog.json", "passages.json", "pac_answer_eval.json")
COMMANDS = ["--qa-knowledge-deploy", "--qa-knowledge-rollback"]
DEPLOY, ROLLBACK = COMMANDS
AS_OF = date(2026, 10, 13)
NAME = "mac-mini.tail1234.ts.net"
ROLLBACK_HINT = "./scripts/init.sh --qa-knowledge-rollback"

pytestmark = pytest.mark.skipif(
    not os.access(VENV_PYTHON, os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)

FAKE_DOCKER = """#!{python}
import json, os, shutil, sys
from pathlib import Path

argv = sys.argv[1:]
state_path = Path(os.environ["FAKE_DOCKER_STATE"])
with Path(os.environ["FAKE_DOCKER_CALLS"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(argv) + "\\n")
state = json.loads(state_path.read_text(encoding="utf-8"))


def save():
    state_path.write_text(json.dumps(state), encoding="utf-8")


def values(option):
    return [argv[i + 1] for i, item in enumerate(argv) if item == option]


if argv[0] == "info":
    print("27.3.1")
elif argv[:2] == ["image", "inspect"]:
    image = state["images"].get(argv[2])
    if image is None:
        print("Error: No such image", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps([{{"Id": "sha256:one", "Size": 1, "Config": {{"Labels": image}}}}]))
elif argv[:2] == ["container", "inspect"]:
    box = state["container"]
    if box is None:
        print("Error: No such container", file=sys.stderr)
        raise SystemExit(1)
    ports = {{"8000/tcp": [{{"HostIp": "127.0.0.1", "HostPort": box["port"]}}]}} if box["running"] else {{}}
    print(json.dumps([{{
        "Config": {{"Labels": box["labels"]}},
        "State": {{"Running": box["running"], "StartedAt": "2026-11-11T09:30:12.1Z"}},
        "NetworkSettings": {{"Ports": ports}},
    }}]))
elif argv[0] == "run":
    labels = dict(item.split("=", 1) for item in values("--label"))
    labels.setdefault("org.manijero.knowledge-release", state["image_release"])
    state["container"] = {{"labels": labels, "running": True, "port": values("--publish")[0].split(":")[1]}}
    save()
    print("c0ffee")
elif argv[0] == "rm":
    state["container"] = None
    save()
elif argv[0] == "logs":
    print("service started")
elif argv[0] == "cp":
    if state.get("cp_fails"):
        raise SystemExit(1)
    shutil.copytree(state["image_release_dir"], argv[2])
elif argv[0] in ("exec", "stop", "tag"):
    pass
else:
    raise SystemExit(64)
"""

FAKE_TAILSCALE = """#!{python}
import json, os, sys
from pathlib import Path

argv = sys.argv[1:]
state_path = Path(os.environ["FAKE_TAILSCALE_STATE"])
with Path(os.environ["FAKE_TAILSCALE_CALLS"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(argv) + "\\n")
state = json.loads(state_path.read_text(encoding="utf-8"))
name = "{name}"
if argv == ["status", "--json"]:
    node = {{"DNSName": name + ".", "CapMap": {{"https": None, "https://tailscale.com/cap/funnel": None}}}}
    print(json.dumps({{"BackendState": "Running", "Self": node}}))
elif argv == ["funnel", "status", "--json"]:
    key = name + ":443"
    on = {{
        "TCP": {{"443": {{"HTTPS": True}}}},
        "Web": {{key: {{"Handlers": {{"/": {{"Proxy": "http://127.0.0.1:" + os.environ["MANIJERO_QA_PORT"]}}}}}}}},
        "AllowFunnel": {{key: True}},
    }}
    print(json.dumps(on if state["funnel"] else {{}}))
elif argv[:2] == ["funnel", "--bg"]:
    state["funnel"] = True
    state_path.write_text(json.dumps(state), encoding="utf-8")
elif argv == ["funnel", "--https=443", "off"]:
    state["funnel"] = False
    state_path.write_text(json.dumps(state), encoding="utf-8")
else:
    raise SystemExit(64)
"""

FAKE_GATE = """import os, sys
sys.exit(int(os.environ.get("FAKE_GATE_CODE", "0")))
"""

FAKE_EMBEDDINGS = """import sys
from pathlib import Path

args = sys.argv[1:]
Path(args[args.index("--index") + 1]).write_text("{{}}", encoding="utf-8")
"""

FAKE_RELEASE = """import json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, "{backend}")
from app import knowledge_release as kr

args = sys.argv[1:]
assert args[0] == "prepare" and "--with-vector-store" in args and "--json" in args


def option(name):
    return args[args.index(name) + 1]


result = kr.prepare_release(
    root=Path(option("--root")),
    catalog=Path(option("--catalog")),
    passages=Path(option("--passages")),
    cases=Path(option("--cases")),
    as_of=date.fromisoformat(option("--as-of")),
    active_campaign=option("--active-campaign"),
    code_revision=option("--code-revision"),
    reviewed_baseline_revision=option("--reviewed-baseline-revision"),
)
print(json.dumps({{
    "gate": "passed" if result.passed else "failed",
    "release_id": result.release_id,
    "failures": ",".join(result.failures) or "none",
}}))
sys.exit(0 if result.passed else 1)
"""


def free_port() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return str(probe.getsockname()[1])


def git(cwd: Path, *args: str) -> str:
    environment = dict(
        os.environ, GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="t@example.invalid",
    )
    completed = subprocess.run(
        ["git", *args], cwd=cwd, env=environment, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


class Owner:
    """One temporary owner machine: homes, a clone with a local bare origin, fakes, and a QA service."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp = tmp_path
        self.port = free_port()
        self.local_home = tmp_path / "local"
        self.qa_home = tmp_path / "qa"
        self.address_file = tmp_path / "qa-address.local"
        monkeypatch.setenv("MANIJERO_LOCAL_HOME", str(self.local_home))
        self.qa_home.mkdir()
        (self.qa_home / "settings.env").write_text(profiles.render_template(self.qa_home), encoding="utf-8")
        profiles.make_new_credentials(self.qa_home, profiles.QA_CLIENT_ID)
        self.token = profiles.read_token(profiles.credential_paths(self.qa_home, profiles.QA_CLIENT_ID).token)
        profiles.write_public_url(self.qa_home, "https://" + NAME)
        self.address_file.write_text("https://" + NAME + "\n", encoding="utf-8")
        self._model()
        self._image_release()
        self._remote()
        self._fakes()
        self.bad_metrics = False
        self._serve()

    # -- setup ---------------------------------------------------------------------------

    def _model(self) -> None:
        artifact = self.local_home / "models" / "bge-m3"
        artifact.mkdir(parents=True)
        payload = b'{"hidden_size": 1024, "max_position_embeddings": 8194}'
        (artifact / "config.json").write_bytes(payload)
        import hashlib

        document = json.loads((REPO_ROOT / "backend" / "config" / "bge_m3_embedding.json").read_text(encoding="utf-8"))
        document["files"] = [{"path": "config.json", "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}]
        self.pin = self.tmp / "pin.json"
        self.pin.write_text(json.dumps(document), encoding="utf-8")

    def _image_release(self) -> None:
        source = self.tmp / "image-knowledge"
        source.mkdir()
        for name in FILES:
            shutil.copy(KNOWLEDGE / name, source / name)
        root = self.tmp / "image-root"
        result = kr.prepare_release(
            root=root, catalog=source / FILES[0], passages=source / FILES[1], cases=source / FILES[2],
            as_of=AS_OF, active_campaign="2026", code_revision="a" * 40, reviewed_baseline_revision="a" * 40,
        )
        self.image_id = result.release_id
        self.image_dir = root / kr.RELEASES_DIR / self.image_id

    def _remote(self) -> None:
        self.remote = self.tmp / "remote.git"
        self.checkout = self.tmp / "checkout"
        git(self.tmp, "init", "--bare", "--initial-branch=main", str(self.remote))
        git(self.tmp, "clone", str(self.remote), str(self.checkout))
        git(self.checkout, "checkout", "-b", "main")
        scripts = self.checkout / "backend" / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "check_quality_gate.py").write_text(FAKE_GATE, encoding="utf-8")
        (scripts / "manage_embeddings.py").write_text(FAKE_EMBEDDINGS.format(), encoding="utf-8")
        (scripts / "knowledge_release.py").write_text(FAKE_RELEASE.format(backend=BACKEND_ROOT), encoding="utf-8")
        knowledge = self.checkout / "knowledge"
        knowledge.mkdir()
        for name in FILES:
            shutil.copy(KNOWLEDGE / name, knowledge / name)
        self.merge(" (revisado)")

    def merge(self, suffix: str) -> str:
        """The owner merges a knowledge change on GitHub: ``origin/main`` gets new knowledge."""

        path = self.checkout / "knowledge" / FILES[0]
        document = json.loads((KNOWLEDGE / FILES[0]).read_text(encoding="utf-8"))
        document["sources"][0]["title"] += suffix
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        git(self.checkout, "add", "-A")
        git(self.checkout, "commit", "-m", "merge " + suffix)
        git(self.checkout, "push", "origin", "main")
        self.main_sha = git(self.checkout, "rev-parse", "HEAD")
        return self.main_sha

    def _fakes(self) -> None:
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        self.docker = bin_dir / "docker"
        self.docker.write_text(FAKE_DOCKER.format(python=sys.executable), encoding="utf-8")
        self.tailscale = bin_dir / "tailscale"
        self.tailscale.write_text(FAKE_TAILSCALE.format(python=sys.executable, name=NAME), encoding="utf-8")
        for script in (self.docker, self.tailscale):
            script.chmod(0o755)
        self.docker_state = self.tmp / "docker-state.json"
        self.docker_calls = self.tmp / "docker-calls.txt"
        self.tailscale_state = self.tmp / "tailscale-state.json"
        self.tailscale_calls = self.tmp / "tailscale-calls.txt"
        labels = {
            "org.manijero.managed": "1",
            "org.manijero.knowledge-release": self.image_id,
            "org.manijero.revision": "a" * 40,
            "org.manijero.campaign": "2026",
            "org.manijero.launchers": "default,pilot",
        }
        self.docker_json = {
            "images": {"manijero-backend:local": labels, "manijero-backend:qa-current": labels},
            "container": None,
            "image_release": self.image_id,
            "image_release_dir": str(self.image_dir),
        }
        self.set_running(True)
        self.tailscale_state.write_text(json.dumps({"funnel": True}), encoding="utf-8")

    def set_running(self, running: bool) -> None:
        self.docker_json["container"] = (
            {
                "labels": {
                    "org.manijero.managed": "1",
                    "org.manijero.environment": "qa",
                    "org.manijero.knowledge-release": self.image_id,
                },
                "running": True,
                "port": self.port,
            }
            if running
            else None
        )
        self.docker_state.write_text(json.dumps(self.docker_json), encoding="utf-8")

    def docker_state_now(self) -> dict:
        return json.loads(self.docker_state.read_text(encoding="utf-8"))

    def served(self) -> Optional[str]:
        box = self.docker_state_now()["container"]
        return box["labels"]["org.manijero.knowledge-release"] if box else None

    def _serve(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                return

            def _send(self, status: int, body: str, kind: str = "application/json") -> None:
                payload = body.encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", kind)
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:  # noqa: N802 - http.server API
                if self.path == "/health":
                    self._send(200, json.dumps({"service": "manijero-backend"}))
                elif self.path == "/ready":
                    self._send(200, json.dumps({"status": "ready"}))
                elif self.path == "/metrics":
                    if self.headers.get("authorization") != "Bearer " + str(owner.token):
                        self._send(401, "{}")
                        return
                    release = owner.served() or "none"
                    if owner.bad_metrics and release != owner.image_id:
                        release = "f" * 16
                    self._send(200, 'manijero_knowledge_release_info{release_id="%s",state="serving"} 1\n' % release, "text/plain")
                else:
                    self._send(404, "{}")

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                self.rfile.read(int(self.headers.get("content-length") or 0))
                self._send(200, json.dumps({"status": "abstained"})) if self.path == "/ask" else self._send(404, "{}")

        self.server = ThreadingHTTPServer(("127.0.0.1", int(self.port)), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    # -- running -------------------------------------------------------------------------

    def run(self, *args: str, answer: Optional[str] = "yes\n", extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        environment = dict(os.environ)
        environment.update(
            {
                "MANIJERO_LOCAL_HOME": str(self.local_home),
                "MANIJERO_QA_HOME": str(self.qa_home),
                "MANIJERO_QA_ADDRESS_FILE": str(self.address_file),
                "MANIJERO_DOCKER_CLI": str(self.docker),
                "MANIJERO_TAILSCALE_CLI": str(self.tailscale),
                "MANIJERO_QA_PORT": self.port,
                "MANIJERO_OLLAMA_CLI": str(self.tmp / "no-ollama-here"),
                "MANIJERO_QA_KNOWLEDGE_REPO": str(self.checkout),
                "MANIJERO_QA_KNOWLEDGE_DEV_PYTHON": sys.executable,
                "MANIJERO_QA_KNOWLEDGE_HYBRID_PYTHON": sys.executable,
                "MANIJERO_QA_KNOWLEDGE_EMBEDDING_CONFIG": str(self.pin),
                "MANIJERO_QA_KNOWLEDGE_TODAY": AS_OF.isoformat(),
                "MANIJERO_QA_PUBLIC_PROBE_URL": "http://127.0.0.1:" + self.port,
                "FAKE_DOCKER_STATE": str(self.docker_state),
                "FAKE_DOCKER_CALLS": str(self.docker_calls),
                "FAKE_TAILSCALE_STATE": str(self.tailscale_state),
                "FAKE_TAILSCALE_CALLS": str(self.tailscale_calls),
            }
        )
        environment.update(extra or {})
        master = slave = None
        stdin: object = subprocess.DEVNULL
        if answer is not None:
            master, slave = pty.openpty()
            os.write(master, answer.encode("utf-8"))
            stdin = slave
        try:
            return subprocess.run(
                [str(INIT), *args], cwd=REPO_ROOT, env=environment, stdin=stdin,  # type: ignore[arg-type]
                capture_output=True, text=True, timeout=240, check=False,
            )
        finally:
            for descriptor in (master, slave):
                if descriptor is not None:
                    os.close(descriptor)

    def docker_runs(self) -> List[List[str]]:
        if not self.docker_calls.exists():
            return []
        calls = [json.loads(line) for line in self.docker_calls.read_text(encoding="utf-8").splitlines()]
        return [call for call in calls if call[0] == "run"]

    def current(self) -> Optional[str]:
        root = self.qa_home / "knowledge-releases"
        return kr.current_release_id(root) if (root / "releases").is_dir() else None


@pytest.fixture
def owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    machine = Owner(tmp_path, monkeypatch)
    yield machine
    machine.close()


def results(completed: subprocess.CompletedProcess) -> List[str]:
    return [line for line in completed.stdout.splitlines() if line.startswith("Result:")]


def one_result(completed: subprocess.CompletedProcess) -> str:
    (result,) = results(completed)
    assert completed.stdout.splitlines()[-1] == result
    assert "Traceback" not in completed.stdout + completed.stderr
    return result


@pytest.mark.parametrize("mode", COMMANDS)
def test_an_extra_argument_is_misuse(owner: Owner, mode: str) -> None:
    completed = owner.run(mode, "extra")
    assert completed.returncode == 2
    assert completed.stderr.strip() == "Run {} on its own, with nothing after it.".format(mode)
    assert completed.stdout == ""


def test_the_owner_guide_names_both_commands() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    for command in COMMANDS:
        assert "./scripts/init.sh " + command in text


def test_deploy_sends_the_merged_knowledge_to_qa_and_status_shows_it(owner: Owner) -> None:
    completed = owner.run(DEPLOY)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    new = owner.current()
    assert new and new != owner.image_id
    assert one_result(completed) == (
        "Result: QA now answers from knowledge release {} (main at {}). If something is wrong, run {}.".format(
            new, owner.main_sha[:7], ROLLBACK_HINT
        )
    )
    assert owner.served() == new
    (run,) = owner.docker_runs()
    assert "type=bind,source={},target=/opt/manijero/qa-knowledge-releases".format(owner.qa_home / "knowledge-releases") in run
    assert "MANIJERO_KNOWLEDGE_RELEASE_ROOT=/opt/manijero/qa-knowledge-releases" in run
    assert "--cap-drop" in run and "127.0.0.1:{}:8000".format(owner.port) in run
    assert owner.token not in completed.stdout + completed.stderr + " ".join(run)
    assert not list((owner.qa_home / "work").iterdir())
    assert git(owner.checkout, "status", "--porcelain") == ""
    status = owner.run("--qa-status", answer=None)
    assert status.returncode == 0, status.stdout
    assert "Knowledge: release {} published to QA.".format(new) in status.stdout
    again = owner.run(DEPLOY)
    assert again.returncode == 0 and one_result(again) == (
        "Result: QA already has the approved knowledge from main; nothing was changed."
    )
    assert owner.current() == new


def test_a_failed_gate_publishes_nothing(owner: Owner) -> None:
    completed = owner.run(DEPLOY, extra={"FAKE_GATE_CODE": "1"})
    assert completed.returncode == 1
    result = one_result(completed)
    assert result.startswith("Result: the approved knowledge was not sent to QA: ")
    assert result.endswith("QA keeps answering from knowledge release {}.".format(owner.image_id))
    assert owner.current() == owner.image_id and owner.served() == owner.image_id and not owner.docker_runs()


def test_failed_qa_checks_after_the_switch_roll_back_automatically(owner: Owner) -> None:
    owner.bad_metrics = True
    completed = owner.run(DEPLOY)
    assert completed.returncode == 1, completed.stdout
    result = one_result(completed)
    assert result.startswith("Result: the new knowledge failed the QA checks (QA does not report the knowledge release")
    assert "so QA went back to knowledge release {} automatically.".format(owner.image_id) in result
    assert owner.current() == owner.image_id and owner.served() == owner.image_id
    assert len(owner.docker_runs()) == 2
    assert list((owner.qa_home / "logs").glob("qa-knowledge-deploy-*.log"))


def test_rollback_goes_back_and_running_it_again_goes_forward(owner: Owner) -> None:
    first = owner.run(ROLLBACK)
    assert first.returncode == 1
    assert one_result(first) == "Result: there is no earlier QA knowledge to go back to; nothing was changed."
    assert owner.run(DEPLOY).returncode == 0
    new = owner.current()
    back = owner.run(ROLLBACK)
    assert back.returncode == 0, back.stdout
    assert one_result(back) == "Result: QA was rolled back to knowledge release {}.".format(owner.image_id)
    assert owner.current() == owner.image_id and owner.served() == owner.image_id
    forward = owner.run(ROLLBACK)
    assert one_result(forward) == "Result: QA was rolled back to knowledge release {}.".format(new)
    assert owner.served() == new


def test_a_missing_prerequisite_changes_nothing_and_is_fixed_by_starting_qa(owner: Owner) -> None:
    owner.set_running(False)
    for mode, prefix in ((DEPLOY, "Result: the approved knowledge was not sent to QA. "), (ROLLBACK, "Result: QA's knowledge was not rolled back. ")):
        completed = owner.run(mode)
        assert completed.returncode == 1
        assert "QA is not running." in completed.stdout
        assert one_result(completed) == prefix + "Start it with ./scripts/init.sh --qa-deploy"
    assert owner.current() is None and not owner.docker_runs()
    owner.set_running(True)  # what ./scripts/init.sh --qa-deploy does
    recovered = owner.run(DEPLOY)
    assert recovered.returncode == 0 and one_result(recovered).startswith("Result: QA now answers from knowledge release ")


def test_without_a_terminal_or_with_another_answer_nothing_is_changed(owner: Owner) -> None:
    silent = owner.run(DEPLOY, answer=None)
    assert silent.returncode == 1 and "no Terminal window" in silent.stdout
    assert one_result(silent).startswith("Result: the approved knowledge was not sent to QA. Run this command in a Terminal window")
    declined = owner.run(DEPLOY, answer="no\n")
    assert declined.returncode == 1 and "Nothing was changed." in declined.stdout
    assert one_result(declined) == "Result: the approved knowledge was not sent to QA. You did not type yes."
    assert owner.current() == owner.image_id and not owner.docker_runs()


def test_a_missing_search_model_is_reported_with_its_fix(owner: Owner) -> None:
    shutil.rmtree(owner.local_home / "models" / "bge-m3")
    completed = owner.run(DEPLOY)
    assert completed.returncode == 1
    assert one_result(completed) == "Result: the approved knowledge was not sent to QA. Run ./scripts/init.sh --local-rag-setup"
    assert re.search(r"bge-m3", completed.stdout)
