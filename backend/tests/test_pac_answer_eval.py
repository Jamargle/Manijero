import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.answer_eval import (
    AnswerEvalError,
    evaluate,
    load_case_document,
    load_cases,
)
from app.retrieval import load_passage_set
from app.source_catalog import load_catalog

ROOT = Path(__file__).resolve().parents[2]
VERSION = "pac-answer-eval-v2"


def canonical():
    catalog = load_catalog(ROOT / "knowledge/source_catalog.json")
    passages = load_passage_set(ROOT / "knowledge/passages.json")
    cases = load_cases(ROOT / "knowledge/pac_answer_eval.json", catalog, passages)
    return catalog, passages, cases


def review():
    return {"reviewed_by": "reviewer", "reviewed_on": "2026-10-17", "role": "author_only"}


def coverage():
    return {
        "reviewed_against": "knowledge/pac_coverage.md",
        "areas": [
            {"id": "topic-a", "kind": "topic", "label": "Reviewed topic A"},
            {"id": "boundary-a", "kind": "boundary", "label": "Reviewed boundary A"},
        ],
        "omissions": ["excluded topic"],
    }


def case(**overrides):
    item = {
        "id": "case",
        "area": "topic-a",
        "question": "Question",
        "land_context": {"mode": "general", "lands": []},
        "expected_status": "abstained",
        "review": review(),
    }
    item.update(overrides)
    return item


def artifact(*items, coverage_block=None):
    return {
        "schema_version": VERSION,
        "coverage": coverage_block or coverage(),
        "cases": list(items) or [case()],
    }


def write_artifact(tmp_path, document):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class Client:
    def __init__(self, payload):
        self.payload = payload

    def post(self, path, json):
        assert path == "/ask"
        return Response(self.payload)


def test_canonical_case_artifact_loads_with_declared_coverage():
    catalog, passages, cases = canonical()
    _, coverage_block = load_case_document(
        ROOT / "knowledge/pac_answer_eval.json", catalog, passages
    )
    assert cases
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["review"]["role"] == "author_only" for case in cases)
    assert {area["kind"] for area in coverage_block["areas"]} == {"topic", "boundary"}
    assert len([a for a in coverage_block["areas"] if a["kind"] == "topic"]) == 3
    assert len([a for a in coverage_block["areas"] if a["kind"] == "boundary"]) == 5
    assert len(cases) == 14
    assert coverage_block["omissions"]


def test_known_misses_remain_in_the_case_set():
    _, _, cases = canonical()
    by_id = {case["id"]: case for case in cases}
    for case_id in (
        "canal-sga-2026",
        "fecha-modificacion-2026",
        "distingue-fechas-2026",
    ):
        assert case_id in by_id
        assert by_id[case_id]["expected_source_ids"]
        assert by_id[case_id]["expected_passage_ids"]


