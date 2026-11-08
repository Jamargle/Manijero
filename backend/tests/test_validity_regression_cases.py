"""Validity regression cases, pinned offline through the real /ask route.

Every expectation rests only on reviewed catalog and passage metadata. Cases 1 and 3
abstain because the reviewed corpus holds no source for them; the precondition tests
fail once such a source appears so the case is revisited. Nothing here states whether
RD 1077/2014 is repealed or whether the digital notebook is voluntary or mandatory.
"""

import hashlib
import json
import socket
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.abstention import ABSTENTION_MESSAGES  # noqa: E402
from app.answer_eval import evaluate, load_case_document  # noqa: E402
from app.ask_api import (  # noqa: E402
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
    get_retrieval_k,
)
from app.deadline_notices import COOPERATIVE, EXPIRED_PREFIX  # noqa: E402
from app.main import app  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "knowledge" / "source_catalog.json"
PASSAGES = ROOT / "knowledge" / "passages.json"
CASES = ROOT / "knowledge" / "pac_answer_eval.json"

AS_OF = date(2026, 10, 26)
CONTROL_AS_OF = date(2026, 5, 15)
CAMPAIGN = "2026"
K = 5

RD_1077 = "¿Sigue en vigor el Real Decreto 1077/2014?"
EXPIRED = "¿Ya terminó el plazo para presentar la solicitud única de 2026?"
NOTEBOOK = "¿Es obligatorio el cuaderno digital de explotación?"
DEADLINE_PASSAGE = "pasaje-plazo-presentacion-2026-andalucia"
DEADLINE_SOURCE = "dl_1_2026"
EXPIRED_SENTENCE = EXPIRED_PREFIX + " 15 de mayo de 2026."
CASE_IDS = ("rd-1077-2014-derogado", "plazo-presentacion-vencido-2026", "cuaderno-digital-obligatorio")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    for name in (
        "MANIJERO_GENERATION_PROVIDER",
        "MANIJERO_RETRIEVAL_MODE",
        "MANIJERO_KNOWLEDGE_RELEASE_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MANIJERO_ANSWER_CACHE", "off")

    def _forbid(*_args, **_kwargs):
        raise AssertionError("network access is forbidden in validity regression tests")

    # The in-process TestClient needs local socketpairs, so block only outbound traffic.
    monkeypatch.setattr(socket.socket, "connect", _forbid)
    monkeypatch.setattr(socket.socket, "connect_ex", _forbid)
    monkeypatch.setattr(socket, "create_connection", _forbid)
    monkeypatch.setattr(socket, "getaddrinfo", _forbid)


@pytest.fixture
def docs():
    return CorpusDocuments(catalog=load_catalog(CATALOG), passages=load_passage_set(PASSAGES))


def client_for(docs, as_of):
    app.dependency_overrides[get_corpus_documents] = lambda: docs
    app.dependency_overrides[get_as_of_date] = lambda: as_of
    app.dependency_overrides[get_active_campaign] = lambda: CAMPAIGN
    app.dependency_overrides[get_retrieval_k] = lambda: K
    return TestClient(app)


@pytest.fixture
def ask(docs):
    def run(question, as_of=AS_OF):
        try:
            response = client_for(docs, as_of).post(
                "/ask", json={"question": question, "land_context": {"mode": "general", "lands": []}}
            )
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == 200
        return response.json()

    return run


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- Scenario 1 --------------------------------------------------------------


def test_repealed_rd_1077_2014_abstains_with_no_evidence(ask):
    body = ask(RD_1077)
    assert body["status"] == "abstained"
    assert body["sources"] == []
    assert body["answer"] == ABSTENTION_MESSAGES["no_evidence"]
    lowered = body["answer"].lower()
    for word in ("1077", "vigor", "vigente", "derog"):
        assert word not in lowered


# --- Scenario 2 --------------------------------------------------------------


def test_expired_deadline_is_flagged_against_the_injected_date(ask):
    body = ask(EXPIRED)
    assert body["status"] == "answered"
    assert [s["url"] for s in body["sources"]]
    assert "15 de mayo de 2026" in body["answer"]
    assert EXPIRED_SENTENCE in body["answer"]
    assert COOPERATIVE in body["answer"]


def test_deadline_on_its_last_open_day_has_no_expired_notice(ask):
    body = ask(EXPIRED, CONTROL_AS_OF)
    assert body["status"] == "answered"
    assert COOPERATIVE in body["answer"]
    assert EXPIRED_PREFIX not in body["answer"]


# --- Scenario 3 --------------------------------------------------------------


def test_digital_notebook_obligation_abstains_with_no_evidence(ask):
    body = ask(NOTEBOOK)
    assert body["status"] == "abstained"
    assert body["sources"] == []
    assert body["answer"] == ABSTENTION_MESSAGES["no_evidence"]
    assert "obligatori" not in body["answer"].lower()


# --- Scenario 4 --------------------------------------------------------------


