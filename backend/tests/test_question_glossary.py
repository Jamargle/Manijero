"""Tests for the runtime question glossary (scenarios 1-5 and 10 of ``docs/specs/question_rewriting.md``).

Everything is in process over the synthetic clarification fixtures; sockets are blocked.
"""

from __future__ import annotations

import ast
import io
import json
import logging
import socket
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import pytest
from fastapi.testclient import TestClient

import app.ask_api as ask_api
from app import answer_cache as cache_module
from app.answer_cache import AnswerCache
from app.ask_api import CorpusDocuments, get_active_campaign, get_as_of_date, get_corpus_documents
from app.main import create_app
from app.pilot_config import load_config
from app.pilot_logging import LOGGER_NAME, configure_operational_logging
from app.question_glossary import (
    MAX_APPENDED,
    SCHEMA_VERSION,
    SETTING_ENV,
    QuestionGlossary,
    load_question_glossary,
)
from app.readiness import get_configured_campaign
from app.retrieval import Retriever, load_passage_set
from app.retrieval_backend import get_retrieval_backend
from app.source_catalog import load_catalog

APP_DIR = Path(__file__).resolve().parents[1] / "app"
CLARIFICATION = Path(__file__).resolve().parent / "fixtures" / "clarification"
FIXED_DAY = date(2026, 10, 13)
QUESTION = "¿Cómo se presenta el papeleo anual de ejemplo?"
GENERAL = {"mode": "general", "lands": []}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("no outbound connection may be attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.delenv(SETTING_ENV, raising=False)


# --- helpers -----------------------------------------------------------------------------------


def entry(
    number: int, colloquial: str, official: str, state: str = "approved", **overrides: Any
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "id": "gl-{:03d}".format(number),
        "colloquial": colloquial,
        "official": official,
        "origin": {"kind": "golden", "ref": "golden-041"},
        "drafted": {"by": "agent:test", "on": "2026-11-08"},
        "review_state": state,
    }
    if state != "proposed":
        item["decision"] = {"decision": state, "reviewed_by": "Test Owner", "reviewed_on": "2026-11-08"}
    item.update(overrides)
    return item


def write_glossary(path: Path, entries: Sequence[Dict[str, Any]]) -> Path:
    path.write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "entries": list(entries)}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def pairs(*items: Tuple[str, str]) -> QuestionGlossary:
    return QuestionGlossary(list(items))


