"""Focused tests for the approved source-catalog admission boundary.

The fixtures under ``fixtures/source_catalog/`` are synthetic catalog metadata
used to exercise the policy. They are not a review of a real document and must
never be read as one.
"""

import json
import socket
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.source_catalog import (  # noqa: E402  (path setup must run first)
    ISSUER_ALLOWED_HOSTS,
    SCHEMA_VERSION,
    SOURCE_OPTIONAL_KEYS,
    SOURCE_REQUIRED_KEYS,
    CatalogReadError,
    load_catalog,
    validate_catalog,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = BACKEND_ROOT / "scripts" / "validate_source_catalog.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "source_catalog"
CANONICAL_CATALOG = REPO_ROOT / "knowledge" / "source_catalog.json"
SCHEMA_FILE = REPO_ROOT / "knowledge" / "source_catalog.schema.json"

AS_OF = "2026-10-12"

# Each rejection fixture must exit non-zero and name this JSON path and rule.
REJECTION_CASES = [
    ("invalid_missing_field.json", "$.sources[0].content_sha256", "required key is missing"),
    ("invalid_bad_date.json", "$.sources[0].published_on", "real calendar date"),
    ("invalid_date_order.json", "$.sources[0].verified_on", "on or after downloaded_on"),
    ("invalid_bad_hash.json", "$.sources[0].content_sha256", "lowercase 64-character SHA-256"),
    ("invalid_duplicate_id.json", "$.sources[1].id", "duplicate id"),
    ("invalid_bad_url.json", "$.sources[0].original_url", "must not embed credentials"),
    ("invalid_site_root_url.json", "$.sources[0].original_url", "not a site root"),
    ("invalid_empty_applicability.json", "$.sources[0].applicability", "must not be empty"),
    (
        "invalid_unknown_applicability_value.json",
        "$.sources[0].applicability.water_regime",
        "leave unknown absent",
    ),
    ("invalid_unknown_key.json", "$.sources[0].source_note", "unknown key is not allowed"),
    ("invalid_unknown_top_level_key.json", "$.reviewed_on", "unknown key is not allowed"),
    ("invalid_root_not_object.json", "$", "catalog document must be a JSON object"),
    ("invalid_non_https_url.json", "$.sources[0].original_url", "must use https://"),
    (
        "invalid_lookalike_host.json",
        "$.sources[0].original_url",
        "approved official-domain allowlist",
    ),
    (
        "invalid_unapproved_host.json",
        "$.sources[0].original_url",
        "approved official-domain allowlist",
    ),
    (
        "invalid_issuer_host_mismatch.json",
        "$.sources[0].original_url",
        "declared issuing_body",
    ),
    ("invalid_unapproved_review.json", "$.sources[0].review_status", "must be 'approved'"),
    ("invalid_empty_reviewer.json", "$.sources[0].reviewed_by", "non-blank string"),
    ("invalid_not_current.json", "$.sources[0].lifecycle_status", "must be 'current'"),
    ("invalid_expired.json", "$.sources[0].valid_until", "expired and ineligible"),
]


def run_cli(catalog_path: Path, as_of: str = AS_OF) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), str(catalog_path), "--as-of", as_of],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def fixture(name: str) -> Path:
    return FIXTURES / name


def report_for(name: str, as_of: str = AS_OF):
    return validate_catalog(load_catalog(fixture(name)), as_of=date.fromisoformat(as_of))


def source_with(**overrides) -> dict:
    """Return a valid source entry with ``overrides`` applied."""

    entry = {
        "id": "rd_1048_2022",
        "title": "Real Decreto 1048/2022 (inline test entry)",
        "issuing_body": "BOE",
        "original_url": "https://www.boe.es/buscar/doc.php?id=BOE-A-2022-23048",
        "published_on": "2022-12-29",
        "downloaded_on": "2026-10-01",
        "verified_on": "2026-10-05",
        "content_sha256": "3f2a1b0c9d8e7f60514233241506f7e8d9c0b1a2938475665748392011fedcba",
        "review_status": "approved",
        "reviewed_by": "inline test reviewer",
        "reviewed_on": "2026-10-06",
        "lifecycle_status": "current",
    }
    entry.update(overrides)
    return entry


