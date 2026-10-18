"""Focused tests for the offline land-safety evaluation harness.

The fixtures under ``fixtures/land_safety/`` are synthetic and clearly labelled:
they are not real legal documents and they carry no real deadline, amount, or
article. They exist only to exercise the trap taxonomy, the source-anchored
checks, the report-only metrics, the enforced safety invariants, and the
critical-review gate.

The tests never call a model or the network: the harness runs the accepted
code-composed extractive generator over the local fixtures, and grading is
deterministic rule checking.
"""

import importlib.util
import json
import socket
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.abstention import (  # noqa: E402  (path setup must run first)
    ABSTENTION_MESSAGES,
    ABSTENTION_REASONS,
    Abstention,
    prepare_corpus,
    to_abstention_response,
)
from app.clarification import (  # noqa: E402
    CLARIFICATION_SCOPE,
    LAND_SCOPES,
    DEFAULT_MAX_CLAIMS,
)
from app.land_safety_eval import (  # noqa: E402
    ANSWER_SOURCE_KEYS,
    CATEGORIES,
    CASE_OPTIONAL_KEYS,
    CASE_REQUIRED_KEYS,
    EXPECTED_OUTCOMES,
    LAND_SAFETY_EVAL_SCHEMA_VERSION,
    RESPONSE_KEYS,
    EvalCase,
    LandSafetyEvalError,
    applicable_checks,
    evaluate,
    load_cases,
    run_case,
    safety_violations,
    validate_cases,
)
from app.retrieval import (  # noqa: E402
    DEFAULT_K,
    load_passage_set,
)
from app.source_catalog import load_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = BACKEND_ROOT / "scripts" / "evaluate_land_safety.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "land_safety"
EMPTY_CATALOG = Path(__file__).resolve().parent / "fixtures" / "empty_catalog.json"
EDGE = FIXTURES / "edge"
SCHEMA_PATH = REPO_ROOT / "knowledge" / "land_safety_eval.schema.json"

AS_OF = "2026-10-13"
RIEGO_QUESTION = "¿Puedo usar el riego de apoyo en la parcela de muestra?"


# --- helpers ----------------------------------------------------------------


def fixture(name: str) -> Path:
    return FIXTURES / name


def edge(name: str) -> Path:
    return EDGE / name


def as_of_date(as_of: str = AS_OF) -> date:
    return date.fromisoformat(as_of)


def catalog_document():
    return load_catalog(fixture("catalog.json"))


def passage_document():
    return load_passage_set(fixture("passages.json"))


def current_corpus(as_of: str = AS_OF):
    corpus = prepare_corpus(
        catalog_document(), passage_document(), as_of_date(as_of), "2026"
    )
    assert not isinstance(corpus, Abstention)
    return corpus


def load_fixture_cases() -> Tuple[EvalCase, ...]:
    return load_cases(fixture("cases.json"))


def case_by_id(case_id: str) -> EvalCase:
    for case in load_fixture_cases():
        if case.id == case_id:
            return case
    raise AssertionError("unknown fixture case: {}".format(case_id))


def corpus_source_ids() -> frozenset:
    from app.retrieval import eligible_source_ids

    return eligible_source_ids(catalog_document(), as_of_date())


def result_by_id(results: Sequence[Any], case_id: str):
    for result in results:
        if result.id == case_id:
            return result
    raise AssertionError("unknown result: {}".format(case_id))


def make_case(case_id: str, **overrides: Any) -> EvalCase:
    values: Dict[str, Any] = {
        "id": case_id,
        "category": "covered",
        "question": "¿Pregunta sintética de prueba?",
        "land_context": {"mode": "general", "lands": []},
        "expect": "answered",
        "expected_source_ids": ("fixture_lse_junta",),
    }
    values.update(overrides)
    return EvalCase(**values)


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *arguments],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def baseline_cli(*extra: str) -> subprocess.CompletedProcess:
    return run_cli(
        "--catalog",
        str(fixture("catalog.json")),
        "--passages",
        str(fixture("passages.json")),
        "--cases",
        str(fixture("cases.json")),
        "--as-of",
        AS_OF,
        "--active-campaign",
        "2026",
        "--k",
        "5",
        *extra,
    )


