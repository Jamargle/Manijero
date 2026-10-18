import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.answer_eval import AnswerEvalError, evaluate, load_cases
from app.retrieval import load_passage_set
from app.source_catalog import load_catalog

ROOT = Path(__file__).resolve().parents[2]


def canonical():
    catalog = load_catalog(ROOT / "knowledge/source_catalog.json")
    passages = load_passage_set(ROOT / "knowledge/passages.json")
    cases = load_cases(ROOT / "knowledge/pac_answer_eval.json", catalog, passages)
    return catalog, passages, cases


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


def test_canonical_case_artifact_loads():
    _, _, cases = canonical()
    assert cases
    assert len({case["id"] for case in cases}) == len(cases)


def test_schema_parses_and_validates_canonical_artifact():
    schema = json.loads((ROOT / "knowledge/pac_answer_eval.schema.json").read_text(encoding="utf-8"))
    artifact = json.loads((ROOT / "knowledge/pac_answer_eval.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert validator.is_valid(artifact), list(validator.iter_errors(artifact))


@pytest.mark.parametrize("mutation", [
    lambda item: item.update(unexpected_key=True),
    lambda item: item.update(expected_status="not-a-status"),
    lambda item: item.update(question=""),
    lambda item: item["review"].update(reviewed_on="yesterday"),
    lambda item: item.update(expected_source_ids=["duplicate", "duplicate"]),
])
def test_schema_and_loader_reject_malformed_case_artifacts(tmp_path, mutation):
    schema = json.loads((ROOT / "knowledge/pac_answer_eval.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    catalog, passages, _ = canonical()
    item = {"id": "case", "question": "Question", "land_context": {"mode": "general", "lands": []},
            "expected_status": "abstained", "review": {"reviewed_by": "reviewer", "reviewed_on": "2026-10-17"}}
    mutation(item)
    artifact = {"schema_version": "pac-answer-eval-v1", "cases": [item]}
    assert not validator.is_valid(artifact)
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(AnswerEvalError):
        load_cases(path, catalog, passages)


def test_unknown_source_reference_is_rejected(tmp_path):
    catalog, passages, _ = canonical()
    artifact = {"schema_version": "pac-answer-eval-v1", "cases": [{
        "id": "case", "question": "pregunta", "land_context": {"mode": "general", "lands": []},
        "expected_status": "answered", "expected_source_ids": ["missing"], "expected_passage_ids": ["missing-passage"],
        "review": {"reviewed_by": "reviewer", "reviewed_on": "2026-10-17"},
    }]}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(AnswerEvalError, match="unknown reference"):
        load_cases(path, catalog, passages)


def test_quality_mismatch_is_reported_not_failed():
    case = {"id": "case", "question": "q", "land_context": {"mode": "general", "lands": []},
            "expected_status": "abstained", "review": {"reviewed_by":"reviewer", "reviewed_on":"2026-10-17"}}
    payload = {"status": "answered", "answer": "answer", "sources": [], "land_scope":"general", "land_ids_to_choose": []}
    catalog, passages, _ = canonical()
    report = evaluate([case], Client(payload), catalog, passages)
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
    case = {"id": "supplied-corpus-case", "question": "q",
            "land_context": {"mode": "general", "lands": []}, "expected_status": "answered",
            "expected_source_ids": [source["id"]], "expected_passage_ids": [passage["id"]],
            "review": {"reviewed_by": "reviewer", "reviewed_on": "2026-10-17"}}
    payload = {"status": "answered", "answer": "answer", "land_scope": "general", "land_ids_to_choose": [],
               "sources": [{"title": source["title"], "issuing_body": source["issuing_body"],
                            "url": source["original_url"], "location": passage["location"],
                            "published_or_updated_on": source["published_on"], "verified_on": source["verified_on"],
                            "excerpt": passage["text"]}]}

    report = evaluate([case], Client(payload), catalog, passages)

    assert report["case_rows"][0]["source_match"] is True
    assert report["case_rows"][0]["passage_match"] is True


@pytest.mark.parametrize("mutation", [
    {"expected_status": "Answered"}, {"expected_status": "answered", "expected_source_ids": ["x"]},
])
def test_case_status_and_answer_requirements_are_strict(tmp_path, mutation):
    catalog, passages, _ = canonical()
    item = {"id":"case", "question":"q", "land_context":{"mode":"general","lands":[]},
            "expected_status":"abstained", "review":{"reviewed_by":"reviewer","reviewed_on":"2026-10-17"}}
    item.update(mutation)
    path=tmp_path/"cases.json"
    path.write_text(json.dumps({"schema_version":"pac-answer-eval-v1","cases":[item]}))
    with pytest.raises(AnswerEvalError): load_cases(path,catalog,passages)


def test_contract_invalid_response_is_integrity_error():
    case={"id":"private-case","question":"q","land_context":{"mode":"general","lands":[]},"expected_status":"abstained"}
    bad={"status":"answered","answer":"x","sources":[],"land_scope":"general","land_ids_to_choose":[],"unexpected":True}
    with pytest.raises(AnswerEvalError, match="private-case.*contract"):
        catalog, passages, _ = canonical()
        evaluate([case], Client(bad), catalog, passages)


def test_cli_k_is_dependency_overridden_into_same_ask_route(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.ask_api import get_retrieval_k
    observed=[]
    monkeypatch.setattr("app.ask_api._prepare_runtime_corpus", lambda *a: object())
    monkeypatch.setattr("app.ask_api.answer_with_clarification", lambda *a, **kw: (observed.append(kw["k"]) or __import__("app.abstention", fromlist=["Abstention"]).Abstention("no_evidence", issues=())))
    from app.ask_api import get_corpus_documents, get_as_of_date, get_active_campaign
    app.dependency_overrides[get_retrieval_k]=lambda:2
    app.dependency_overrides[get_as_of_date]=lambda:__import__("datetime").date(2026,10,17)
    app.dependency_overrides[get_active_campaign]=lambda:"2026"
    app.dependency_overrides[get_corpus_documents]=lambda: __import__("app.ask_api",fromlist=["CorpusDocuments"]).CorpusDocuments(catalog={"sources":[]},passages={"passages":[]})
    try:
        response=TestClient(app).post("/ask",json={"question":"q","land_context":{"mode":"general","lands":[]}})
        assert response.status_code==200
        assert observed==[2]
    finally: app.dependency_overrides.clear()
