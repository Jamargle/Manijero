"""Deterministic generated conformance tests for the ``POST /ask`` wire contract.

The only corpus is the synthetic clarification fixture set. Every prompt, land id,
and land attribute here is invented for decision wiring; nothing in this module
establishes legal coverage, answer quality, performance, or pilot behavior.

The contract is the authority: ``contracts/openapi.yaml`` supplies the schemas,
bounds, and enums used to generate requests, and ``contracts/validate_examples.py``
stays the single cross-field oracle. Nothing here forks those rules.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path
import random
import sys
from typing import Any, Iterable, Mapping

import yaml
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_ROOT = REPO_ROOT / "contracts"
EXAMPLES_ROOT = CONTRACTS_ROOT / "examples"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "clarification"
CONTRACT_PATH = CONTRACTS_ROOT / "openapi.yaml"

# The committed request/response rules are the oracle; reuse them instead of copying.
sys.path.insert(0, str(CONTRACTS_ROOT))
from validate_examples import validate_request, validate_response  # noqa: E402

from app.ask_api import (  # noqa: E402
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
)
from app.main import app  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

SCHEMA_REF_PREFIX = "#/components/schemas/"
DEFAULT_SEED = 20261106
DEFAULT_CASES = 40
# A string no product copy contains; it must never come back on a rejection.
SENTINEL = "synthetic-sentinel-do-not-echo"
ANSWERED, ABSTAINED, CLARIFICATION = (
    "answered",
    "abstained",
    "needs_land_clarification",
)


# --- Contract loading and local reference resolution -------------------------


def load_contract() -> dict[str, Any]:
    """Read the versioned YAML contract once; PyYAML is a dev-only dependency."""

    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    assert isinstance(document, dict), "openapi.yaml must be a mapping"
    assert str(document.get("openapi", "")).startswith("3."), "openapi.yaml must be OpenAPI 3"
    return document


def local_schema_name(reference: Any) -> str:
    """Return the component name of a local schema reference, or fail loudly."""

    assert isinstance(reference, str) and reference.startswith(SCHEMA_REF_PREFIX), (
        "only local '{}<name>' references are allowed, got {!r}".format(
            SCHEMA_REF_PREFIX, reference
        )
    )
    name = reference[len(SCHEMA_REF_PREFIX):]
    assert name and "/" not in name, "malformed local schema reference {!r}".format(reference)
    return name


def resolve_schema(
    document: Mapping[str, Any], node: Any, stack: tuple[str, ...] = ()
) -> Any:
    """Copy ``node`` with every local component reference inlined.

    Any other reference form, a dangling name, or a cycle fails the assertion
    rather than silently passing an unresolved schema to the validator.
    """

    if isinstance(node, list):
        return [resolve_schema(document, item, stack) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        assert set(node) == {"$ref"}, "a $ref must not carry sibling keywords"
        name = local_schema_name(node["$ref"])
        assert name not in stack, "cyclic $ref to {}".format(name)
        schemas = document["components"]["schemas"]
        assert name in schemas, "unresolved $ref {!r}".format(node["$ref"])
        return resolve_schema(document, schemas[name], stack + (name,))
    return {key: resolve_schema(document, value, stack) for key, value in node.items()}


def iter_references(node: Any) -> Iterable[Any]:
    """Yield every ``$ref`` value anywhere in the document."""

    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from iter_references(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_references(item)


CONTRACT = load_contract()
REQUEST_SCHEMA = resolve_schema(
    CONTRACT,
    CONTRACT["paths"]["/ask"]["post"]["requestBody"]["content"]["application/json"]["schema"],
)
RESPONSE_SCHEMA = resolve_schema(
    CONTRACT,
    CONTRACT["paths"]["/ask"]["post"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ],
)
INSPECTION_SCHEMA = RESPONSE_SCHEMA["properties"]["inspection"]

FORMAT_CHECKER = FormatChecker()
REQUEST_VALIDATOR = Draft202012Validator(REQUEST_SCHEMA, format_checker=FORMAT_CHECKER)
RESPONSE_VALIDATOR = Draft202012Validator(RESPONSE_SCHEMA, format_checker=FORMAT_CHECKER)
INSPECTION_VALIDATOR = Draft202012Validator(INSPECTION_SCHEMA, format_checker=FORMAT_CHECKER)

# Generation inputs come from the contract itself, never from hardcoded copies.
QUESTION_MAX = REQUEST_SCHEMA["properties"]["question"]["maxLength"]
LAND_CONTEXT_SCHEMA = REQUEST_SCHEMA["properties"]["land_context"]
MODE_VALUES = tuple(LAND_CONTEXT_SCHEMA["properties"]["mode"]["enum"])
LAND_SCHEMA = LAND_CONTEXT_SCHEMA["properties"]["lands"]["items"]
LAND_ID_MAX = LAND_SCHEMA["properties"]["id"]["maxLength"]
MUNICIPALITY_MAX = LAND_SCHEMA["properties"]["municipality"]["maxLength"]
WATER_REGIMES = tuple(LAND_SCHEMA["properties"]["water_regime"]["enum"])
PRODUCTION_METHODS = tuple(LAND_SCHEMA["properties"]["production_method"]["enum"])

RESPONSE_KEYS = frozenset(RESPONSE_SCHEMA["properties"])
RESPONSE_REQUIRED = tuple(RESPONSE_SCHEMA["required"])


# --- Contract validity helpers ----------------------------------------------


def assert_schema_valid(validator: Draft202012Validator, payload: Any, label: str) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    assert not errors, "{} violates the contract schema: {}".format(
        label,
        "; ".join(
            "{}: {}".format(list(error.absolute_path) or "<root>", error.message)
            for error in errors[:5]
        ),
    )


def contract_accepts(payload: Any) -> bool:
    """Whether the contract (schema plus committed cross-field rules) accepts it."""

    if not REQUEST_VALIDATOR.is_valid(payload):
        return False
    try:
        validate_request(payload)
    except AssertionError:
        return False
    except (AttributeError, KeyError, TypeError):
        # A shape the oracle cannot even inspect is a rejected shape.
        return False
    return True


def assert_conformant_response(payload: Mapping[str, Any], response: Any) -> Mapping[str, Any]:
    """Assert one contract-valid request got a schema-valid response in contract shape."""

    assert response.status_code == 200, (
        "contract-valid request returned {}: {}".format(
            response.status_code, response.text[:200]
        )
    )
    body = response.json()
    assert isinstance(body, dict), "the response body must be a JSON object"
    undeclared = set(body) - RESPONSE_KEYS
    assert not undeclared, "undeclared top-level keys: {}".format(sorted(undeclared))
    missing = set(RESPONSE_REQUIRED) - set(body)
    assert not missing, "missing required response keys: {}".format(sorted(missing))
    assert_schema_valid(RESPONSE_VALIDATOR, body, "AskResponse")
    if "inspection" in body:
        # Development-only debug payload; when present it is still contract-shaped.
        assert_schema_valid(INSPECTION_VALIDATOR, body["inspection"], "AnswerInspection")
    # The committed cross-field rules see exactly the required five wire keys.
    wire_payload = {name: body[name] for name in RESPONSE_REQUIRED}
    validate_response(wire_payload)

    status = body["status"]
    if status == ANSWERED:
        assert body["answer"].strip() and body["sources"], "answered needs an answer and sources"
    elif status == ABSTAINED:
        assert body["answer"].strip() and body["sources"] == [], (
            "abstained needs an answer and no sources"
        )
    else:
        assert status == CLARIFICATION, "unexpected status {!r}".format(status)
        assert body["answer"] == "" and body["sources"] == [], (
            "clarification carries an empty answer and no sources"
        )
        assert body["land_ids_to_choose"], "clarification needs choices"
        request_ids = {land["id"] for land in payload["land_context"]["lands"]}
        assert set(body["land_ids_to_choose"]) <= request_ids, (
            "clarification returned an id the request did not carry"
        )
    return body


def assert_rejected(response: Any, sentinel: str = SENTINEL) -> None:
    """Assert a non-reflective 400/422 whose JSON body carries only ``detail``."""

    assert response.status_code in (400, 422), (
        "expected 400 or 422, got {}".format(response.status_code)
    )
    assert response.status_code < 500
    assert response.headers.get("content-type", "").startswith("application/json")
    body = response.json()
    assert isinstance(body, dict), "a rejection body must be a JSON object"
    assert set(body) == {"detail"}, "a rejection body must carry only detail, got {}".format(
        sorted(body)
    )
    assert isinstance(body["detail"], str) and body["detail"].strip()
    assert sentinel not in response.text, "the rejection echoed request text"


# --- Deterministic generation ----------------------------------------------


def configured_seed() -> int:
    """``MANIJERO_CONTRACT_FUZZ_SEED`` (default ``20261106``)."""

    return int(os.environ.get("MANIJERO_CONTRACT_FUZZ_SEED", DEFAULT_SEED))


def configured_case_count() -> int:
    """``MANIJERO_CONTRACT_FUZZ_CASES`` (default ``40``) generated cases."""

    count = int(os.environ.get("MANIJERO_CONTRACT_FUZZ_CASES", DEFAULT_CASES))
    assert count >= 0, "MANIJERO_CONTRACT_FUZZ_CASES must not be negative"
    return count


# Fixed fixture-corpus prompts that reach each response state. They are always
# first in the list, so even MANIJERO_CONTRACT_FUZZ_CASES=0 keeps state coverage.
STATE_COVERAGE_CASES: tuple[dict[str, Any], ...] = (
    {
        "question": "¿Cuándo se presenta la solicitud anual de ejemplo?",
        "land_context": {"mode": "general", "lands": []},
    },
    {
        "question": "¿Qué ayuda me corresponde?",
        "land_context": {"mode": "general", "lands": []},
    },
    {
        "question": "¿Puedo regar mi olivar de ejemplo?",
        "land_context": {
            "mode": "all_active",
            "lands": [
                {"id": "opaque-one", "water_regime": "irrigated"},
                {"id": "opaque-two", "water_regime": "dryland"},
            ],
        },
    },
)

GENERATED_WORDS = (
    "olivar",
    "aceituna",
    "riego",
    "solicitud",
    "parcela",
    "documento",
    "oficina",
    "cosecha",
    "ayuda",
    "ejemplo",
)
MUNICIPALITY_LETTERS = "abcdefghijklmnopqrstuvwxyz"
OPAQUE_ID_LETTERS = "abcdefghijklmnopqrstuvwxyz0123456789-_"


def generated_question(rng: random.Random) -> str:
    body = " ".join(rng.choices(GENERATED_WORDS, k=rng.randint(1, 6)))
    question = "¿{}?".format(body)
    if rng.random() < 0.1:
        # Exercise the contract's own upper bound with a still-valid question.
        filler = QUESTION_MAX - len(body) - 3
        assert filler > 0
        question = "¿{} {}?".format(body, "x" * filler)
        assert len(question) == QUESTION_MAX
    return question


def generated_municipality(rng: random.Random) -> str:
    length = MUNICIPALITY_MAX if rng.random() < 0.1 else rng.randint(1, 16)
    return "".join(rng.choices(MUNICIPALITY_LETTERS, k=length))


def generated_land_id(rng: random.Random, index: int) -> str:
    prefix = "land-{}-".format(index)
    length = LAND_ID_MAX if rng.random() < 0.1 else rng.randint(4, 20)
    suffix = "".join(rng.choices(OPAQUE_ID_LETTERS, k=length))
    land_id = prefix + suffix
    if len(land_id) > LAND_ID_MAX:
        land_id = land_id[:LAND_ID_MAX]
    assert 1 <= len(land_id) <= LAND_ID_MAX
    return land_id


def generate_case(rng: random.Random) -> dict[str, Any]:
    """Build one request from the contract's own bounds, enums, and optional keys."""

    mode = rng.choice(MODE_VALUES)
    land_count = 0 if mode == "general" else rng.choice((1, 1, 2, 3))
    lands = []
    for index in range(land_count):
        land: dict[str, Any] = {"id": generated_land_id(rng, index)}
        if rng.random() < 0.5:
            land["municipality"] = generated_municipality(rng)
        if rng.random() < 0.7:
            land["water_regime"] = rng.choice(WATER_REGIMES)
        if rng.random() < 0.5:
            land["production_method"] = rng.choice(PRODUCTION_METHODS)
        lands.append(land)
    case: dict[str, Any] = {
        "question": generated_question(rng),
        "land_context": {"mode": mode, "lands": lands},
    }
    if rng.random() < 0.25:
        case["retain_for_improvement"] = rng.random() < 0.5
    assert len(case["question"]) <= QUESTION_MAX
    assert contract_accepts(case), "the generator must only emit contract-valid cases"
    return case