def load_cli_module():
    spec = importlib.util.spec_from_file_location("evaluate_land_safety_cli", CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case_document(case: Dict[str, Any]) -> Dict[str, Any]:
    return {"schema_version": LAND_SAFETY_EVAL_SCHEMA_VERSION, "cases": [case]}


def minimal_case(**overrides: Any) -> Dict[str, Any]:
    case: Dict[str, Any] = {
        "id": "covered-01",
        "category": "covered",
        "question": "¿Pregunta sintética de prueba?",
        "land_context": {"mode": "general", "lands": []},
        "expect": "answered",
        "expected_source_ids": ["fixture_lse_junta"],
    }
    case.update(overrides)
    return case


# --- schema and case-set contract -------------------------------------------


def test_schema_file_parses_and_matches_the_executable_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    case = schema["$defs"]["case"]

    assert schema["properties"]["schema_version"]["const"] == LAND_SAFETY_EVAL_SCHEMA_VERSION
    assert set(case["properties"]["category"]["enum"]) == set(CATEGORIES)
    assert set(case["properties"]["expect"]["enum"]) == set(EXPECTED_OUTCOMES)
    assert set(case["required"]) == set(CASE_REQUIRED_KEYS)
    assert set(case["properties"]) == set(CASE_REQUIRED_KEYS) | set(CASE_OPTIONAL_KEYS)
    assert set(schema["$defs"]["landContext"]["properties"]["mode"]["enum"]) == set(
        LAND_SCOPES
    )
    assert set(schema["$defs"]["review"]["required"]) == {
        "reviewed_by",
        "reviewed_on",
        "level",
        "anchor",
    }


def test_schema_names_the_executable_validator_and_is_tracked() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert "backend/app/land_safety_eval.py" in schema["description"]
    # Git-tracked: the path resolves inside the repository.
    assert SCHEMA_PATH.is_file()
    assert str(SCHEMA_PATH).startswith(str(REPO_ROOT))


def test_load_cases_reads_every_fixture_case() -> None:
    cases = load_fixture_cases()

    assert {case.id for case in cases} == {
        "covered-solicitud-01",
        "covered-plazo-01",
        "uncovered-tractor-01",
        "false-premise-decreto-01",
        "mixed-land-riego-01",
        "unknown-attribute-riego-01",
    }
    assert {case.category for case in cases} == set(CATEGORIES)


def test_load_cases_rejects_a_missing_file() -> None:
    with pytest.raises(LandSafetyEvalError):
        load_cases(fixture("does-not-exist.json"))


def test_load_cases_rejects_malformed_json() -> None:
    with pytest.raises(LandSafetyEvalError):
        load_cases(edge("malformed.json"))


def test_load_cases_rejects_a_wrong_schema_version() -> None:
    with pytest.raises(LandSafetyEvalError) as error:
        load_cases(edge("wrong_schema_version.json"))

    assert "$.schema_version" in str(error.value)


@pytest.mark.parametrize(
    "name,path_fragment",
    [
        ("unknown_category.json", "$.cases[0].category"),
        ("unknown_expect.json", "$.cases[0].expect"),
        ("unknown_reason.json", "$.cases[0].expect_reason"),
        ("abstained_without_reason.json", "$.cases[0].expect_reason"),
        ("answered_without_sources.json", "$.cases[0].expected_source_ids"),
        (
            "clarification_without_land_ids.json",
            "$.cases[0].expected_land_ids_to_choose",
        ),
        ("critical_without_review.json", "$.cases[0].review"),
        ("duplicate_ids.json", "$.cases[1].id"),
        ("unknown_key.json", "$.cases[0]"),
    ],
)
def test_load_cases_reports_a_located_error(name: str, path_fragment: str) -> None:
    with pytest.raises(LandSafetyEvalError) as error:
        load_cases(edge(name))

    assert path_fragment in str(error.value)


def test_unknown_land_key_is_a_located_error() -> None:
    document = case_document(
        minimal_case(land_context={"mode": "general", "lands": [{"id": "land-A", "name": "x"}]})
    )

    with pytest.raises(LandSafetyEvalError) as error:
        validate_cases(document)

    assert "$.cases[0].land_context.lands[0]" in str(error.value)


def test_non_calendar_review_date_is_a_located_error() -> None:
    document = case_document(
        minimal_case(
            critical=True,
            review={
                "reviewed_by": "fixture reviewer",
                "reviewed_on": "2026-02-30",
                "level": 1,
                "anchor": "fixture_lse_junta#Art. 1",
            },
        )
    )

    with pytest.raises(LandSafetyEvalError) as error:
        validate_cases(document)

    assert "$.cases[0].review.reviewed_on" in str(error.value)


def test_review_level_must_be_a_positive_integer() -> None:
    document = case_document(
        minimal_case(
            critical=True,
            review={
                "reviewed_by": "fixture reviewer",
                "reviewed_on": "2026-10-13",
                "level": 0,
                "anchor": "fixture_lse_junta#Art. 1",
            },
        )
    )

    with pytest.raises(LandSafetyEvalError) as error:
        validate_cases(document)

    assert "$.cases[0].review.level" in str(error.value)


def test_review_anchor_must_be_source_anchored() -> None:
    document = case_document(
        minimal_case(
            critical=True,
            review={
                "reviewed_by": "fixture reviewer",
                "reviewed_on": "2026-10-13",
                "level": 1,
                "anchor": "no-anchor",
            },
        )
    )

    with pytest.raises(LandSafetyEvalError) as error:
        validate_cases(document)

    assert "$.cases[0].review.anchor" in str(error.value)


def test_a_well_formed_critical_case_loads() -> None:
    cases = load_fixture_cases()
    critical = [case for case in cases if case.critical]

    assert len(critical) == 1
    assert critical[0].review is not None
    assert critical[0].review["anchor"].startswith("fixture_lse_junta#")


def test_load_diagnostics_never_echo_case_text() -> None:
    """A located load error names only the JSON path, never the case text."""

    secret = "ZZQQPREGUNTASECRETA"
    document = case_document(
        minimal_case(id="zzqq-secret-id", question=secret, expect="abstained")
    )

    with pytest.raises(LandSafetyEvalError) as error:
        validate_cases(document)

    message = str(error.value)
    assert "$.cases[0].expect_reason" in message
    assert secret not in message
    assert "zzqq-secret-id" not in message


def test_duplicate_ids_do_not_echo_the_id_value() -> None:
    document = case_document(minimal_case(id="zzqq-secret-id"))
    document["cases"].append(minimal_case(id="zzqq-secret-id"))

    with pytest.raises(LandSafetyEvalError) as error:
        validate_cases(document)

    assert "zzqq-secret-id" not in str(error.value)


# --- per-category behaviour -------------------------------------------------


def test_covered_case_answers_with_its_expected_source() -> None:
    case = case_by_id("covered-solicitud-01")
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert result.outcome == "answered"
    assert case.expected_source_ids[0] in result.source_ids
    assert case.expected_passage_ids[0] in result.passage_ids
    assert result.checks["correct_outcome"] is True
    assert result.checks["correct_sources"] is True
    assert result.expectation_met is True


def test_critical_covered_case_answers_literally_from_the_critical_passage() -> None:
    case = case_by_id("covered-plazo-01")
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert result.outcome == "answered"
    assert "fixture-lse-plazo-1" in result.passage_ids
    assert result.expectation_met is True


def test_uncovered_case_abstains_safely_with_no_evidence() -> None:
    case = case_by_id("uncovered-tractor-01")
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert result.outcome == "abstained"
    assert result.reason == "no_evidence"
    assert result.source_ids == ()
    assert result.land_ids_to_choose == ()
    assert result.payload["sources"] == []
    assert result.payload["answer"] == ABSTENTION_MESSAGES["no_evidence"]
    assert result.checks["safe_abstention"] is True
    assert result.expectation_met is True


def test_false_premise_case_abstains_with_the_false_premise_reason() -> None:
    case = case_by_id("false-premise-decreto-01")
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert result.outcome == "abstained"
    assert result.reason == "false_premise"
    assert result.source_ids == ()
    assert result.checks["safe_abstention"] is True
    assert result.expectation_met is True


def test_mixed_land_case_clarifies_exactly_the_request_ids() -> None:
    case = case_by_id("mixed-land-riego-01")
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert result.outcome == "needs_land_clarification"
    assert set(result.land_ids_to_choose) == {"land-A", "land-B"}
    assert set(result.land_ids_to_choose) <= {"land-A", "land-B"}
    assert result.checks["correct_clarification"] is True
    assert result.expectation_met is True


def test_unknown_attribute_case_answers_without_over_clarifying() -> None:
    case = case_by_id("unknown-attribute-riego-01")
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert result.outcome == "answered"
    assert result.checks["no_over_clarification"] is True
    assert result.checks["correct_sources"] is True
    assert result.land_ids_to_choose == ()
    assert result.expectation_met is True


def test_a_stale_corpus_abstains_safely_for_every_case() -> None:
    stale = Abstention(reason="stale_evidence")
    result = run_case(case_by_id("covered-solicitud-01"), stale, as_of_date(), 5)

    assert result.outcome == "abstained"
    assert result.reason == "stale_evidence"
    assert result.checks["safe_abstention"] is True


# --- source anchoring -------------------------------------------------------


def test_an_expected_source_that_is_not_returned_fails_the_source_check() -> None:
    case = make_case("covered-missing-source", expected_source_ids=("ghost_source",))
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert result.outcome == "answered"
    assert result.checks["correct_sources"] is False
    assert result.expectation_met is False


def test_a_source_outside_the_corpus_fails_the_source_check() -> None:
    case = case_by_id("covered-solicitud-01")
    result = run_case(
        case,
        current_corpus(),
        as_of_date(),
        5,
        corpus_source_ids=frozenset({"ghost_source"}),
    )

    assert result.checks["correct_sources"] is False


def test_the_accepted_decision_is_called_once_per_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.land_safety_eval as module

    calls = []
    original = module.answer_with_clarification

    def recording(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "answer_with_clarification", recording)
    run_case(case_by_id("covered-solicitud-01"), current_corpus(), as_of_date(), 5)

    assert len(calls) == 1


# --- enforced safety invariants ---------------------------------------------


def test_safety_violations_accept_clean_payloads() -> None:
    assert safety_violations(
        {"status": "abstained", "answer": ABSTENTION_MESSAGES["no_evidence"],
         "sources": [], "land_scope": "general", "land_ids_to_choose": []},
        "abstained",
        "no_evidence",
        (),
    ) == ()
    assert safety_violations(
        {"status": "needs_land_clarification", "answer": "", "sources": [],
         "land_scope": "selected", "land_ids_to_choose": ["land-A"]},
        "needs_land_clarification",
        None,
        ("land-A",),
    ) == ()
    assert safety_violations(
        {"status": "answered", "answer": "texto [1]",
         "sources": [dict.fromkeys(ANSWER_SOURCE_KEYS, "x")],
         "land_scope": "general", "land_ids_to_choose": []},
        "answered",
        None,
        (),
    ) == ()


def _abstention_payload(**overrides: Any) -> Dict[str, Any]:
    payload = to_abstention_response(Abstention(reason="no_evidence"))
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "mutate,expected",
    [
        ({"sources": [{"title": "x"}]}, "abstention_has_sources"),
        ({"land_ids_to_choose": ["land-A"]}, "abstention_has_land_ids"),
        ({"status": "answered"}, "payload_status_mismatch"),
        ({"answer": "42 días"}, "abstention_message_not_pinned"),
        ({"answer": " "}, "abstention_blank_message"),
    ],
)
def test_abstention_invariants_detect_each_leak(
    mutate: Dict[str, Any], expected: str
) -> None:
    payload = _abstention_payload(**mutate)

    assert expected in safety_violations(payload, "abstained", "no_evidence", ())


