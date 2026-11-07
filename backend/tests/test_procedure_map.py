"""Focused tests for the reviewed olive-grove procedure map.

The canonical map is a taxonomy index only. These tests assert its seed set,
review honesty, digit-free human wording, and report-only coverage declarations;
they never assert a legal fact.
"""

import copy
import json
import socket
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.procedure_map import (  # noqa: E402  (path setup must run first)
    COVERAGE_OPTIONAL_KEYS,
    COVERAGE_REQUIRED_KEYS,
    COVERAGE_STATES,
    MAX_SUMMARY_LENGTH,
    MAX_TITLE_LENGTH,
    REVIEW_STATUSES,
    SCHEMA_VERSION,
    SEED_TOPIC_IDS,
    TOPIC_OPTIONAL_KEYS,
    TOPIC_REQUIRED_KEYS,
    ProcedureMapReadError,
    load_catalog_ids,
    load_passage_sources,
    load_procedure_map,
    validate_procedure_map,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = BACKEND_ROOT / "scripts" / "validate_procedure_map.py"
CANONICAL_MAP = REPO_ROOT / "knowledge" / "procedure_map.json"
SCHEMA_FILE = REPO_ROOT / "knowledge" / "procedure_map.schema.json"
CANONICAL_CATALOG = REPO_ROOT / "knowledge" / "source_catalog.json"
CANONICAL_PASSAGES = REPO_ROOT / "knowledge" / "passages.json"

CATALOG_IDS = load_catalog_ids(CANONICAL_CATALOG)
PASSAGE_SOURCES = load_passage_sources(CANONICAL_PASSAGES)


def canonical_document() -> dict:
    return json.loads(CANONICAL_MAP.read_text(encoding="utf-8"))


def topic(document: dict, topic_id: str) -> dict:
    return next(entry for entry in document["topics"] if entry["id"] == topic_id)


def validate(document: dict):
    return validate_procedure_map(document, CATALOG_IDS, PASSAGE_SOURCES)


def issue_pairs(report) -> list:
    return [(issue.location, issue.rule) for issue in report.issues]


def write_map(tmp_path: Path, document: dict, name: str = "map.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI)] + [str(arg) for arg in args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


# --- canonical artifact -----------------------------------------------------


def test_canonical_map_lists_the_seed_topics_in_order() -> None:
    document = canonical_document()
    report = validate(document)

    assert report.ok, report.format_issues()
    assert tuple(entry["id"] for entry in document["topics"]) == SEED_TOPIC_IDS
    assert len(SEED_TOPIC_IDS) == 16
    assert len(set(SEED_TOPIC_IDS)) == 16


def test_canonical_map_ships_every_topic_as_proposed() -> None:
    document = canonical_document()

    assert all(entry["review_status"] == "proposed" for entry in document["topics"])
    assert all("reviewed_by" not in entry for entry in document["topics"])


def test_canonical_map_declares_only_the_pac_topic_as_partial() -> None:
    document = canonical_document()
    states = {entry["id"]: entry["coverage"]["state"] for entry in document["topics"]}

    assert states["solicitud-unica-pac"] == "partial"
    assert sorted(states.values()) == ["partial"] + ["uncovered"] * 15


def test_canonical_pac_topic_references_the_accepted_slice() -> None:
    pac = topic(canonical_document(), "solicitud-unica-pac")
    source_ids = pac["coverage"]["source_ids"]
    passage_ids = pac["coverage"]["passage_ids"]

    assert set(source_ids) == set(CATALOG_IDS)
    assert set(passage_ids) == set(PASSAGE_SOURCES)
    for passage_id in passage_ids:
        assert PASSAGE_SOURCES[passage_id] in source_ids


def test_canonical_human_fields_contain_no_digits() -> None:
    for entry in canonical_document()["topics"]:
        human_text = [entry["title"], entry["summary"], *entry["search_terms"]]
        gap_note = entry["coverage"].get("gap_note")
        if gap_note is not None:
            human_text.append(gap_note)
        for value in human_text:
            assert not any(character.isdigit() for character in value)


def test_canonical_search_phrases_are_unique_across_procedures() -> None:
    document = canonical_document()
    terms = [
        " ".join(term.strip().casefold().split())
        for entry in document["topics"]
        for term in entry["search_terms"]
    ]

    assert len(terms) == len(set(terms))


def test_coverage_gaps_are_reported_not_rejected() -> None:
    report = validate(canonical_document())

    assert report.ok
    assert report.coverage.partial == 1
    assert report.coverage.uncovered == 15
    assert report.coverage.proposed == 16
    assert report.coverage.reviewed == 0


# --- JSON Schema ------------------------------------------------------------


def schema_validator() -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


def test_schema_accepts_the_canonical_map() -> None:
    schema_validator().validate(canonical_document())


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda document: topic(document, "sigpac")["coverage"].update(
                source_ids=["res_20260121"]
            ),
            id="uncovered-with-reference",
        ),
        pytest.param(
            lambda document: topic(document, "sigpac").update(reviewed_by="Alguien"),
            id="proposed-with-reviewer",
        ),
        pytest.param(
            lambda document: topic(document, "riego").update(title="Riego 2"),
            id="digit-in-title",
        ),
        pytest.param(
            lambda document: topic(document, "riego").pop("summary"),
            id="missing-required-field",
        ),
    ],
)
def test_schema_rejects_unsafe_shapes(mutate) -> None:
    document = canonical_document()
    mutate(document)

    assert not schema_validator().is_valid(document)