def build_valid_cases(seed: int, generated_count: int) -> list[dict[str, Any]]:
    """The deterministic case list: fixed state coverage, then seeded generation."""

    rng = random.Random(seed)
    cases = [deepcopy(case) for case in STATE_COVERAGE_CASES]
    cases.extend(generate_case(rng) for _ in range(generated_count))
    return cases


def over_max(maximum: int, sentinel: str = SENTINEL) -> str:
    """A string of exactly ``maximum + 1`` characters that carries the sentinel."""

    filler = maximum + 1 - len(sentinel) - 1
    assert filler >= 0
    value = "{} {}".format(sentinel, "x" * filler)
    assert len(value) == maximum + 1
    return value


def build_invalid_cases() -> list[tuple[str, dict[str, Any]]]:
    """Fixed contract-invalid requests, one rule violated per case where practical."""

    def selected(lands: list[dict[str, Any]]) -> dict[str, Any]:
        return {"mode": "selected", "lands": lands}

    return [
        ("empty_question", {"question": "", "land_context": selected([{"id": SENTINEL}])}),
        (
            "over_long_question",
            {"question": over_max(QUESTION_MAX), "land_context": {"mode": "general", "lands": []}},
        ),
        (
            "wrong_question_type",
            {"question": 7, "land_context": selected([{"id": SENTINEL}])},
        ),
        ("missing_land_context", {"question": "¿{}?".format(SENTINEL)}),
        (
            "general_with_lands",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": {"mode": "general", "lands": [{"id": SENTINEL}]},
            },
        ),
        (
            "land_aware_without_lands",
            {"question": "¿{}?".format(SENTINEL), "land_context": selected([])},
        ),
        (
            "duplicate_land_ids",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": {
                    "mode": "all_active",
                    "lands": [{"id": SENTINEL}, {"id": SENTINEL}],
                },
            },
        ),
        (
            "unknown_mode",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": {"mode": "otro", "lands": []},
            },
        ),
        (
            "extra_top_level_field",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": {"mode": "general", "lands": []},
                "municipality": SENTINEL,
            },
        ),
        (
            "forbidden_privacy_key",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": selected([{"id": SENTINEL, "name": SENTINEL + "-nombre"}]),
            },
        ),
        (
            "non_boolean_opt_in",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": {"mode": "general", "lands": []},
                "retain_for_improvement": SENTINEL,
            },
        ),
        (
            "empty_land_id",
            {"question": "¿{}?".format(SENTINEL), "land_context": selected([{"id": ""}])},
        ),
        (
            "over_long_land_id",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": selected([{"id": over_max(LAND_ID_MAX)}]),
            },
        ),
        (
            "empty_municipality",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": selected([{"id": SENTINEL, "municipality": ""}]),
            },
        ),
        (
            "over_long_municipality",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": selected(
                    [{"id": SENTINEL, "municipality": over_max(MUNICIPALITY_MAX)}]
                ),
            },
        ),
        (
            "unknown_water_regime",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": selected([{"id": SENTINEL, "water_regime": "flooded"}]),
            },
        ),
        (
            "unknown_production_method",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": selected([{"id": SENTINEL, "production_method": "biodynamic"}]),
            },
        ),
        (
            "unknown_land_key",
            {
                "question": "¿{}?".format(SENTINEL),
                "land_context": selected([{"id": SENTINEL, "sigpac": SENTINEL}]),
            },
        ),
    ]