# --- accepted cases ---------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected_sources",
    [("valid_official_source.json", 3), ("valid_empty_catalog.json", 0)],
)
def test_valid_fixture_is_accepted(name: str, expected_sources: int) -> None:
    result = run_cli(fixture(name))

    assert result.returncode == 0, result.stderr
    assert "{} source(s) checked as of {}".format(expected_sources, AS_OF) in result.stdout


def test_valid_fixture_reports_the_checked_entry_count_and_schema() -> None:
    report = report_for("valid_official_source.json")

    assert report.ok, report.format_issues()
    assert report.checked_sources == 3
    assert report.schema_version == SCHEMA_VERSION


def test_valid_fixture_uses_approved_https_provenance() -> None:
    document = load_catalog(fixture("valid_official_source.json"))
    issuers = {source["issuing_body"] for source in document["sources"]}
    hosts = {
        source["original_url"].split("/")[2]
        for source in document["sources"]
    }

    assert issuers == {"BOE", "Junta de Andalucía", "FEGA"}
    for source in document["sources"]:
        assert source["original_url"].startswith("https://")
        assert source["original_url"].split("/")[2] in ISSUER_ALLOWED_HOSTS[source["issuing_body"]]
    assert "www.boe.es" in hosts


def test_canonical_catalog_is_a_valid_empty_catalog() -> None:
    result = run_cli(CANONICAL_CATALOG)

    assert result.returncode == 0, result.stderr
    assert "0 source(s) checked" in result.stdout


def test_canonical_catalog_does_not_claim_corpus_coverage() -> None:
    document = load_catalog(CANONICAL_CATALOG)

    assert document == {"schema_version": SCHEMA_VERSION, "sources": []}
    report = validate_catalog(document, as_of=date.fromisoformat(AS_OF))
    assert report.ok


# --- rejected cases ---------------------------------------------------------


@pytest.mark.parametrize("name, location, rule_fragment", REJECTION_CASES)
def test_rejection_fixture_exits_non_zero_with_a_located_rule(
    name: str, location: str, rule_fragment: str
) -> None:
    result = run_cli(fixture(name))

    assert result.returncode != 0, result.stdout
    assert "invalid source catalog" in result.stderr
    assert "{}:".format(location) in result.stderr
    assert rule_fragment in result.stderr
    assert result.stdout == ""


def test_malformed_json_exits_unreadable() -> None:
    result = run_cli(fixture("malformed_json.json"))

    assert result.returncode == 2
    assert "not valid JSON" in result.stderr


def test_missing_catalog_file_exits_unreadable() -> None:
    result = run_cli(FIXTURES / "does_not_exist.json")

    assert result.returncode == 2
    assert "cannot read catalog file" in result.stderr


