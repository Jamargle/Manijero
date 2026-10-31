"""Focused, dependency-free checks for the answer API contract fixtures."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).parent
EXAMPLES = ROOT / "examples"
FORBIDDEN_LAND_KEYS = {"name", "label", "notes", "parcel_id", "sigpac", "area"}
WATER_REGIMES = {"dryland", "irrigated", "mixed", "unknown"}
PRODUCTION_METHODS = {"conventional", "organic", "mixed", "unknown"}
REQUEST_MODES = {"general", "all_active", "selected"}
RESPONSE_STATUSES = {"answered", "abstained", "needs_land_clarification"}
SCOPES = {"general", "all_active", "selected"}


def load(name: str) -> dict:
    with (EXAMPLES / name).open(encoding="utf-8") as file:
        return json.load(file)


def assert_date(value: str, field: str) -> None:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise AssertionError(f"{field} must be an ISO date") from error


def validate_request(payload: dict) -> None:
    assert set(payload) <= {"question", "land_context", "retain_for_improvement"}
    if "retain_for_improvement" in payload:
        assert isinstance(payload["retain_for_improvement"], bool), "opt-in must be a boolean"
    assert isinstance(payload.get("question"), str) and 1 <= len(payload["question"]) <= 2000
    context = payload.get("land_context")
    assert isinstance(context, dict) and set(context) == {"mode", "lands"}
    assert context["mode"] in REQUEST_MODES
    assert isinstance(context["lands"], list)
    if context["mode"] == "general":
        assert context["lands"] == []
    else:
        assert context["lands"], "non-general requests need at least one land"
    ids = set()
    for land in context["lands"]:
        assert isinstance(land, dict)
        assert not FORBIDDEN_LAND_KEYS.intersection(land), land
        assert set(land).issubset({"id", "municipality", "water_regime", "production_method"})
        assert isinstance(land.get("id"), str) and 1 <= len(land["id"]) <= 128
        assert land["id"] not in ids, "land IDs must be unique per request"
        ids.add(land["id"])
        if "water_regime" in land:
            assert land["water_regime"] in WATER_REGIMES
        if "production_method" in land:
            assert land["production_method"] in PRODUCTION_METHODS


def validate_source(source: dict) -> None:
    required = {"title", "issuing_body", "url", "location", "verified_on", "excerpt"}
    assert required.issubset(source)
    assert urlparse(source["url"]).scheme == "https"
    assert source["url"].endswith(".invalid") is False, "fixtures must use a reviewable URL"
    assert_date(source["verified_on"], "verified_on")
    if "published_or_updated_on" in source:
        assert_date(source["published_or_updated_on"], "published_or_updated_on")


def validate_response(payload: dict) -> None:
    assert set(payload) == {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}
    assert payload["status"] in RESPONSE_STATUSES
    assert payload["land_scope"] in SCOPES
    assert isinstance(payload["answer"], str) and len(payload["answer"]) <= 1200
    assert isinstance(payload["sources"], list)
    assert isinstance(payload["land_ids_to_choose"], list)
    assert all(isinstance(item, str) and 1 <= len(item) <= 128 for item in payload["land_ids_to_choose"])
    assert len(payload["land_ids_to_choose"]) == len(set(payload["land_ids_to_choose"]))
    for source in payload["sources"]:
        validate_source(source)

    if payload["status"] == "answered":
        assert payload["answer"].strip()
        assert payload["sources"], "answered responses require evidence"
        assert payload["land_ids_to_choose"] == []
    elif payload["status"] == "abstained":
        assert payload["answer"].strip()
        assert payload["sources"] == []
        assert payload["land_ids_to_choose"] == []
    else:
        assert payload["answer"] == ""
        assert payload["sources"] == []
        assert payload["land_ids_to_choose"], "clarification needs choices"


def main() -> None:
    validate_request(load("ask-request-general.json"))
    validate_request(load("ask-request-all-lands.json"))
    validate_request(load("ask-request-retention-opt-in.json"))
    validate_response(load("response-answered.json"))
    validate_response(load("response-abstained.json"))
    validate_response(load("response-needs-land-clarification.json"))
    print("Validated 3 request and 3 response examples against answer_api_contract")


if __name__ == "__main__":
    main()
