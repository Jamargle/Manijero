"""Tests for the offline grounding judge.

No test needs Ollama or any network: the generator and the judge are in-process fakes, the
Ollama opener is an in-process fake that records every URL, and sockets are blocked for every
test. The judge record under ``fixtures/grounding_judge/`` is a clearly labelled synthetic
fixture; the committed judge record is checked separately. The inputs are the real, read-only
``knowledge/`` files (the run never writes there).
"""

from __future__ import annotations

import ast
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import stat
import subprocess
from typing import Any, Callable, Optional

import jsonschema
import pytest

import app.grounding_judge as judge_module
import app.local_generation as local_module
from app.gemini_generation import GeminiDraftRequest
from app.local_generation import (
    OLLAMA_BASE_URL,
    RECORD_KEYS,
    LocalTransportError,
    evaluate_local_model_record,
    load_local_model_record,
)
from app.local_rag_bootstrap import OllamaUnavailable

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
KNOWLEDGE = ROOT / "knowledge"
SCRIPT = BACKEND / "scripts" / "judge_grounding.py"
SYNTHETIC_JUDGE = Path(__file__).resolve().parent / "fixtures" / "grounding_judge" / "synthetic_judge_record.json"
COMMITTED_JUDGE = BACKEND / "config" / "grounding_judge_model.json"
SCHEMA = json.loads((KNOWLEDGE / "grounding-judge-report.schema.json").read_text(encoding="utf-8"))
FIXED_DAY = date(2026, 11, 8)
INPUT_FILES = ("source_catalog.json", "passages.json", "pac_answer_eval.json", "golden_set.json")


# --- fakes -----------------------------------------------------------------------------------


class TickClock:
    """Every ``monotonic`` read advances one second, so the generator's rate window never fills."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        self.now += 1.0
        return self.now

    def utc_day(self) -> date:
        return FIXED_DAY


class FixedClock(TickClock):
    """Time never moves, so the generator's 30-per-minute limit is reached."""

    def monotonic(self) -> float:
        return self.now


class ScriptedGenerator:
    """Answers each request through ``behave(call_number, payload)``; an exception is raised."""

    def __init__(self, behave: Callable[[int, dict], str]) -> None:
        self.behave = behave
        self.requests: list[GeminiDraftRequest] = []

    def send(self, request: GeminiDraftRequest) -> str:
        self.requests.append(request)
        return self.behave(len(self.requests), json.loads(request.payload_json))


class ScriptedJudge:
    """Cycles through ``replies``; an exception instance is raised."""

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.requests: list[GeminiDraftRequest] = []

    def send(self, request: GeminiDraftRequest) -> str:
        self.requests.append(request)
        reply = self.replies[(len(self.requests) - 1) % len(self.replies)]
        if isinstance(reply, BaseException):
            raise reply
        return reply

    def payloads(self) -> list[dict]:
        return [json.loads(request.payload_json) for request in self.requests]


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
    """Records every URL; answers ``/api/show`` with a fixed document and the rest with ``{}``."""

    def __init__(self, show: Optional[dict] = None) -> None:
        self.urls: list[str] = []
        self.show = show or {}

    def open(self, request: Any, timeout: float = 0) -> FakeResponse:
        self.urls.append(request.full_url)
        body = self.show if request.full_url.endswith("/api/show") else {}
        return FakeResponse(json.dumps(body).encode("utf-8"))


class FakeOllama:
    def __init__(
        self,
        models: Any,
        *,
        cli: bool = True,
        pull_code: int = 0,
        after_pull: Any = None,
    ) -> None:
        self._models = models
        self._after_pull = after_pull
        self._cli = cli
        self._pull_code = pull_code
        self.pulled: list[str] = []

    def cli_present(self) -> bool:
        return self._cli

    def tags(self) -> list:
        models = self._after_pull if self.pulled and self._after_pull is not None else self._models
        if isinstance(models, BaseException):
            raise models
        return models

    def pull(self, model: str) -> int:
        self.pulled.append(model)
        return self._pull_code