def test_load_catalog_rejects_invalid_json(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")

    with pytest.raises(CatalogReadError):
        load_catalog(broken)


# --- rule detail ------------------------------------------------------------


def test_duplicate_id_reports_both_entries() -> None:
    report = report_for("invalid_duplicate_id.json")

    issues = [str(issue) for issue in report.issues]
    assert any("$.sources[1].id:" in issue and "$.sources[0]" in issue for issue in issues)


def test_date_order_violations_are_reported_per_field() -> None:
    report = report_for("invalid_date_order.json")

    locations = [issue.location for issue in report.issues]
    assert "$.sources[0].verified_on" in locations


def test_reviewed_on_before_downloaded_on_is_reported() -> None:
    document = {
        "schema_version": SCHEMA_VERSION,
        "sources": [
            source_with(reviewed_on="2026-09-01"),
        ],
    }

    report = validate_catalog(document, as_of=date.fromisoformat(AS_OF))

    assert not report.ok
    assert [(issue.location, issue.rule) for issue in report.issues] == [
        ("$.sources[0].reviewed_on", "must be on or after downloaded_on")
    ]


def test_schema_version_mismatch_is_reported() -> None:
    document = {"schema_version": "source-catalog-v2", "sources": []}

    report = validate_catalog(document, as_of=date.fromisoformat(AS_OF))

    assert [(issue.location, issue.rule) for issue in report.issues] == [
        ("$.schema_version", "must equal '{}'".format(SCHEMA_VERSION))
    ]


def test_state_bodies_may_publish_in_the_boe_gazette() -> None:
    document = {
        "schema_version": SCHEMA_VERSION,
        "sources": [source_with(issuing_body="MAPA")],
    }

    report = validate_catalog(document, as_of=date.fromisoformat(AS_OF))

    assert report.ok, report.format_issues()


def test_unlisted_lookalike_suffix_is_rejected() -> None:
    document = {
        "schema_version": SCHEMA_VERSION,
        "sources": [source_with(original_url="https://notboe.es/buscar/doc.php?id=BOE-A-2022-23048")],
    }

    report = validate_catalog(document, as_of=date.fromisoformat(AS_OF))

    assert [issue.location for issue in report.issues] == ["$.sources[0].original_url"]


def test_expired_entry_is_accepted_on_its_valid_until_date() -> None:
    boundary = run_cli(fixture("invalid_expired.json"), as_of="2026-06-15")

    assert boundary.returncode == 0, boundary.stderr
    assert "1 source(s) checked" in boundary.stdout


def test_expiry_is_deterministic_with_as_of() -> None:
    document = load_catalog(fixture("invalid_expired.json"))

    accepted = validate_catalog(document, as_of=date(2026, 6, 15))
    rejected = validate_catalog(document, as_of=date(2026, 6, 16))

    assert accepted.ok
    assert [issue.location for issue in rejected.issues] == ["$.sources[0].valid_until"]


# --- local-only and no-content guarantees -----------------------------------


def test_validation_never_opens_a_network_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid(*args, **kwargs):
        raise AssertionError("validation must not touch the network")

    monkeypatch.setattr(socket, "socket", _forbid)

    report = report_for("valid_official_source.json")
    rejection = report_for("invalid_expired.json")

    assert report.ok
    assert not rejection.ok


@pytest.mark.parametrize("name", ["invalid_not_current.json", "invalid_unapproved_review.json"])
def test_diagnostics_do_not_echo_catalog_field_values(name: str) -> None:
    result = run_cli(fixture(name))
    document = load_catalog(fixture(name))

    assert result.returncode != 0
    for source in document["sources"]:
        assert source["title"] not in result.stderr
        assert source["title"] not in result.stdout
        assert source["reviewed_by"] not in result.stderr
        assert source["original_url"] not in result.stderr


def test_cli_without_as_of_still_validates() -> None:
    result = subprocess.run(
        [sys.executable, str(CLI), str(CANONICAL_CATALOG)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )

    assert result.returncode == 0, result.stderr
    assert "0 source(s) checked" in result.stdout


# --- schema / validator contract sync ---------------------------------------


def test_schema_declares_the_same_fields_as_the_validator() -> None:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    source_schema = schema["$defs"]["source"]

    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"schema_version", "sources"}
    assert set(source_schema["required"]) == set(SOURCE_REQUIRED_KEYS)
    assert set(source_schema["properties"]) == set(SOURCE_REQUIRED_KEYS | SOURCE_OPTIONAL_KEYS)
    assert source_schema["additionalProperties"] is False
    assert set(source_schema["properties"]["issuing_body"]["enum"]) == set(ISSUER_ALLOWED_HOSTS)


def test_source_with_helper_is_accepted() -> None:
    report = validate_catalog(
        {"schema_version": SCHEMA_VERSION, "sources": [source_with()]},
        as_of=date.fromisoformat(AS_OF),
    )

    assert report.ok, report.format_issues()