def test_cases_live_in_the_reviewed_set_and_the_report_stays_honest(docs):
    catalog, passages = docs.catalog, docs.passages
    cases, coverage = load_case_document(CASES, catalog, passages)
    by_id = {case["id"]: case for case in cases}
    assert len(cases) == 17
    assert len(coverage["omissions"]) == 8
    assert {a["id"] for a in coverage["areas"] if a["kind"] == "boundary"} >= {
        "norma-derogada",
        "plazo-vencido",
        "cuaderno-digital-fuera-de-alcance",
    }
    for case_id in CASE_IDS:
        assert by_id[case_id]["review"] == {
            "reviewed_by": "Diego",
            "reviewed_on": "2026-11-07",
            "role": "author_only",
        }
    for case_id in (CASE_IDS[0], CASE_IDS[2]):
        for key in ("expected_source_ids", "expected_passage_ids", "critical_facts"):
            assert key not in by_id[case_id]
    assert by_id[CASE_IDS[1]]["expected_source_ids"] == [DEADLINE_SOURCE]
    assert by_id[CASE_IDS[1]]["expected_passage_ids"] == [DEADLINE_PASSAGE]
    assert by_id[CASE_IDS[1]]["critical_facts"] == ["15 de mayo de 2026", EXPIRED_SENTENCE]

    client = client_for(docs, AS_OF)
    try:
        report = evaluate(cases, client, catalog, passages, K, coverage=coverage)
    finally:
        app.dependency_overrides.clear()
    rows = {row["id"]: row for row in report["case_rows"]}
    for case_id in CASE_IDS:
        assert rows[case_id]["expected_state_match"] is True
    assert rows[CASE_IDS[1]]["source_match"] is True
    assert rows[CASE_IDS[1]]["passage_match"] is True
    assert rows[CASE_IDS[1]]["critical_facts_match"] is True
    assert report["cases"] == 17
    assert report["answered_cases"] == 12
    assert report["abstention_cases"] == 5
    assert report["unexpected_answers"] == 0


# --- Scenario 5 --------------------------------------------------------------


def grounding_problems(catalog_path, passages_path):
    """Return revisit messages for any reviewed source that now touches a pinned gap."""
    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    passages = json.loads(Path(passages_path).read_text(encoding="utf-8"))
    problems = []
    for source in catalog["sources"]:
        if "1077/2014" in json.dumps(source, ensure_ascii=False):
            problems.append(
                "a reviewed source now mentions 1077/2014: revisit case rd-1077-2014-derogado"
            )
    for passage in passages["passages"]:
        blob = json.dumps(passage, ensure_ascii=False)
        lowered = blob.lower()
        if "1077/2014" in blob:
            problems.append(
                "a reviewed passage now mentions 1077/2014: revisit case rd-1077-2014-derogado"
            )
        if "cuaderno digital" in lowered or "cuaderno de explotación" in lowered:
            problems.append(
                "a reviewed passage now mentions the digital notebook: "
                "revisit case cuaderno-digital-obligatorio"
            )
    deadlines = [p for p in passages["passages"] if p["id"] == DEADLINE_PASSAGE]
    if len(deadlines) != 1 or deadlines[0].get("official_deadline") != "2026-05-15":
        problems.append(
            f"official_deadline of {DEADLINE_PASSAGE} changed: "
            "revisit case plazo-presentacion-vencido-2026"
        )
    return problems


def write_mutated(tmp_path, mutate):
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    passages = json.loads(PASSAGES.read_text(encoding="utf-8"))
    mutate(catalog, passages)
    catalog_path, passages_path = tmp_path / "catalog.json", tmp_path / "passages.json"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    passages_path.write_text(json.dumps(passages, ensure_ascii=False), encoding="utf-8")
    return catalog_path, passages_path


def test_grounding_preconditions_hold_on_canonical_files():
    assert grounding_problems(CATALOG, PASSAGES) == []


def _title(catalog, _passages):
    catalog["sources"][0]["title"] += " (Real Decreto 1077/2014)"


def _url(catalog, _passages):
    catalog["sources"][0]["original_url"] += "?ref=1077/2014"


def _text(_catalog, passages):
    passages["passages"][0]["text"] += " Queda derogado el Real Decreto 1077/2014."


def _location(_catalog, passages):
    passages["passages"][0]["location"] += ", RD 1077/2014"


def _notebook(_catalog, passages):
    passages["passages"][0]["text"] += " El cuaderno digital de explotación es voluntario."


def _notebook_alt(_catalog, passages):
    passages["passages"][0]["text"] += " El cuaderno de explotación es obligatorio."


def _deadline(_catalog, passages):
    for passage in passages["passages"]:
        if passage["id"] == DEADLINE_PASSAGE:
            passage["official_deadline"] = "2026-06-01"


@pytest.mark.parametrize(
    ("mutate", "case_id"),
    [
        (_title, "rd-1077-2014-derogado"),
        (_url, "rd-1077-2014-derogado"),
        (_text, "rd-1077-2014-derogado"),
        (_location, "rd-1077-2014-derogado"),
        (_notebook, "cuaderno-digital-obligatorio"),
        (_notebook_alt, "cuaderno-digital-obligatorio"),
        (_deadline, "plazo-presentacion-vencido-2026"),
    ],
)
def test_a_new_reviewed_source_forces_a_revisit(tmp_path, mutate, case_id):
    problems = grounding_problems(*write_mutated(tmp_path, mutate))
    assert problems
    assert any("revisit case " + case_id in message for message in problems)


# --- Scenario 6 --------------------------------------------------------------


def test_runs_are_deterministic_and_leave_knowledge_untouched(ask):
    before = {path: digest(path) for path in (CATALOG, PASSAGES, CASES)}
    release_files = {
        str(p): digest(p) for p in sorted((ROOT / "knowledge").rglob("*")) if p.is_file()
    }
    first = [ask(q) for q in (RD_1077, EXPIRED, NOTEBOOK)]
    second = [ask(q) for q in (RD_1077, EXPIRED, NOTEBOOK)]
    assert first == second
    assert before == {path: digest(path) for path in (CATALOG, PASSAGES, CASES)}
    assert release_files == {
        str(p): digest(p) for p in sorted((ROOT / "knowledge").rglob("*")) if p.is_file()
    }
