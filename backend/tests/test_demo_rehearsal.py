"""The demo rehearsal command: passing run, refusal rules, no-service path, and init.sh dispatch.

Everything here is offline: a threaded stdlib fake service on loopback (or a closed port), the
real synthetic review fixtures in one temporary copy, and the real ``scripts/init.sh``. No local
answer service, Ollama, container, app, or network is used, and canonical ``knowledge/`` is only
hashed.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPT = REPO_ROOT / "backend" / "scripts" / "demo_rehearsal.py"
INIT = REPO_ROOT / "scripts" / "init.sh"
CATALOG = REPO_ROOT / "knowledge" / "source_catalog.json"
PASSAGES = REPO_ROOT / "knowledge" / "passages.json"

sys.path.insert(0, str(BACKEND_ROOT))
from scripts import demo_rehearsal as rehearsal  # noqa: E402

APPROVED_URL = "https://www.juntadeandalucia.es/boja/2026/20/2"
GROUNDED_ANSWER = "Respuesta de ensayo; no afirma ningún plazo real."
TRAP_ANSWER = "No tengo una respuesta segura para esa pregunta."

GROUNDED: Dict[str, Any] = {
    "status": "answered",
    "answer": GROUNDED_ANSWER,
    "sources": [
        {
            "title": "Fuente de ensayo",
            "issuing_body": "Junta de Andalucía",
            "url": APPROVED_URL,
            "location": "Artículo 1",
            "published_or_updated_on": "2026-01-30",
            "verified_on": "2026-10-17",
            "excerpt": "Fragmento de ensayo.",
        }
    ],
    "land_scope": "general",
    "land_ids_to_choose": [],
}

TRAP: Dict[str, Any] = {
    "status": "abstained",
    "answer": TRAP_ANSWER,
    "sources": [],
    "land_scope": "general",
    "land_ids_to_choose": [],
}


def inspection(reason: Optional[str] = None, cited: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "schema": "answer-inspection-v1",
        "retrieval": None,
        "drafting": None,
        "verification": None,
        "outcome": {
            "abstention_reason": reason,
            "generation_reason": None if reason else "extractive",
            "cited_passage_ids": list(cited or []),
        },
        "total_ms": 1,
    }


AskHandler = Callable[[Dict[str, Any]], Tuple[int, Any]]


class FakeService:
    """A loopback fake of ``/health``, ``/ready``, and ``/ask`` that records every request."""

    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []
        self.ask: AskHandler = self.grounded_or_trap
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                outer.requests.append({"method": "GET", "path": self.path, "body": None})
                if self.path == "/health":
                    outer.send_json(self, 200, {"status": "ok", "service": "manijero-backend"})
                elif self.path == "/ready":
                    outer.send_json(self, 200, {"status": "ready", "service": "manijero-backend"})
                else:
                    outer.send_json(self, 404, {"status": "not_found"})

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    body = None
                outer.requests.append({"method": "POST", "path": self.path, "body": body})
                status, payload = outer.ask(body if isinstance(body, dict) else {})
                if isinstance(payload, bytes):
                    outer.send_bytes(self, status, payload)
                else:
                    outer.send_json(self, status, payload)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def grounded_or_trap(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        if "importe" in str(body.get("question", "")):
            return 200, dict(TRAP, inspection=inspection(reason="no_evidence"))
        return 200, dict(GROUNDED, inspection=inspection(cited=["pasaje-1"]))

    @staticmethod
    def send_json(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
        FakeService.send_bytes(
            handler, status, json.dumps(payload, ensure_ascii=False).encode("utf-8")
        )

    @staticmethod
    def send_bytes(handler: BaseHTTPRequestHandler, status: int, payload: bytes) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)

    @property
    def url(self) -> str:
        return "http://127.0.0.1:{}".format(self.server.server_address[1])

    def __enter__(self) -> "FakeService":
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def run_rehearsal(url: str, *, tmpdir: Optional[Path] = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    if tmpdir is not None:
        environment["TMPDIR"] = str(tmpdir)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--url", url],
        cwd=REPO_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def run_init(*args: str, extra: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment.update(extra or {})
    return subprocess.run(
        [str(INIT), *args],
        cwd=REPO_ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def step_lines(completed: subprocess.CompletedProcess) -> List[str]:
    return [
        line
        for line in completed.stdout.splitlines()
        if line.startswith(("PASS  ", "FAIL  ", "SKIP  "))
    ]


def statuses(completed: subprocess.CompletedProcess) -> List[str]:
    return [line.split("  ", 1)[0] for line in step_lines(completed)]


def result_lines(completed: subprocess.CompletedProcess) -> List[str]:
    return [line for line in completed.stdout.splitlines() if line.startswith("Result:")]


def knowledge_hashes() -> Dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (CATALOG, PASSAGES)
    }


def closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# --- A ready service --------------------------------------------------------


def test_rehearsal_passes_and_sends_general_non_retained_requests() -> None:
    hashes = knowledge_hashes()
    with FakeService() as service:
        completed = run_rehearsal(service.url)
        requests = list(service.requests)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert statuses(completed) == ["PASS", "PASS", "PASS", "PASS"]
    results = result_lines(completed)
    assert len(results) == 1
    assert results[0].startswith("Result: the demo rehearsal passed (4 of 4 steps)")
    assert service.url in results[0]
    assert "synthetic fixtures" in results[0]
    assert "canonical knowledge was not changed" in results[0]
    assert "Traceback" not in completed.stdout + completed.stderr

    asks = [request for request in requests if request["method"] == "POST"]
    assert [request["path"] for request in asks] == ["/ask", "/ask"]
    assert [request["body"]["question"] for request in asks] == [
        rehearsal.GROUNDED_QUESTION,
        rehearsal.TRAP_QUESTION,
    ]
    for request in asks:
        assert request["body"]["land_context"] == {"mode": "general", "lands": []}
        assert request["body"]["retain_for_improvement"] is False

    output = completed.stdout
    assert "fecha final" not in output
    assert "importe de ayuda" not in output
    assert GROUNDED_ANSWER not in output
    assert TRAP_ANSWER not in output
    assert rehearsal.NEW_PASSAGE_TEXT not in output
    assert knowledge_hashes() == hashes


def test_public_fields_pass_when_the_development_inspection_is_absent() -> None:
    with FakeService() as service:
        service.ask = lambda body: (
            (200, dict(TRAP))
            if "importe" in str(body.get("question", ""))
            else (200, dict(GROUNDED))
        )
        completed = run_rehearsal(service.url)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert statuses(completed) == ["PASS", "PASS", "PASS", "PASS"]


def test_trap_answered_fails_only_that_step_and_the_rest_still_runs() -> None:
    with FakeService() as service:
        service.ask = lambda body: (200, dict(GROUNDED, inspection=inspection(cited=["p"])))
        completed = run_rehearsal(service.url)

    assert completed.returncode == 1
    assert statuses(completed) == ["PASS", "PASS", "FAIL", "PASS"]
    failed = [line for line in step_lines(completed) if line.startswith("FAIL  ")]
    assert failed[0].startswith("FAIL  Trap abstention")
    result = result_lines(completed)[0]
    assert "failed" in result and "Trap abstention" in result


def test_malformed_grounded_reply_fails_that_step() -> None:
    def broken_grounded(body: Dict[str, Any]) -> Tuple[int, Any]:
        if "importe" in str(body.get("question", "")):
            return 200, dict(TRAP, inspection=inspection(reason="no_evidence"))
        return 200, b"{not json"

    with FakeService() as service:
        service.ask = broken_grounded
        completed = run_rehearsal(service.url)

    assert completed.returncode == 1
    assert statuses(completed) == ["PASS", "FAIL", "PASS", "PASS"]
    assert step_lines(completed)[1].startswith("FAIL  Grounded answer")
    assert "Traceback" not in completed.stdout + completed.stderr


def test_unapproved_source_address_fails_the_grounded_step() -> None:
    outside = dict(GROUNDED, sources=[dict(GROUNDED["sources"][0], url="https://example.invalid/x")])
    with FakeService() as service:
        service.ask = lambda body: (200, outside)
        completed = run_rehearsal(service.url)

    assert completed.returncode == 1
    assert statuses(completed)[1] == "FAIL"


def test_unknown_abstention_code_fails_the_trap_step() -> None:
    with FakeService() as service:
        service.ask = lambda body: (200, dict(TRAP, inspection=inspection(reason="made_up_code")))
        completed = run_rehearsal(service.url)

    assert completed.returncode == 1
    assert statuses(completed)[2] == "FAIL"
    assert "abstention code" in step_lines(completed)[2]


# --- No service -------------------------------------------------------------


def test_closed_port_skips_service_steps_and_still_runs_the_reviewed_update() -> None:
    hashes = knowledge_hashes()
    completed = run_rehearsal("http://127.0.0.1:{}".format(closed_port()))

    assert completed.returncode == 1
    assert statuses(completed) == ["SKIP", "SKIP", "SKIP", "PASS"]
    result = result_lines(completed)[0]
    assert result.startswith("Result: the demo rehearsal is incomplete (1 of 4 steps;")
    assert "skipped: Service, Grounded answer, Trap abstention" in result
    assert "Start it with ./scripts/init.sh --local-rag-start, then run this command again." in result
    assert "Traceback" not in completed.stdout + completed.stderr
    assert knowledge_hashes() == hashes


# --- The reviewed update, in process ----------------------------------------


def test_synthetic_proposal_is_declared_and_uses_the_fixed_values() -> None:
    proposal = rehearsal.synthetic_proposal()
    serialized = json.dumps(proposal, ensure_ascii=False)

    assert "sintético" in serialized
    assert proposal["author"]["identity"] == "preparador-sintetico"
    assert proposal["catalog"]["add"][0]["id"] == "fixture-rd-2200-2099"
    assert proposal["passages"]["add"][0]["text"] == "Texto sintético de revisión; no afirma ningún plazo real."
    assert rehearsal.REVIEWER == "Revisora de ensayo"


def test_reviewed_update_blocks_the_draft_and_leaves_canonical_knowledge_unchanged() -> None:
    hashes = rehearsal._canonical_hashes()
    step = rehearsal._review_step(hashes)

    assert (step.status, step.name) == ("PASS", "Reviewed update")
    assert rehearsal._canonical_hashes() == hashes


# --- The owner command ------------------------------------------------------


def test_init_script_runs_the_rehearsal_against_the_configured_port() -> None:
    if not os.access(BACKEND_ROOT / ".venv" / "bin" / "python", os.X_OK):
        pytest.skip("needs the linked shared backend/.venv (./scripts/init.sh --setup-python)")
    with FakeService() as service:
        port = service.url.rsplit(":", 1)[1]
        completed = run_init("--demo-rehearsal", extra={"MANIJERO_LOCAL_RAG_PORT": port})

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert statuses(completed) == ["PASS", "PASS", "PASS", "PASS"]
    assert len(result_lines(completed)) == 1


def test_init_script_refuses_an_extra_argument_without_a_request_or_a_write(tmp_path: Path) -> None:
    temporary = tmp_path / "tmp"
    temporary.mkdir()
    marker = REPO_ROOT / "local.properties"
    before_marker = marker.stat().st_mtime_ns if marker.exists() else None
    with FakeService() as service:
        port = service.url.rsplit(":", 1)[1]
        completed = run_init(
            "--demo-rehearsal",
            "extra",
            extra={"MANIJERO_LOCAL_RAG_PORT": port, "TMPDIR": str(temporary)},
        )
        requests = list(service.requests)

    assert completed.returncode == 2
    assert "Run --demo-rehearsal on its own, with nothing after it." in completed.stderr
    assert requests == []
    assert list(temporary.iterdir()) == []
    after_marker = marker.stat().st_mtime_ns if marker.exists() else None
    assert after_marker == before_marker
