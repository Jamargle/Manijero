"""Command tests for the report-only metrics report.

Every test reads the real, read-only ``knowledge/`` files unless it says otherwise, uses an
in-process FastAPI client, and blocks sockets. No live service, Ollama, judge, or network is
needed: the judge is faked at its transport and Ollama seams.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from datetime import date
from pathlib import Path
import socket
from typing import Any, Callable, Optional

import pytest

from app.answer_eval import AnswerEvalError
from app.gemini_generation import GeminiDraftRequest
from app.local_generation import load_local_model_record
from app.local_rag_bootstrap import OllamaUnavailable

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
KNOWLEDGE = ROOT / "knowledge"
SCRIPT = BACKEND / "scripts" / "evaluate_metrics.py"
FIXED_DAY = date(2026, 11, 8)
ENV_KEYS = (
    "MANIJERO_GENERATION_PROVIDER",
    "MANIJERO_LOCAL_MODEL",
    "MANIJERO_GEMINI_MODEL",
    "MANIJERO_ANSWER_TRACE",
    "MANIJERO_RERANKER",
    "MANIJERO_RETRIEVAL_MODE",
    "MANIJERO_STRUCTURED_INDEX",
    "MANIJERO_STRUCTURED_INDEX_DIR",
    "MANIJERO_KNOWLEDGE_RELEASE_ROOT",
    "MANIJERO_QUESTION_GLOSSARY",
    "MANIJERO_ANSWER_CACHE",
)


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("tests must not open a socket")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def _script() -> Any:
    spec = importlib.util.spec_from_file_location("evaluate_metrics_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT_MODULE = _script()


# --- fakes ---------------------------------------------------------------------------------


class TickClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        self.now += 1.0
        return self.now

    def utc_day(self) -> date:
        return FIXED_DAY


class FakeResponse:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def read(self, size: int = -1) -> bytes:
        return self._raw if size < 0 else self._raw[:size]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


class FakeOpener:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def open(self, request: Any, timeout: float = 0) -> FakeResponse:
        self.urls.append(request.full_url)
        return FakeResponse(b"{}")


class FakeOllama:
    def __init__(self, models: Any) -> None:
        self._models = models

    def cli_present(self) -> bool:
        return True

    def tags(self) -> Any:
        if isinstance(self._models, BaseException):
            raise self._models
        return self._models

    def pull(self, model: str) -> int:
        return 0


class ScriptedGenerator:
    def __init__(self, behave: Callable[[int, dict], str]) -> None:
        self.behave = behave
        self.requests: list[GeminiDraftRequest] = []

    def send(self, request: GeminiDraftRequest) -> str:
        self.requests.append(request)
        return self.behave(len(self.requests), json.loads(request.payload_json))


class ScriptedJudge:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.requests: list[GeminiDraftRequest] = []

    def send(self, request: GeminiDraftRequest) -> str:
        self.requests.append(request)
        return self.replies[(len(self.requests) - 1) % len(self.replies)]


def _two_sentences(call: int, payload: dict) -> str:
    ids = [int(item["passage_id"]) for item in payload["passages"]]
    answer = "Primera frase afirmada [1]. Segunda frase afirmada [1]."
    return json.dumps({"status": "answered", "answer": answer, "sources": ids})


def _entry(document: dict) -> dict:
    return {"name": document["model"], "model": document["model"], "digest": document["digest"]}


def _judge_options(tmp_path: Path, *, available: bool) -> dict[str, Any]:
    judge_record = json.loads(
        (BACKEND / "config" / "grounding_judge_model.json").read_text(encoding="utf-8")
    )
    generator_record = dict(load_local_model_record() or {})
    models = (
        [_entry(generator_record), _entry(judge_record)]
        if available
        else OllamaUnavailable("not_running")
    )
    return {
        "opener": FakeOpener(),
        "generator_transport": ScriptedGenerator(_two_sentences),
        "judge_transport": ScriptedJudge(
            ['{"verdict":"supported"}', '{"verdict":"not_supported"}']
        ),
        "ollama": FakeOllama(models),
        "clock": TickClock(),
        "error_log": tmp_path / "judge-last-error.log",
    }


# --- helpers -------------------------------------------------------------------------------


def _run(
    tmp_path: Path,
    *extra: str,
    reports_root: Optional[Path] = None,
    judge_options: Optional[dict[str, Any]] = None,
    capsys: Any = None,
) -> tuple[int, str, Path]:
    root = reports_root if reports_root is not None else tmp_path / "reports"
    if capsys is not None:
        capsys.readouterr()
    code = SCRIPT_MODULE.main(
        ["run", "--as-of", "2026-11-10", *extra],
        reports_root=root,
        judge_options=judge_options,
    )
    output = capsys.readouterr().out if capsys is not None else ""
    return code, output, root


def _result_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("Result:")]


def _report_file(root: Path) -> Path:
    files = list(root.glob("*/metrics.json"))
    assert len(files) == 1, files
    return files[0]


def _report(root: Path) -> dict:
    return json.loads(_report_file(root).read_text(encoding="utf-8"))


def _tree_hashes(path: Path) -> dict[str, str]:
    return {
        str(item.relative_to(path)): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


# --- scenario 1: the approved sets ---------------------------------------------------------


def _approved_golden_count() -> int:
    golden_doc = json.loads((KNOWLEDGE / "golden_set.json").read_text(encoding="utf-8"))
    return sum(1 for item in golden_doc["items"] if item["review_state"] == "approved")


def test_real_sets_counts_17_golden_26_and_report_written(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    golden = _approved_golden_count()
    code, output, root = _run(tmp_path, "--no-judge", capsys=capsys)

    assert code == 0
    report = _report(root)
    assert report["schema_version"] == "eval-metrics-report-v1"
    assert report["case_counts"] == {
        "reviewed": 17,
        "golden": golden,
        "trap": 26,
        "total": 17 + golden + 26,
    }
    assert len(report["cases"]) == 17 + golden + 26
    assert report["version"]["k"] == 5
    assert report["version"]["retrieval_mode"] == "bm25"
    assert report["version_id"] == report["version_id"].lower()
    assert len(report["version_id"]) == 16
    lines = _result_lines(output)
    assert len(lines) == 1
    assert f"(17 reviewed, {golden} golden, 26 trap)" in lines[0]
    assert "faithfulness: not judged (skipped)" in lines[0]
    assert lines[0].endswith("Report only, no gate. Report: metrics.json.")


def test_drafts_and_rejected_items_never_counted(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    traps_doc = json.loads((KNOWLEDGE / "trap_set.json").read_text(encoding="utf-8"))
    variants = {item["variant_of"] for item in traps_doc["items"] if "variant_of" in item}
    golden_doc = json.loads((KNOWLEDGE / "golden_set.json").read_text(encoding="utf-8"))
    candidates = [item for item in golden_doc["items"] if item["id"] not in variants]
    draft, rejected = candidates[0], candidates[1]
    draft["review_state"] = "draft"
    draft.pop("decision", None)
    rejected["review_state"] = "rejected"
    rejected["decision"]["decision"] = "rejected"
    synthetic = tmp_path / "golden_set.json"
    synthetic.write_text(json.dumps(golden_doc), encoding="utf-8")

    code, output, root = _run(
        tmp_path, "--no-judge", "--golden", str(synthetic), capsys=capsys
    )

    assert code == 0
    report = _report(root)
    golden = _approved_golden_count() - 2
    assert report["case_counts"]["golden"] == golden
    assert report["case_counts"]["total"] == 17 + golden + 26
    ids = {row["id"] for row in report["cases"]}
    assert draft["id"] not in ids
    assert rejected["id"] not in ids
    assert f"(17 reviewed, {golden} golden, 26 trap)" in _result_lines(output)[0]


# --- scenario 7: deterministic and version-keyed -------------------------------------------


def test_two_runs_byte_identical_and_knowledge_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    before = _tree_hashes(KNOWLEDGE)

    first_code, _, root = _run(tmp_path, "--no-judge", capsys=capsys)
    first = _report_file(root).read_bytes()
    second_code, _, _ = _run(tmp_path, "--no-judge", capsys=capsys)
    second = _report_file(root).read_bytes()

    assert (first_code, second_code) == (0, 0)
    assert first == second
    assert _tree_hashes(KNOWLEDGE) == before
    text = first.decode("utf-8")
    assert str(ROOT) not in text
    assert '"label": "repository"' in text


def test_glossary_flag_changes_the_version(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _, _, root = _run(tmp_path, "--no-judge", capsys=capsys)
    without = _report(root)
    _, _, _ = _run(tmp_path, "--no-judge", "--glossary", "on", capsys=capsys)
    reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in root.glob("*/metrics.json")
    ]
    with_glossary = next(item for item in reports if item["version"]["glossary"] != "off")

    assert without["version"]["glossary"] == "off"
    assert len(with_glossary["version"]["glossary"]) == 64
    assert with_glossary["version_id"] != without["version_id"]


# --- scenario 8: isolation ----------------------------------------------------------------


def test_environment_keys_removed_then_restored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    for index, key in enumerate(ENV_KEYS):
        monkeypatch.setenv(key, f"sentinel-{index}")

    with SCRIPT_MODULE._isolated_environment():
        for key in ENV_KEYS:
            if key == "MANIJERO_ANSWER_CACHE":
                assert os.environ[key] == "off"
            else:
                assert key not in os.environ
    for index, key in enumerate(ENV_KEYS):
        assert os.environ[key] == f"sentinel-{index}"

    code, _, root = _run(tmp_path, "--no-judge", capsys=capsys)

    assert code == 0
    assert _report(root)["version"]["glossary"] == "off"
    for index, key in enumerate(ENV_KEYS):
        assert os.environ[key] == f"sentinel-{index}"


# --- scenario 9: failures stop cleanly ----------------------------------------------------


def test_invalid_inputs_exit_2_nothing_written_old_report_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root = tmp_path / "reports"
    old = root / "earlier" / "metrics.json"
    old.parent.mkdir(parents=True)
    old.write_text('{"old": true}\n', encoding="utf-8")

    code, output, _ = _run(
        tmp_path,
        "--no-judge",
        "--catalog",
        str(tmp_path / "missing.json"),
        reports_root=root,
        capsys=capsys,
    )

    assert code == 2
    assert _result_lines(output) == [
        "Result: the metrics report did not run (invalid_inputs): the knowledge files or the "
        "case lists could not be read; a developer must check them. Nothing was written."
    ]
    assert old.read_text(encoding="utf-8") == '{"old": true}\n'
    assert [path.name for path in root.iterdir()] == ["earlier"]


def test_ask_failure_exit_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise AnswerEvalError("case x: /ask returned invalid status")

    monkeypatch.setattr(SCRIPT_MODULE, "evaluate", broken)
    code, output, root = _run(tmp_path, "--no-judge", capsys=capsys)

    assert code == 2
    assert "ask_failed" in _result_lines(output)[0]
    assert not list(root.glob("*/metrics.json"))


def test_internal_error_traceback_only_in_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    def broken(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("secret-detail")

    monkeypatch.setattr(SCRIPT_MODULE, "evaluate", broken)
    code, output, root = _run(tmp_path, "--no-judge", capsys=capsys)

    assert code == 2
    assert _result_lines(output) == [
        "Result: the metrics report did not run (internal_error): something unexpected stopped "
        "the run; a developer can read build/eval-reports/last-error.log. Nothing was written."
    ]
    assert "secret-detail" not in output
    assert "RuntimeError: secret-detail" in (root / "last-error.log").read_text(encoding="utf-8")
    assert not list(root.glob("*/metrics.json"))


# --- scenario 6: faithfulness -------------------------------------------------------------


def test_judge_unavailable_fake_ollama_reports_not_judged(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    code, output, root = _run(
        tmp_path,
        judge_options=_judge_options(tmp_path, available=False),
        capsys=capsys,
    )

    assert code == 0
    report = _report(root)
    assert report["faithfulness"] == {"status": "not_judged", "reason": "ollama_unavailable"}
    assert "supported_share" not in report["faithfulness"]
    assert "verdicts" not in report["faithfulness"]
    assert "faithfulness: not judged (ollama_unavailable)" in _result_lines(output)[0]


def test_judge_available_fake_transports_reports_judged(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    code, output, root = _run(
        tmp_path,
        judge_options=_judge_options(tmp_path, available=True),
        capsys=capsys,
    )

    assert code == 0
    report = _report(root)
    faithfulness = report["faithfulness"]
    judge_record = json.loads(
        (BACKEND / "config" / "grounding_judge_model.json").read_text(encoding="utf-8")
    )
    generator_record = load_local_model_record()
    assert faithfulness["status"] == "judged"
    assert set(faithfulness["by_case_set"]) == {"reviewed", "golden"}
    assert faithfulness["judge"] == {
        "model": judge_record["model"],
        "digest": judge_record["digest"],
    }
    assert faithfulness["generator"] == {
        "model": generator_record["model"],
        "digest": generator_record["digest"],
    }
    assert faithfulness["drafts_from"] == "local_generator"
    assert faithfulness["judge_review"] == "unchecked_against_human_review"
    assert faithfulness["report"].endswith("grounding-judge.json")
    assert (root / report["version_id"] / "grounding-judge.json").is_file()
    assert "supported (unchecked against human review)" in _result_lines(output)[0]


def test_judge_stdout_not_printed(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _, output, _ = _run(
        tmp_path,
        judge_options=_judge_options(tmp_path, available=True),
        capsys=capsys,
    )

    assert "Checked case" not in output
    assert len(_result_lines(output)) == 1
