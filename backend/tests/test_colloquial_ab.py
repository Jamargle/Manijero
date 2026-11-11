"""Unit tests for the colloquial A/B comparison: variants, arms, rule, and report.

The repository ``knowledge/`` files are read only to prove the committed variant set and the
freeze/derive rules. Every other test builds small documents in a temporary folder. No test
opens a socket, calls Ollama, or touches a live service.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterator, List, Mapping, Sequence

import pytest

from app import colloquial_ab as ab
from app import golden_set
from app.answer_eval import load_case_document
from app.question_glossary import QuestionGlossary
from app.retrieval import load_passage_set, tokenize
from app.source_catalog import load_catalog

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
KNOWLEDGE = ROOT / "knowledge"
VARIANTS = BACKEND / "config" / "colloquial_variants.json"


# --- real inputs ----------------------------------------------------------------------------


def _real() -> tuple[Any, Any, List[dict], dict, dict, str]:
    catalog = load_catalog(KNOWLEDGE / "source_catalog.json")
    passages = load_passage_set(KNOWLEDGE / "passages.json")
    cases, coverage = load_case_document(KNOWLEDGE / "pac_answer_eval.json", catalog, passages)
    golden = golden_set.load_golden(KNOWLEDGE / "golden_set.json", catalog, passages, cases, coverage)
    digest = hashlib.sha256((KNOWLEDGE / "golden_set.json").read_bytes()).hexdigest()
    return catalog, passages, cases, coverage, golden, digest


def _variant(vid: str, parent: str, question: str, terms, state="approved") -> dict:
    return {
        "id": vid,
        "parent_id": parent,
        "question": question,
        "colloquial_terms": list(terms),
        "drafted": {"by": "tests", "on": "2026-11-01"},
        "review_state": state,
        "decision": (
            None
            if state == "draft"
            else {
                "decision": state,
                "reviewed_by": "Reviewer",
                "reviewed_on": "2026-11-01",
            }
        ),
    }


# --- the committed set ---------------------------------------------------------------------


def test_committed_variants_pass_all_checks_and_cover_every_approved_parent() -> None:
    catalog, passages, cases, coverage, golden, digest = _real()
    document = ab.read_variants(VARIANTS)

    assert ab.check_variants(document, golden, cases, digest, coverage["omissions"]) == []
    assert len(document["variants"]) == 49
    # The owner approved every variant on 2026-11-11; the committed set is the approved one.
    assert ab.state_counts(document) == {"draft": 0, "approved": 49, "rejected": 0}
    approved_parents = {
        item["id"] for item in golden["items"] if item["review_state"] == "approved"
    }
    assert {entry["parent_id"] for entry in document["variants"]} == approved_parents


def test_missing_variant_duplicate_parent_and_bad_question_are_named_by_id() -> None:
    catalog, passages, cases, coverage, golden, digest = _real()
    baseline = ab.read_variants(VARIANTS)
    omissions = coverage["omissions"]

    dropped = json.loads(json.dumps(baseline))
    dropped["variants"].pop()
    lines = ab.check_variants(dropped, golden, cases, digest, omissions)
    assert "coll-049: missing" in lines
    assert any(line.startswith("$: orphan approved parents: golden-049") for line in lines)

    shared = json.loads(json.dumps(baseline))
    shared["variants"][0]["parent_id"] = shared["variants"][1]["parent_id"]
    lines = ab.check_variants(shared, golden, cases, digest, omissions)
    assert "coll-002: parent_id used twice" in lines

    same = json.loads(json.dumps(baseline))
    parent = next(
        item for item in golden["items"] if item["id"] == same["variants"][0]["parent_id"]
    )
    same["variants"][0]["question"] = parent["question"]
    lines = ab.check_variants(same, golden, cases, digest, omissions)
    assert "coll-001: question_same_as_parent" in lines

    broken = json.loads(json.dumps(baseline))
    broken["variants"][0]["question"] = 7
    lines = ab.check_variants(broken, golden, cases, digest, omissions)
    assert "coll-001: question_shape" in lines


def test_rejected_variant_keeps_structure_but_is_exempt_from_content_rules() -> None:
    catalog, passages, cases, coverage, golden, digest = _real()
    document = ab.read_variants(VARIANTS)
    omissions = coverage["omissions"]
    rejected = json.loads(json.dumps(document))
    entry = rejected["variants"][0]
    entry["review_state"] = "rejected"
    entry["decision"] = {
        "decision": "rejected",
        "reviewed_by": "Reviewer",
        "reviewed_on": "2026-11-01",
    }
    entry["colloquial_terms"] = ["palabra que no está"]

    assert ab.check_variants(rejected, golden, cases, digest, omissions) == []

    rejected["variants"][0]["parent_id"] = "golden-999"
    lines = ab.check_variants(rejected, golden, cases, digest, omissions)
    assert "coll-001: parent_id is not a golden item" in lines


# --- one variant against its parent --------------------------------------------------------


def _codes(question: str, terms: Sequence[str], *, parent: str = "¿Cómo presento la solicitud única?",
           duplicates: Sequence[str] = (), omissions: Sequence[str] = ()) -> List[str]:
    variant = {"question": question, "colloquial_terms": list(terms)}
    parent_item = {"question": parent, "expected_status": "answered"}
    return ab.variant_failures(
        variant, parent_item, duplicate_ids=duplicates, omissions=omissions
    )


def test_variant_failures_length_digit_guardrail_scope_terms_duplicate() -> None:
    assert _codes("x" * 201, ["x"]) == ["question_length"]
    long_but_ok = "¿Cómo mando los papeles de la solicitud este año?"
    assert "question_multiline" in _codes(long_but_ok + "\notra", ["mando"])
    assert "question_screened" in _codes(
        "¿Dónde está mi receta de cocina para la cena?", ["receta"]
    )
    assert "question_url" in _codes(
        "¿Cómo mando los papeles? mira en https://example.com", ["mando"]
    )
    assert "question_digit" in _codes(
        "¿Cómo mando los papeles para 2019?", ["mando"]
    )
    assert "question_out_of_scope" in _codes(
        "¿Cuánto me van a pagar por la ayuda?", ["pagar"]
    )
    assert "question_duplicate" in _codes(
        "¿Cómo mando los papeles?", ["mando"], duplicates=["coll-002"]
    )

    assert "term_missing" in _codes("¿Cómo mando los papeles?", ["receta"])
    assert "term_in_parent" in _codes("¿Cómo mando la solicitud?", ["solicitud"])
    assert "term_duplicate" in _codes("¿Cómo mando los papeles?", ["papeles", "papeles"])
    assert "terms_count" in _codes("¿Cómo mando los papeles?", [])
    assert "terms_count" in _codes("¿Cómo mando los papeles?", ["a", "b", "c", "d", "e"])


def test_abstained_variant_must_keep_the_declared_omission() -> None:
    basis = "elegibilidad individual"
    parent = {
        "question": "¿Cumplo los requisitos de la ayuda?",
        "expected_status": "abstained",
        "deliberate_abstention": {"basis": basis},
    }
    variant = {"question": "¿Qué día presento la solicitud?", "colloquial_terms": ["día"]}

    assert "question_omission" in ab.variant_failures(
        variant, parent, omissions=[basis]
    )
    right = {"question": "¿Tengo derecho a la ayuda?", "colloquial_terms": ["tengo derecho"]}
    assert ab.variant_failures(right, parent, omissions=[basis]) == []


# --- approval only --------------------------------------------------------------------------


def _frozen_golden() -> tuple[dict, dict, str]:
    parent = {
        "id": "golden-001",
        "question": "¿Cómo presento la solicitud única?",
        "area": "canal-presentacion",
        "question_type": "procedure",
        "segment": "transversal",
        "land_context": {"mode": "all_active", "lands": []},
        "expected_status": "answered",
        "expected_source_ids": ["src-1"],
        "expected_passage_ids": ["pas-1"],
        "critical_facts": ["SGA"],
        "review_state": "approved",
        "decision": {"decision": "approved", "reviewed_by": "Diego", "reviewed_on": "2026-11-01"},
    }
    golden = {"items": [parent]}
    digest = "a" * 64
    return golden, parent, digest


def test_approved_cases_derive_the_parent_and_never_read_a_draft() -> None:
    golden, parent, digest = _frozen_golden()
    document = {
        "schema_version": ab.VARIANTS_VERSION,
        "golden_sha256": digest,
        "variants": [
            _variant("coll-001", "golden-001", "¿Cómo mando los papeles?", ["mando"]),
            _variant(
                "coll-002",
                "golden-001",
                "POISON pregunta que nunca debe leerse",
                ["poison"],
                state="draft",
            ),
        ],
    }

    cases = ab.approved_cases(document, golden, [], digest)

    assert [case["id"] for case in cases] == ["coll-001"]
    assert cases[0]["question"] == "¿Cómo mando los papeles?"
    assert cases[0]["expected_status"] == parent["expected_status"]
    assert cases[0]["expected_passage_ids"] == parent["expected_passage_ids"]
    assert cases[0]["land_context"] == parent["land_context"]
    assert cases[0]["parent_id"] == "golden-001"
    assert cases[0]["case_set"] == ab.CASE_SET_COLLOQUIAL
    assert "POISON" not in json.dumps(cases, ensure_ascii=False)


def test_decide_is_atomic_repeatable_and_bad_input_records_nothing(tmp_path: Path) -> None:
    golden, _parent, digest = _frozen_golden()
    document = {
        "schema_version": ab.VARIANTS_VERSION,
        "golden_sha256": digest,
        "variants": [
            _variant("coll-001", "golden-001", "¿Cómo mando los papeles?", ["mando"], state="draft")
        ],
    }
    path = tmp_path / "variants.json"
    path.write_text(ab.dump_variants(document), encoding="utf-8")

    recorded, waiting = ab.decide(
        path, "approve", "Diego", ["1"], date(2026, 11, 10), golden, [], digest
    )
    assert (recorded, waiting) == (1, 0)
    approved = ab.read_variants(path)["variants"][0]
    assert approved["review_state"] == "approved"
    assert approved["decision"] == {
        "decision": "approved",
        "reviewed_by": "Diego",
        "reviewed_on": "2026-11-10",
    }

    before = path.read_bytes()
    with pytest.raises(ab.DecisionError) as caught:
        ab.decide(path, "approve", "Diego", ["999"], date(2026, 11, 10), golden, [], digest)
    assert caught.value.kind == "unknown"
    assert path.read_bytes() == before

    recorded, waiting = ab.decide(
        path, "reject", "Diego", ["coll-001"], date(2026, 11, 11), golden, [], digest
    )
    assert (recorded, waiting) == (1, 0)
    assert ab.read_variants(path)["variants"][0]["review_state"] == "rejected"


def test_decide_refuses_a_variant_that_fails_the_rules(tmp_path: Path) -> None:
    golden, _parent, digest = _frozen_golden()
    document = {
        "schema_version": ab.VARIANTS_VERSION,
        "golden_sha256": digest,
        "variants": [
            _variant("coll-001", "golden-001", "¿Cómo mando los papeles?", ["receta"], state="draft")
        ],
    }
    path = tmp_path / "variants.json"
    path.write_text(ab.dump_variants(document), encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ab.DecisionError) as caught:
        ab.decide(path, "approve", "Diego", ["1"], date(2026, 11, 10), golden, [], digest)
    assert caught.value.kind == "entry"
    assert path.read_bytes() == before


# --- arms ---------------------------------------------------------------------------------


def test_arm_a_is_none_arm_b_glossary_arm_c_appends_and_dedupes() -> None:
    glossary = QuestionGlossary([("los papeles", "documentación de la solicitud")])
    question = "¿Dónde mando los papeles?"
    terms = {question: ["solicitud única", "los papeles", "solicitud única"]}

    expanded = ab.GlossaryPlusModel(glossary, terms).expand(question)

    assert expanded.startswith(question)
    assert expanded.count("solicitud única") == 1
    assert "documentación de la solicitud" in expanded
    assert expanded.count("los papeles") == 1


def test_parse_model_terms_accepts_only_safe_new_official_words() -> None:
    question = "¿Cómo mando los papeles?"
    expanded = "¿Cómo mando los papeles? documentación de la solicitud"

    accepted, status = ab.parse_model_terms(
        '{"terms": ["solicitud única", "2026", "https://x.es", "receta", "los papeles"]}',
        question=question,
        expanded=expanded,
    )
    assert accepted == ["solicitud única"]
    assert status == ab.MODEL_REWRITTEN

    assert ab.parse_model_terms("", question=question, expanded=expanded) == ([], ab.MODEL_EMPTY)
    assert ab.parse_model_terms("not json", question=question, expanded=expanded) == (
        [],
        ab.MODEL_REJECTED,
    )
    assert ab.parse_model_terms('{"terms": ["2026"]}', question=question, expanded=expanded) == (
        [],
        ab.MODEL_REJECTED,
    )
    assert ab.parse_model_terms('{"terms": []}', question=question, expanded=expanded) == (
        [],
        ab.MODEL_EMPTY,
    )


def test_three_arms_differ_only_in_the_query_expansion() -> None:
    seen: List[dict] = []
    glossary = QuestionGlossary([("los papeles", "documentación de la solicitud")])

    def build(settings: Mapping[str, Any]):
        @contextlib.contextmanager
        def opened() -> Iterator[Any]:
            seen.append(dict(settings))
            yield object()

        return opened()

    def fake_evaluate(cases, client, catalog, passages, k, *, row_extra=None):
        return {"case_rows": []}

    ab.run_arms(
        [],
        {"sources": []},
        {"passages": []},
        as_of=date(2026, 11, 10),
        campaign="2026",
        glossary=glossary,
        model_terms_by_question={},
        model_terms_by_id={},
        model_status_by_id={},
        pairs=[],
        application_factory=build,
        evaluator=fake_evaluate,
    )

    assert [block["expansion"].__class__.__name__ for block in seen] == [
        "NoneType",
        "QuestionGlossary",
        "GlossaryPlusModel",
    ]
    base = {key: value for key, value in seen[0].items() if key not in ("mode", "expansion")}
    for block in seen[1:]:
        assert {key: value for key, value in block.items() if key not in ("mode", "expansion")} == base
        assert block["k"] == 5
        assert block["answer_cache"] is None
        assert block["retention_store"] is None
        assert block["answer_inspection"] is True


# --- rule and report ----------------------------------------------------------------------


def _row(**overrides: Any) -> dict:
    row = {
        "id": "x",
        "case_set": ab.CASE_SET_COLLOQUIAL,
        "expected_status": "answered",
        "expected_state_match": True,
        "abstention_reason_match": None,
        "must_not_say_hits": 0,
        "first_expected_rank": 1,
    }
    row.update(overrides)
    return row


def test_trap_worse_definitions_and_fixed_denominator_hit_at_5() -> None:
    assert ab.trap_worse(_row(case_set=ab.CASE_SET_TRAP), _row(case_set=ab.CASE_SET_TRAP, expected_state_match=False))
    assert ab.trap_worse(
        _row(case_set=ab.CASE_SET_TRAP, abstention_reason_match=True),
        _row(case_set=ab.CASE_SET_TRAP, abstention_reason_match=False),
    )
    assert ab.trap_worse(
        _row(case_set=ab.CASE_SET_TRAP), _row(case_set=ab.CASE_SET_TRAP, must_not_say_hits=1)
    )
    assert not ab.trap_worse(_row(), _row())

    rows = [
        _row(first_expected_rank=1),
        _row(first_expected_rank=5),
        _row(first_expected_rank=6),
        _row(first_expected_rank=None),
        _row(expected_status="abstained", first_expected_rank=None),
        _row(case_set=ab.CASE_SET_TRAP, first_expected_rank=1),
    ]
    assert ab.hit_at_5(rows) == (2, 4)

    baseline = [_row(id="trap-1", case_set=ab.CASE_SET_TRAP)]
    candidate = [_row(id="trap-1", case_set=ab.CASE_SET_TRAP, expected_state_match=False)]
    assert ab.trap_regressions(baseline, candidate) == ["trap-1"]


def test_adoption_improve_no_improve_trap_worse_incomplete_no_effect() -> None:
    counts = {"approved": 3, "draft": 0, "rejected": 0}
    assert ab.adoption(
        variant_counts=counts, baseline_hits=1, candidate_hits=2,
        changed_queries=2, regressions=0,
    )["adoptable"] is True
    assert ab.adoption(
        variant_counts=counts, baseline_hits=2, candidate_hits=2,
        changed_queries=2, regressions=0,
    )["reason"] == "no_gain"
    assert ab.adoption(
        variant_counts=counts, baseline_hits=1, candidate_hits=2,
        changed_queries=2, regressions=1,
    )["reason"] == "trap_worse"
    assert ab.adoption(
        variant_counts=counts, baseline_hits=1, candidate_hits=2,
        changed_queries=0, regressions=0,
    )["reason"] == "no_effect"
    incomplete = ab.adoption(
        variant_counts={"approved": 2, "draft": 1, "rejected": 0},
        baseline_hits=1, candidate_hits=2, changed_queries=2, regressions=0,
    )
    assert incomplete["adoptable"] is None
    assert incomplete["label"] == "not assessable (review incomplete)"


def _minimal_report() -> dict:
    _, _, _, _, _, digest = _real()
    version = ab.version_block(
        catalog=KNOWLEDGE / "source_catalog.json",
        passages=KNOWLEDGE / "passages.json",
        cases=KNOWLEDGE / "pac_answer_eval.json",
        golden=KNOWLEDGE / "golden_set.json",
        traps=KNOWLEDGE / "trap_set.json",
        variants=VARIANTS,
        glossary="glossary-digest",
        model="model-tag",
        model_digest="f" * 64,
        as_of="2026-11-10",
        active_campaign="2026",
        label="repository",
        schema_versions={"report": ab.SCHEMA_VERSION},
    )
    report = ab.build_report(
        version=version,
        report_id=ab.version_id(version),
        variants={"approved": 1, "draft": 0, "rejected": 0},
        arms={
            "no_rewriting": {"hit_at_5": {"hits": 1, "of": 1, "value": 1.0}},
            "glossary": {"hit_at_5": {"hits": 1, "of": 1, "value": 1.0}},
            "glossary_plus_model": {"hit_at_5": {"hits": 1, "of": 1, "value": 1.0}},
        },
        adoption_block={"arms": {}},
        rewrites={"rewritten": 1, "empty": 0, "rejected": 0, "skipped_screened": 0},
        rows=[{"id": "coll-001", "case_set": "colloquial", "mode": "no_rewriting"}],
    )
    assert digest
    return report


def test_report_is_deterministic_version_keyed_and_has_no_text_rows(tmp_path: Path) -> None:
    report = _minimal_report()

    assert report["report_only"] is True
    assert report["defaults_changed"] is False
    assert len(report["version_id"]) == 16
    assert report["version"]["variants_sha256"] == hashlib.sha256(VARIANTS.read_bytes()).hexdigest()
    assert report["version"]["model"] == "model-tag"
    assert report["version"]["model_digest"] == "f" * 64
    assert "question" not in report["cases"][0]
    assert "¿" not in json.dumps(report, ensure_ascii=False)

    first = tmp_path / "a" / "report.json"
    second = tmp_path / "b" / "report.json"
    ab.write_document_atomically(report, first)
    ab.write_document_atomically(report, second)
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8"))["version_id"] == ab.version_id(
        report["version"]
    )


def test_output_root_inside_knowledge_is_refused_and_abort_lines_are_fixed() -> None:
    with pytest.raises(ab.ColloquialAbort) as caught:
        ab.check_output_root(KNOWLEDGE / "reports", [])
    assert caught.value.code == "unsafe_output_path"
    with pytest.raises(ab.ColloquialAbort) as caught:
        ab.check_output_root(KNOWLEDGE / "golden_set.json", [KNOWLEDGE / "golden_set.json"])
    assert caught.value.code == "unsafe_output_path"

    line = ab.abort_line("ask_failed")
    assert line.startswith("Result: the colloquial comparison did not run (ask_failed):")
    assert line.endswith("Nothing was written.")


def test_variant_term_helpers_reject_multiline_digits_urls_and_screened_text() -> None:
    variant = "¿Cómo mando los papeles para 2026? mira https://x.es y llama al 600123456"
    parent = "¿Cómo presento la solicitud?"
    codes = ab.variant_term_failures(
        "2026", variant=variant, parent=parent
    )
    assert "term_digit" in codes
    assert "term_screened" in ab.variant_term_failures(
        "receta de cocina", variant="¿Dónde está mi receta de cocina?", parent=parent
    )
    assert "term_url" in ab.variant_term_failures(
        "https://x.es", variant=variant, parent=parent
    )
    assert tokenize("no tokens here") == ("no", "tokens", "here")
