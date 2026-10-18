"""Deterministic report-only evaluation of the canonical PAC /ask slice."""
import json
from datetime import date
from pathlib import Path
from typing import Any
from app.ask_api import AskResponse, get_retrieval_k

VERSION = "pac-answer-eval-v1"


class AnswerEvalError(ValueError):
    pass


def load_cases(path: Path, catalog: Any, passages: Any) -> list[dict[str, Any]]:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnswerEvalError("cannot read valid case artifact") from exc
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "cases"} or doc["schema_version"] != VERSION or not isinstance(doc["cases"], list):
        raise AnswerEvalError("$: invalid case-set structure")
    source_ids = {s["id"] for s in catalog["sources"]}
    passage_ids = {p["id"] for p in passages["passages"]}
    seen: set[str] = set()
    for i, c in enumerate(doc["cases"]):
        required = {"id", "question", "land_context", "expected_status", "review"}
        allowed = required | {"expected_source_ids", "expected_passage_ids", "critical_facts", "expected_land_ids_to_choose"}
        if not isinstance(c, dict) or not required <= set(c) or set(c) - allowed:
            raise AnswerEvalError(f"$.cases[{i}]: invalid keys")
        if not isinstance(c["id"], str) or not c["id"] or c["id"] in seen:
            raise AnswerEvalError(f"$.cases[{i}].id: blank or duplicate")
        seen.add(c["id"])
        if not isinstance(c.get("expected_status"), str) or c["expected_status"] not in ("answered", "abstained", "needs_land_clarification"):
            raise AnswerEvalError(f"$.cases[{i}].expected_status: invalid")
        if not isinstance(c["question"], str) or not c["question"].strip() or len(c["question"]) > 2000 or not isinstance(c["land_context"], dict):
            raise AnswerEvalError(f"$.cases[{i}]: invalid request")
        try:
            from app.ask_api import LandContext
            if not c["land_context"]:
                raise ValueError()
            LandContext.model_validate(c["land_context"])
            review = c["review"]
            if set(review) != {"reviewed_by", "reviewed_on"} or not isinstance(review["reviewed_by"], str) or not review["reviewed_by"].strip() or date.fromisoformat(review["reviewed_on"]).isoformat() != review["reviewed_on"]:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise AnswerEvalError(f"$.cases[{i}]: invalid land context or review metadata")
        if "critical_facts" in c and (not isinstance(c["critical_facts"], list) or any(not isinstance(x, str) or not x for x in c["critical_facts"])):
            raise AnswerEvalError(f"$.cases[{i}].critical_facts: invalid")
        for key, known in (("expected_source_ids", source_ids), ("expected_passage_ids", passage_ids)):
            values = c.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values) or len(values) != len(set(values)) or not set(values) <= known:
                raise AnswerEvalError(f"$.cases[{i}].{key}: unknown reference")
        if c["expected_status"] == "answered" and not c.get("expected_source_ids"):
            raise AnswerEvalError(f"$.cases[{i}].expected_source_ids: required")
        status = c["expected_status"]
        if status != "answered" and (c.get("expected_source_ids") or c.get("expected_passage_ids") or c.get("critical_facts")):
            raise AnswerEvalError(f"$.cases[{i}]: non-answer case has answer expectations")
        if status == "answered" and not c.get("expected_passage_ids"):
            raise AnswerEvalError(f"$.cases[{i}].expected_passage_ids: required")
        if status == "needs_land_clarification":
            lands = c["land_context"].get("lands", [])
            ids = c.get("expected_land_ids_to_choose")
            if not isinstance(ids, list) or not ids or not set(ids) <= {x.get("id") for x in lands}:
                raise AnswerEvalError(f"$.cases[{i}].expected_land_ids_to_choose: invalid")
        elif c.get("expected_land_ids_to_choose"):
            raise AnswerEvalError(f"$.cases[{i}].expected_land_ids_to_choose: unexpected")
    return doc["cases"]


def evaluate(cases: list[dict[str, Any]], client: Any, catalog: Any, passages: Any, k: int = 5) -> dict[str, Any]:
    rows = []
    for case in cases:
        response = client.post("/ask", json={"question": case["question"], "land_context": case["land_context"]})
        if response.status_code != 200:
            raise AnswerEvalError(f"case {case['id']}: /ask returned invalid status")
        actual = response.json()
        try:
            actual = AskResponse.model_validate(actual).model_dump(mode="json")
        except Exception as exc:
            raise AnswerEvalError(f"case {case['id']}: /ask response violates API contract") from exc
        state = actual.get("status")
        sources = set()
        facts = []
        if state == "answered":
            # This evaluator maps exact canonical source URL and passage location/excerpt.
            for item in actual["sources"]:
                matching = [s for s in catalog["sources"] if s["original_url"] == str(item["url"])]
                if len(matching) == 1:
                    sources.add(matching[0]["id"])
                    exact = [p for p in passages["passages"] if p["source_id"] == matching[0]["id"] and p["location"] == item["location"] and p["text"] == item["excerpt"]]
                    if len(exact) == 1:
                        facts.extend((exact[0]["id"],))
        returned_passages = set(facts)
        choices = actual.get("land_ids_to_choose", [])
        row = {"id":case["id"],"expected_status":case["expected_status"],"actual_status":state,
               "expected_state_match":state == case["expected_status"],
               "source_match":set(case.get("expected_source_ids", [])) <= sources,
               "passage_match":set(case.get("expected_passage_ids", [])) <= returned_passages,
               "critical_facts_match":all(f in actual.get("answer", "") for f in case.get("critical_facts", [])),
               "land_ids_to_choose":choices,
               "clarification_ids_match":set(choices) <= {l["id"] for l in case["land_context"]["lands"]}}
        rows.append(row)
    count = len(rows)
    return {"schema_version": VERSION, "cases": count, "expected_state_agreement": sum(r["expected_state_match"] for r in rows),
            "expected_answer_coverage": sum(r["expected_status"] == "answered" and r["actual_status"] == "answered" for r in rows),
            "unexpected_answers": sum(r["expected_status"] != "answered" and r["actual_status"] == "answered" for r in rows),
            "source_citation_agreement": sum(r["source_match"] for r in rows if r["expected_status"] == "answered"),
            "critical_fact_matches": sum(r["critical_facts_match"] for r in rows if r["expected_status"] == "answered"),
            "clarification_outcomes": sum(r["clarification_ids_match"] for r in rows if r["expected_status"] == "needs_land_clarification"), "case_rows": rows}
