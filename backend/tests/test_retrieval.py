"""Focused tests for the offline retrieval boundary.

The fixtures under ``fixtures/retrieval/`` are synthetic and clearly labelled:
they are not real legal documents and they assert no real deadline, amount, or
article. They exist only to exercise the passage-set contract, the eligibility
coupling to the accepted catalog gate, and the lexical ranking code.
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

from app.retrieval import (  # noqa: E402  (path setup must run first)
    APPLICABILITY_KEYS,
    BM25_B,
    BM25_K1,
    DEFAULT_K,
    PASSAGE_OPTIONAL_KEYS,
    PASSAGE_REQUIRED_KEYS,
    PASSAGE_SET_SCHEMA_VERSION,
    PRODUCTION_METHODS,
    STOPWORDS,
    WATER_REGIMES,
    Bm25Index,
    CatalogRejectedError,
    PassageSetError,
    Retriever,
    eligible_source_ids,
    load_passage_set,
    source_is_eligible,
    tokenize,
    validate_passage_set,
)
from app.source_catalog import (  # noqa: E402
    load_catalog,
    validate_catalog,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = BACKEND_ROOT / "scripts" / "evaluate_retrieval.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval"
CANONICAL_CATALOG = REPO_ROOT / "knowledge" / "source_catalog.json"
EMPTY_CATALOG = Path(__file__).resolve().parent / "fixtures" / "empty_catalog.json"
CATALOG_SCHEMA_FILE = REPO_ROOT / "knowledge" / "source_catalog.schema.json"
SCHEMA_FILE = REPO_ROOT / "knowledge" / "passages.schema.json"

AS_OF = "2026-10-13"

CATALOG_FIXTURE = "catalog.json"
PASSAGE_FIXTURE = "passages.json"
EVAL_FIXTURE = "eval_questions.jsonl"


# --- helpers ----------------------------------------------------------------


def fixture(name: str) -> Path:
    return FIXTURES / name


def catalog_document(name: str = CATALOG_FIXTURE):
    return load_catalog(fixture(name))


def passage_document(name: str = PASSAGE_FIXTURE):
    return load_passage_set(fixture(name))


def build_retriever(
    catalog_name: str = CATALOG_FIXTURE,
    passages_name: str = PASSAGE_FIXTURE,
    as_of: str = AS_OF,
) -> Retriever:
    return Retriever.from_documents(
        catalog_document(catalog_name),
        passage_document(passages_name),
        date.fromisoformat(as_of),
    )


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
        str(fixture(CATALOG_FIXTURE)),
        "--passages",
        str(fixture(PASSAGE_FIXTURE)),
        "--eval",
        str(fixture(EVAL_FIXTURE)),
        "--as-of",
        AS_OF,
        "--k",
        "5",
        *extra,
    )


def source_entry(**overrides) -> dict:
    """Return a valid catalog source entry with ``overrides`` applied."""

    entry = {
        "id": "fixture_source",
        "title": "Documento sintético de prueba (fixture; no es una norma real)",
        "issuing_body": "BOE",
        "original_url": "https://www.boe.es/buscar/doc.php?id=DOC-FIXTURE-9999",
        "published_on": "2026-01-15",
        "downloaded_on": "2026-09-30",
        "verified_on": "2026-10-05",
        "content_sha256": "3f2a1b0c9d8e7f60514233241506f7e8d9c0b1a2938475665748392011fedcba",
        "review_status": "approved",
        "reviewed_by": "inline test reviewer (synthetic)",
        "reviewed_on": "2026-10-06",
        "lifecycle_status": "current",
    }
    entry.update(overrides)
    return entry


def passage_entry(**overrides) -> dict:
    """Return a valid passage entry with ``overrides`` applied."""

    entry = {
        "id": "fixture-passage-1",
        "source_id": "fixture_source",
        "location": "Art. 1 (fixture, sintético)",
        "text": "Fragmento sintético de prueba; no afirma nada real.",
    }
    entry.update(overrides)
    return entry


def single_passage_document(**overrides) -> dict:
    return {
        "schema_version": PASSAGE_SET_SCHEMA_VERSION,
        "passages": [passage_entry(**overrides)],
    }


# --- tokenizer --------------------------------------------------------------


def test_tokenizer_lowercases_and_strips_diacritics() -> None:
    assert tokenize("SOLICITUD ÚNICA") == ("solicitud", "unica")
    assert tokenize("solicitud unica") == tokenize("solicitud única")


def test_tokenizer_splits_on_non_alphanumerics() -> None:
    assert tokenize("Art. 3-bis, cuaderno:campo") == (
        "art",
        "3",
        "bis",
        "cuaderno",
        "campo",
    )


def test_tokenizer_transliterates_spanish_letters() -> None:
    assert tokenize("acompaña al olivar") == ("acompana", "olivar")


def test_tokenizer_drops_spanish_stopwords() -> None:
    assert tokenize("de la que y el") == ()
    assert tokenize("el cuaderno de campo") == ("cuaderno", "campo")


def test_tokenizer_never_keeps_a_stopword() -> None:
    tokens = tokenize("La solicitud que se presenta para una ayuda")

    assert tokens
    assert not set(tokens) & set(STOPWORDS)


def test_tokenizer_handles_blank_and_non_string_input() -> None:
    assert tokenize("") == ()
    assert tokenize(" ... ") == ()
    assert tokenize(None) == ()  # type: ignore[arg-type]


# --- ranking ----------------------------------------------------------------


@pytest.mark.parametrize(
    "question, expected_passage_id",
    [
        ("¿Cómo se presenta la solicitud única?", "fixture-p-solicitud-1"),
        ("¿Como se presenta la solicitud unica?", "fixture-p-solicitud-1"),
        ("¿Qué anoto en el cuaderno de campo?", "fixture-p-cuaderno-1"),
        ("¿Cómo se describe el riego del olivar?", "fixture-p-riego-olivar-1"),
        ("¿Qué es la condicionalidad?", "fixture-p-condicionalidad-1"),
        (
            "¿Qué menciona sobre las buenas prácticas agrarias?",
            "fixture-p-condicionalidad-1",
        ),
    ],
)
def test_source_anchored_question_returns_the_expected_passage(
    question: str, expected_passage_id: str
) -> None:
    retriever = build_retriever()

    candidates = retriever.search(question, k=DEFAULT_K)

    assert candidates
    assert candidates[0].passage_id == expected_passage_id
    assert candidates[0].rank == 1
    assert candidates[0].score > 0.0


def test_accented_and_unaccented_questions_rank_the_same_passage() -> None:
    retriever = build_retriever()

    accented = retriever.search("¿Cómo se presenta la solicitud única?", k=5)
    unaccented = retriever.search("¿Como se presenta la solicitud unica?", k=5)

    assert [candidate.passage_id for candidate in accented] == [
        candidate.passage_id for candidate in unaccented
    ]
    assert accented[0].passage_id == "fixture-p-solicitud-1"


def test_expected_passage_outranks_unrelated_passages() -> None:
    retriever = build_retriever()

    candidates = retriever.search("¿Cómo se describe el riego del olivar?", k=5)

    assert candidates[0].passage_id == "fixture-p-riego-olivar-1"
    assert {"fixture-p-olivar-1", "fixture-p-riego-general-1"} <= {
        candidate.passage_id for candidate in candidates[1:]
    }


def test_search_is_deterministic_across_repeated_calls_and_instances() -> None:
    first = build_retriever()
    second = build_retriever()

    runs = [
        [(candidate.passage_id, candidate.rank, candidate.score) for candidate in first.search("cuaderno de campo", k=5)]
        for _ in range(3)
    ] + [
        [(candidate.passage_id, candidate.rank, candidate.score) for candidate in second.search("cuaderno de campo", k=5)]
    ]

    assert all(run == runs[0] for run in runs)


def test_index_ties_break_by_document_id() -> None:
    index = Bm25Index((("zzz", "olivar riego"), ("aaa", "olivar riego")))

    ranked = index.ranked_scores(tokenize("olivar riego"))

    assert [document_id for document_id, _ in ranked] == ["aaa", "zzz"]
    assert ranked[0][1] == pytest.approx(ranked[1][1])


def test_bm25_uses_the_documented_parameters() -> None:
    assert (BM25_K1, BM25_B) == (1.5, 0.75)


def test_window_limits_the_number_of_candidates() -> None:
    retriever = build_retriever()

    assert len(retriever.search("prueba", k=1)) == 1
    assert len(retriever.search("prueba", k=3)) == 3
    assert len(retriever.search("prueba", k=50)) == retriever.indexed_passage_count


def test_fewer_matches_than_k_are_returned_without_fabrication() -> None:
    retriever = build_retriever()

    candidates = retriever.search("condicionalidad", k=5)

    assert [candidate.passage_id for candidate in candidates] == [
        "fixture-p-condicionalidad-1"
    ]


@pytest.mark.parametrize("k", [0, -1])
def test_non_positive_window_returns_no_candidates(k: int) -> None:
    assert build_retriever().search("¿Qué es la condicionalidad?", k=k) == ()


@pytest.mark.parametrize(
    "question",
    ["", "   ", "de la que y el", "zzzz qqqq", "###"],
)
def test_blank_stopword_only_and_out_of_vocabulary_questions_return_nothing(
    question: str,
) -> None:
    assert build_retriever().search(question, k=5) == ()


def test_no_candidate_is_returned_with_a_zero_score() -> None:
    retriever = build_retriever()

    for candidate in retriever.search("prueba", k=50):
        assert candidate.score > 0.0


# --- candidate metadata -----------------------------------------------------


def candidates_by_id(retriever: Retriever) -> dict:
    """Return every indexed candidate keyed by passage id.

    Every fixture passage contains the synthetic word "prueba", so this query
    retrieves the complete corpus without depending on the eval questions.
    """

    return {
        candidate.passage_id: candidate
        for candidate in retriever.search("prueba", k=100)
    }


def test_candidate_exposes_contract_compatible_source_metadata() -> None:
    retriever = build_retriever()
    catalog = catalog_document()
    sources = {source["id"]: source for source in catalog["sources"]}
    passage = next(
        item
        for item in passage_document()["passages"]
        if item["id"] == "fixture-p-solicitud-1"
    )
    source = sources[passage["source_id"]]

    candidate = candidates_by_id(retriever)["fixture-p-solicitud-1"]

    assert candidate.passage_id == "fixture-p-solicitud-1"
    assert candidate.source_id == source["id"]
    assert candidate.title == source["title"]
    assert candidate.issuing_body == source["issuing_body"]
    assert candidate.url == source["original_url"]
    assert candidate.location == passage["location"]
    assert candidate.published_or_updated_on == source["published_on"]
    assert candidate.verified_on == source["verified_on"]
    assert candidate.excerpt == passage["text"]
    assert candidate.rank >= 1
    assert candidate.score > 0.0


def test_candidate_ranks_are_sequential_and_score_ordered() -> None:
    candidates = candidates_by_id(build_retriever())

    ranked = sorted(candidates.values(), key=lambda candidate: candidate.rank)

    assert [candidate.rank for candidate in ranked] == list(
        range(1, len(ranked) + 1)
    )
    assert [candidate.score for candidate in ranked] == sorted(
        (candidate.score for candidate in ranked), reverse=True
    )


def test_candidate_applicability_and_critical_fall_back_to_the_source() -> None:
    retriever = build_retriever()
    candidates = candidates_by_id(retriever)

    inherited = candidates["fixture-p-olivar-1"]
    assert inherited.applicability == {
        "crop": "olivar",
        "water_regime": "dryland",
        "production_method": "conventional",
    }
    assert inherited.critical is True

    overridden = candidates["fixture-p-riego-olivar-1"]
    assert overridden.applicability == {"crop": "olivar", "water_regime": "mixed"}

    passage_level_false = candidates["fixture-p-cuaderno-1"]
    assert passage_level_false.critical is False


def test_candidate_without_known_applicability_stays_absent() -> None:
    retriever = build_retriever()

    candidate = candidates_by_id(retriever)["fixture-p-solicitud-1"]

    assert candidate.applicability is None
    assert candidate.critical is False


# --- passage-set contract ---------------------------------------------------


def test_fixture_passage_set_is_valid() -> None:
    report = validate_passage_set(passage_document())

    assert report.ok, report.format_issues()
    assert report.schema_version == PASSAGE_SET_SCHEMA_VERSION
    assert report.checked_passages == 12


def test_empty_passage_set_is_valid() -> None:
    report = validate_passage_set(
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []}
    )

    assert report.ok
    assert report.checked_passages == 0


@pytest.mark.parametrize(
    "overrides, location, rule_fragment",
    [
        ({"id": ""}, "$.passages[0].id", "non-blank string"),
        ({"id": "Fixture ID"}, "$.passages[0].id", "lowercase slug"),
        ({"source_id": ""}, "$.passages[0].source_id", "non-blank string"),
        ({"location": "  "}, "$.passages[0].location", "non-blank string"),
        ({"text": ""}, "$.passages[0].text", "non-blank string"),
        ({"critical": "yes"}, "$.passages[0].critical", "true or false"),
        ({"excerpt": "x"}, "$.passages[0].excerpt", "unknown key is not allowed"),
        (
            {"applicability": {}},
            "$.passages[0].applicability",
            "must not be empty",
        ),
        (
            {"applicability": {"water_regime": "unknown"}},
            "$.passages[0].applicability.water_regime",
            "leave unknown absent",
        ),
        (
            {"applicability": {"production_method": "unknown"}},
            "$.passages[0].applicability.production_method",
            "leave unknown absent",
        ),
        (
            {"applicability": {"crop": ""}},
            "$.passages[0].applicability.crop",
            "non-blank string",
        ),
    ],
)
def test_passage_schema_violation_is_located(
    overrides: dict, location: str, rule_fragment: str
) -> None:
    report = validate_passage_set(single_passage_document(**overrides))

    issues = [issue for issue in report.issues if issue.location == location]
    assert issues, report.format_issues()
    assert any(rule_fragment in issue.rule for issue in issues)


def test_duplicate_passage_ids_are_reported_on_the_second_entry() -> None:
    document = {
        "schema_version": PASSAGE_SET_SCHEMA_VERSION,
        "passages": [
            passage_entry(id="fixture-duplicate"),
            passage_entry(id="fixture-duplicate"),
        ],
    }

    report = validate_passage_set(document)

    assert [issue.location for issue in report.issues] == ["$.passages[1].id"]
    assert "duplicate id" in report.issues[0].rule


def test_unknown_top_level_key_is_reported() -> None:
    report = validate_passage_set(
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": [], "reviewer": "x"}
    )

    assert [issue.location for issue in report.issues] == ["$.reviewer"]


def test_wrong_schema_version_is_reported() -> None:
    report = validate_passage_set({"schema_version": "passage-set-v2", "passages": []})

    assert [issue.location for issue in report.issues] == ["$.schema_version"]


def test_known_applicability_values_are_accepted() -> None:
    report = validate_passage_set(
        single_passage_document(
            applicability={
                "crop": "olivar",
                "water_regime": WATER_REGIMES[0],
                "production_method": PRODUCTION_METHODS[0],
            }
        )
    )

    assert report.ok, report.format_issues()


def test_malformed_passage_set_raises_a_read_error() -> None:
    with pytest.raises(PassageSetError) as error:
        load_passage_set(fixture("passages_malformed.json"))

    assert "not valid JSON" in str(error.value)


def test_missing_passage_set_raises_a_read_error() -> None:
    with pytest.raises(PassageSetError) as error:
        load_passage_set(fixture("does_not_exist.json"))

    assert "cannot read passage set file" in str(error.value)


# --- eligibility and fail-closed behaviour ----------------------------------


def test_unknown_source_id_is_a_located_error() -> None:
    with pytest.raises(PassageSetError) as error:
        Retriever.from_documents(
            catalog_document(),
            passage_document("passages_unknown_source.json"),
            date.fromisoformat(AS_OF),
        )

    message = str(error.value)
    assert "$.passages[0].source_id" in message
    assert "does not resolve to a source" in message


def test_unknown_passage_key_is_rejected_before_indexing() -> None:
    with pytest.raises(PassageSetError) as error:
        Retriever.from_documents(
            catalog_document(),
            passage_document("passages_unknown_key.json"),
            date.fromisoformat(AS_OF),
        )

    assert "$.passages[0].excerpt: unknown key is not allowed" in str(error.value)


@pytest.mark.parametrize(
    "catalog_name",
    ["catalog_expired.json", "catalog_not_approved.json", "catalog_not_current.json"],
)
def test_retriever_refuses_an_ineligible_catalog(catalog_name: str) -> None:
    with pytest.raises(CatalogRejectedError):
        build_retriever(catalog_name=catalog_name)


def test_retriever_refuses_an_invalid_catalog_without_indexing_partial_data() -> None:
    document = {
        "schema_version": "source-catalog-v1",
        "sources": [source_entry(source_note="not allowed")],
    }

    with pytest.raises(CatalogRejectedError) as error:
        Retriever.from_documents(
            document, passage_document(PASSAGE_FIXTURE), date.fromisoformat(AS_OF)
        )

    assert "$.sources[0].source_note" in str(error.value)


def test_source_is_eligible_requires_approved_current_and_unexpired() -> None:
    as_of = date.fromisoformat(AS_OF)

    assert source_is_eligible(source_entry(), as_of)
    assert source_is_eligible(source_entry(valid_until="2026-10-13"), as_of)
    assert not source_is_eligible(source_entry(valid_until="2026-10-12"), as_of)
    assert not source_is_eligible(source_entry(valid_until="not-a-date"), as_of)
    assert not source_is_eligible(source_entry(review_status="pending"), as_of)
    assert not source_is_eligible(source_entry(lifecycle_status="repealed"), as_of)
    assert not source_is_eligible(None, as_of)


def test_eligible_source_ids_excludes_ineligible_entries() -> None:
    document = {
        "schema_version": "source-catalog-v1",
        "sources": [
            source_entry(id="eligible_source"),
            source_entry(id="expired_source", valid_until="2026-01-01"),
            source_entry(id="unapproved_source", review_status="pending"),
            source_entry(id="repealed_source", lifecycle_status="repealed"),
        ],
    }

    eligible = eligible_source_ids(document, date.fromisoformat(AS_OF))

    assert eligible == {"eligible_source"}


def test_expired_source_stops_being_indexed_when_the_date_advances() -> None:
    catalog = catalog_document()
    # The fixture catalog documents expiry as a catalog-level rule; confirm the
    # current as-of indexes the corpus and a later as-of refuses to.
    assert validate_catalog(catalog, as_of=date.fromisoformat("2026-12-31")).ok
    assert not validate_catalog(catalog, as_of=date.fromisoformat("2027-01-01")).ok
    assert build_retriever(as_of="2026-12-31").indexed_passage_count == 12
    with pytest.raises(CatalogRejectedError):
        build_retriever(as_of="2027-01-01")


# --- empty corpus -----------------------------------------------------------


def test_empty_catalog_and_empty_passage_set_return_no_candidates() -> None:
    retriever = Retriever.from_documents(
        load_catalog(EMPTY_CATALOG),
        {"schema_version": PASSAGE_SET_SCHEMA_VERSION, "passages": []},
        date.fromisoformat(AS_OF),
    )

    assert retriever.eligible_source_count == 0
    assert retriever.indexed_passage_count == 0
    assert retriever.excluded_passage_count == 0
    assert retriever.search("¿Qué es la condicionalidad?", k=5) == ()


# --- no-network guarantee ---------------------------------------------------


def test_retrieval_never_opens_a_network_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbid(*args, **kwargs):
        raise AssertionError("retrieval must not touch the network")

    monkeypatch.setattr(socket, "socket", _forbid)

    retriever = build_retriever()
    candidates = retriever.search("¿Cómo se describe el riego del olivar?", k=5)
    refused = run_cli(
        "--catalog",
        str(fixture("catalog_expired.json")),
        "--passages",
        str(fixture(PASSAGE_FIXTURE)),
        "--as-of",
        AS_OF,
    )

    assert candidates[0].passage_id == "fixture-p-riego-olivar-1"
    assert refused.returncode == 2


# --- baseline CLI -----------------------------------------------------------


def test_cli_prints_the_measured_baseline() -> None:
    result = baseline_cli()

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "hit@5: " in result.stdout
    assert "recall@5: " in result.stdout
    assert "MRR: " in result.stdout
    assert "expected fixture-p-solicitud-1 -> rank 1" in result.stdout
    assert "expected fixture-p-titular-1 -> not retrieved within k=5" in result.stdout
    assert "thresholds are not release gates" in result.stdout


def test_cli_json_mode_is_machine_readable() -> None:
    result = baseline_cli("--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["as_of"] == AS_OF
    assert report["k"] == 5
    assert report["thresholds_are_release_gates"] is False
    assert report["index"] == {
        "eligible_sources": 3,
        "indexed_passages": 12,
        "excluded_passages_ineligible_source": 0,
    }
    assert report["metrics"]["questions"] == 7
    assert report["metrics"]["hit_at_k"] == pytest.approx(6 / 7)
    assert report["metrics"]["recall_at_k"] == pytest.approx(6 / 7)
    assert report["metrics"]["mrr"] == pytest.approx(6 / 7)


def test_cli_run_is_deterministic() -> None:
    first = baseline_cli()
    second = baseline_cli()

    assert first.stdout == second.stdout
    assert first.returncode == second.returncode == 0


def test_cli_fail_on_miss_is_off_by_default_and_opt_in_is_exit_one() -> None:
    default = baseline_cli()
    strict = baseline_cli("--fail-on-miss")

    assert default.returncode == 0
    assert strict.returncode == 1
    assert strict.stdout == default.stdout


def test_cli_empty_corpus_reports_zero_candidates() -> None:
    result = run_cli("--catalog", str(EMPTY_CATALOG), "--as-of", AS_OF, "--k", "5")

    assert result.returncode == 0, result.stderr
    assert "eligible sources: 0" in result.stdout
    assert "indexed passages: 0" in result.stdout
    assert "no evaluation questions supplied" in result.stdout


def test_cli_without_passages_returns_no_candidates_for_questions() -> None:
    result = run_cli(
        "--catalog",
        str(CANONICAL_CATALOG),
        "--eval",
        str(fixture(EVAL_FIXTURE)),
        "--as-of",
        AS_OF,
        "--k",
        "5",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["index"]["indexed_passages"] == 0
    assert report["metrics"]["hit_at_k"] == 0.0
    assert all(not question["hit"] for question in report["questions"])
    assert all(question["retrieved_passage_ids"] == [] for question in report["questions"])


def test_cli_rejects_an_ineligible_catalog_with_exit_two() -> None:
    result = run_cli(
        "--catalog",
        str(fixture("catalog_expired.json")),
        "--passages",
        str(fixture(PASSAGE_FIXTURE)),
        "--as-of",
        AS_OF,
    )

    assert result.returncode == 2
    assert "$.sources[0].valid_until" in result.stderr
    assert result.stdout == ""


def test_cli_rejects_an_unknown_source_reference_with_exit_two() -> None:
    result = run_cli(
        "--catalog",
        str(fixture(CATALOG_FIXTURE)),
        "--passages",
        str(fixture("passages_unknown_source.json")),
        "--as-of",
        AS_OF,
    )

    assert result.returncode == 2
    assert "$.passages[0].source_id" in result.stderr
    assert result.stdout == ""


def test_cli_missing_catalog_exits_unreadable() -> None:
    result = run_cli("--catalog", str(fixture("does_not_exist.json")), "--as-of", AS_OF)

    assert result.returncode == 2
    assert "cannot read catalog file" in result.stderr


def test_cli_rejects_a_malformed_eval_file_with_exit_two(tmp_path: Path) -> None:
    broken = tmp_path / "eval.jsonl"
    broken.write_text('{"question": "¿Qué es?"}\n', encoding="utf-8")

    result = run_cli(
        "--catalog",
        str(fixture(CATALOG_FIXTURE)),
        "--passages",
        str(fixture(PASSAGE_FIXTURE)),
        "--eval",
        str(broken),
        "--as-of",
        AS_OF,
    )

    assert result.returncode == 2
    assert "expected_passage_ids" in result.stderr


def test_cli_rejects_a_non_positive_window() -> None:
    result = baseline_cli("--k", "0")

    assert result.returncode == 2
    assert "--k must be a positive integer" in result.stderr


# --- contract sync and fixture hygiene --------------------------------------


def test_schema_declares_the_same_fields_as_the_validator() -> None:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    passage = schema["$defs"]["passage"]

    assert schema["properties"]["schema_version"]["const"] == PASSAGE_SET_SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"schema_version", "passages"}
    assert set(passage["required"]) == set(PASSAGE_REQUIRED_KEYS)
    assert set(passage["properties"]) == set(PASSAGE_REQUIRED_KEYS | PASSAGE_OPTIONAL_KEYS)
    assert passage["additionalProperties"] is False
    assert set(passage["properties"]["applicability"]["properties"]) == set(
        APPLICABILITY_KEYS
    )
    assert set(passage["properties"]["applicability"]["properties"]["water_regime"]["enum"]) == set(
        WATER_REGIMES
    )
    assert set(
        passage["properties"]["applicability"]["properties"]["production_method"]["enum"]
    ) == set(PRODUCTION_METHODS)


def test_catalog_fixture_passes_the_accepted_gate() -> None:
    report = validate_catalog(catalog_document(), as_of=date.fromisoformat(AS_OF))

    assert report.ok, report.format_issues()


def test_fixtures_are_labelled_synthetic_and_contain_no_real_legal_claim() -> None:
    catalog = catalog_document()
    passages = passage_document()

    for source in catalog["sources"]:
        assert "fixture" in source["title"]
        assert "no es una norma real" in source["title"]
    for passage in passages["passages"]:
        assert passage["text"].startswith("Fragmento sintético de prueba")
        assert "prueba" in passage["text"]
        # No real deadlines, amounts, or article claims are asserted.
        assert "€" not in passage["text"]
        assert "%" not in passage["text"]
        assert not any(character.isdigit() for character in passage["text"])


def test_canonical_source_catalog_is_unchanged_and_reviewed() -> None:
    document = load_catalog(CANONICAL_CATALOG)

    assert len(document["sources"]) == 4
    assert all(source["review_status"] == "approved" for source in document["sources"])
    assert CATALOG_SCHEMA_FILE.exists()