def general_base() -> dict[str, Any]:
    return {
        "question": "¿{} del olivar?".format(SENTINEL),
        "land_context": {"mode": "general", "lands": []},
    }


def land_aware_base() -> dict[str, Any]:
    return {
        "question": "¿{} del olivar?".format(SENTINEL),
        "land_context": {
            "mode": "all_active",
            "lands": [
                {"id": "{}-uno".format(SENTINEL), "water_regime": "irrigated"},
                {"id": "{}-dos".format(SENTINEL), "water_regime": "dryland"},
            ],
        },
    }


def build_mutations() -> list[tuple[str, dict[str, Any]]]:
    """One-field mutations of valid bases; each must still follow the oracle's verdict."""

    def delete_question(payload: dict[str, Any]) -> None:
        del payload["question"]

    def delete_land_context(payload: dict[str, Any]) -> None:
        del payload["land_context"]

    def question_wrong_type(payload: dict[str, Any]) -> None:
        payload["question"] = 7

    def question_over_max(payload: dict[str, Any]) -> None:
        payload["question"] = over_max(QUESTION_MAX)

    def land_id_wrong_type(payload: dict[str, Any]) -> None:
        payload["land_context"]["lands"][0]["id"] = 7

    def duplicate_land_id(payload: dict[str, Any]) -> None:
        lands = payload["land_context"]["lands"]
        lands[1]["id"] = lands[0]["id"]

    def missing_land_id(payload: dict[str, Any]) -> None:
        del payload["land_context"]["lands"][0]["id"]

    def forbidden_land_key(payload: dict[str, Any]) -> None:
        payload["land_context"]["lands"][0]["notes"] = SENTINEL

    def over_long_land_id(payload: dict[str, Any]) -> None:
        payload["land_context"]["lands"][0]["id"] = over_max(LAND_ID_MAX)

    def empty_municipality(payload: dict[str, Any]) -> None:
        payload["land_context"]["lands"][0]["municipality"] = ""

    def unknown_top_level_key(payload: dict[str, Any]) -> None:
        payload["sigpac"] = SENTINEL

    def non_boolean_opt_in(payload: dict[str, Any]) -> None:
        payload["retain_for_improvement"] = "yes"

    def invalid_mode_enum(payload: dict[str, Any]) -> None:
        payload["land_context"]["mode"] = "otro"

    def invalid_water_regime_enum(payload: dict[str, Any]) -> None:
        payload["land_context"]["lands"][0]["water_regime"] = "flooded"

    mutations: list[tuple[str, dict[str, Any]]] = []
    changes = (
        ("delete_question", land_aware_base(), delete_question),
        ("delete_land_context", general_base(), delete_land_context),
        ("question_wrong_type", land_aware_base(), question_wrong_type),
        ("question_over_long", general_base(), question_over_max),
        ("land_id_wrong_type", land_aware_base(), land_id_wrong_type),
        ("duplicate_land_id", land_aware_base(), duplicate_land_id),
        ("missing_land_id", land_aware_base(), missing_land_id),
        ("forbidden_land_key", land_aware_base(), forbidden_land_key),
        ("over_long_land_id", land_aware_base(), over_long_land_id),
        ("empty_municipality", land_aware_base(), empty_municipality),
        ("unknown_top_level_key", general_base(), unknown_top_level_key),
        ("non_boolean_opt_in", general_base(), non_boolean_opt_in),
        ("invalid_mode_enum", general_base(), invalid_mode_enum),
        ("invalid_water_regime_enum", land_aware_base(), invalid_water_regime_enum),
    )
    for label, base, mutate in changes:
        payload = deepcopy(base)
        mutate(payload)
        mutations.append((label, payload))
    return mutations