def _record(path: Path = SYNTHETIC_JUDGE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry(document: dict, digest: Optional[str] = None) -> dict:
    return {"name": document["model"], "model": document["model"], "digest": digest or document["digest"]}


GENERATOR = dict(load_local_model_record() or {})
JUDGE_FIXTURE = _record()


def _both_models() -> list[dict]:
    return [_entry(GENERATOR), _entry(JUDGE_FIXTURE)]


@pytest.fixture(autouse=True)
def _no_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("tests must not open a socket")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def _script() -> Any:
    spec = importlib.util.spec_from_file_location("judge_grounding_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _draft(payload: dict, answer: str) -> str:
    ids = [int(item["passage_id"]) for item in payload["passages"]]
    return json.dumps({"status": "answered", "answer": answer, "sources": ids})


def _two_sentences(call: int, payload: dict) -> str:
    return _draft(payload, "Primera frase afirmada [1]. Segunda frase afirmada [1][2].")


def _args(report: Path, *, judge_record: Path = SYNTHETIC_JUDGE, **overrides: str) -> list[str]:
    values = {
        "--catalog": str(KNOWLEDGE / "source_catalog.json"),
        "--passages": str(KNOWLEDGE / "passages.json"),
        "--cases": str(KNOWLEDGE / "pac_answer_eval.json"),
        "--golden": str(KNOWLEDGE / "golden_set.json"),
        "--active-campaign": "2026",
        "--as-of": "2026-11-08",
        "--report": str(report),
        "--judge-record": str(judge_record),
    }
    values.update(overrides)
    return ["run"] + [item for pair in values.items() for item in pair]


def _run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    *,
    generator: Optional[ScriptedGenerator] = None,
    judge: Optional[ScriptedJudge] = None,
    ollama: Optional[FakeOllama] = None,
    opener: Optional[FakeOpener] = None,
    clock: Optional[TickClock] = None,
    report: Optional[Path] = None,
    **overrides: Any,
) -> tuple[int, str, Path, ScriptedGenerator, ScriptedJudge, FakeOpener]:
    generator = generator or ScriptedGenerator(_two_sentences)
    judge = judge or ScriptedJudge(['{"verdict":"supported"}', '{"verdict":"not_supported"}'])
    opener = opener or FakeOpener()
    target = report or tmp_path / "out" / "report.json"
    capsys.readouterr()
    code = _script().main(
        _args(target, **{k: v for k, v in overrides.items() if k.startswith("--")}),
        opener=opener,
        generator_transport=generator,
        judge_transport=judge,
        ollama=ollama or FakeOllama(_both_models()),
        clock=clock or TickClock(),
        error_log=tmp_path / "last-error.log",
    )
    return code, capsys.readouterr().out, target, generator, judge, opener


def _report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line.startswith("Result:")]


def _judged_rows(report: dict) -> list[dict]:
    return [case for case in report["cases"] if case["outcome"] in ("local_used", "verifier_rejected")]


# --- scenario 1: each draft sentence gets one judged verdict ----------------------------------