def test_an_off_taxonomy_abstention_reason_is_a_violation() -> None:
    payload = _abstention_payload()

    assert "abstention_reason_off_taxonomy" in safety_violations(
        payload, "abstained", "not_a_reason", ()
    )


def test_a_digit_or_date_in_an_abstention_message_is_a_violation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.land_safety_eval as module

    monkeypatch.setitem(module.ABSTENTION_MESSAGES, "no_evidence", "Hay 42 días.")
    payload = {
        "status": "abstained",
        "answer": "Hay 42 días.",
        "sources": [],
        "land_scope": "general",
        "land_ids_to_choose": [],
    }
    violations = safety_violations(payload, "abstained", "no_evidence", ())

    assert "abstention_message_has_digit" in violations
    assert "abstention_message_has_figure_or_date" in violations


@pytest.mark.parametrize(
    "mutate,expected",
    [
        ({"answer": "una respuesta"}, "clarification_answer_not_empty"),
        ({"sources": [{"title": "x"}]}, "clarification_has_sources"),
        ({"land_scope": "general"}, "clarification_scope_not_selected"),
        ({"land_ids_to_choose": []}, "clarification_ids_empty"),
        ({"land_ids_to_choose": ["land-A", "land-A"]}, "clarification_ids_not_unique"),
        ({"land_ids_to_choose": ["ghost"]}, "clarification_id_not_requested"),
        ({"land_ids_to_choose": ["  "]}, "clarification_id_blank"),
    ],
)
def test_clarification_invariants_detect_each_leak(
    mutate: Dict[str, Any], expected: str
) -> None:
    payload: Dict[str, Any] = {
        "status": "needs_land_clarification",
        "answer": "",
        "sources": [],
        "land_scope": "selected",
        "land_ids_to_choose": ["land-A"],
    }
    payload.update(mutate)

    assert expected in safety_violations(
        payload, "needs_land_clarification", None, ("land-A",)
    )