INVALID_CASES = build_invalid_cases()
MUTATIONS = build_mutations()


# --- Test client and corpus -------------------------------------------------


def fixture_documents() -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(FIXTURES / "catalog.json"),
        passages=load_passage_set(FIXTURES / "passages.json"),
    )


@pytest.fixture(scope="module")
def client():
    """The real app over the synthetic clarification corpus, pinned to one date."""

    app.dependency_overrides[get_corpus_documents] = fixture_documents
    app.dependency_overrides[get_as_of_date] = lambda: date(2026, 10, 13)
    app.dependency_overrides[get_active_campaign] = lambda: "2026"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def valid_run(client):
    """Post the default deterministic case list once and keep the responses."""

    cases = build_valid_cases(configured_seed(), configured_case_count())
    return [(payload, client.post("/ask", json=payload)) for payload in cases]


# --- Scenario 1: contract and committed examples agree ----------------------


def test_contract_resolves_every_local_reference_and_rejects_other_forms() -> None:
    references = list(iter_references(CONTRACT))
    assert references, "the contract must carry schema references"
    schemas = CONTRACT["components"]["schemas"]
    for reference in references:
        assert local_schema_name(reference) in schemas
    for name in schemas:
        assert resolve_schema(CONTRACT, {"$ref": SCHEMA_REF_PREFIX + name})
    with pytest.raises(AssertionError):
        resolve_schema(CONTRACT, {"$ref": "https://example.invalid/schema.json"})
    with pytest.raises(AssertionError):
        resolve_schema(CONTRACT, {"$ref": "#/components/schemas/DoesNotExist"})