def test_schema_and_validator_agree_on_fields_and_states() -> None:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    topic_schema = schema["$defs"]["topic"]
    coverage_schema = schema["$defs"]["coverage"]

    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"schema_version", "topics"}
    assert set(topic_schema["required"]) == set(TOPIC_REQUIRED_KEYS)
    assert set(topic_schema["properties"]) == set(TOPIC_REQUIRED_KEYS | TOPIC_OPTIONAL_KEYS)
    assert topic_schema["additionalProperties"] is False
    assert set(topic_schema["properties"]["review_status"]["enum"]) == set(REVIEW_STATUSES)
    assert set(coverage_schema["required"]) == set(COVERAGE_REQUIRED_KEYS)
    assert set(coverage_schema["properties"]) == set(
        COVERAGE_REQUIRED_KEYS | COVERAGE_OPTIONAL_KEYS
    )
    assert set(coverage_schema["properties"]["state"]["enum"]) == set(COVERAGE_STATES)
    assert schema["properties"]["topics"]["minItems"] == len(SEED_TOPIC_IDS)


# --- rejected cases ---------------------------------------------------------


def _remove_a_topic(document: dict) -> None:
    document["topics"].pop()


def _unknown_topic(document: dict) -> None:
    document["topics"][1]["id"] = "riego-extra"


def _duplicate_topic(document: dict) -> None:
    document["topics"][1]["id"] = document["topics"][0]["id"]


def _reviewed_without_reviewer(document: dict) -> None:
    entry = document["topics"][1]
    entry["review_status"] = "reviewed"
    entry.pop("reviewed_by", None)


def _reviewer_on_proposed(document: dict) -> None:
    document["topics"][1]["reviewed_by"] = "Alguien"


def _covered_without_references(document: dict) -> None:
    document["topics"][1]["coverage"]["state"] = "covered"


def _partial_without_gap_note(document: dict) -> None:
    topic(document, "solicitud-unica-pac")["coverage"].pop("gap_note")


def _uncovered_with_references(document: dict) -> None:
    document["topics"][1]["coverage"]["source_ids"] = ["res_20260121"]


def _unknown_source_reference(document: dict) -> None:
    topic(document, "solicitud-unica-pac")["coverage"]["source_ids"].append(
        "unknown-source"
    )


def _unknown_passage_reference(document: dict) -> None:
    topic(document, "solicitud-unica-pac")["coverage"]["passage_ids"].append(
        "unknown-passage"
    )


def _passage_source_not_listed(document: dict) -> None:
    coverage = topic(document, "solicitud-unica-pac")["coverage"]
    coverage["source_ids"].remove("dl_1_2026")


def _unknown_topic_key(document: dict) -> None:
    document["topics"][1]["note"] = "x"


def _unknown_top_level_key(document: dict) -> None:
    document["generated_on"] = "x"


def _blank_summary(document: dict) -> None:
    document["topics"][1]["summary"] = "   "


def _over_long_title(document: dict) -> None:
    document["topics"][1]["title"] = "x" * (MAX_TITLE_LENGTH + 1)


def _digit_in_title(document: dict) -> None:
    document["topics"][1]["title"] = "Riego 2"