def test_answered_invariant_detects_missing_sources_and_out_of_range_markers() -> None:
    assert "answered_no_sources" in safety_violations(
        {"status": "answered", "answer": "texto [1]", "sources": [],
         "land_scope": "general", "land_ids_to_choose": []},
        "answered",
        None,
        (),
    )
    assert "answered_marker_out_of_range" in safety_violations(
        {"status": "answered", "answer": "texto [3]",
         "sources": [dict.fromkeys(ANSWER_SOURCE_KEYS, "x")],
         "land_scope": "general", "land_ids_to_choose": []},
        "answered",
        None,
        (),
    )


def test_payload_key_violation_is_detected() -> None:
    payload = _abstention_payload(extra="x")

    assert safety_violations(payload, "abstained", "no_evidence", ()) == ("payload_keys",)


def test_payload_key_set_is_the_accepted_ask_response() -> None:
    assert RESPONSE_KEYS == {
        "status",
        "answer",
        "sources",
        "land_scope",
        "land_ids_to_choose",
    }


def test_every_fixture_payload_holds_the_safety_invariants() -> None:
    report = evaluate(
        load_fixture_cases(),
        current_corpus(),
        as_of_date(),
        5,
        corpus_source_ids=corpus_source_ids(),
    )

    assert report["safety_invariants_hold"] is True
    for row in report["case_rows"]:
        assert row["safety_violations"] == []


