"""Focused tests for the review-only source-validity checker.

The fixtures under ``fixtures/source_validity/`` are synthetic catalog metadata,
passages, and an accepted impact report. They exercise the checker; they are not
a review of a real document and must never be read as one.
"""

import copy
import hashlib
import json
import shutil
import socket
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import source_validity  # noqa: E402  (path setup must run first)
from app.source_validity import (  # noqa: E402
    CHECKER,
    MAX_CANDIDATES,
    REPORT_VERSION,
    SourceValidityError,
    check_validity,
    structural_as_of,
    write_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "source_validity"
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "check_source_validity.py"
AS_OF = date(2099, 6, 1)
AS_OF_TEXT = AS_OF.isoformat()

FIXTURE_IMPACT = json.loads((FIXTURES / "impact-report.json").read_text(encoding="utf-8"))
CANDIDATE_IDS = {
    candidate["stable_identity"]: candidate["candidate_id"]
    for candidate in FIXTURE_IMPACT["candidates"]
}
REPEAL = CANDIDATE_IDS["BOE-A-2099-00901"]
AMBIGUOUS = CANDIDATE_IDS["BOE-A-2099-00902"]
NEGATED = CANDIDATE_IDS["BOE-A-2099-00903"]
VALIDITY = CANDIDATE_IDS["BOE-A-2099-00905"]
LINKED_PUBLICATION = CANDIDATE_IDS["BOE-A-2099-00906"]
UNLINKED_PUBLICATION = CANDIDATE_IDS["BOE-A-2099-00907"]
APPROVED_COPY = CANDIDATE_IDS["BOE-A-2099-00908"]
AMENDMENT = CANDIDATE_IDS["BOE-A-2099-00909"]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _forbid(*_args, **_kwargs):
        raise AssertionError("network access is forbidden in source-validity tests")

    monkeypatch.setattr(socket, "socket", _forbid)
    monkeypatch.setattr(socket, "create_connection", _forbid)


# --- Helpers ---------------------------------------------------------------


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_tree(root):
    root = Path(root)
    return {
        str(path.relative_to(root)): digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def copy_fixtures(base):
    target = Path(base) / "source_validity"
    shutil.copytree(FIXTURES, target)
    return target


def load(fixtures, name):
    return json.loads((Path(fixtures) / name).read_text(encoding="utf-8"))


def save(fixtures, name, document):
    (Path(fixtures) / name).write_text(canonical(document), encoding="utf-8")


def bind(fixtures, impact=None):
    """Keep the accepted report's input digests bound to the fixture bytes."""
    document = impact if impact is not None else load(fixtures, "impact-report.json")
    document["inputs"]["catalog_sha256"] = digest(Path(fixtures) / "catalog.json")
    document["inputs"]["passages_sha256"] = digest(Path(fixtures) / "passages.json")
    save(fixtures, "impact-report.json", document)
    return document


def save_catalog(fixtures, document):
    save(fixtures, "catalog.json", document)
    bind(fixtures)


def save_passages(fixtures, document):
    save(fixtures, "passages.json", document)
    bind(fixtures)


def run(fixtures, as_of=AS_OF):
    return check_validity(
        Path(fixtures) / "catalog.json",
        Path(fixtures) / "passages.json",
        Path(fixtures) / "impact-report.json",
        as_of,
    )


def proposals_of(report, kind=None):
    return [
        proposal
        for proposal in report["proposals"]
        if kind is None or proposal["kind"] == kind
    ]


def proposal_for(report, kind, target_id):
    return next(
        proposal
        for proposal in report["proposals"]
        if proposal["kind"] == kind and proposal["target"]["id"] == target_id
    )


def maybe_proposal(report, kind, target_id):
    return next(
        (
            proposal
            for proposal in report["proposals"]
            if proposal["kind"] == kind and proposal["target"]["id"] == target_id
        ),
        None,
    )


def source_of(report, source_id):
    return next(source for source in report["sources"] if source["id"] == source_id)


def cli(fixtures, report_path, as_of=AS_OF_TEXT):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--catalog",
            str(Path(fixtures) / "catalog.json"),
            "--passages",
            str(Path(fixtures) / "passages.json"),
            "--impact-report",
            str(Path(fixtures) / "impact-report.json"),
            "--as-of",
            as_of,
            "--report",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def clean_fixtures(tmp_path, candidates=()):
    """A catalog with only in-force, already-published sources and a chosen report."""
    fixtures = copy_fixtures(tmp_path)
    catalog = load(fixtures, "catalog.json")
    keep = {"fixture-active-source", "fixture-unknown-source"}
    catalog["sources"] = [source for source in catalog["sources"] if source["id"] in keep]
    save(fixtures, "catalog.json", catalog)
    passages = load(fixtures, "passages.json")
    passages["passages"] = [
        passage for passage in passages["passages"] if passage["source_id"] in keep
    ]
    save(fixtures, "passages.json", passages)
    impact = load(fixtures, "impact-report.json")
    impact["candidates"] = list(candidates)
    bind(fixtures, impact)
    return fixtures


def fixture_candidate(identity):
    return copy.deepcopy(
        next(
            candidate
            for candidate in FIXTURE_IMPACT["candidates"]
            if candidate["stable_identity"] == identity
        )
    )


def abort_line(failure):
    return "Result: the validity check did not run: {}. Nothing was written.\n".format(failure)


def assert_aborts(fixtures, report_path, failure):
    with pytest.raises(SourceValidityError) as raised:
        run(fixtures)
    assert raised.value.failure == failure

    completed = cli(fixtures, report_path)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == abort_line(failure)
    assert not Path(report_path).exists()
    assert str(report_path) not in completed.stderr


# --- Reviewed per-source facts ---------------------------------------------


def test_expired_source_becomes_a_review_required_retirement(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    impact = load(fixtures, "impact-report.json")
    impact["candidates"] = []
    bind(fixtures, impact)

    report = run(fixtures)

    assert source_of(report, "fixture-expired-source")["expiry"] == {
        "state": "expired",
        "valid_until": "2099-05-01",
    }
    assert source_of(report, "fixture-active-source")["expiry"] == {
        "state": "in_force",
        "valid_until": "2099-12-31",
    }
    retirement = proposal_for(report, "retirement", "fixture-expired-source")
    assert retirement["reasons"] == ["expired_valid_until"]
    assert retirement["passage_ids"] == [
        "fixture-expired-deadline",
        "fixture-expired-scope",
    ]
    assert retirement["review"] == {"required": True, "applied": False}
    assert [proposal["target"]["id"] for proposal in proposals_of(report, "retirement")] == [
        "fixture-expired-source"
    ]


def test_valid_until_equal_to_as_of_stays_in_force(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    catalog = load(fixtures, "catalog.json")
    for source in catalog["sources"]:
        if source["id"] == "fixture-expired-source":
            source["valid_until"] = AS_OF_TEXT
    save_catalog(fixtures, catalog)
    impact = load(fixtures, "impact-report.json")
    impact["candidates"] = []
    bind(fixtures, impact)

    report = run(fixtures)

    assert source_of(report, "fixture-expired-source")["expiry"] == {
        "state": "in_force",
        "valid_until": AS_OF_TEXT,
    }
    assert proposals_of(report, "retirement") == []


def test_structural_as_of_uses_the_earliest_valid_until():
    catalog = {
        "sources": [
            {"valid_until": "2099-01-01"},
            {"valid_until": "2099-12-31"},
        ]
    }

    assert structural_as_of(catalog, AS_OF) == date(2099, 1, 1)
    assert structural_as_of({"sources": [{}]}, AS_OF) == AS_OF
    assert structural_as_of({"sources": [{"valid_until": "not-a-date"}]}, AS_OF) == AS_OF


def test_missing_valid_until_and_consolidated_url_stay_unknown(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    unknown = source_of(report, "fixture-unknown-source")
    assert unknown["expiry"] == {"state": "unknown", "valid_until": None}
    assert unknown["consolidation"] == {"state": "unknown"}
    assert unknown["lifecycle_status"] == "current"
    assert source_of(report, "fixture-consolidated-source")["consolidation"] == {
        "state": "official_consolidated_text_linked"
    }


def test_future_publication_date_is_review_required(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    future = source_of(report, "fixture-future-source")
    assert future["publication"] == {"state": "future", "published_on": "2099-07-01"}
    review = proposal_for(report, "review", "fixture-future-source")
    assert review["reasons"] == ["future_publication_date"]
    assert review["target"] == {"type": "source", "id": "fixture-future-source"}
    assert review["review"] == {"required": True, "applied": False}


# --- Signal-to-proposal mapping --------------------------------------------


def test_machine_evident_repeal_retires_only_the_linked_source(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    repeal_retirements = [
        proposal
        for proposal in proposals_of(report, "retirement")
        if "machine_evident_repeal" in proposal["reasons"]
    ]
    assert [proposal["target"]["id"] for proposal in repeal_retirements] == [
        "fixture-repeal-target"
    ]
    assert repeal_retirements[0]["reasons"] == ["machine_evident_repeal"]
    assert repeal_retirements[0]["passage_ids"] == ["fixture-repeal-target-scope"]
    assert maybe_proposal(report, "retirement", "fixture-active-source") is None


def test_repeal_without_matching_instrument_is_review_not_retirement(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    impact = load(fixtures, "impact-report.json")
    candidate = next(item for item in impact["candidates"] if item["candidate_id"] == REPEAL)
    candidate["potentially_affected"]["sources"][0]["instrument_keys"] = [
        "real decreto 999/2099"
    ]
    bind(fixtures, impact)

    report = run(fixtures)

    assert maybe_proposal(report, "retirement", "fixture-repeal-target") is None
    review = proposal_for(report, "review", REPEAL)
    assert review["reasons"] == ["unmatched_repeal_target"]


def test_ambiguous_and_negated_signals_never_retire(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    impact = load(fixtures, "impact-report.json")
    candidate = next(item for item in impact["candidates"] if item["candidate_id"] == AMBIGUOUS)
    candidate["potentially_affected"]["sources"] = [
        {
            "id": "fixture-active-source",
            "reasons": ["repeal_target"],
            "instrument_keys": ["real decreto 102/2099"],
        }
    ]
    bind(fixtures, impact)

    report = run(fixtures)

    assert maybe_proposal(report, "retirement", "fixture-active-source") is None
    ambiguous = proposal_for(report, "review", AMBIGUOUS)
    assert ambiguous["reasons"] == ["ambiguous_signal"]
    assert ambiguous["source_ids"] == ["fixture-active-source"]
    negated = proposal_for(report, "review", NEGATED)
    assert negated["reasons"] == ["ambiguous_signal", "negated_signal"]
    assert [
        proposal["kind"]
        for proposal in report["proposals"]
        if proposal["target"]["id"] == AMBIGUOUS
    ] == ["review"]


def test_machine_evident_validity_signal_does_not_change_expiry(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    review = proposal_for(report, "review", VALIDITY)
    assert review["reasons"] == ["validity_signal"]
    assert source_of(report, "fixture-active-source")["expiry"] == {
        "state": "in_force",
        "valid_until": "2099-12-31",
    }
    assert maybe_proposal(report, "retirement", "fixture-active-source") is None


def test_machine_evident_amendment_is_not_consumed(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    assert all(
        proposal["target"]["id"] != AMENDMENT for proposal in report["proposals"]
    )


def test_publication_signal_proposes_addition_only_for_an_unlinked_candidate(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    additions = proposals_of(report, "addition")
    assert [proposal["target"]["id"] for proposal in additions] == [UNLINKED_PUBLICATION]
    addition = proposal_for(report, "addition", UNLINKED_PUBLICATION)
    assert addition["review"] == {"required": True, "applied": False}
    assert maybe_proposal(report, "review", UNLINKED_PUBLICATION) is None
    assert maybe_proposal(report, "addition", APPROVED_COPY) is None


def test_linked_publication_signal_is_review_not_addition(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    review = proposal_for(report, "review", LINKED_PUBLICATION)
    assert review["reasons"] == ["linked_publication"]
    assert review["source_ids"] == ["fixture-consolidated-source"]
    assert maybe_proposal(report, "addition", LINKED_PUBLICATION) is None


def test_retirement_lists_every_affected_passage(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    assert proposal_for(report, "retirement", "fixture-expired-source")["passage_ids"] == [
        "fixture-expired-deadline",
        "fixture-expired-scope",
    ]
    assert proposal_for(report, "retirement", "fixture-repeal-target")["passage_ids"] == [
        "fixture-repeal-target-scope"
    ]


# --- Artifact, safety, and failures ----------------------------------------


def test_report_is_written_outside_knowledge_and_canonical_bytes_are_unchanged(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    knowledge_before = digest_tree(ROOT / "knowledge")
    inputs_before = digest_tree(fixtures)
    report = run(fixtures)
    report_path = tmp_path / "var" / "validity-review.json"

    write_report(
        report,
        report_path,
        input_paths=(
            fixtures / "catalog.json",
            fixtures / "passages.json",
            fixtures / "impact-report.json",
        ),
    )

    assert report_path.exists()
    assert report["schema_version"] == REPORT_VERSION
    assert report["checker"] == CHECKER
    assert digest_tree(ROOT / "knowledge") == knowledge_before
    assert digest_tree(fixtures) == inputs_before
    text = report_path.read_text(encoding="utf-8")
    for forbidden in ("excerpt", "question", "land_context", "generated_at", "timestamp"):
        assert forbidden not in text
    assert report["review_gate"] == {
        "canonical_changes_applied": False,
        "automatic_retirement": False,
        "requires_human_approval": True,
    }


def test_report_path_equal_to_an_input_is_refused(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    report = run(fixtures)
    catalog_before = (fixtures / "catalog.json").read_bytes()

    with pytest.raises(SourceValidityError) as raised:
        write_report(
            report,
            fixtures / "catalog.json",
            input_paths=(
                fixtures / "catalog.json",
                fixtures / "passages.json",
                fixtures / "impact-report.json",
            ),
        )

    assert raised.value.failure == "unsafe_report_path"
    assert (fixtures / "catalog.json").read_bytes() == catalog_before

    completed = cli(fixtures, fixtures / "catalog.json")

    assert completed.returncode == 2
    assert completed.stderr == abort_line("unsafe_report_path")
    assert (fixtures / "catalog.json").read_bytes() == catalog_before


def test_report_path_inside_knowledge_is_refused(tmp_path, monkeypatch):
    fixtures = copy_fixtures(tmp_path)
    knowledge_root = tmp_path / "knowledge"
    knowledge_root.mkdir()
    monkeypatch.setattr(source_validity, "KNOWLEDGE_ROOT", knowledge_root)
    report = run(fixtures)

    with pytest.raises(SourceValidityError) as raised:
        write_report(report, knowledge_root / "validity-review.json")

    assert raised.value.failure == "unsafe_report_path"
    assert not (knowledge_root / "validity-review.json").exists()


def test_invalid_inputs_and_digest_mismatch_write_nothing(tmp_path):
    bad_catalog = copy_fixtures(tmp_path / "bad-catalog")
    catalog = load(bad_catalog, "catalog.json")
    catalog["sources"][0]["original_url"] = "https://evil.example/document"
    save_catalog(bad_catalog, catalog)
    assert_aborts(bad_catalog, tmp_path / "bad-catalog.json", "invalid_catalog")

    bad_passages = copy_fixtures(tmp_path / "bad-passages")
    passages = load(bad_passages, "passages.json")
    passages["passages"].append(
        {
            "id": "fixture-orphan-passage",
            "source_id": "fixture-missing-source",
            "location": "Artículo 1",
            "text": "Pasaje sin fuente en el catálogo.",
        }
    )
    save_passages(bad_passages, passages)
    assert_aborts(bad_passages, tmp_path / "bad-passages.json", "invalid_passage_set")

    bad_report = copy_fixtures(tmp_path / "bad-report")
    (bad_report / "impact-report.json").write_text("{not json", encoding="utf-8")
    assert_aborts(bad_report, tmp_path / "bad-report.json", "invalid_impact_report")

    bad_shape = copy_fixtures(tmp_path / "bad-shape")
    impact = load(bad_shape, "impact-report.json")
    impact["candidates"][0].pop("signals")
    save(bad_shape, "impact-report.json", impact)
    assert_aborts(bad_shape, tmp_path / "bad-shape.json", "invalid_impact_report")

    mismatch = copy_fixtures(tmp_path / "mismatch")
    impact = load(mismatch, "impact-report.json")
    impact["inputs"]["catalog_sha256"] = "0" * 64
    save(mismatch, "impact-report.json", impact)
    assert_aborts(mismatch, tmp_path / "mismatch.json", "impact_inputs_mismatch")


def test_oversized_report_aborts_before_writing(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    impact = load(fixtures, "impact-report.json")
    template = impact["candidates"][0]
    candidates = []
    for index in range(MAX_CANDIDATES + 1):
        candidate = copy.deepcopy(template)
        candidate["candidate_id"] = hashlib.sha256(
            "candidate-{}".format(index).encode()
        ).hexdigest()
        candidate["stable_identity"] = "BOE-A-2099-{:05d}".format(20000 + index)
        candidate["signals"] = []
        candidate["potentially_affected"] = {
            "sources": [],
            "passages": [],
            "evaluation_cases": [],
        }
        candidates.append(candidate)
    impact["candidates"] = candidates
    bind(fixtures, impact)
    report_path = tmp_path / "oversized.json"

    assert_aborts(fixtures, report_path, "candidate_count_exceeded")


def test_proposal_count_is_bounded(tmp_path, monkeypatch):
    fixtures = copy_fixtures(tmp_path)
    monkeypatch.setattr(source_validity, "MAX_PROPOSALS", 1)

    with pytest.raises(SourceValidityError) as raised:
        run(fixtures)

    assert raised.value.failure == "proposal_count_exceeded"


def test_module_rejects_datetime_and_missing_as_of(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    with pytest.raises(SourceValidityError) as raised:
        run(fixtures, datetime(2099, 6, 1))
    assert raised.value.failure == "invalid_as_of"

    with pytest.raises(SourceValidityError) as raised:
        run(fixtures, None)
    assert raised.value.failure == "invalid_as_of"


def test_structural_validation_still_rejects_policy_errors(tmp_path):
    def bad_host(catalog):
        catalog["sources"][1]["original_url"] = "https://evil.example/document"

    def bad_date_order(catalog):
        catalog["sources"][1]["published_on"] = "2099-04-01"
        catalog["sources"][1]["downloaded_on"] = "2099-03-01"

    def impossible_date(catalog):
        catalog["sources"][1]["valid_until"] = "2099-02-30"

    for name, mutate in (
        ("host", bad_host),
        ("date-order", bad_date_order),
        ("impossible-date", impossible_date),
    ):
        fixtures = copy_fixtures(tmp_path / name)
        catalog = load(fixtures, "catalog.json")
        mutate(catalog)
        save_catalog(fixtures, catalog)
        with pytest.raises(SourceValidityError) as raised:
            run(fixtures)
        assert raised.value.failure == "invalid_catalog"


# --- Determinism, schema, and operator CLI ---------------------------------


def test_report_is_byte_identical_for_the_same_inputs_and_as_of(tmp_path):
    fixtures = copy_fixtures(tmp_path)
    first_path = tmp_path / "reports" / "first.json"
    second_path = tmp_path / "reports" / "second.json"

    write_report(run(fixtures), first_path)
    write_report(run(fixtures), second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(first_path.read_text(encoding="utf-8"))["as_of"] == AS_OF_TEXT


def test_report_has_no_wall_clock_or_excerpt_and_matches_schema(tmp_path):
    from jsonschema import Draft202012Validator

    fixtures = copy_fixtures(tmp_path)
    report = run(fixtures)
    schema = json.loads(
        (ROOT / "knowledge" / "validity-review.schema.json").read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(report)

    text = canonical(report)
    for forbidden in ("excerpt", "generated_at", "timestamp", "question", "land_context"):
        assert forbidden not in text
    assert report["as_of"] == AS_OF_TEXT
    assert set(report) == {
        "schema_version",
        "checker",
        "as_of",
        "inputs",
        "sources",
        "proposals",
        "summary",
        "review_gate",
        "limits",
    }


def test_summary_and_artifact_are_sorted(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    report = run(fixtures)

    assert report["summary"] == {
        "sources": 6,
        "expired": 1,
        "in_force": 4,
        "expiry_unknown": 1,
        "future_publications": 1,
        "retirements": 2,
        "additions": 1,
        "reviews": 6,
        "proposals": 9,
    }
    assert [source["id"] for source in report["sources"]] == sorted(
        source["id"] for source in report["sources"]
    )
    assert [proposal["kind"] for proposal in report["proposals"]] == sorted(
        proposal["kind"] for proposal in report["proposals"]
    )
    assert all(
        proposal["review"] == {"required": True, "applied": False}
        for proposal in report["proposals"]
    )


def test_fixture_impact_report_satisfies_the_published_schema():
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (ROOT / "knowledge" / "legal-change-impact.schema.json").read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(FIXTURE_IMPACT)


def test_cli_result_lines_and_exit_codes(tmp_path):
    full = copy_fixtures(tmp_path / "full")
    full_path = tmp_path / "full-report.json"
    completed = cli(full, full_path)

    assert completed.returncode == 1
    assert completed.stderr == ""
    lines = completed.stdout.splitlines()
    assert sum(1 for line in lines if line.startswith("Proposal:")) == 9
    assert lines[-1] == "Result: 9 proposals need review; report written to {}.".format(
        full_path
    )
    assert full_path.exists()

    clean = clean_fixtures(tmp_path / "clean")
    clean_path = tmp_path / "clean-report.json"
    completed = cli(clean, clean_path)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == (
        "Result: no proposals need review; report written to {}.\n".format(clean_path)
    )
    assert json.loads(clean_path.read_text(encoding="utf-8"))["proposals"] == []

    single = clean_fixtures(
        tmp_path / "single", candidates=[fixture_candidate("BOE-A-2099-00907")]
    )
    single_path = tmp_path / "single-report.json"
    completed = cli(single, single_path)

    assert completed.returncode == 1
    lines = completed.stdout.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("Proposal:")
    assert lines[1] == "Result: 1 proposal needs review; report written to {}.".format(
        single_path
    )

    aborted = copy_fixtures(tmp_path / "aborted")
    catalog = load(aborted, "catalog.json")
    catalog["sources"][0]["original_url"] = "https://evil.example/document"
    save_catalog(aborted, catalog)
    abort_path = tmp_path / "abort-report.json"
    completed = cli(aborted, abort_path)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr == abort_line("invalid_catalog")
    assert not abort_path.exists()


def test_cli_rejects_invalid_as_of_dates(tmp_path):
    fixtures = copy_fixtures(tmp_path)

    for index, value in enumerate(("01/06/2099", "2099-6-1", "20990601", "2099-02-30")):
        report_path = tmp_path / "invalid-{}.json".format(index)
        completed = cli(fixtures, report_path, as_of=value)

        assert completed.returncode == 2
        assert completed.stderr == abort_line("invalid_as_of")
        assert not report_path.exists()


def test_checker_is_import_safe_and_offline(tmp_path):
    source = (BACKEND_ROOT / "app" / "source_validity.py").read_text(encoding="utf-8")
    for forbidden in (
        "import socket",
        "import urllib",
        "import httpx",
        "import requests",
        "from app.server",
        "app.generation",
        "app.embeddings",
        "app.local_generation",
        "gemini",
        "datetime.now(",
        "date.today(",
        "time.time(",
        "time.localtime",
        "from zoneinfo",
    ):
        assert forbidden not in source

    script = """
import socket
import sys

def forbidden(*_args, **_kwargs):
    raise AssertionError("network access attempted")

socket.socket = forbidden
socket.create_connection = forbidden

sys.path.insert(0, "backend")
from datetime import date
from pathlib import Path
import app.source_validity as module

report = module.check_validity(
    Path("backend/tests/fixtures/source_validity/catalog.json"),
    Path("backend/tests/fixtures/source_validity/passages.json"),
    Path("backend/tests/fixtures/source_validity/impact-report.json"),
    date(2099, 6, 1),
)
assert report["schema_version"] == "validity-review-v1"
for name in (
    "app.server",
    "app.generation",
    "app.embeddings",
    "app.local_generation",
    "httpx",
    "requests",
):
    assert name not in sys.modules, name
print("ok")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"