def _digit_in_summary(document: dict) -> None:
    document["topics"][1]["summary"] += " 2"


def _digit_in_search_term(document: dict) -> None:
    document["topics"][1]["search_terms"][0] = "riego 2"


def _digit_in_gap_note(document: dict) -> None:
    topic(document, "solicitud-unica-pac")["coverage"]["gap_note"] += " 2"


def _empty_search_terms(document: dict) -> None:
    document["topics"][1]["search_terms"] = []


def _too_many_search_terms(document: dict) -> None:
    document["topics"][1]["search_terms"].extend(["uno", "dos", "tres"])


def _duplicate_search_wording(document: dict) -> None:
    entry = document["topics"][1]
    entry["search_terms"].append(entry["search_terms"][0])


def _duplicate_search_wording_across_topics(document: dict) -> None:
    document["topics"][1]["search_terms"][0] = document["topics"][0]["search_terms"][0]


def _swap_seed_order(document: dict) -> None:
    document["topics"][0], document["topics"][1] = (
        document["topics"][1],
        document["topics"][0],
    )


def _unknown_review_status(document: dict) -> None:
    document["topics"][1]["review_status"] = "aprobado"


def _unknown_coverage_state(document: dict) -> None:
    document["topics"][1]["coverage"]["state"] = "unknown"


REJECTION_CASES = [
    ("missing seed topic", _remove_a_topic, "$.topics", "seed topic is missing"),
    ("unknown topic id", _unknown_topic, "$.topics[1].id", "not in the seed set"),
    ("duplicate topic id", _duplicate_topic, "$.topics[1].id", "duplicate id"),
    (
        "reviewed without reviewer",
        _reviewed_without_reviewer,
        "$.topics[1].reviewed_by",
        "named human reviewer",
    ),
    (
        "reviewer on proposed topic",
        _reviewer_on_proposed,
        "$.topics[1].reviewed_by",
        "proposed topics must omit reviewed_by",
    ),
    (
        "covered without references",
        _covered_without_references,
        "$.topics[1].coverage.source_ids",
        "at least one approved source",
    ),
    (
        "partial without gap note",
        _partial_without_gap_note,
        "$.topics[0].coverage.gap_note",
        "partial coverage requires a gap note",
    ),
    (
        "uncovered with references",
        _uncovered_with_references,
        "$.topics[1].coverage",
        "uncovered topic must not list evidence references",
    ),
    (
        "unknown source reference",
        _unknown_source_reference,
        "$.topics[0].coverage.source_ids[6]",
        "unknown catalog source id",
    ),
    (
        "unknown passage reference",
        _unknown_passage_reference,
        "$.topics[0].coverage.passage_ids[7]",
        "unknown reviewed passage id",
    ),
    (
        "passage source not listed",
        _passage_source_not_listed,
        "$.topics[0].coverage.passage_ids[2]",
        "passage source is not listed by the topic",
    ),
    (
        "unknown topic key",
        _unknown_topic_key,
        "$.topics[1].note",
        "unknown key is not allowed",
    ),
    (
        "unknown top-level key",
        _unknown_top_level_key,
        "$.generated_on",
        "unknown key is not allowed",
    ),
    ("blank summary", _blank_summary, "$.topics[1].summary", "non-blank string"),
    (
        "over-long title",
        _over_long_title,
        "$.topics[1].title",
        "at most {} characters".format(MAX_TITLE_LENGTH),
    ),
    ("digit in title", _digit_in_title, "$.topics[1].title", "must not contain digits"),
    ("digit in summary", _digit_in_summary, "$.topics[1].summary", "must not contain digits"),
    (
        "digit in search term",
        _digit_in_search_term,
        "$.topics[1].search_terms[0]",
        "must not contain digits",
    ),
    (
        "digit in gap note",
        _digit_in_gap_note,
        "$.topics[0].coverage.gap_note",
        "must not contain digits",
    ),
    (
        "empty search terms",
        _empty_search_terms,
        "$.topics[1].search_terms",
        "between 1 and 6",
    ),
    (
        "too many search terms",
        _too_many_search_terms,
        "$.topics[1].search_terms",
        "between 1 and 6",
    ),
    (
        "duplicate search wording",
        _duplicate_search_wording,
        "$.topics[1].search_terms[4]",
        "duplicate search wording",
    ),
    (
        "duplicate search wording across topics",
        _duplicate_search_wording_across_topics,
        "$.topics[1].search_terms[0]",
        "duplicate search wording",
    ),
    ("seed order changed", _swap_seed_order, "$.topics", "must follow the seed order"),
    (
        "unknown review status",
        _unknown_review_status,
        "$.topics[1].review_status",
        "must be 'proposed' or 'reviewed'",
    ),
    (
        "unknown coverage state",
        _unknown_coverage_state,
        "$.topics[1].coverage.state",
        "must be 'covered', 'partial', or 'uncovered'",
    ),
]


