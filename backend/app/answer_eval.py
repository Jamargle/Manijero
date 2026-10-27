"""Deterministic report-only evaluation of the canonical PAC /ask slice."""
import json
from datetime import date
from pathlib import Path
from typing import Any
from app.ask_api import AskResponse, get_retrieval_k

VERSION = "pac-answer-eval-v2"

# The only review role this artifact admits today. A later independent review
# would need an explicit schema and process change, not a quiet edit here.
AUTHOR_REVIEW_ROLE = "author_only"
COVERAGE_KINDS = ("topic", "boundary")


class AnswerEvalError(ValueError):
    pass


def load_case_document(
    path: Path, catalog: Any, passages: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load and validate the case artifact, returning its cases and coverage."""

    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnswerEvalError("cannot read valid case artifact") from exc
    if (
        not isinstance(doc, dict)
        or set(doc) != {"schema_version", "cases", "coverage"}
        or doc["schema_version"] != VERSION
        or not isinstance(doc["cases"], list)
    ):
        raise AnswerEvalError("$: invalid case-set structure")
    coverage = _validate_coverage(doc["coverage"])
    area_ids = {area["id"] for area in coverage["areas"]}
    source_ids = {s["id"] for s in catalog["sources"]}
    passage_ids = {p["id"] for p in passages["passages"]}
    seen: set[str] = set()
    for i, c in enumerate(doc["cases"]):
        required = {"id", "question", "land_context", "expected_status", "review", "area"}
        allowed = required | {
            "expected_source_ids",
            "expected_passage_ids",
            "critical_facts",
            "expected_land_ids_to_choose",
        }
        if not isinstance(c, dict) or not required <= set(c) or set(c) - allowed:
            raise AnswerEvalError(f"$.cases[{i}]: invalid keys")
        if not isinstance(c["id"], str) or not c["id"] or c["id"] in seen:
            raise AnswerEvalError(f"$.cases[{i}].id: blank or duplicate")
        seen.add(c["id"])
        if not isinstance(c["area"], str) or c["area"] not in area_ids:
            raise AnswerEvalError(f"$.cases[{i}].area: undeclared coverage area")
        if not isinstance(c.get("expected_status"), str) or c["expected_status"] not in (
            "answered",
            "abstained",
            "needs_land_clarification",
        ):
            raise AnswerEvalError(f"$.cases[{i}].expected_status: invalid")
        if (
            not isinstance(c["question"], str)
            or not c["question"].strip()
            or len(c["question"]) > 2000
            or not isinstance(c["land_context"], dict)
        ):
            raise AnswerEvalError(f"$.cases[{i}]: invalid request")
        try:
            from app.ask_api import LandContext

            if not c["land_context"]:
                raise ValueError()
            LandContext.model_validate(c["land_context"])
            review = c["review"]
            if (
                set(review) != {"reviewed_by", "reviewed_on", "role"}
                or not isinstance(review["reviewed_by"], str)
                or not review["reviewed_by"].strip()
                or review["role"] != AUTHOR_REVIEW_ROLE
                or date.fromisoformat(review["reviewed_on"]).isoformat()
                != review["reviewed_on"]
            ):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise AnswerEvalError(
                f"$.cases[{i}]: invalid land context or review metadata"
            )
        if "critical_facts" in c and (
            not isinstance(c["critical_facts"], list)
            or any(not isinstance(x, str) or not x for x in c["critical_facts"])
        ):
            raise AnswerEvalError(f"$.cases[{i}].critical_facts: invalid")
        for key, known in (
            ("expected_source_ids", source_ids),
            ("expected_passage_ids", passage_ids),
        ):
            values = c.get(key, [])
            if (
                not isinstance(values, list)
                or any(not isinstance(v, str) for v in values)
                or len(values) != len(set(values))
                or not set(values) <= known
            ):
                raise AnswerEvalError(f"$.cases[{i}].{key}: unknown reference")
        if c["expected_status"] == "answered" and not c.get("expected_source_ids"):
            raise AnswerEvalError(f"$.cases[{i}].expected_source_ids: required")
        status = c["expected_status"]
        if status != "answered" and (
            c.get("expected_source_ids")
            or c.get("expected_passage_ids")
            or c.get("critical_facts")
        ):
            raise AnswerEvalError(f"$.cases[{i}]: non-answer case has answer expectations")
        if status == "answered" and not c.get("expected_passage_ids"):
            raise AnswerEvalError(f"$.cases[{i}].expected_passage_ids: required")
        if status == "needs_land_clarification":
            lands = c["land_context"].get("lands", [])
            ids = c.get("expected_land_ids_to_choose")
            if (
                not isinstance(ids, list)
                or not ids
                or not set(ids) <= {x.get("id") for x in lands}
            ):
                raise AnswerEvalError(
                    f"$.cases[{i}].expected_land_ids_to_choose: invalid"
                )
        elif c.get("expected_land_ids_to_choose"):
            raise AnswerEvalError(
                f"$.cases[{i}].expected_land_ids_to_choose: unexpected"
            )
    return doc["cases"], coverage


def load_cases(path: Path, catalog: Any, passages: Any) -> list[dict[str, Any]]:
    """Load and validate the case artifact, returning only its cases."""

    return load_case_document(path, catalog, passages)[0]


def _validate_coverage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "reviewed_against",
        "areas",
        "omissions",
    }:
        raise AnswerEvalError("$.coverage: invalid structure")
    if (
        not isinstance(value["reviewed_against"], str)
        or not value["reviewed_against"].strip()
    ):
        raise AnswerEvalError("$.coverage.reviewed_against: invalid")
    areas = value["areas"]
    if not isinstance(areas, list) or not areas:
        raise AnswerEvalError("$.coverage.areas: invalid")
    seen: set[str] = set()
    for i, area in enumerate(areas):
        if not isinstance(area, dict) or set(area) != {"id", "kind", "label"}:
            raise AnswerEvalError(f"$.coverage.areas[{i}]: invalid keys")
        if (
            not isinstance(area["id"], str)
            or not area["id"]
            or area["id"] in seen
        ):
            raise AnswerEvalError(f"$.coverage.areas[{i}].id: blank or duplicate")
        seen.add(area["id"])
        if area["kind"] not in COVERAGE_KINDS:
            raise AnswerEvalError(f"$.coverage.areas[{i}].kind: invalid")
        if not isinstance(area["label"], str) or not area["label"].strip():
            raise AnswerEvalError(f"$.coverage.areas[{i}].label: invalid")
    omissions = value["omissions"]
    if (
        not isinstance(omissions, list)
        or not omissions
        or any(not isinstance(x, str) or not x.strip() for x in omissions)
        or len(omissions) != len(set(omissions))
    ):
        raise AnswerEvalError("$.coverage.omissions: invalid")
    return value


def _coverage_report(
    cases: list[dict[str, Any]], coverage: dict[str, Any] | None
) -> dict[str, Any]:
    if coverage is None:
        return {
            "cases_by_area": {},
            "topics": {},
            "boundaries": {},
            "omissions": [],
        }
    counts = {area["id"]: 0 for area in coverage["areas"]}
    for case in cases:
        area_id = case.get("area")
        if area_id in counts:
            counts[area_id] += 1
    return {
        "cases_by_area": counts,
        "topics": {
            area["id"]: counts[area["id"]]
            for area in coverage["areas"]
            if area["kind"] == "topic"
        },
        "boundaries": {
            area["id"]: counts[area["id"]]
            for area in coverage["areas"]
            if area["kind"] == "boundary"
        },
        "omissions": list(coverage["omissions"]),
    }


def evaluate(
    cases: list[dict[str, Any]],
    client: Any,
    catalog: Any,
    passages: Any,
    k: int = 5,
    *,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []
    for case in cases:
        response = client.post(
            "/ask",
            json={"question": case["question"], "land_context": case["land_context"]},
        )
        if response.status_code != 200:
            raise AnswerEvalError(f"case {case['id']}: /ask returned invalid status")
        actual = response.json()
        try:
            actual = AskResponse.model_validate(actual).model_dump(mode="json")
        except Exception as exc:
            raise AnswerEvalError(
                f"case {case['id']}: /ask response violates API contract"
            ) from exc
        state = actual.get("status")
        sources = set()
        facts = []
        if state == "answered":
            # This evaluator maps exact canonical source URL and passage location/excerpt.
            for item in actual["sources"]:
                matching = [
                    s
                    for s in catalog["sources"]
                    if s["original_url"] == str(item["url"])
                ]
                if len(matching) == 1:
                    sources.add(matching[0]["id"])
                    exact = [
                        p
                        for p in passages["passages"]
                        if p["source_id"] == matching[0]["id"]
                        and p["location"] == item["location"]
                        and p["text"] == item["excerpt"]
                    ]
                    if len(exact) == 1:
                        facts.extend((exact[0]["id"],))
        returned_passages = set(facts)
        choices = actual.get("land_ids_to_choose", [])
        expected_sources = set(case.get("expected_source_ids", []))
        expected_passages = set(case.get("expected_passage_ids", []))
        expected_facts = list(case.get("critical_facts", []))
        answer = actual.get("answer", "")
        missing_facts = [fact for fact in expected_facts if fact not in answer]
        row = {
            "id": case["id"],
            "area": case.get("area"),
            "expected_status": case["expected_status"],
            "actual_status": state,
            "expected_state_match": state == case["expected_status"],
            "source_match": expected_sources <= sources,
            "passage_match": expected_passages <= returned_passages,
            "critical_facts_match": not missing_facts,
            "missing_expected_source_ids": sorted(expected_sources - sources),
            "missing_expected_passage_ids": sorted(expected_passages - returned_passages),
            "actual_source_ids": sorted(sources),
            "actual_passage_ids": sorted(returned_passages),
            "missing_critical_facts": missing_facts,
            "land_ids_to_choose": choices,
            "clarification_ids_match": set(choices)
            <= {land["id"] for land in case["land_context"]["lands"]},
            "unexpected_land_ids": sorted(
                set(choices) - {land["id"] for land in case["land_context"]["lands"]}
            ),
        }
        rows.append(row)
    count = len(rows)
    roles = sorted(
        {
            case["review"]["role"]
            for case in cases
            if isinstance(case.get("review"), dict) and case["review"].get("role")
        }
    )
    return {
        "schema_version": VERSION,
        "cases": count,
        "expected_state_agreement": sum(r["expected_state_match"] for r in rows),
        "answered_cases": sum(
            r["expected_status"] == "answered" for r in rows
        ),
        "abstention_cases": sum(
            r["expected_status"] == "abstained" for r in rows
        ),
        "clarification_cases": sum(
            r["expected_status"] == "needs_land_clarification" for r in rows
        ),
        "expected_answer_coverage": sum(
            r["expected_status"] == "answered" and r["actual_status"] == "answered"
            for r in rows
        ),
        "unexpected_answers": sum(
            r["expected_status"] != "answered" and r["actual_status"] == "answered"
            for r in rows
        ),
        "source_citation_agreement": sum(
            r["source_match"] for r in rows if r["expected_status"] == "answered"
        ),
        "critical_fact_matches": sum(
            r["critical_facts_match"] for r in rows if r["expected_status"] == "answered"
        ),
        "clarification_outcomes": sum(
            r["clarification_ids_match"]
            for r in rows
            if r["expected_status"] == "needs_land_clarification"
        ),
        "review": {
            "roles": roles,
            "independent_legal_review": False,
        },
        "coverage": _coverage_report(cases, coverage),
        "case_rows": rows,
    }