# --- checks and metrics -----------------------------------------------------


def test_applicable_checks_ignore_irrelevant_expectations() -> None:
    assert applicable_checks("covered", "answered") == (
        "correct_outcome",
        "correct_sources",
        "no_over_clarification",
    )
    assert applicable_checks("uncovered", "abstained") == (
        "correct_outcome",
        "safe_abstention",
    )
    assert applicable_checks("mixed_land", "needs_land_clarification") == (
        "correct_outcome",
        "correct_clarification",
    )
    assert applicable_checks("unknown_attribute", "answered") == (
        "correct_outcome",
        "correct_sources",
        "no_over_clarification",
    )
    assert "correct_sources" not in applicable_checks("covered", "abstained")


def test_metrics_block_reports_the_measured_fixture_baseline() -> None:
    report = evaluate(
        load_fixture_cases(),
        current_corpus(),
        as_of_date(),
        5,
        corpus_source_ids=corpus_source_ids(),
    )

    assert report["metrics"] == {
        "covered_source_hit_rate": 1.0,
        "correct_abstention_rate": 1.0,
        "correct_clarification_rate": 1.0,
        "no_over_clarification_rate": 1.0,
        "expected_outcome_match_rate": 1.0,
    }
    assert report["metric_counts"]["covered_source_hit_rate"] == {"matched": 2, "total": 2}
    assert report["metric_counts"]["correct_abstention_rate"] == {"matched": 2, "total": 2}
    assert report["totals"]["expectation_mismatches"] == 0
    assert report["totals"]["clarifications"] == 1


