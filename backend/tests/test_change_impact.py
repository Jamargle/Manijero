import hashlib
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.change_impact import (
    ANALYZER,
    REPORT_VERSION,
    ImpactAnalysisError,
    analyze,
    exit_code,
    fold,
    instrument_keys,
    load_evaluation_cases,
    load_ingestion_state,
    own_instrument_key,
    write_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "change_impact"
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "analyze_legal_changes.py"
AS_OF = date(2099, 10, 27)

FIXTURE_STATE = json.loads((FIXTURES / "ingestion-state.json").read_text(encoding="utf-8"))
IDS = {
    record["stable_identity"]: candidate_id
    for candidate_id, record in FIXTURE_STATE["candidates"].items()
}
AMENDING_RD = IDS["BOE-A-2099-04444"]
REPEALING_DL = IDS["BOJA2099-00010-01"]
APPROVED_RES = IDS["BOJA2099-00050-02"]
FAILED_INGESTION = IDS["BOE-A-2099-09999"]
AMENDING_LEY = IDS["BOJA2099-00060-01"]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def copy_fixtures(tmp_path):
    target = tmp_path / "change_impact"
    shutil.copytree(FIXTURES, target)
    return target


def state_of(fixtures):
    return json.loads((fixtures / "ingestion-state.json").read_text(encoding="utf-8"))


def save_state(fixtures, state):
    (fixtures / "ingestion-state.json").write_text(canonical(state), encoding="utf-8")


def run(fixtures, cases=True, as_of=AS_OF):
    return analyze(
        fixtures / "ingestion-state.json",
        fixtures / "quarantine",
        fixtures / "catalog.json",
        fixtures / "passages.json",
        cases_path=(fixtures / "cases.json") if cases else None,
        as_of=as_of,
    )


def candidate(report, candidate_id):
    return next(item for item in report["candidates"] if item["candidate_id"] == candidate_id)


def report_text(report):
    return canonical(report)


def rewrite_document(fixtures, candidate_id, digest, blocks):
    """Replace one extracted document and keep its recorded digest consistent."""
    document = {
        "schema_version": "official-ingestion-document-v1",
        "candidate_id": candidate_id,
        "media_type": "html",
        "extractor": "manijero-document-extractor-v1",
        "title": None,
        "blocks": [
            {"kind": "text", "page": None, "section": section, "text": text}
            for section, text in blocks
        ],
    }
    payload = canonical(document).encode("utf-8")
    path = fixtures / "quarantine" / candidate_id / "extracted-{}.json".format(digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def set_extracted(fixtures, candidate_id, blocks, *, previous=None):
    """Rewrite a candidate's current extracted text and update its state record."""
    state = state_of(fixtures)
    record = state["candidates"][candidate_id]
    digest = rewrite_document(fixtures, candidate_id, record["original_sha256"], blocks)
    record["extracted_text_sha256"] = digest
    record["previous_original_sha256"] = previous
    save_state(fixtures, state)
    return record


def add_passage(fixtures, passage):
    document = json.loads((fixtures / "passages.json").read_text(encoding="utf-8"))
    document["passages"].append(passage)
    (fixtures / "passages.json").write_text(canonical(document), encoding="utf-8")


def link_case_to_passage(fixtures, case_id, passage_id):
    document = json.loads((fixtures / "cases.json").read_text(encoding="utf-8"))
    case = next(item for item in document["cases"] if item["id"] == case_id)
    case["expected_passage_ids"] = sorted(set(case.get("expected_passage_ids", [])) | {passage_id})
    (fixtures / "cases.json").write_text(canonical(document), encoding="utf-8")


# --- Normal operation -------------------------------------------------------


def test_fixture_report_analyzes_every_candidate_with_provenance(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    assert report["schema_version"] == REPORT_VERSION
    assert report["analyzer"] == ANALYZER
    assert report["as_of"] == "2099-10-27"
    assert report["inputs"]["catalog_sha256"] == hashlib.sha256(
        (fixtures / "catalog.json").read_bytes()
    ).hexdigest()
    assert report["inputs"]["evaluation_cases_sha256"] == hashlib.sha256(
        (fixtures / "cases.json").read_bytes()
    ).hexdigest()
    assert [item["candidate_id"] for item in report["candidates"]] == sorted(IDS.values())
    assert all(item["review_status"] == "pending" for item in report["candidates"])
    assert report["review_gate"] == {
        "canonical_changes_applied": False,
        "automatic_retirement": False,
        "requires_human_approval": True,
    }
    assert exit_code(report) == 1


def test_machine_evident_amendment_links_source_passage_and_case(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)
    amending = candidate(report, AMENDING_RD)

    assert amending["version_status"] == "new_version"
    assert amending["ingestion_status"] == "extracted"
    assert amending["review"]["required"] is True
    assert amending["review"]["reasons"] == ["new_version", "affected_source"]
    assert amending["review"]["automatic_retirement_allowed"] is False
    assert amending["analysis_failure"] is None

    amendments = [signal for signal in amending["signals"] if signal["kind"] == "amendment"]
    assert amendments
    assert all(signal["classification"] == "machine_evident" for signal in amendments)
    assert all(
        signal["reason"] == "explicit_action_on_named_instrument" for signal in amendments
    )
    assert any("real decreto 2077/2099" in signal["instrument_keys"] for signal in amendments)

    affected = amending["potentially_affected"]
    assert [source["id"] for source in affected["sources"]] == ["fixture-rd-2077-2099"]
    assert affected["sources"][0]["reasons"] == ["amendment_target"]
    assert affected["sources"][0]["instrument_keys"] == ["real decreto 2077/2099"]
    assert [passage["id"] for passage in affected["passages"]] == [
        "fixture-pasaje-rd-2077-plazo"
    ]
    assert affected["passages"][0]["reasons"] == ["source_affected"]
    assert [case["id"] for case in affected["evaluation_cases"]] == ["fixture-caso-plazo-rd"]
    assert affected["evaluation_cases"][0]["reasons"] == ["expected_passage", "expected_source"]


def test_text_diff_reports_the_changed_deadline_without_copying_whole_document(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)
    version = candidate(report, AMENDING_RD)["version"]

    assert version["baseline_text_available"] is True
    diff = version["text_diff"]
    assert diff["text_changed"] is True
    assert diff["blocks_added"] == 1
    assert diff["blocks_removed"] == 1
    assert diff["locations_changed"] == 1
    assert [item["change"] for item in diff["excerpts"]] == ["added", "removed"]
    assert "20 de mayo de 2099" in diff["excerpts"][0]["excerpt"]
    assert "15 de mayo de 2099" in diff["excerpts"][1]["excerpt"]
    assert all(len(item["excerpt"]) <= 280 for item in diff["excerpts"])

    introduced = {signal["kind"]: signal["introduced"] for signal in candidate(report, AMENDING_RD)["signals"]}
    assert introduced["amendment"] is False
    assert introduced["validity"] is False


def test_approved_copy_needs_no_review_and_emits_no_signal(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)
    approved = candidate(report, APPROVED_RES)

    assert approved["version_status"] == "approved_copy"
    assert approved["signals"] == []
    assert approved["potentially_affected"] == {
        "sources": [],
        "passages": [],
        "evaluation_cases": [],
    }
    assert approved["review"] == {
        "required": False,
        "reasons": [],
        "automatic_retirement_allowed": False,
    }


def test_failed_ingestion_candidate_is_reported_without_text_analysis(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)
    failed = candidate(report, FAILED_INGESTION)

    assert failed["version_status"] == "no_extracted_document"
    assert failed["ingestion_status"] == "failed"
    assert failed["signals"] == []
    # The report states why no text analysis exists instead of leaving it null;
    # recovering the missing text stays owned by the ingestion state.
    assert failed["analysis_failure"] == "no_extracted_document"
    assert failed["review"]["required"] is False
    assert report["summary"]["no_extracted_document"] == 1
    assert report["summary"]["analysis_failed"] == 0


def test_baseline_unknown_amendment_links_cross_referencing_passage(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)
    amending = candidate(report, AMENDING_LEY)

    assert amending["version_status"] == "baseline_unknown"
    assert amending["review"]["reasons"] == ["baseline_unknown", "affected_source"]
    assert amending["version"]["baseline_text_available"] is False
    assert amending["version"]["text_diff"] is None
    assert all(signal["introduced"] is None for signal in amending["signals"])

    affected = amending["potentially_affected"]
    assert [source["id"] for source in affected["sources"]] == ["fixture-ley-5-2098"]
    assert [(item["id"], item["reasons"]) for item in affected["passages"]] == [
        ("fixture-pasaje-dl-2-2099-plazo", ["cites_target_instrument"]),
        ("fixture-pasaje-ley-5-2098-art-3", ["source_affected"]),
    ]
    assert [case["id"] for case in affected["evaluation_cases"]] == ["fixture-caso-cambios-ley"]


def test_target_without_catalog_source_still_reviews_its_linked_passage(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [("Página 1", "Se modifica el Real Decreto 9999/2099, de 1 de enero.")],
    )
    add_passage(
        fixtures,
        {
            "id": "fixture-pasaje-9999",
            "source_id": "fixture-res-3-2099",
            "location": "Artículo 1",
            "text": "De conformidad con el Real Decreto 9999/2099, de 1 de enero.",
        },
    )

    result = candidate(run(fixtures), AMENDING_LEY)

    # No catalog source describes Real Decreto 9999/2099, so the approved-source
    # link is empty, but a reviewed passage cites the target instrument.
    assert result["version_status"] == "baseline_unknown"
    assert result["potentially_affected"]["sources"] == []
    assert result["potentially_affected"]["passages"] == [
        {"id": "fixture-pasaje-9999", "reasons": ["cites_target_instrument"]}
    ]
    assert result["review"]["required"] is True
    assert result["review"]["reasons"] == ["affected_passage"]
    assert result["review"]["automatic_retirement_allowed"] is False


def test_target_without_catalog_source_still_reviews_its_linked_case(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [("Página 1", "Se modifica el Real Decreto 9999/2099, de 1 de enero.")],
    )
    add_passage(
        fixtures,
        {
            "id": "fixture-pasaje-9999",
            "source_id": "fixture-res-3-2099",
            "location": "Artículo 1",
            "text": "De conformidad con el Real Decreto 9999/2099, de 1 de enero.",
        },
    )
    link_case_to_passage(fixtures, "fixture-caso-canal-res", "fixture-pasaje-9999")

    result = candidate(run(fixtures), AMENDING_LEY)

    assert result["potentially_affected"]["sources"] == []
    assert result["potentially_affected"]["evaluation_cases"] == [
        {"id": "fixture-caso-canal-res", "reasons": ["expected_passage"]}
    ]
    assert result["review"]["required"] is True
    assert result["review"]["reasons"] == ["affected_passage"]


def test_realistic_unnumbered_title_still_links_the_amended_instrument(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    state = state_of(fixtures)
    title = (
        "Resolución de 9 de septiembre de 2099, de la Dirección General competente, "
        "por la que se modifica la Ley 5/2098, de 1 de diciembre (documento sintético)"
    )
    state["candidates"][AMENDING_LEY]["title"] = title
    save_state(fixtures, state)

    result = candidate(run(fixtures), AMENDING_LEY)

    # The title starts with an unnumbered act, so the Ley it amends is a target,
    # not the candidate's own identity.
    assert own_instrument_key(title) is None
    assert [source["id"] for source in result["potentially_affected"]["sources"]] == [
        "fixture-ley-5-2098"
    ]
    assert result["potentially_affected"]["sources"][0]["reasons"] == ["amendment_target"]
    assert result["potentially_affected"]["sources"][0]["instrument_keys"] == ["ley 5/2098"]
    assert result["review"]["reasons"] == ["baseline_unknown", "affected_source"]


def test_summary_counts_the_fixture_corpus(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    assert report["summary"] == {
        "candidates": 5,
        "no_extracted_document": 1,
        "approved_copy": 1,
        "unchanged_since_ingestion": 0,
        "new_version": 2,
        "baseline_unknown": 1,
        "analysis_failed": 0,
        "review_required": 3,
        "machine_evident_signals": 7,
        "ambiguous_signals": 1,
        "affected_sources": 3,
        "affected_passages": 3,
        "affected_evaluation_cases": 2,
    }


def test_cases_are_optional(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures, cases=False)

    assert report["inputs"]["evaluation_cases_sha256"] is None
    assert report["summary"]["affected_evaluation_cases"] == 0
    assert all(
        item["potentially_affected"]["evaluation_cases"] == []
        for item in report["candidates"]
    )
    assert report["summary"]["affected_sources"] == 3


def test_report_validates_against_the_published_schema(tmp_path):
    from jsonschema import Draft202012Validator

    fixtures = copy_fixtures(tmp_path)
    schema = json.loads(
        (ROOT / "knowledge" / "legal-change-impact.schema.json").read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(run(fixtures))


def test_evaluation_cases_fixture_satisfies_the_authoritative_contract():
    from app.answer_eval import load_cases
    from app.retrieval import load_passage_set
    from app.source_catalog import load_catalog

    catalog = load_catalog(FIXTURES / "catalog.json")
    passages = load_passage_set(FIXTURES / "passages.json")

    assert len(load_cases(FIXTURES / "cases.json", catalog, passages)) == 4


# --- Invalid, unavailable, or ambiguous input -------------------------------


def test_ambiguous_repeal_requires_review_and_never_retires(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)
    repealing = candidate(report, REPEALING_DL)

    assert repealing["version_status"] == "new_version"
    repeals = [signal for signal in repealing["signals"] if signal["kind"] == "repeal"]
    assert [signal["classification"] for signal in repeals] == ["ambiguous"]
    assert [signal["reason"] for signal in repeals] == ["no_named_instrument"]
    assert repealing["review"]["required"] is True
    assert "ambiguous_signal" in repealing["review"]["reasons"]
    assert repealing["review"]["automatic_retirement_allowed"] is False
    assert report["review_gate"]["automatic_retirement"] is False
    assert all(
        item["review"]["automatic_retirement_allowed"] is False
        for item in report["candidates"]
    )
    # A potentially affected source is still surfaced for the reviewer.
    assert [source["id"] for source in repealing["potentially_affected"]["sources"]] == [
        "fixture-dl-2-2099"
    ]
    assert repealing["potentially_affected"]["sources"][0]["reasons"] == [
        "candidate_version_differs_from_approved"
    ]


def test_unlinked_ambiguous_repeal_forces_review(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [
            (
                "Página 1",
                "Se deroga la normativa vigente que se oponga a lo dispuesto en la "
                "presente resolución.",
            )
        ],
    )

    result = candidate(run(fixtures), AMENDING_LEY)

    assert result["version_status"] == "baseline_unknown"
    assert result["potentially_affected"]["sources"] == []
    assert [signal["reason"] for signal in result["signals"] if signal["kind"] == "repeal"] == [
        "no_named_instrument"
    ]
    # A blanket repeal that names no instrument still cannot pass as "nothing to
    # review": it fails closed into review.
    assert result["review"]["required"] is True
    assert result["review"]["reasons"] == ["ambiguous_signal"]
    assert result["review"]["automatic_retirement_allowed"] is False


def test_unlinked_ambiguous_validity_forces_review(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [("Página 1", "La presente resolución prorroga la vigencia del procedimiento.")],
    )

    result = candidate(run(fixtures), AMENDING_LEY)

    validity = next(signal for signal in result["signals"] if signal["kind"] == "validity")
    assert validity["classification"] == "ambiguous"
    assert validity["reason"] == "no_explicit_date"
    assert result["potentially_affected"]["sources"] == []
    assert result["review"]["required"] is True
    assert result["review"]["reasons"] == ["ambiguous_signal"]


def test_negated_and_uncertain_wording_is_ambiguous(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        APPROVED_RES,
        [
            ("Documento", "Resolución sintética de prueba."),
            ("Resuelve", "El presente acto no se modifica por la disposición adicional."),
            ("Resuelve", "No queda derogada la Ley 5/2098, de 1 de diciembre."),
        ],
    )

    report = run(fixtures)
    result = candidate(report, APPROVED_RES)
    signals = [signal for signal in result["signals"] if signal["kind"] in ("amendment", "repeal")]

    assert {signal["reason"] for signal in signals} == {"negated_signal"}
    assert {signal["classification"] for signal in signals} == {"ambiguous"}
    # A negated sentence never targets an instrument, but its ambiguous wording is
    # still a review item: negation is not a licence to drop the sentence.
    assert result["potentially_affected"]["sources"] == []
    assert result["review"] == {
        "required": True,
        "reasons": ["ambiguous_signal"],
        "automatic_retirement_allowed": False,
    }

    fixtures = copy_fixtures(tmp_path / "uncertain")
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [("Página 1", "Se modifica el art\u00edculo 3 de la Ley 5/2098\ufffd, de 1 de diciembre.")],
    )
    result = candidate(run(fixtures), AMENDING_LEY)
    amendment = next(signal for signal in result["signals"] if signal["kind"] == "amendment")
    assert amendment["classification"] == "ambiguous"
    assert amendment["reason"] == "extraction_uncertainty"


@pytest.mark.parametrize(
    "sentence,kind",
    [
        ("No se deja sin efecto la Ley 5/2098, de 1 de diciembre.", "repeal"),
        ("No pierde su vigencia la Ley 5/2098, de 1 de diciembre.", "repeal"),
        (
            "No se publica en el BOE núm. 5, de 1 de enero de 2100.",
            "publication",
        ),
        ("Sin que se modifique la Ley 5/2098, de 1 de diciembre.", "amendment"),
        ("En ningún caso se modifica la Ley 5/2098, de 1 de diciembre.", "amendment"),
        ("Tampoco se deroga la Ley 5/2098, de 1 de diciembre.", "repeal"),
        ("Nunca se modifica la Ley 5/2098, de 1 de diciembre.", "amendment"),
    ],
)
def test_negated_wording_is_ambiguous_and_requires_review(tmp_path, sentence, kind):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(fixtures, AMENDING_LEY, [("Página 1", sentence)])

    result = candidate(run(fixtures), AMENDING_LEY)
    signals = [signal for signal in result["signals"] if signal["kind"] == kind]

    assert signals
    assert {signal["classification"] for signal in signals} == {"ambiguous"}
    assert {signal["reason"] for signal in signals} == {"negated_signal"}
    # Negation is never read as an action on an instrument, but it is also not
    # silently dropped: the sentence still needs an author.
    assert result["potentially_affected"] == {
        "sources": [],
        "passages": [],
        "evaluation_cases": [],
    }
    assert result["review"]["required"] is True
    assert result["review"]["reasons"] == ["ambiguous_signal"]


@pytest.mark.parametrize(
    "sentence,kind",
    [
        ("Disposición derogatoria única.", "repeal"),
        (
            "Disposición adicional primera. Modificaciones presupuestarias.",
            "amendment",
        ),
        (
            "La modificación de las condiciones de acceso se aprueba por resolución.",
            "amendment",
        ),
        (
            "La prórroga del convenio se aprueba por la Dirección General.",
            "validity",
        ),
    ],
)
def test_static_document_wording_produces_an_ambiguous_review_signal(
    tmp_path, sentence, kind
):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(fixtures, AMENDING_LEY, [("Página 1", sentence)])

    result = candidate(run(fixtures), AMENDING_LEY)
    signals = [signal for signal in result["signals"] if signal["kind"] == kind]

    # The lexical stems are deliberately broad: a document-part heading or a noun
    # phrase is not a change action, so it is reported as ambiguous (and therefore
    # review-required) rather than silently treated as a change.
    assert signals
    assert {signal["classification"] for signal in signals} == {"ambiguous"}
    assert result["potentially_affected"]["sources"] == []
    assert result["review"]["required"] is True
    assert "ambiguous_signal" in result["review"]["reasons"]


def test_validity_needs_an_explicit_calendar_date(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [
            ("Página 1", "Se modifica el artículo 3 de la Ley 5/2098, de 1 de diciembre."),
            ("Página 2", "Esta resolución entrará en vigor el día siguiente al de su publicación."),
        ],
    )

    result = candidate(run(fixtures), AMENDING_LEY)
    validity = next(signal for signal in result["signals"] if signal["kind"] == "validity")
    assert validity["classification"] == "ambiguous"
    assert validity["reason"] == "no_explicit_date"

    fixtures = copy_fixtures(tmp_path / "dated")
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [
            ("Página 1", "Se modifica el artículo 3 de la Ley 5/2098, de 1 de diciembre."),
            ("Página 2", "Esta resolución entrará en vigor el 1 de enero de 2100."),
        ],
    )

    result = candidate(run(fixtures), AMENDING_LEY)
    validity = next(signal for signal in result["signals"] if signal["kind"] == "validity")
    assert validity["classification"] == "machine_evident"
    assert validity["reason"] == "explicit_date"


def test_static_deadline_is_not_a_validity_signal(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [
            ("Página 1", "Se modifica el artículo 3 de la Ley 5/2098, de 1 de diciembre."),
            ("Página 2", "El plazo de presentación de la solicitud se mantiene hasta el 20 de mayo de 2099."),
            ("Página 3", "La vigencia del procedimiento alcanza hasta el 31 de diciembre de 2099."),
        ],
    )

    result = candidate(run(fixtures), AMENDING_LEY)

    # A static deadline statement is not evidence that a deadline changed.
    assert [signal for signal in result["signals"] if signal["kind"] == "validity"] == []

    fixtures = copy_fixtures(tmp_path / "changed-deadline")
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [("Página 1", "El plazo de presentación de la solicitud se extiende hasta el 20 de mayo de 2099.")],
    )

    validity = next(
        signal for signal in candidate(run(fixtures), AMENDING_LEY)["signals"] if signal["kind"] == "validity"
    )
    assert validity["classification"] == "machine_evident"
    assert validity["reason"] == "explicit_date"


def test_publication_signal_needs_a_bulletin_reference(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [("Página 1", "Documento publicado en el Boletín Oficial del Estado.")],
    )
    result = candidate(run(fixtures), AMENDING_LEY)
    publication = next(signal for signal in result["signals"] if signal["kind"] == "publication")
    assert publication["classification"] == "ambiguous"
    assert publication["reason"] == "incomplete_publication_reference"

    fixtures = copy_fixtures(tmp_path / "numbered")
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [
            (
                "Página 1",
                "Publicado en el Boletín Oficial del Estado núm. 236, de 1 de octubre de 2099.",
            )
        ],
    )
    result = candidate(run(fixtures), AMENDING_LEY)
    publication = next(signal for signal in result["signals"] if signal["kind"] == "publication")
    assert publication["classification"] == "machine_evident"
    assert publication["reason"] == "explicit_publication_reference"


def test_disposicion_adicional_alone_is_not_an_amendment(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [
            ("Página 1", "La disposición adicional primera regula el procedimiento de acreditación."),
            ("Página 2", "Se añade una disposición adicional a la Ley 5/2098, de 1 de diciembre."),
        ],
    )

    result = candidate(run(fixtures), AMENDING_LEY)

    amendments = [signal for signal in result["signals"] if signal["kind"] == "amendment"]
    # "disposición adicional" is a document part, not an amendment action; only
    # the explicit action phrase counts.
    assert [signal["excerpt"] for signal in amendments] == [
        "Se añade una disposición adicional a la Ley 5/2098, de 1 de diciembre."
    ]
    assert amendments[0]["classification"] == "machine_evident"
    assert amendments[0]["reason"] == "explicit_action_on_named_instrument"


def test_conflicting_amendment_and_repeal_of_one_instrument_needs_review(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [
            ("Página 1", "Se modifica el artículo 3 de la Ley 5/2098, de 1 de diciembre."),
            ("Página 1", "Se deroga el artículo 4 de la Ley 5/2098, de 1 de diciembre."),
        ],
    )

    result = candidate(run(fixtures), AMENDING_LEY)

    assert "conflicting_signals" in result["review"]["reasons"]
    assert {signal["kind"] for signal in result["signals"]} >= {"amendment", "repeal"}


def test_changed_text_without_signal_is_flagged(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    previous_key = hashlib.sha256(b"previous-original").hexdigest()
    rewrite_document(
        fixtures, AMENDING_LEY, previous_key, [("Página 1", "Texto sintético anterior.")]
    )
    set_extracted(
        fixtures,
        AMENDING_LEY,
        [("Página 1", "Otro texto sintético distinto.")],
        previous=previous_key,
    )

    result = candidate(run(fixtures), AMENDING_LEY)

    assert result["version_status"] == "new_version"
    assert result["version"]["baseline_text_available"] is True
    assert result["version"]["text_diff"]["text_changed"] is True
    assert result["signals"] == []
    assert "text_changed_without_signal" in result["review"]["reasons"]


def test_missing_previous_text_is_reported_as_an_incomplete_comparison(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    state = state_of(fixtures)
    previous_key = hashlib.sha256(b"unavailable-previous").hexdigest()
    state["candidates"][AMENDING_LEY]["previous_original_sha256"] = previous_key
    save_state(fixtures, state)

    result = candidate(run(fixtures), AMENDING_LEY)

    assert result["version_status"] == "new_version"
    assert result["version"]["previous_original_sha256"] == previous_key
    assert result["version"]["baseline_text_available"] is False
    assert result["version"]["text_diff"] is None
    assert "previous_text_unavailable" in result["review"]["reasons"]


def test_unchanged_version_since_ingestion_has_no_diff(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    state = state_of(fixtures)
    record = state["candidates"][AMENDING_LEY]
    record["previous_original_sha256"] = record["original_sha256"]
    save_state(fixtures, state)

    result = candidate(run(fixtures), AMENDING_LEY)

    assert result["version_status"] == "unchanged_since_ingestion"
    assert result["version"]["text_diff"] is None


def test_corrupted_extracted_digest_fails_only_that_candidate(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    state = state_of(fixtures)
    state["candidates"][AMENDING_RD]["extracted_text_sha256"] = hashlib.sha256(
        b"different"
    ).hexdigest()
    save_state(fixtures, state)

    report = run(fixtures)
    broken = candidate(report, AMENDING_RD)

    assert broken["version_status"] == "analysis_failed"
    assert broken["analysis_failure"] == "extracted_text_mismatch"
    assert broken["review"]["required"] is True
    assert broken["review"]["reasons"] == ["analysis_failed"]
    assert broken["signals"] == []
    assert broken["potentially_affected"] == {
        "sources": [],
        "passages": [],
        "evaluation_cases": [],
    }
    assert report["summary"]["analysis_failed"] == 1
    assert exit_code(report) == 1
    # Every other candidate is still analyzed.
    assert candidate(report, AMENDING_LEY)["version_status"] == "baseline_unknown"


def test_missing_and_malformed_extracted_documents_are_fixed_categories(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    state = state_of(fixtures)
    record = state["candidates"][AMENDING_RD]
    (fixtures / "quarantine" / record["extracted_path"]).unlink()
    save_state(fixtures, state)

    report = run(fixtures)
    assert candidate(report, AMENDING_RD)["analysis_failure"] == "missing_extracted_document"

    fixtures = copy_fixtures(tmp_path / "malformed")
    state = state_of(fixtures)
    record = state["candidates"][AMENDING_RD]
    path = fixtures / "quarantine" / record["extracted_path"]
    path.write_text("{not json", encoding="utf-8")
    record["extracted_text_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    save_state(fixtures, state)

    report = run(fixtures)
    assert candidate(report, AMENDING_RD)["analysis_failure"] == "malformed_extracted_document"


def test_unsafe_report_path_writes_nothing(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    report = run(fixtures)

    with pytest.raises(ImpactAnalysisError) as raised:
        write_report(report, ROOT / "knowledge" / "impact-report.json")

    assert raised.value.failure == "unsafe_workspace"
    assert not (ROOT / "knowledge" / "impact-report.json").exists()


def test_global_input_failures_fail_closed(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    (fixtures / "ingestion-state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ImpactAnalysisError) as raised:
        run(fixtures)
    assert raised.value.failure == "invalid_ingestion_state"

    fixtures = copy_fixtures(tmp_path / "bad-state")
    state = state_of(fixtures)
    state["schema_version"] = "official-ingestion-state-v2"
    save_state(fixtures, state)
    with pytest.raises(ImpactAnalysisError) as raised:
        run(fixtures)
    assert raised.value.failure == "invalid_ingestion_state"

    fixtures = copy_fixtures(tmp_path / "bad-catalog")
    catalog = json.loads((fixtures / "catalog.json").read_text(encoding="utf-8"))
    catalog["sources"][0]["review_status"] = "pending"
    (fixtures / "catalog.json").write_text(canonical(catalog), encoding="utf-8")
    with pytest.raises(ImpactAnalysisError) as raised:
        run(fixtures)
    assert raised.value.failure == "invalid_catalog"

    fixtures = copy_fixtures(tmp_path / "bad-passages")
    passages = json.loads((fixtures / "passages.json").read_text(encoding="utf-8"))
    passages["passages"][0]["source_id"] = "fixture-unknown-source"
    (fixtures / "passages.json").write_text(canonical(passages), encoding="utf-8")
    with pytest.raises(ImpactAnalysisError) as raised:
        run(fixtures)
    assert raised.value.failure == "invalid_passage_set"

    fixtures = copy_fixtures(tmp_path / "bad-cases")
    cases = json.loads((fixtures / "cases.json").read_text(encoding="utf-8"))
    cases["cases"][0]["expected_passage_ids"] = ["fixture-unknown-passage"]
    (fixtures / "cases.json").write_text(canonical(cases), encoding="utf-8")
    with pytest.raises(ImpactAnalysisError) as raised:
        run(fixtures)
    assert raised.value.failure == "invalid_evaluation_cases"


def test_candidate_count_is_bounded(tmp_path, monkeypatch):
    fixtures = copy_fixtures(tmp_path)
    monkeypatch.setattr("app.change_impact.MAX_CANDIDATES", 2)

    with pytest.raises(ImpactAnalysisError) as raised:
        run(fixtures)

    assert raised.value.failure == "candidate_count_exceeded"


def test_signal_count_is_bounded(tmp_path, monkeypatch):
    fixtures = copy_fixtures(tmp_path)
    monkeypatch.setattr("app.change_impact.MAX_SIGNALS_PER_CANDIDATE", 0)

    report = run(fixtures)

    assert candidate(report, AMENDING_RD)["analysis_failure"] == "size_limit_exceeded"


def test_as_of_is_required_and_rejects_invalid_values(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    with pytest.raises(ImpactAnalysisError) as raised:
        analyze(
            fixtures / "ingestion-state.json",
            fixtures / "quarantine",
            fixtures / "catalog.json",
            fixtures / "passages.json",
            cases_path=fixtures / "cases.json",
            as_of=None,
        )

    assert raised.value.failure == "invalid_as_of"


def test_loader_rejects_non_pending_and_malformed_records(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    state = state_of(fixtures)
    state["candidates"][AMENDING_RD]["review_status"] = "approved"
    save_state(fixtures, state)

    with pytest.raises(ImpactAnalysisError):
        load_ingestion_state(fixtures / "ingestion-state.json")

    fixtures = copy_fixtures(tmp_path / "bad-digest")
    state = state_of(fixtures)
    state["candidates"][AMENDING_RD]["original_sha256"] = "not-a-digest"
    save_state(fixtures, state)

    with pytest.raises(ImpactAnalysisError):
        load_ingestion_state(fixtures / "ingestion-state.json")

    fixtures = copy_fixtures(tmp_path / "bad-cases")
    cases = json.loads((fixtures / "cases.json").read_text(encoding="utf-8"))
    cases["cases"][1]["id"] = cases["cases"][0]["id"]
    (fixtures / "cases.json").write_text(canonical(cases), encoding="utf-8")

    with pytest.raises(ImpactAnalysisError):
        load_evaluation_cases(
            fixtures / "cases.json",
            json.loads((fixtures / "catalog.json").read_text(encoding="utf-8")),
            json.loads((fixtures / "passages.json").read_text(encoding="utf-8")),
        )


def digest_tree(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(Path(root).rglob("*"))
        if path.is_file()
    }


def test_analysis_never_changes_canonical_knowledge(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    knowledge_root = ROOT / "knowledge"
    knowledge_before = digest_tree(knowledge_root)
    inputs_before = digest_tree(fixtures)

    run(fixtures)
    write_report(run(fixtures), tmp_path / "report.json")

    # Neither the canonical knowledge directory nor any input artifact (catalog,
    # passages, cases, ingestion state, quarantine text) is written.
    assert digest_tree(knowledge_root) == knowledge_before
    assert digest_tree(fixtures) == inputs_before


# --- Reproducibility and review --------------------------------------------


def test_repeated_analysis_is_byte_identical(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    first = report_text(run(fixtures))
    second = report_text(run(fixtures))

    assert first == second
    report = json.loads(first)
    assert "generated_at" not in report
    assert "analyzed_at" not in report
    # Only the pinned as_of date is present, never wall-clock time.
    assert report["as_of"] == AS_OF.isoformat()


def test_repeated_runs_write_identical_report_files(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    first_path = tmp_path / "reports" / "first.json"
    second_path = tmp_path / "reports" / "second.json"

    write_report(run(fixtures), first_path)
    write_report(run(fixtures), second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_path.read_text(encoding="utf-8").endswith("\n")


def test_review_required_is_true_exactly_when_a_reason_exists(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    for item in report["candidates"]:
        assert item["review"]["required"] is bool(item["review"]["reasons"])


def test_report_omits_land_data_and_attempt_history(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    text = report_text(run(fixtures))

    assert "attempts" not in text
    assert "land_context" not in text
    assert "question" not in text


# --- Lexical helpers --------------------------------------------------------


def test_instrument_keys_fold_accents_and_titles():
    assert instrument_keys("Real Decreto 1048/2022, de 27 de diciembre") == (
        "real decreto 1048/2022",
    )
    assert instrument_keys("Decreto-ley 1/2026 y la Ley Orgánica 3/2018") == (
        "decreto-ley 1/2026",
        "ley organica 3/2018",
    )
    assert instrument_keys("Orden HAC/1234/2022") == ("orden 1234/2022",)
    assert instrument_keys("Sin referencias normativas") == ()
    assert fold("  Modificación ÚNICA  ") == "modificacion unica"


def test_own_instrument_key_needs_a_leading_numbered_instrument():
    assert (
        own_instrument_key(
            "Real Decreto 2200/2099, de 1 de octubre, por el que se modifica el "
            "Real Decreto 2077/2099, de 1 de enero"
        )
        == "real decreto 2200/2099"
    )
    assert own_instrument_key("Decreto-ley 2/2099, de 1 de febrero") == "decreto-ley 2/2099"
    assert own_instrument_key("Ley 5/2098, de 1 de diciembre") == "ley 5/2098"
    # An unnumbered (or merely citing) title has no own identity.
    assert (
        own_instrument_key(
            "Resolución de 9 de septiembre de 2099, por la que se modifica la "
            "Ley 5/2098, de 1 de diciembre"
        )
        is None
    )
    assert own_instrument_key("por la que se modifica la Ley 5/2098") is None
    assert own_instrument_key("Documento sintético sin texto extraíble") is None


def test_extract_without_cases_keeps_schema_valid(tmp_path):
    from jsonschema import Draft202012Validator

    fixtures = copy_fixtures(tmp_path)
    schema = json.loads(
        (ROOT / "knowledge" / "legal-change-impact.schema.json").read_text(encoding="utf-8")
    )

    Draft202012Validator(schema).validate(run(fixtures, cases=False))


# --- Operator CLI -----------------------------------------------------------


def cli(fixtures, report_path, extra=()):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ingestion-state",
            str(fixtures / "ingestion-state.json"),
            "--quarantine",
            str(fixtures / "quarantine"),
            "--catalog",
            str(fixtures / "catalog.json"),
            "--passages",
            str(fixtures / "passages.json"),
            "--cases",
            str(fixtures / "cases.json"),
            "--as-of",
            AS_OF.isoformat(),
            "--report",
            str(report_path),
            *extra,
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_cli_writes_the_report_and_exits_one_when_review_is_needed(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    report_path = tmp_path / "var" / "impact-report.json"

    completed = cli(fixtures, report_path)

    assert completed.returncode == 1
    assert completed.stderr == ""
    summary = json.loads(completed.stdout)
    assert summary["analyzer"] == ANALYZER
    assert summary["review_required"] == sorted([AMENDING_RD, REPEALING_DL, AMENDING_LEY])
    assert json.loads(report_path.read_text(encoding="utf-8"))["schema_version"] == REPORT_VERSION


def test_cli_exits_zero_when_nothing_needs_review(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    state = state_of(fixtures)
    state["candidates"] = {
        candidate_id: record
        for candidate_id, record in state["candidates"].items()
        if candidate_id in (APPROVED_RES, FAILED_INGESTION)
    }
    save_state(fixtures, state)
    report_path = tmp_path / "impact-report.json"

    completed = cli(fixtures, report_path)

    assert completed.returncode == 0
    assert json.loads(report_path.read_text(encoding="utf-8"))["summary"]["review_required"] == 0


def test_cli_rejects_invalid_input_without_writing_a_report(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    (fixtures / "passages.json").write_text("{not json", encoding="utf-8")
    report_path = tmp_path / "impact-report.json"

    completed = cli(fixtures, report_path)

    assert completed.returncode == 2
    assert json.loads(completed.stderr) == {"error": "invalid_passage_set"}
    assert not report_path.exists()
    assert str(tmp_path) not in completed.stderr


def test_cli_rejects_an_invalid_as_of_date(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    report_path = tmp_path / "impact-report.json"

    completed = cli(fixtures, report_path, extra=("--as-of", "27/10/2099"))

    assert completed.returncode == 2
    assert json.loads(completed.stderr) == {"error": "invalid_as_of"}
    assert not report_path.exists()