class Spy:
    """Records what each step of ``/ask`` sees: search queries and pipeline questions."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.queries: List[str] = []
        self.steps: List[Tuple[str, str]] = []
        original = Retriever._search
        spy = self

        def search(self: Retriever, question: str, k: int) -> Any:
            spy.queries.append(question)
            return original(self, question, k)

        monkeypatch.setattr(Retriever, "_search", search)
        for name in ("screen_question", "clarify_land_scope", "answer_or_abstain", "answer_with_clarification"):
            self._wrap(monkeypatch, name)

    def _wrap(self, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
        original = getattr(ask_api, name)
        spy = self

        def wrapped(question: str, *args: Any, **kwargs: Any) -> Any:
            spy.steps.append((name, question))
            return original(question, *args, **kwargs)

        monkeypatch.setattr(ask_api, name, wrapped)


def documents() -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(CLARIFICATION / "catalog.json"),
        passages=load_passage_set(CLARIFICATION / "passages.json"),
    )


def make_app(monkeypatch: pytest.MonkeyPatch, **options: Any) -> TestClient:
    monkeypatch.setenv("MANIJERO_ACTIVE_CAMPAIGN", "2026")
    application = create_app(load_config({"MANIJERO_ACTIVE_CAMPAIGN": "2026"}), retention_store=None, **options)
    application.dependency_overrides[get_corpus_documents] = documents
    application.dependency_overrides[get_as_of_date] = lambda: FIXED_DAY
    application.dependency_overrides[get_active_campaign] = lambda: "2026"
    application.dependency_overrides[get_configured_campaign] = lambda: "2026"
    return TestClient(application)


def ask(client: TestClient, question: str = QUESTION) -> Dict[str, Any]:
    response = client.post("/ask", json={"question": question, "land_context": GENERAL})
    assert response.status_code == 200, response.text
    return response.json()


# --- 1. appends to the retrieval query only ----------------------------------------------------


def test_search_gets_original_then_official_term_and_nothing_else_does(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = Spy(monkeypatch)
    client = make_app(monkeypatch, question_glossary=pairs(("papeleo", "solicitud")), answer_cache=None)
    ask(client)
    assert spy.queries and set(spy.queries) == {QUESTION + " solicitud"}
    assert {question for _, question in spy.steps} == {QUESTION}


def test_cache_path_also_searches_expanded_and_keeps_original_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = Spy(monkeypatch)
    client = make_app(monkeypatch, question_glossary=pairs(("papeleo", "solicitud")), answer_cache=AnswerCache())
    ask(client)
    assert spy.queries and set(spy.queries) == {QUESTION + " solicitud"}
    assert {question for _, question in spy.steps} == {QUESTION}


def test_response_shape_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    plain = ask(make_app(monkeypatch, question_glossary=None, answer_cache=None))
    expanded = ask(make_app(monkeypatch, question_glossary=pairs(("papeleo", "solicitud")), answer_cache=None))
    assert set(plain) == set(expanded)


def test_hybrid_ranker_receives_the_expanded_query(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: List[str] = []

    class SpyRanker:
        def rank(self, question: str, lexical: Sequence[Tuple[str, float]]) -> Sequence[Tuple[str, float]]:
            seen.append(question)
            return lexical

    class RankerBackend:
        mode = "hybrid"

        def attach(self, retriever: Retriever, active_campaign: Optional[str]) -> Retriever:
            return retriever.with_ranker(SpyRanker())

    client = make_app(monkeypatch, question_glossary=pairs(("papeleo", "solicitud")), answer_cache=None)
    client.app.dependency_overrides[get_retrieval_backend] = RankerBackend
    ask(client)
    assert seen and set(seen) == {QUESTION + " solicitud"}


def test_expansion_and_ranker_keep_each_other(monkeypatch: pytest.MonkeyPatch) -> None:
    class Ranker:
        def rank(self, question: str, lexical: Sequence[Tuple[str, float]]) -> Sequence[Tuple[str, float]]:
            return lexical

    base = Retriever.from_documents(documents().catalog, documents().passages, FIXED_DAY, "2026")
    assert base.with_query_expansion(str.upper).with_ranker(Ranker()).uses_ranker
    ranked_first = base.with_ranker(Ranker()).with_query_expansion(lambda q: q + " solicitud")
    assert ranked_first.uses_ranker
    assert not base.uses_ranker
    assert base.search("papeleo") == ()
    assert ranked_first.search("papeleo")


# --- 2. only approved pairs apply -------------------------------------------------------------


def test_proposed_and_rejected_entries_change_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_glossary(
        tmp_path / "g.json",
        [entry(1, "papeleo", "solicitud", "proposed"), entry(2, "papeleo", "riego", "rejected")],
    )
    glossary, reason = load_question_glossary({}, path)
    assert reason is None and glossary is not None and glossary.approved_count == 0
    assert glossary.expand(QUESTION) == QUESTION
    spy = Spy(monkeypatch)
    plain = ask(make_app(monkeypatch, question_glossary=None, answer_cache=None))
    with_file = ask(make_app(monkeypatch, question_glossary=glossary, answer_cache=None))
    assert plain == with_file
    assert set(spy.queries) == {QUESTION}


def test_no_matching_pair_leaves_the_query_alone() -> None:
    assert pairs(("papeleo", "solicitud")).expand("¿Puedo regar?") == "¿Puedo regar?"


# --- 3. matching rules -------------------------------------------------------------------------


def test_matching_is_case_accent_and_stopword_folded() -> None:
    glossary = pairs(("tramite de la firma", "firma electrónica"))
    assert glossary.expand("¿Y el TRÁMITE, la firma?") == "¿Y el TRÁMITE, la firma? firma electrónica"


def test_whole_token_only() -> None:
    glossary = pairs(("papeleo", "solicitud"))
    assert glossary.expand("papelería") == "papelería"
    assert glossary.expand("papeleos") == "papeleos"


def test_contiguous_sequence_only() -> None:
    glossary = pairs(("firma tramite", "firma electrónica"))
    assert glossary.expand("firma verde tramite") == "firma verde tramite"
    assert glossary.expand("la firma del tramite") == "la firma del tramite firma electrónica"


def test_longest_colloquial_wins_and_matches_do_not_overlap() -> None:
    glossary = pairs(("papeles", "documentación"), ("papeles de la pac", "solicitud única"), ("pac", "campaña"))
    assert glossary.expand("los papeles de la PAC") == "los papeles de la PAC solicitud única"


def test_official_term_already_in_the_question_is_skipped() -> None:
    assert pairs(("papeleo", "solicitud")).expand("papeleo de la solicitud") == "papeleo de la solicitud"
    both = pairs(("papeleo", "solicitud"), ("tramites", "Solicitud"))
    assert both.expand("papeleo y tramites") == "papeleo y tramites solicitud"


def test_at_most_four_terms_in_order_of_first_match() -> None:
    glossary = QuestionGlossary([("pal" + c, "ofi" + c) for c in "abcdef"])
    question = "palf pale pala palb palc pald"
    assert MAX_APPENDED == 4
    assert glossary.expand(question) == question + " ofif ofie ofia ofib"


def test_expansion_is_deterministic_and_idempotent() -> None:
    glossary = pairs(("papeleo", "solicitud"), ("avisar", "notificaciones"))
    once = glossary.expand("papeleo y avisar")
    assert once == glossary.expand("papeleo y avisar")
    assert glossary.expand(once) == once


def test_idempotent_even_past_the_cap() -> None:
    glossary = QuestionGlossary([(f"pal{c}", f"ofi{c}") for c in "abcdef"])
    once = glossary.expand("pala palb palc pald pale palf")
    assert glossary.expand(once) == once


# --- 4. fail closed ----------------------------------------------------------------------------


def good_entries() -> List[Dict[str, Any]]:
    return [entry(1, "papeleo", "solicitud")]


def test_a_valid_file_loads_with_its_approved_count(tmp_path: Path) -> None:
    glossary, reason = load_question_glossary({}, write_glossary(tmp_path / "g.json", good_entries()))
    assert (reason, glossary is not None and glossary.approved_count) == (None, 1)


def damaged_files(tmp_path: Path) -> Iterator[Tuple[str, Path]]:
    yield "missing", tmp_path / "nope.json"
    binary = tmp_path / "binary.json"
    binary.write_bytes(b"\xff\xfe not json")
    yield "unreadable", binary
    text = tmp_path / "text.json"
    text.write_text("not json", encoding="utf-8")
    yield "unreadable", text
    big = tmp_path / "big.json"
    big.write_text(" " * (256 * 1024 + 1), encoding="utf-8")
    yield "too_large", big
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"schema_version": "other", "entries": []}), encoding="utf-8")
    yield "wrong_schema", schema
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "entries": [], "more": 1}), encoding="utf-8")
    yield "wrong_schema", extra
    bad_entries = {
        "digit": entry(1, "papeleo 2", "solicitud"),
        "url": entry(1, "papeleo", "www.ejemplo.es"),
        "same tokens": entry(1, "La Solicitud", "solicitud"),
        "too many colloquial tokens": entry(1, "alfa beta gamma delta epsilon", "solicitud"),
        "multiline": entry(1, "papeleo\notro", "solicitud"),
        "bad id": entry(1, "papeleo", "solicitud", id="x1"),
        "bad state": entry(1, "papeleo", "solicitud", review_state="maybe"),
        "approved without decision": {k: v for k, v in entry(1, "papeleo", "solicitud").items() if k != "decision"},
        "proposed with decision": entry(1, "papeleo", "solicitud", "proposed", decision={"decision": "approved"}),
        "unknown key": entry(1, "papeleo", "solicitud", extra=1),
    }
    for label, bad in bad_entries.items():
        yield "invalid_entry", write_glossary(tmp_path / (label.replace(" ", "_") + ".json"), [bad])
    yield "invalid_entry", write_glossary(tmp_path / "dupid.json", [entry(1, "papeleo", "solicitud"), entry(1, "tramite", "gestión")])
    yield "invalid_entry", write_glossary(
        tmp_path / "duppair.json", [entry(1, "papeleo", "solicitud"), entry(2, "el papeleo", "la solicitud")]
    )
    one = tmp_path / "toomany.json"
    write_glossary(one, [entry(1, "papeleo", "solicitud")] * 501)
    yield "invalid_entry", one


def test_every_bad_file_turns_expansion_off_with_a_fixed_reason(tmp_path: Path) -> None:
    for expected, path in damaged_files(tmp_path):
        glossary, reason = load_question_glossary({}, path)
        assert (glossary, reason) == (None, expected), path.name


@pytest.mark.parametrize("value,reason", [("off", "disabled"), ("OFF", "invalid_setting"), ("maybe", "invalid_setting")])
def test_off_switch_and_bad_setting(tmp_path: Path, value: str, reason: str) -> None:
    path = write_glossary(tmp_path / "g.json", good_entries())
    assert load_question_glossary({SETTING_ENV: value}, path) == (None, reason)
    assert load_question_glossary({SETTING_ENV: "on"}, path)[1] is None
    assert load_question_glossary({SETTING_ENV: ""}, path)[1] is None


@pytest.fixture
def captured_log() -> Iterator[io.StringIO]:
    logger = logging.getLogger(LOGGER_NAME)
    previous = list(logger.handlers)
    logger.handlers.clear()
    stream = io.StringIO()
    configure_operational_logging(stream)
    try:
        yield stream
    finally:
        logger.handlers.clear()
        logger.handlers.extend(previous)


def glossary_lines(stream: io.StringIO) -> List[Dict[str, Any]]:
    records = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    return [r for r in records if r.get("event") == "question_glossary"]


def test_startup_log_line_carries_state_and_never_a_term(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, captured_log: io.StringIO
) -> None:
    make_app(monkeypatch, question_glossary=pairs(("papeleo", "solicitud")))
    monkeypatch.setenv(SETTING_ENV, "off")
    make_app(monkeypatch)
    monkeypatch.setenv(SETTING_ENV, "maybe")
    make_app(monkeypatch)
    lines = glossary_lines(captured_log)
    assert [(l["state"], l.get("reason"), l.get("approved")) for l in lines] == [
        ("on", None, 1),
        ("off", "disabled", None),
        ("off", "invalid_setting", None),
    ]
    assert "papeleo" not in captured_log.getvalue() and "solicitud" not in captured_log.getvalue()


def test_default_app_loads_the_committed_glossary_without_breaking_ask_or_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = make_app(monkeypatch)
    assert client.get("/ready").status_code == 200
    assert ask(client)["status"] in ("answered", "abstained", "needs_land_clarification")


def test_a_broken_glossary_leaves_ask_and_ready_working(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    glossary, reason = load_question_glossary({}, tmp_path / "missing.json")
    assert glossary is None and reason == "missing"
    spy = Spy(monkeypatch)
    client = make_app(monkeypatch, question_glossary=glossary, answer_cache=None)
    assert client.get("/ready").status_code == 200
    ask(client)
    assert set(spy.queries) == {QUESTION}


# --- 5. cache identity -------------------------------------------------------------------------


def model_identities(monkeypatch: pytest.MonkeyPatch) -> List[str]:
    seen: List[str] = []
    original = cache_module.model_identity

    def recording(model_version: str, retrieval_mode: str, k: int, max_claims: int) -> str:
        identity = original(model_version, retrieval_mode, k, max_claims)
        seen.append(identity)
        return identity

    monkeypatch.setattr(cache_module, "model_identity", recording)
    return seen


def test_cache_identity_carries_the_glossary_digest_only_when_pairs_are_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = model_identities(monkeypatch)
    ask(make_app(monkeypatch, question_glossary=None, answer_cache=AnswerCache()))
    ask(make_app(monkeypatch, question_glossary=pairs(), answer_cache=AnswerCache()))
    glossary = pairs(("papeleo", "solicitud"))
    ask(make_app(monkeypatch, question_glossary=glossary, answer_cache=AnswerCache()))
    off, empty, on = seen
    assert off == empty and "glossary" not in off
    assert on == off.replace("|bm25|", "|bm25+glossary:{}|".format(glossary.identity()))
    assert len(glossary.identity()) == 12


def test_digest_depends_on_the_pairs_not_their_order_or_spelling() -> None:
    a = pairs(("papeleo", "solicitud"), ("avisar", "notificaciones"))
    b = pairs(("avisar", "notificaciones"), ("PAPELEO", "solicitud"))
    assert a.identity() == b.identity()
    assert a.identity() != pairs(("papeleo", "solicitud")).identity()
    assert pairs().cache_suffix() == ""


# --- 10. isolation -----------------------------------------------------------------------------


def imported_modules(path: Path) -> set:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(node.module + "." + alias.name for alias in node.names)
    return names


def test_runtime_module_imports_only_stdlib_and_retrieval() -> None:
    imports = imported_modules(APP_DIR / "question_glossary.py")
    assert {name for name in imports if name.startswith("app")} == {"app.retrieval", "app.retrieval.tokenize"}


def test_no_runtime_module_imports_the_review_tooling() -> None:
    banned = ("question_glossary_review", "notice_pipeline", "golden_set")
    for path in sorted(APP_DIR.glob("*.py")):
        if path.name in {"question_glossary_review.py", "notice_pipeline.py", "golden_set.py", "release_gates.py"}:
            continue
        if path.name in {"input_guardrails.py"}:
            continue
        found = {name for name in imported_modules(path) if any(b in name for b in banned)}
        assert not found, (path.name, found)


def test_release_gates_never_apply_the_glossary() -> None:
    assert "question_glossary" not in (APP_DIR / "release_gates.py").read_text(encoding="utf-8")