def test_category_totals_bucket_every_case() -> None:
    report = evaluate(
        load_fixture_cases(),
        current_corpus(),
        as_of_date(),
        5,
        corpus_source_ids=corpus_source_ids(),
    )
    totals = report["category_totals"]

    assert totals["covered"] == {"cases": 2, "expectations_met": 2}
    assert totals["uncovered"] == {"cases": 1, "expectations_met": 1}
    assert totals["false_premise"] == {"cases": 1, "expectations_met": 1}
    assert totals["mixed_land"] == {"cases": 1, "expectations_met": 1}
    assert totals["unknown_attribute"] == {"cases": 1, "expectations_met": 1}


def test_metrics_are_none_without_cases() -> None:
    report = evaluate((), current_corpus(), as_of_date(), 5)

    assert report["metrics"]["expected_outcome_match_rate"] is None
    assert report["metrics"]["covered_source_hit_rate"] is None
    assert report["case_rows"] == []
    assert report["safety_invariants_hold"] is True


def test_critical_reviews_lists_the_provenance_for_audit() -> None:
    report = evaluate(
        load_fixture_cases(),
        current_corpus(),
        as_of_date(),
        5,
        corpus_source_ids=corpus_source_ids(),
    )
    reviews = report["critical_reviews"]

    assert len(reviews) == 1
    assert reviews[0]["id"] == "covered-plazo-01"
    assert reviews[0]["level"] == 1
    assert reviews[0]["anchor"].startswith("fixture_lse_junta#")
    assert reviews[0]["outcome"] == "answered"


def test_no_over_clarification_rate_counts_covered_and_unknown_attribute() -> None:
    no_over = make_case(
        "unknown-over-clarifies",
        category="unknown_attribute",
        question=RIEGO_QUESTION,
        expect="needs_land_clarification",
        expected_source_ids=(),
        expected_land_ids_to_choose=("land-A",),
        land_context={
            "mode": "all_active",
            "lands": [{"id": "land-A", "water_regime": "irrigated"},
                      {"id": "land-B", "water_regime": "dryland"}],
        },
    )
    report = evaluate((no_over,), current_corpus(), as_of_date(), 5)
    row = report["case_rows"][0]

    # It genuinely clarifies, which is a real over-clarification for the category.
    assert row["outcome"] == "needs_land_clarification"
    assert row["checks"]["no_over_clarification"] is False
    assert report["metrics"]["no_over_clarification_rate"] == 0.0


def test_evaluate_is_deterministic() -> None:
    first = evaluate(
        load_fixture_cases(), current_corpus(), as_of_date(), 5,
        corpus_source_ids=corpus_source_ids(),
    )
    second = evaluate(
        load_fixture_cases(), current_corpus(), as_of_date(), 5,
        corpus_source_ids=corpus_source_ids(),
    )

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_evaluating_never_opens_a_network_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid(*args, **kwargs):
        raise AssertionError("a network connection was attempted")

    monkeypatch.setattr(socket, "socket", _forbid)

    report = evaluate(
        load_fixture_cases(), current_corpus(), as_of_date(), 5,
        corpus_source_ids=corpus_source_ids(),
    )

    assert report["safety_invariants_hold"] is True