def test_committed_examples_match_the_contract_and_the_cross_field_rules() -> None:
    request_files = sorted(EXAMPLES_ROOT.glob("ask-request-*.json"))
    response_files = sorted(EXAMPLES_ROOT.glob("response-*.json"))
    assert request_files and response_files
    for path in request_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert_schema_valid(REQUEST_VALIDATOR, payload, path.name)
        validate_request(payload)
    for path in response_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert_schema_valid(RESPONSE_VALIDATOR, payload, path.name)
        validate_response(payload)


# --- Scenarios 2 and 3: generated valid requests and state coverage --------


def test_generated_contract_valid_requests_are_accepted_in_contract_shape(valid_run) -> None:
    assert valid_run
    state_counts: dict[str, int] = {}
    for payload, response in valid_run:
        body = assert_conformant_response(payload, response)
        state_counts[body["status"]] = state_counts.get(body["status"], 0) + 1
    print("\ncontract fuzz: {} valid cases, states={}".format(len(valid_run), state_counts))


def test_all_three_response_states_are_reached_and_conform(valid_run) -> None:
    states = [
        assert_conformant_response(payload, response)["status"]
        for payload, response in valid_run
    ]
    assert ANSWERED in states, "no answered response was observed"
    assert ABSTAINED in states, "no abstained response was observed"
    assert CLARIFICATION in states, "no needs_land_clarification response was observed"