@pytest.mark.parametrize("label, mutate, location, rule_fragment", REJECTION_CASES)
def test_rejection_is_located_and_names_the_rule(
    label: str, mutate, location: str, rule_fragment: str
) -> None:
    document = canonical_document()
    mutate(document)

    report = validate(document)

    assert not report.ok, label
    assert any(
        issue_location == location and rule_fragment in rule
        for issue_location, rule in issue_pairs(report)
    ), report.format_issues()


def test_reference_checks_run_only_when_both_inputs_are_supplied() -> None:
    document = canonical_document()
    _unknown_source_reference(document)

    with_catalog_only = validate_procedure_map(document, CATALOG_IDS, None)
    without_inputs = validate_procedure_map(document, None, None)

    assert with_catalog_only.ok
    assert without_inputs.ok


# --- command line -----------------------------------------------------------


def test_cli_reports_the_valid_map_and_every_topic() -> None:
    result = run_cli(
        CANONICAL_MAP,
        "--catalog",
        CANONICAL_CATALOG,
        "--passages",
        CANONICAL_PASSAGES,
        "--report",
    )

    assert result.returncode == 0, result.stderr
    assert "valid procedure map:" in result.stdout
    assert "16 topics: 16 proposed, 0 reviewed" in result.stdout
    assert "1 partial, 15 uncovered" in result.stdout
    assert "6 mapped source(s), 7 mapped passage(s)" in result.stdout
    assert "unreferenced source ids: none" in result.stdout
    assert "unreferenced passage ids: none" in result.stdout
    assert "topic solicitud-unica-pac: proposed, partial, 6 source(s), 7 passage(s)" in (
        result.stdout
    )
    assert sum(1 for line in result.stdout.splitlines() if line.startswith("topic ")) == 16


def test_cli_without_reference_files_still_validates() -> None:
    result = run_cli(CANONICAL_MAP)

    assert result.returncode == 0, result.stderr
    assert "reference ids not checked" in result.stdout


def test_cli_requires_catalog_and_passages_together() -> None:
    result = run_cli(CANONICAL_MAP, "--catalog", CANONICAL_CATALOG)

    assert result.returncode == 2
    assert "--catalog and --passages must be supplied together" in result.stderr


def test_cli_invalid_map_exits_one(tmp_path: Path) -> None:
    document = canonical_document()
    _unknown_topic_key(document)
    path = write_map(tmp_path, document)

    result = run_cli(path)

    assert result.returncode == 1
    assert "invalid procedure map" in result.stderr
    assert "unknown key is not allowed" in result.stderr
    assert result.stdout == ""


def test_cli_malformed_json_exits_two(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")

    result = run_cli(broken)

    assert result.returncode == 2
    assert "not valid JSON" in result.stderr


def test_cli_missing_file_exits_two(tmp_path: Path) -> None:
    result = run_cli(tmp_path / "does_not_exist.json")

    assert result.returncode == 2
    assert "cannot read procedure map file" in result.stderr


def test_load_procedure_map_rejects_invalid_json(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")

    with pytest.raises(ProcedureMapReadError):
        load_procedure_map(broken)


def test_diagnostics_do_not_echo_map_field_values(tmp_path: Path) -> None:
    document = canonical_document()
    marker = "ZZZSECRETO"
    document["topics"][1]["title"] = marker * 20
    path = write_map(tmp_path, document)

    result = run_cli(path)

    assert result.returncode == 1
    assert "$.topics[1].title" in result.stderr
    assert marker not in result.stderr
    assert marker not in result.stdout


# --- offline guarantee ------------------------------------------------------


def test_validation_never_opens_a_network_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbid(*args, **kwargs):
        raise AssertionError("validation must not touch the network")

    monkeypatch.setattr(socket, "socket", _forbid)

    report = validate(canonical_document())

    assert report.ok, report.format_issues()