def test_the_module_imports_no_network_client() -> None:
    source = (BACKEND_ROOT / "app" / "land_safety_eval.py").read_text(encoding="utf-8")
    for forbidden in ("import socket", "import urllib", "import httpx", "import requests"):
        assert forbidden not in source


# --- CLI --------------------------------------------------------------------


def test_cli_reports_every_category_and_holds_the_invariants() -> None:
    result = baseline_cli()

    assert result.returncode == 0
    assert "corpus: current" in result.stdout
    assert "eligible sources: 2" in result.stdout
    assert "mixed-land-riego-01 [mixed_land]" in result.stdout
    assert "land ids to choose: land-A, land-B" in result.stdout
    assert "safety invariants hold: yes" in result.stdout
    assert "cases not meeting their expectation: 0" in result.stdout
    assert "covered-plazo-01" in result.stdout


def test_cli_json_report_is_machine_readable_and_report_only() -> None:
    result = baseline_cli("--json")

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["corpus_status"] == "current"
    assert report["fixtures_are_synthetic"] is True
    assert report["thresholds_are_release_gates"] is False
    assert report["safety_invariants_hold"] is True
    assert report["metrics"]["correct_abstention_rate"] == 1.0
    assert report["totals"]["clarifications"] == 1
    assert report["critical_reviews"][0]["id"] == "covered-plazo-01"


def test_cli_json_report_is_byte_identical_across_runs() -> None:
    first = baseline_cli("--json")
    second = baseline_cli("--json")

    assert first.returncode == 0
    assert first.stdout == second.stdout


def test_cli_never_prints_a_question_text() -> None:
    result = baseline_cli()

    assert "presenta la solicitud" not in result.stdout
    assert "matricular" not in result.stdout
    assert "999/2099" not in result.stdout
    assert "trámite de prueba" not in result.stdout


def test_cli_fail_on_miss_is_off_by_default_and_opt_in_is_exit_one() -> None:
    without = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--cases", str(edge("mismatch.json")),
        "--as-of", AS_OF, "--k", "5",
    )
    with_flag = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--cases", str(edge("mismatch.json")),
        "--as-of", AS_OF, "--k", "5", "--fail-on-miss",
    )

    assert without.returncode == 0
    assert with_flag.returncode == 1


def test_cli_fail_on_miss_exits_zero_on_the_whole_fixture_set() -> None:
    result = baseline_cli("--fail-on-miss")

    assert result.returncode == 0


@pytest.mark.parametrize(
    "name",
    [
        "critical_without_review.json",
        "unknown_category.json",
        "unknown_expect.json",
        "abstained_without_reason.json",
        "answered_without_sources.json",
        "clarification_without_land_ids.json",
        "duplicate_ids.json",
        "unknown_key.json",
        "unknown_reason.json",
        "malformed.json",
        "wrong_schema_version.json",
    ],
)
def test_cli_exits_two_for_an_invalid_case_set(name: str) -> None:
    result = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--cases", str(edge(name)),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr


def test_cli_stderr_never_echoes_case_text(tmp_path: Path) -> None:
    secret = "ZZQQPREGUNTASECRETA"
    document = case_document(
        minimal_case(id="zzqq-secret-id", question=secret, expect="abstained")
    )
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    result = run_cli(
        "--catalog", str(fixture("catalog.json")),
        "--passages", str(fixture("passages.json")),
        "--cases", str(path),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 2
    assert secret not in result.stderr
    assert "zzqq-secret-id" not in result.stderr


def test_cli_exits_two_for_a_missing_catalog() -> None:
    result = run_cli("--catalog", str(fixture("does-not-exist.json")), "--k", "5")

    assert result.returncode == 2
    assert result.stdout == ""


def test_cli_empty_catalog_reports_zero_candidates_and_no_metrics() -> None:
    result = run_cli(
        "--catalog", str(EMPTY_CATALOG),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 0
    assert "eligible sources: 0" in result.stdout
    assert "indexed passages: 0" in result.stdout
    assert "no evaluation cases supplied" in result.stdout
    assert "metrics: (none; no cases supplied)" in result.stdout


@pytest.mark.parametrize("flag,value", [("--k", "0"), ("--max-claims", "0")])
def test_cli_exits_two_for_a_non_positive_window(flag: str, value: str) -> None:
    result = run_cli(
        "--catalog", str(fixture("catalog.json")), flag, value,
    )

    assert result.returncode == 2


def test_cli_reports_a_stale_catalog_corpus_as_not_current() -> None:
    # A catalog whose sources are all ineligible is a corpus-level stale
    # abstention (exit 0), not a hard error: the accepted gate decides it.
    result = run_cli(
        "--catalog", str(REPO_ROOT / "backend" / "tests" / "fixtures" / "retrieval" / "catalog_expired.json"),
        "--passages", str(fixture("passages.json")),
        "--cases", str(fixture("cases.json")),
        "--as-of", AS_OF, "--k", "5",
    )

    assert result.returncode == 0
    assert "corpus: not_current" in result.stdout
    assert "abstained outcomes: 6" in result.stdout


def test_cli_exits_one_when_a_payload_invariant_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = load_cli_module()
    original = cli.evaluate

    def leaking(*args, **kwargs):
        report = original(*args, **kwargs)
        report["case_rows"][0]["safety_violations"] = ["abstention_has_sources"]
        report["safety_invariants_hold"] = False
        return report

    monkeypatch.setattr(cli, "evaluate", leaking)
    exit_code = cli.main(
        [
            "--catalog", str(fixture("catalog.json")),
            "--passages", str(fixture("passages.json")),
            "--cases", str(fixture("cases.json")),
            "--as-of", AS_OF, "--k", "5",
        ]
    )

    assert exit_code == 1


# --- fixture hygiene --------------------------------------------------------


def test_fixtures_are_labelled_synthetic() -> None:
    catalog = catalog_document()
    passages = passage_document()

    assert len(catalog["sources"]) == 2
    for source in catalog["sources"]:
        assert "fixture" in source["title"]
        assert "no es una norma real" in source["title"]
    for passage in passages["passages"]:
        assert "Sintético" in passage["text"] or "sintético" in passage["text"]


def test_fixture_passages_carry_a_differing_pair_and_a_critical_fact() -> None:
    passages = passage_document()["passages"]
    regimes = {
        passage["applicability"]["water_regime"]
        for passage in passages
        if passage.get("applicability", {}).get("water_regime")
    }
    critical = [passage for passage in passages if passage.get("critical")]

    assert regimes == {"irrigated", "dryland"}
    assert len(critical) == 1
    assert "42" in critical[0]["text"]


def test_fixture_cases_declare_only_documented_fields() -> None:
    for case in load_fixture_cases():
        assert case.category in CATEGORIES
        assert case.expect in EXPECTED_OUTCOMES
        assert case.land_context["mode"] in LAND_SCOPES
        if case.expect == "abstained":
            assert case.expect_reason in ABSTENTION_REASONS
        if case.expect == "answered":
            assert case.expected_source_ids
        if case.expect == "needs_land_clarification":
            assert case.expected_land_ids_to_choose


def test_fixture_cases_cover_every_category() -> None:
    categories = {case.category for case in load_fixture_cases()}

    assert categories == set(CATEGORIES)


def test_all_abstention_reasons_are_documented() -> None:
    assert "no_evidence" in ABSTENTION_REASONS
    assert "false_premise" in ABSTENTION_REASONS
    assert "no_evidence" in ABSTENTION_MESSAGES


def test_default_max_claims_matches_the_accepted_window() -> None:
    assert DEFAULT_MAX_CLAIMS == 2
    assert DEFAULT_K == 5
    assert CLARIFICATION_SCOPE == "selected"


def test_run_case_uses_the_request_land_ids_for_the_clarification_check() -> None:
    case = case_by_id("mixed-land-riego-01")
    result = run_case(case, current_corpus(), as_of_date(), 5)

    assert set(result.land_ids_to_choose) <= {"land-A", "land-B"}
    assert set(result.land_ids_to_choose) == set(case.expected_land_ids_to_choose)