def test_schema_parses_and_validates_canonical_artifact():
    schema = json.loads(
        (ROOT / "knowledge/pac_answer_eval.schema.json").read_text(encoding="utf-8")
    )
    artifact_document = json.loads(
        (ROOT / "knowledge/pac_answer_eval.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert validator.is_valid(artifact_document), list(
        validator.iter_errors(artifact_document)
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda item: item.update(unexpected_key=True),
        lambda item: item.update(expected_status="not-a-status"),
        lambda item: item.update(question=""),
        lambda item: item["review"].update(reviewed_on="yesterday"),
        lambda item: item["review"].update(role="independent_reviewer"),
        lambda item: item.update(expected_source_ids=["duplicate", "duplicate"]),
    ],
)
def test_schema_and_loader_reject_malformed_case_artifacts(tmp_path, mutation):
    schema = json.loads(
        (ROOT / "knowledge/pac_answer_eval.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    catalog, passages, _ = canonical()
    item = case()
    mutation(item)
    document = artifact(item)
    assert not validator.is_valid(document)
    with pytest.raises(AnswerEvalError):
        load_cases(write_artifact(tmp_path, document), catalog, passages)


def test_schema_and_loader_reject_malformed_coverage(tmp_path):
    schema = json.loads(
        (ROOT / "knowledge/pac_answer_eval.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    catalog, passages, _ = canonical()
    for mutation in (
        lambda block: block.update(omissions=[]),
        lambda block: block.update(reviewed_against=""),
        lambda block: block.update(areas=[]),
        lambda block: block.update(areas=[{"id": "topic-a", "kind": "other", "label": "x"}]),
    ):
        block = coverage()
        mutation(block)
        document = artifact(coverage_block=block)
        assert not validator.is_valid(document)
        with pytest.raises(AnswerEvalError):
            load_cases(write_artifact(tmp_path, document), catalog, passages)


def test_loader_rejects_undeclared_area_and_duplicate_area_ids(tmp_path):
    catalog, passages, _ = canonical()
    undeclared = artifact(case(area="topic-not-declared"))
    with pytest.raises(AnswerEvalError, match="undeclared coverage area"):
        load_cases(write_artifact(tmp_path, undeclared), catalog, passages)

    duplicated = coverage()
    duplicated["areas"].append(
        {"id": "topic-a", "kind": "topic", "label": "Duplicate id"}
    )
    with pytest.raises(AnswerEvalError, match="blank or duplicate"):
        load_cases(
            write_artifact(tmp_path, artifact(coverage_block=duplicated)),
            catalog,
            passages,
        )


def test_unknown_source_reference_is_rejected(tmp_path):
    catalog, passages, _ = canonical()
    document = artifact(
        case(
            expected_status="answered",
            expected_source_ids=["missing"],
            expected_passage_ids=["missing-passage"],
        )
    )
    with pytest.raises(AnswerEvalError, match="unknown reference"):
        load_cases(write_artifact(tmp_path, document), catalog, passages)


def test_quality_mismatch_is_reported_not_failed():
    item = case()
    payload = {
        "status": "answered",
        "answer": "answer",
        "sources": [],
        "land_scope": "general",
        "land_ids_to_choose": [],
    }
    catalog, passages, _ = canonical()
    report = evaluate([item], Client(payload), catalog, passages)
    assert report["expected_state_agreement"] == 0
    assert report["unexpected_answers"] == 1


def test_citation_and_passage_matching_uses_supplied_corpus():
    catalog, passages, _ = canonical()
    source = catalog["sources"][0]
    passage = next(p for p in passages["passages"] if p["source_id"] == source["id"])
    source["id"] = "supplied-source"
    source["original_url"] = "https://example.test/supplied-source"
    passage["source_id"] = source["id"]
    passage["id"] = "supplied-passage"
    item = case(
        id="supplied-corpus-case",
        expected_status="answered",
        expected_source_ids=[source["id"]],
        expected_passage_ids=[passage["id"]],
    )
    payload = {
        "status": "answered",
        "answer": "answer",
        "land_scope": "general",
        "land_ids_to_choose": [],
        "sources": [
            {
                "title": source["title"],
                "issuing_body": source["issuing_body"],
                "url": source["original_url"],
                "location": passage["location"],
                "published_or_updated_on": source["published_on"],
                "verified_on": source["verified_on"],
                "excerpt": passage["text"],
            }
        ],
    }

    report = evaluate([item], Client(payload), catalog, passages)

    assert report["case_rows"][0]["source_match"] is True
    assert report["case_rows"][0]["passage_match"] is True


def test_case_row_exposes_missing_expected_references_and_facts():
    catalog, passages, _ = canonical()
    source = catalog["sources"][0]
    passage = next(p for p in passages["passages"] if p["source_id"] == source["id"])
    item = case(
        id="detail-case",
        expected_status="answered",
        expected_source_ids=[source["id"]],
        expected_passage_ids=[passage["id"]],
        critical_facts=["literal que falta"],
    )
    payload = {
        "status": "answered",
        "answer": "respuesta sin la referencia",
        "sources": [],
        "land_scope": "general",
        "land_ids_to_choose": [],
    }

    report = evaluate([item], Client(payload), catalog, passages)
    row = report["case_rows"][0]

    assert row["missing_expected_source_ids"] == [source["id"]]
    assert row["missing_expected_passage_ids"] == [passage["id"]]
    assert row["missing_critical_facts"] == ["literal que falta"]
    assert row["actual_source_ids"] == []
    assert row["actual_passage_ids"] == []


@pytest.mark.parametrize(
    "mutation",
    [
        {"expected_status": "Answered"},
        {"expected_status": "answered", "expected_source_ids": ["x"]},
    ],
)
def test_case_status_and_answer_requirements_are_strict(tmp_path, mutation):
    catalog, passages, _ = canonical()
    item = case(**mutation)
    with pytest.raises(AnswerEvalError):
        load_cases(write_artifact(tmp_path, artifact(item)), catalog, passages)


def test_contract_invalid_response_is_integrity_error():
    item = case(id="private-case")
    bad = {
        "status": "answered",
        "answer": "x",
        "sources": [],
        "land_scope": "general",
        "land_ids_to_choose": [],
        "unexpected": True,
    }
    with pytest.raises(AnswerEvalError, match="private-case.*contract"):
        catalog, passages, _ = canonical()
        evaluate([item], Client(bad), catalog, passages)


def test_report_reports_author_only_review_coverage_and_denominators():
    catalog, passages, cases = canonical()
    _, coverage_block = load_case_document(
        ROOT / "knowledge/pac_answer_eval.json", catalog, passages
    )
    abstained = {
        "status": "abstained",
        "answer": "No he encontrado esta información.",
        "sources": [],
        "land_scope": "general",
        "land_ids_to_choose": [],
    }

    report = evaluate(
        cases, Client(abstained), catalog, passages, coverage=coverage_block
    )

    assert report["review"] == {
        "roles": ["author_only"],
        "independent_legal_review": False,
    }
    assert report["coverage"]["topics"] == {
        "canal-presentacion": 3,
        "plazo-presentacion": 2,
        "plazo-modificacion": 4,
    }
    assert sum(report["coverage"]["boundaries"].values()) == 5
    assert report["coverage"]["omissions"] == coverage_block["omissions"]
    assert report["answered_cases"] == 11
    assert report["abstention_cases"] == 3
    assert report["clarification_cases"] == 0


def test_cli_k_is_dependency_overridden_into_same_ask_route(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ask_api import get_retrieval_k

    observed = []
    monkeypatch.setattr(
        "app.ask_api._prepare_runtime_corpus", lambda *a: object()
    )
    monkeypatch.setattr(
        "app.ask_api.answer_with_clarification",
        lambda *a, **kw: (
            observed.append(kw["k"])
            or __import__("app.abstention", fromlist=["Abstention"]).Abstention(
                "no_evidence", issues=()
            )
        ),
    )
    from app.ask_api import get_corpus_documents, get_as_of_date, get_active_campaign

    app.dependency_overrides[get_retrieval_k] = lambda: 2
    app.dependency_overrides[get_as_of_date] = lambda: __import__(
        "datetime"
    ).date(2026, 10, 17)
    app.dependency_overrides[get_active_campaign] = lambda: "2026"
    app.dependency_overrides[get_corpus_documents] = lambda: __import__(
        "app.ask_api", fromlist=["CorpusDocuments"]
    ).CorpusDocuments(catalog={"sources": []}, passages={"passages": []})
    try:
        response = TestClient(app).post(
            "/ask", json={"question": "q", "land_context": {"mode": "general", "lands": []}}
        )
        assert response.status_code == 200
        assert observed == [2]
    finally:
        app.dependency_overrides.clear()