# --- Scenario 4: generated invalid requests are rejected without echo ------


@pytest.mark.parametrize(
    "label,payload", INVALID_CASES, ids=[label for label, _ in INVALID_CASES]
)
def test_contract_invalid_request_is_rejected_without_echo(client, label, payload) -> None:
    assert not contract_accepts(payload), "{} must violate the contract".format(label)
    response = client.post("/ask", json=payload)
    assert response.status_code < 500, "{} produced a 5xx".format(label)
    assert_rejected(response)


def test_malformed_json_is_rejected_without_echo(client) -> None:
    response = client.post(
        "/ask",
        content='{{"question":"{}",'.format(SENTINEL),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert_rejected(response)


# --- Scenario 5: single-field mutations follow the same rule ---------------


def test_mutations_violate_the_contract_before_they_are_posted() -> None:
    for label, payload in MUTATIONS:
        assert not contract_accepts(payload), "{} unexpectedly satisfies the contract".format(label)


@pytest.mark.parametrize("label,payload", MUTATIONS, ids=[label for label, _ in MUTATIONS])
def test_single_field_mutation_matches_the_contract_oracle(client, label, payload) -> None:
    accepted = contract_accepts(payload)
    response = client.post("/ask", json=payload)
    assert response.status_code < 500, "{} returned a 5xx".format(label)
    if accepted:
        assert_conformant_response(payload, response)
    else:
        assert_rejected(response)


# --- Scenario 6: determinism and bounded cost ------------------------------


def test_the_generated_case_list_is_deterministic_for_a_seed() -> None:
    seed = configured_seed()
    count = configured_case_count()
    first = build_valid_cases(seed, count)
    second = build_valid_cases(seed, count)
    assert first == second, "same seed must generate the identical case list"
    assert len(first) == len(STATE_COVERAGE_CASES) + count
    assert first[: len(STATE_COVERAGE_CASES)] == list(STATE_COVERAGE_CASES)
    for payload in first:
        assert contract_accepts(payload)


def test_a_different_seed_still_passes(client) -> None:
    cases = build_valid_cases(configured_seed() + 1, configured_case_count())
    for payload in cases:
        assert_conformant_response(payload, client.post("/ask", json=payload))


# --- Scenario 7: no silent schema drift ------------------------------------


def flatten_non_null(schema: Any) -> list[dict[str, Any]]:
    """The non-null members of a schema, so nullable wrappers compare structurally."""

    if not isinstance(schema, dict):
        return []
    if "anyOf" in schema:
        members: list[dict[str, Any]] = []
        for member in schema["anyOf"]:
            if isinstance(member, dict) and member.get("type") == "null":
                continue
            members.extend(flatten_non_null(member))
        return members or [schema]
    return [schema]


def describe_schema(schema: Any) -> dict[str, Any]:
    """The compared facets: property names, required keys, enums, and string bounds."""

    description: dict[str, Any] = {
        "enum": None,
        "min_length": None,
        "max_length": None,
        "properties": {},
        "required": set(),
        "items": None,
    }
    for member in flatten_non_null(schema):
        if "const" in member:
            description["enum"] = (member["const"],)
        if "enum" in member:
            description["enum"] = tuple(member["enum"])
        if "minLength" in member:
            description["min_length"] = member["minLength"]
        if "maxLength" in member:
            description["max_length"] = member["maxLength"]
        for name, sub_schema in member.get("properties", {}).items():
            description["properties"].setdefault(name, sub_schema)
        description["required"].update(member.get("required", ()))
        if "items" in member:
            description["items"] = member["items"]
    return description


def assert_matching_contract_facets(
    contract_schema: Any, app_schema: Any, location: str
) -> None:
    """Fail on a real drift of property names, required keys, enums, or string bounds."""

    expected = describe_schema(contract_schema)
    actual = describe_schema(app_schema)
    assert set(expected["properties"]) == set(actual["properties"]), (
        "{}: property names drift; contract-only {}, service-only {}".format(
            location,
            sorted(set(expected["properties"]) - set(actual["properties"])),
            sorted(set(actual["properties"]) - set(expected["properties"])),
        )
    )
    assert expected["required"] == actual["required"], "{}: required keys drift: {} vs {}".format(
        location, sorted(expected["required"]), sorted(actual["required"])
    )
    assert expected["enum"] == actual["enum"], "{}: enum values drift; contract {} vs service {}".format(
        location, expected["enum"], actual["enum"]
    )
    assert (expected["min_length"], expected["max_length"]) == (
        actual["min_length"],
        actual["max_length"],
    ), "{}: string bounds drift; contract ({}, {}) vs service ({}, {})".format(
        location,
        expected["min_length"],
        expected["max_length"],
        actual["min_length"],
        actual["max_length"],
    )
    for name in expected["properties"]:
        assert_matching_contract_facets(
            expected["properties"][name], actual["properties"][name], "{}.{}".format(location, name)
        )
    assert (expected["items"] is None) == (actual["items"] is None), (
        "{}: item schema drift; contract {} vs service {}".format(
            location, expected["items"] is not None, actual["items"] is not None
        )
    )
    if expected["items"] is not None:
        assert_matching_contract_facets(expected["items"], actual["items"], location + "[]")


def test_the_service_openapi_does_not_drift_from_the_contract(client) -> None:
    document = client.get("/openapi.json")
    assert document.status_code == 200, "the local profile must advertise /openapi.json"
    openapi = document.json()
    operation = openapi["paths"]["/ask"]["post"]
    app_request = resolve_schema(
        openapi, operation["requestBody"]["content"]["application/json"]["schema"]
    )
    app_response = resolve_schema(
        openapi, operation["responses"]["200"]["content"]["application/json"]["schema"]
    )
    assert_matching_contract_facets(REQUEST_SCHEMA, app_request, "AskRequest")
    assert_matching_contract_facets(RESPONSE_SCHEMA, app_response, "AskResponse")