def test_answered_draft_sentences_each_get_one_verdict(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    code, output, target, generator, judge, _ = _run(tmp_path, capsys)

    assert code == 0
    report = _report(target)
    jsonschema.validate(report, SCHEMA)
    assert len(_result_lines(output)) == 1
    drafted = [case for case in _judged_rows(report) if len(case["sentences"]) == 2]
    assert drafted, "at least one case reaches drafting"
    # A case that offered one passage cannot validate the second sentence's [2].
    for case in drafted:
        assert case["sentences"][0]["verdict"] in judge_module.JUDGED_VERDICTS
        assert case["sentences"][1]["verdict"] in judge_module.JUDGED_VERDICTS + ("citation_invalid",)
    both = [case for case in drafted if case["sentences"][1]["verdict"] != "citation_invalid"]
    assert both, "at least one case offered two passages"
    first = both[0]
    assert [sentence["index"] for sentence in first["sentences"]] == [1, 2]
    assert first["sentences"][0]["text"] == "Primera frase afirmada."
    assert first["sentences"][0]["cited"] == [1]
    assert first["sentences"][1]["text"] == "Segunda frase afirmada."
    assert first["sentences"][1]["cited"] == [1, 2]
    # The judge saw each sentence with only the excerpts of the passages it cites.
    for payload in judge.payloads():
        assert "[" not in payload["sentence"]
        cited = [1] if payload["sentence"].startswith("Primera") else [1, 2]
        assert [item["number"] for item in payload["passages"]] == cited
    offered = {
        (case_payload["question"], item["passage_id"]): item["text"]
        for case_payload in (json.loads(r.payload_json) for r in generator.requests)
        for item in case_payload["passages"]
    }
    judged_texts = {item["text"] for payload in judge.payloads() for item in payload["passages"]}
    assert judged_texts <= set(offered.values())
    assert all(request.model == JUDGE_FIXTURE["model"] for request in judge.requests)
    assert all(request.timeout_seconds == judge_module.JUDGE_TIMEOUT_SECONDS for request in judge.requests)
    assert "Checked case 1 of " in output


# --- scenario 2: only model drafts are judged --------------------------------------------------


def test_non_drafted_outcomes_are_counted_not_judged(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    def behave(call: int, payload: dict) -> str:
        mode = call % 6
        if mode == 1:
            raise TimeoutError()
        if mode == 2:
            raise LocalTransportError("http_error")
        if mode == 3:
            return "this is not json"
        if mode == 4:
            return json.dumps({"status": "abstained", "answer": "", "sources": []})
        if mode == 5:
            return _draft(payload, "Frase inventada con cifra 99 [1].")
        verbatim = payload["passages"][0]["text"]  # the first excerpt, copied, so the verifier accepts it
        answer = verbatim if "[" in verbatim else verbatim.rstrip() + " [1]"
        return json.dumps({"status": "answered", "answer": answer, "sources": [1]})

    code, _, target, _, judge, _ = _run(
        tmp_path, capsys, generator=ScriptedGenerator(behave), clock=FixedClock()
    )

    assert code == 0
    report = _report(target)
    outcomes = report["summary"]["outcomes"]
    for name in ("timeout", "transport_error", "malformed_output", "provider_abstained", "rate_limited", "not_drafted"):
        assert outcomes.get(name, 0) > 0, name
    judged_total = 0
    for case in report["cases"]:
        if case["outcome"] in ("local_used", "verifier_rejected"):
            judged_total += len(case["sentences"])
        else:
            assert case["sentences"] == [], case["outcome"]
    assert len(judge.requests) <= judged_total
    assert len(judge.requests) > 0
    assert outcomes.get("local_used", 0) > 0 and outcomes.get("verifier_rejected", 0) > 0
    summary = report["summary"]
    assert summary["drafts"] == outcomes["local_used"] + outcomes["verifier_rejected"]
    assert summary["by_verifier"]["accepted"]["sentences"] > 0
    assert summary["by_verifier"]["rejected"]["sentences"] > 0


# --- scenario 3: sentences the judge cannot see are marked, not sent -------------------------------


def test_uncited_and_out_of_range_markers_skip_the_judge(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    def behave(call: int, payload: dict) -> str:
        return _draft(payload, "Sin cita alguna. Cita fuera de rango [9]. Con cita valida [1].")

    code, _, target, _, judge, _ = _run(tmp_path, capsys, generator=ScriptedGenerator(behave))

    assert code == 0
    rows = [case for case in _judged_rows(_report(target)) if case["sentences"]]
    assert rows
    for case in rows:
        verdicts = [sentence["verdict"] for sentence in case["sentences"]]
        assert verdicts[0] == "uncited" and verdicts[1] == "citation_invalid"
        assert verdicts[2] in judge_module.JUDGED_VERDICTS
        assert case["sentences"][1]["cited"] == [9]
    assert len(judge.requests) == len(rows)
    assert all(payload["sentence"] == "Con cita valida." for payload in judge.payloads())


# --- scenario 4: judge output fails closed -----------------------------------------------------------


def _one_sentence(call: int, payload: dict) -> str:
    return _draft(payload, "Una sola frase [1].")


@pytest.mark.parametrize(
    "reply",
    [
        "texto secreto del juez",
        '["supported"]',
        "{}",
        '{"verdict":"supported","extra":"x"}',
        '{"verdict":"maybe-secret"}',
        '{"verdict":3}',
    ],
)
def test_invalid_judge_output_fails_closed(
    reply: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    code, output, target, _, _, _ = _run(
        tmp_path, capsys, generator=ScriptedGenerator(_one_sentence), judge=ScriptedJudge([reply])
    )

    assert code == 0
    report = _report(target)
    judged = [sentence for case in report["cases"] for sentence in case["sentences"]]
    assert judged and {sentence["verdict"] for sentence in judged} == {"unjudged_invalid_output"}
    block = report["summary"]["overall"]
    assert block["verdicts"]["supported"] == 0 and block["supported_share"] is None
    for secret in ("secreto", "maybe-secret"):
        assert secret not in output
        assert secret not in target.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "error", [TimeoutError(), LocalTransportError("http_error"), LocalTransportError("response_invalid")]
)
def test_judge_transport_errors_are_unjudged(
    error: BaseException, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    code, _, target, _, judge, _ = _run(
        tmp_path, capsys, generator=ScriptedGenerator(_one_sentence), judge=ScriptedJudge([error])
    )

    assert code == 0
    judged = [sentence for case in _report(target)["cases"] for sentence in case["sentences"]]
    assert judged and {sentence["verdict"] for sentence in judged} == {"unjudged_error"}
    assert len(judge.requests) == len(judged)


def test_parse_verdict_is_strict() -> None:
    parse = judge_module.parse_verdict

    assert parse('{"verdict":"supported"}') == "supported"
    assert parse('{"verdict":"not_supported"}') == "not_supported"
    assert parse('{"verdict":"unclear"}') == "unclear"
    for bad in (None, 3, "", "nope", "[]", "{}", '{"verdict":"uncited"}', '{"verdict":"Supported"}',
                '{"verdict":"supported","why":"x"}', '{"verdict":["supported"]}'):
        assert parse(bad) is None


# --- scenario 5: scores are labelled unchecked --------------------------------------------------------


def _row(case_id: str, case_set: str, outcome: str, verdicts: list[str]) -> dict:
    return {
        "id": case_id,
        "case_set": case_set,
        "outcome": outcome,
        "sentences": [
            {"index": i, "text": "t", "cited": [1], "verdict": verdict} for i, verdict in enumerate(verdicts, 1)
        ],
    }


def test_summary_shares_splits_and_unchecked_label() -> None:
    rows = [
        _row("a", "reviewed", "local_used", ["supported", "supported", "not_supported", "uncited"]),
        _row("b", "golden", "verifier_rejected", ["unclear", "supported", "unjudged_error"]),
        _row("c", "golden", "timeout", []),
        _row("d", "reviewed", "local_used", ["citation_invalid", "unjudged_invalid_output"]),
    ]

    summary = judge_module.summarize(rows)

    overall = summary["overall"]
    assert overall["sentences"] == 9
    assert overall["verdicts"]["supported"] == 3
    assert overall["supported_share"] == round(3 / 5, 4)  # supported / (supported + not_supported + unclear)
    assert summary["by_verifier"]["accepted"]["supported_share"] == round(2 / 3, 4)
    assert summary["by_verifier"]["rejected"]["supported_share"] == 0.5
    assert summary["by_case_set"]["reviewed"]["supported_share"] == round(2 / 3, 4)
    assert summary["by_case_set"]["golden"]["supported_share"] == 0.5
    assert summary["drafts"] == 3 and summary["cases"] == 4
    assert summary["outcomes"] == {"local_used": 2, "timeout": 1, "verifier_rejected": 1}
    empty = judge_module.summarize([_row("e", "golden", "local_used", ["uncited", "unjudged_error"])])
    assert empty["overall"]["supported_share"] is None
    assert judge_module.summarize([])["overall"]["supported_share"] is None


def test_report_is_labelled_unchecked_and_stdout_has_no_text(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    code, output, target, generator, judge, _ = _run(tmp_path, capsys)

    assert code == 0
    report = _report(target)
    assert report["judge_review"] == "unchecked_against_human_review"
    assert report["limits"] == list(judge_module.LIMITS)
    assert any("not checked against human review" in line for line in report["limits"])
    assert any("No accuracy" in line for line in report["limits"])
    (line,) = _result_lines(output)
    assert "unchecked against human review" in line
    assert line.startswith("Result: judged ") and " draft sentences from " in line
    for request in generator.requests[:5]:
        payload = json.loads(request.payload_json)
        assert payload["question"] not in output
        assert all(item["text"] not in output for item in payload["passages"])
    assert "afirmada" not in output
    assert not any(line.startswith(("{", "[")) for line in output.splitlines())


# --- scenario 6: pins and preconditions abort before writing --------------------------------------------


def _write(path: Path, document: Any) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _precondition(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Keyword arguments for ``_run`` that trigger the named failure."""

    report = tmp_path / "out" / "report.json"
    if name == "judge_model_unpinned":
        return {"--judge-record": str(_write(tmp_path / "judge.json", {**JUDGE_FIXTURE, "digest": "unpinned"}))}
    if name == "judge_model_record_invalid":
        return {"--judge-record": str(_write(tmp_path / "judge.json", {**JUDGE_FIXTURE, "timeout_seconds": 99}))}
    if name == "generator_model_record_invalid":
        monkeypatch.setattr(local_module, "DEFAULT_RECORD_PATH", _write(tmp_path / "generator.json", {"model": "x"}))
        return {}
    if name == "judge_same_as_generator":
        return {"--judge-record": str(local_module.DEFAULT_RECORD_PATH)}
    if name == "ollama_unavailable":
        return {"ollama": FakeOllama(OllamaUnavailable("not_running"))}
    if name == "generator_unavailable":
        return {"ollama": FakeOllama([_entry(JUDGE_FIXTURE)])}
    if name == "generator_unavailable_digest":
        return {"ollama": FakeOllama([_entry(GENERATOR, "0" * 64), _entry(JUDGE_FIXTURE)])}
    if name == "judge_unavailable":
        return {"ollama": FakeOllama([_entry(GENERATOR), _entry(JUDGE_FIXTURE, "0" * 64)])}
    if name == "invalid_inputs":
        return {"--cases": str(tmp_path / "missing.json")}
    if name == "unsafe_report_inside_knowledge":
        return {"report": KNOWLEDGE / "grounding-report.json"}
    if name == "unsafe_report_is_input":
        copy = tmp_path / "catalog-copy.json"
        shutil.copy(KNOWLEDGE / "source_catalog.json", copy)
        return {"--catalog": str(copy), "report": copy}
    raise AssertionError(name)


EXPECTED_CODE = {
    "generator_unavailable_digest": "generator_unavailable",
    "unsafe_report_inside_knowledge": "unsafe_report_path",
    "unsafe_report_is_input": "unsafe_report_path",
}


@pytest.mark.parametrize(
    "name",
    [
        "judge_model_unpinned",
        "judge_model_record_invalid",
        "generator_model_record_invalid",
        "judge_same_as_generator",
        "ollama_unavailable",
        "generator_unavailable",
        "generator_unavailable_digest",
        "judge_unavailable",
        "invalid_inputs",
        "unsafe_report_inside_knowledge",
        "unsafe_report_is_input",
    ],
)
def test_preconditions_abort_without_writing(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The report path tests below point inside knowledge/ or at an input, which must stay untouched.
    knowledge_before = {f: (KNOWLEDGE / f).read_bytes() for f in INPUT_FILES}
    kwargs = _precondition(name, tmp_path, monkeypatch)
    report = kwargs.get("report") or tmp_path / "out" / "report.json"
    kwargs["report"] = report
    if report.parent == tmp_path / "out":
        report.parent.mkdir()
        report.write_bytes(b"earlier report")
    before = report.read_bytes() if report.exists() else None
    generator, judge = ScriptedGenerator(_two_sentences), ScriptedJudge(['{"verdict":"supported"}'])

    code, output, _, _, _, _ = _run(tmp_path, capsys, generator=generator, judge=judge, **kwargs)

    assert code == 2
    (line,) = _result_lines(output)
    assert EXPECTED_CODE.get(name, name) in line
    assert "Nothing was written" in line
    assert generator.requests == [] and judge.requests == []
    assert "Checked case" not in output
    assert (report.read_bytes() if report.exists() else None) == before
    assert {f: (KNOWLEDGE / f).read_bytes() for f in INPUT_FILES} == knowledge_before
    if name == "unsafe_report_inside_knowledge":
        assert not report.exists()


@pytest.mark.parametrize("code", ["connection_refused", "model_not_found", "model_digest_mismatch"])
def test_a_judge_that_disappears_mid_run_aborts_without_writing(
    code: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    report = tmp_path / "out" / "report.json"
    report.parent.mkdir()
    report.write_bytes(b"earlier report")

    status, output, _, _, judge, _ = _run(
        tmp_path, capsys, judge=ScriptedJudge([LocalTransportError(code)]), report=report
    )

    assert status == 2
    (line,) = _result_lines(output)
    assert "judge_unavailable" in line and "Nothing was written" in line
    assert len(judge.requests) == 1
    assert report.read_bytes() == b"earlier report"
    assert not list(report.parent.glob("*.tmp"))


def test_an_unexpected_failure_logs_the_trace_to_a_file_only(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("secret internal text")

    monkeypatch.setattr(judge_module, "write_report", boom)
    code, output, _, _, _, _ = _run(tmp_path, capsys)

    assert code == 2
    (line,) = _result_lines(output)
    assert "internal_error" in line
    assert "secret internal text" not in output
    assert "RuntimeError" not in output
    assert not (tmp_path / "out" / "report.json").exists()
    assert "secret internal text" in (tmp_path / "last-error.log").read_text(encoding="utf-8")


# --- scenario 7: deterministic, loopback only, live path untouched -----------------------------------------


def test_report_is_byte_identical_across_runs(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    first = _run(tmp_path, capsys, report=tmp_path / "one" / "report.json")
    second = _run(tmp_path, capsys, report=tmp_path / "two" / "report.json")

    assert first[0] == second[0] == 0
    assert first[2].read_bytes() == second[2].read_bytes()
    report = _report(first[2])
    assert report["generator"] == {"model": GENERATOR["model"], "digest": GENERATOR["digest"]}
    assert report["judge"] == {"model": JUDGE_FIXTURE["model"], "digest": JUDGE_FIXTURE["digest"]}
    assert report["instruction_versions"] == {"generator": "gemini-draft-v2", "judge": "grounding-judge-v1"}
    names = ("catalog", "passages", "cases", "golden")
    for name, file in zip(names, INPUT_FILES):
        assert report["inputs"][f"{name}_sha256"] == hashlib.sha256((KNOWLEDGE / file).read_bytes()).hexdigest()
    assert not {"timestamp", "started_at", "generated_at"} & set(report)


def test_only_the_loopback_constant_is_used_and_knowledge_is_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    before = {path: path.read_bytes() for path in KNOWLEDGE.glob("*.json")}
    opener = FakeOpener()

    code, _, _, _, _, _ = _run(tmp_path, capsys, opener=opener)

    assert code == 0
    assert opener.urls == [OLLAMA_BASE_URL + "/api/generate"] * 2  # one load-only call per model
    assert {path: path.read_bytes() for path in KNOWLEDGE.glob("*.json")} == before


def test_ask_path_does_not_import_the_judge_module() -> None:
    for path in (BACKEND / "app").glob("*.py"):
        if path.name == "grounding_judge.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "")] + [alias.name for alias in node.names]
            else:
                continue
            assert not any("grounding_judge" in name for name in names), path.name


def test_judge_module_imports_only_the_standard_library_and_app() -> None:
    tree = ast.parse((BACKEND / "app" / "grounding_judge.py").read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            roots.add((node.module or "").split(".")[0])
    assert roots <= {"__future__", "json", "os", "datetime", "pathlib", "re", "typing", "app"}


# --- scenario 8: setup -----------------------------------------------------------------------------------------


def _setup(ollama: FakeOllama, capsys: pytest.CaptureFixture, record: Path = SYNTHETIC_JUDGE) -> tuple[int, str]:
    capsys.readouterr()
    code = _script().main(["setup", "--judge-record", str(record)], ollama=ollama, opener=FakeOpener(), clock=TickClock())
    return code, capsys.readouterr().out


def test_setup_pulls_verifies_and_reports_ready(capsys: pytest.CaptureFixture) -> None:
    before = SYNTHETIC_JUDGE.read_bytes()
    ollama = FakeOllama([_entry(GENERATOR)], after_pull=_both_models())

    code, output = _setup(ollama, capsys)

    assert code == 0
    assert ollama.pulled == [JUDGE_FIXTURE["model"]]
    assert _result_lines(output) == ["Result: the grounding judge model is ready."]
    assert SYNTHETIC_JUDGE.read_bytes() == before


def test_setup_already_ready_skips_pull(capsys: pytest.CaptureFixture) -> None:
    ollama = FakeOllama(_both_models())

    code, output = _setup(ollama, capsys)

    assert code == 0 and ollama.pulled == []
    (line,) = _result_lines(output)
    assert "already ready" in line


@pytest.mark.parametrize(
    "case",
    ["unpinned", "invalid", "no_cli", "not_running", "pull_failed", "mismatch", "missing_after_pull"],
)
def test_setup_failures_print_pinned_lines_and_never_edit_record(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    record = tmp_path / "judge.json"
    document = dict(JUDGE_FIXTURE)
    ollama = FakeOllama([])
    expected = case
    if case == "unpinned":
        document["digest"] = "unpinned"
    elif case == "invalid":
        document["num_ctx"] = 1
    elif case == "no_cli":
        ollama = FakeOllama([], cli=False)
    elif case == "not_running":
        ollama = FakeOllama(OllamaUnavailable("not_running"))
    elif case == "pull_failed":
        ollama = FakeOllama([], pull_code=1)
    elif case == "mismatch":
        ollama = FakeOllama([], after_pull=[_entry(JUDGE_FIXTURE, "0" * 64)])
    else:
        ollama = FakeOllama([], after_pull=[])
        expected = "pull_failed"
    _write(record, document)
    before = record.read_bytes()
    script = _script()

    code, output = _setup(ollama, capsys, record)

    assert code != 0
    assert _result_lines(output) == [script.SETUP_LINES[expected]]
    assert record.read_bytes() == before
    if case in ("unpinned", "invalid", "no_cli", "not_running"):
        assert ollama.pulled == []


# --- the committed record, check-record, show-pin ---------------------------------------------------------------


def test_committed_judge_record_is_valid_and_differs_from_generator() -> None:
    document = _record(COMMITTED_JUDGE)

    assert list(document) == list(_record(local_module.DEFAULT_RECORD_PATH))
    assert set(document) == RECORD_KEYS
    gate, record = evaluate_local_model_record(document, as_of=FIXED_DAY)
    assert gate.passed and record is not None
    assert record.model == "qwen2.5:7b-instruct-q4_K_M"
    assert record.digest == "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
    assert record.size_bytes == 4683087332 and record.parameter_size == "7.6B"
    assert record.quantization == "Q4_K_M" and record.license == "Apache-2.0"
    assert "832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e" in record.license_reference
    assert "11343 chars" in record.license_reference and "0.40.14" in record.license_reference
    assert record.recorded_on == date(2026, 11, 8)
    judge, generator = judge_module.check_records(document, _record(local_module.DEFAULT_RECORD_PATH), FIXED_DAY)
    assert (judge.model, judge.digest) != (generator.model, generator.digest)
    assert judge_module.JUDGE_TIMEOUT_SECONDS > record.timeout_seconds  # per-request constant, not the record


def test_check_record_command(capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
    script = _script()

    assert script.main(["check-record"], clock=TickClock()) == 0
    assert "valid and pinned" in capsys.readouterr().out
    unpinned = _write(tmp_path / "judge.json", {**JUDGE_FIXTURE, "digest": "unpinned"})
    assert script.main(["check-record", "--judge-record", str(unpinned)], clock=TickClock()) == 2
    assert "judge_model_unpinned" in capsys.readouterr().out


def test_check_records_requires_a_different_family() -> None:
    generator = _record(local_module.DEFAULT_RECORD_PATH)
    same_family = {**JUDGE_FIXTURE, "model": "mistral-tiny:1b", "digest": "a" * 64}

    with pytest.raises(judge_module.JudgeAbort) as raised:
        judge_module.check_records(same_family, generator, FIXED_DAY)
    assert raised.value.failure == "judge_same_as_generator"
    with pytest.raises(judge_module.JudgeAbort) as raised:
        judge_module.check_records({**JUDGE_FIXTURE, "digest": generator["digest"]}, generator, FIXED_DAY)
    assert raised.value.failure == "judge_same_as_generator"


def test_show_pin_prints_without_writing(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    license_text = "Apache License, Version 2.0, January 2004"
    opener = FakeOpener(show={"license": license_text, "details": {"family": "synthetic"}})
    ollama = FakeOllama(_both_models())
    before = sorted(path.name for path in tmp_path.iterdir())
    record_before = SYNTHETIC_JUDGE.read_bytes()

    code = _script().main(
        ["show-pin", "--judge-record", str(SYNTHETIC_JUDGE)], opener=opener, ollama=ollama, clock=TickClock()
    )

    output = capsys.readouterr().out
    assert code == 0
    assert JUDGE_FIXTURE["digest"] in output
    assert hashlib.sha256(license_text.encode("utf-8")).hexdigest() in output
    assert f"({len(license_text)} chars)" in output
    assert opener.urls == [OLLAMA_BASE_URL + "/api/show"]
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert SYNTHETIC_JUDGE.read_bytes() == record_before


def test_show_pin_reports_a_missing_model(capsys: pytest.CaptureFixture) -> None:
    code = _script().main(["show-pin", "--tag", "absent:1b"], opener=FakeOpener(), ollama=FakeOllama([]), clock=TickClock())

    assert code == 2
    assert "Result:" in capsys.readouterr().out


# --- scenarios 8 and 9: init.sh dispatch -------------------------------------------------------------------------


def make_checkout(tmp_path: Path, with_python: bool) -> Path:
    # init.sh sources scripts/lib and scripts/commands, so the checkout needs the whole folder.
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    (tmp_path / "backend" / "scripts").mkdir(parents=True)
    init = tmp_path / "scripts" / "init.sh"
    stub = tmp_path / "scripts" / "python-env.sh"
    stub.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    for script in (init, stub):
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
    if with_python:
        python = tmp_path / "backend" / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n', encoding="utf-8")
        python.chmod(python.stat().st_mode | stat.S_IXUSR)
    return init


@pytest.mark.parametrize("flag", ["--grounding-judge-setup", "--grounding-judge-report"])
def test_init_prints_the_setup_result_without_a_backend_environment(tmp_path: Path, flag: str) -> None:
    init = make_checkout(tmp_path, with_python=False)

    done = subprocess.run([str(init), flag], capture_output=True, text=True, cwd=tmp_path, timeout=60)

    assert done.returncode == 1
    assert done.stdout.strip().splitlines()[-1] == (
        "Result: the grounding judge command did not run. Run ./scripts/init.sh --local-rag-setup."
    )


def test_init_dispatches_setup_and_the_argument_free_report(tmp_path: Path) -> None:
    init = make_checkout(tmp_path, with_python=True)

    setup = subprocess.run([str(init), "--grounding-judge-setup"], capture_output=True, text=True, cwd=tmp_path, timeout=60)
    report = subprocess.run([str(init), "--grounding-judge-report"], capture_output=True, text=True, cwd=tmp_path, timeout=60)
    extra = subprocess.run([str(init), "--grounding-judge-report", "x"], capture_output=True, text=True, cwd=tmp_path, timeout=60)

    assert setup.stdout.splitlines()[0].endswith("judge_grounding.py") and setup.stdout.splitlines()[1:] == ["setup"]
    lines = report.stdout.splitlines()
    assert lines[1] == "run"
    options = dict(zip(lines[2::2], lines[3::2]))
    assert options["--catalog"] == str(tmp_path / "knowledge" / "source_catalog.json")
    assert options["--passages"] == str(tmp_path / "knowledge" / "passages.json")
    assert options["--cases"] == str(tmp_path / "knowledge" / "pac_answer_eval.json")
    assert options["--golden"] == str(tmp_path / "knowledge" / "golden_set.json")
    assert options["--active-campaign"] == "2026"
    assert date.fromisoformat(options["--as-of"]) == date.today()
    assert options["--report"] == str(tmp_path / "build" / "grounding-judge" / "report.json")
    assert extra.returncode == 2
