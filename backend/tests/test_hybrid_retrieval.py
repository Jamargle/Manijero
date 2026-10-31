"""Focused tests for opt-in hybrid (BM25 + vector) retrieval.

Everything here runs in the default backend environment: no ``chromadb``, no
``torch``, no model. A deterministic four-keyword embedder and an in-memory
vector searcher stand in for BGE-M3 and Chroma, so these tests pin the fusion
math, the retriever seam, the fail-closed fallbacks, the store manifest and
freshness contract, environment selection, and the unchanged ``/ask`` contract.
The Chroma adapter itself is covered by ``test_vector_store_chroma.py`` when the
optional runtime is installed.

No test here claims retrieval quality, legal coverage, or a latency figure.
"""

import io
import json
import logging
import math
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import retrieval_backend  # noqa: E402  (path setup must run first)
from app.ask_api import (  # noqa: E402
    AskResponse,
    CorpusDocuments,
    get_active_campaign,
    get_as_of_date,
    get_corpus_documents,
)
from app.embedding_index import IndexInputs, PassageEmbeddingIndex  # noqa: E402
from app.embeddings import EmbeddingExecutionError, load_model_spec  # noqa: E402
from app.hybrid_retrieval import (  # noqa: E402
    HybridBackend,
    HybridComponents,
    HybridConfigError,
    HybridRanker,
    HybridSettings,
    failure_code,
    load_hybrid_settings,
    reciprocal_rank_fusion,
    validate_hybrid_config,
)
from app.main import app  # noqa: E402
from app.pilot_logging import LOGGER_NAME, configure_operational_logging  # noqa: E402
from app.retrieval import Retriever, load_passage_set  # noqa: E402
from app.retrieval_backend import (  # noqa: E402
    Bm25Backend,
    backend_from_environment,
    get_retrieval_backend,
)
from app.source_catalog import load_catalog  # noqa: E402
from app.vector_store import (  # noqa: E402
    MANIFEST_NAME,
    STORE_INVALID,
    STORE_MISSING,
    STORE_STALE,
    STORE_UP_TO_DATE,
    VectorMatch,
    VectorStoreError,
    build_manifest,
    documents_sha256,
    manifest_status,
    read_manifest,
    store_status,
    validate_manifest,
    vectors_sha256,
    write_store,
)

TESTS = Path(__file__).resolve().parent
RETRIEVAL = TESTS / "fixtures" / "retrieval"
CLARIFICATION = TESTS / "fixtures" / "clarification"
FIXTURE_SPEC = TESTS / "fixtures" / "embeddings" / "spec.json"
PINNED_HYBRID_CONFIG = BACKEND_ROOT / "config" / "hybrid_retrieval.json"
SCRIPT = BACKEND_ROOT / "scripts" / "manage_vector_store.py"
AS_OF = date(2026, 10, 13)
CAMPAIGN = "2026"
DIGEST = "a" * 64
SECRET_QUESTION = "¿Cuándo presento la solicitud de Josefa García, DNI 12345678Z?"


# --- deterministic stand-ins ----------------------------------------------------


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


class KeywordEmbedder:
    """Four-dimension bag-of-keywords embedder; unit length; deterministic."""

    def __init__(self, keywords: Sequence[str] = ("riego", "secano", "solicitud", "regadio")) -> None:
        self._keywords = tuple(keywords)
        self.calls: List[Tuple[str, ...]] = []

    model_id = "fixture/embedding-model"
    model_revision = "0123456789abcdef0123456789abcdef01234567"
    normalized = True

    @property
    def dimension(self) -> int:
        return len(self._keywords)

    def embed(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        self.calls.append(tuple(texts))
        vectors = []
        for text in texts:
            normalized = _normalize(text)
            raw = [float(normalized.count(keyword)) + 0.01 for keyword in self._keywords]
            norm = math.sqrt(sum(value * value for value in raw))
            vectors.append(tuple(value / norm for value in raw))
        return tuple(vectors)


class FailingEmbedder(KeywordEmbedder):
    def embed(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        raise EmbeddingExecutionError("encode_failed")


class LeakyEmbedder(KeywordEmbedder):
    """Raises a third-party style error whose message echoes the input."""

    def embed(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        raise RuntimeError("could not encode: {}".format(texts[0]))


class MemoryStore:
    """In-memory vector searcher reusing the accepted cosine search."""

    def __init__(self, index: PassageEmbeddingIndex, manifest: Optional[Dict[str, Any]] = None) -> None:
        self._index = index
        self.manifest = manifest or {}
        self.passage_count = index.passage_count
        self.queries = 0

    def query(self, vector: Sequence[float], depth: int) -> Tuple[VectorMatch, ...]:
        self.queries += 1
        return tuple(
            VectorMatch(passage_id=match.passage_id, similarity=match.score, rank=match.rank)
            for match in self._index.search_vector(vector, depth)
        )


class FailingStore(MemoryStore):
    def query(self, vector: Sequence[float], depth: int) -> Tuple[VectorMatch, ...]:
        raise VectorStoreError("store_query_failed")


class FixedRanker:
    def __init__(self, ranking: Sequence[Tuple[str, Any]]) -> None:
        self.ranking = list(ranking)
        self.calls = 0

    def rank(self, question: str, lexical: Tuple[Tuple[str, float], ...]) -> Sequence[Tuple[str, Any]]:
        self.calls += 1
        return self.ranking


def settings(**overrides: Any) -> HybridSettings:
    values = {"rrf_k": 60, "candidate_depth": 20, "vector_min_similarity": 0.0, "config_sha256": DIGEST}
    values.update(overrides)
    return HybridSettings(**values)


def spec():
    return load_model_spec(FIXTURE_SPEC)


def retrieval_retriever() -> Retriever:
    return Retriever.from_documents(
        load_catalog(RETRIEVAL / "catalog.json"),
        load_passage_set(RETRIEVAL / "passages.json"),
        AS_OF,
        active_campaign=CAMPAIGN,
    )


def clarification_documents() -> CorpusDocuments:
    return CorpusDocuments(
        catalog=load_catalog(CLARIFICATION / "catalog.json"),
        passages=load_passage_set(CLARIFICATION / "passages.json"),
    )


def clarification_retriever() -> Retriever:
    documents = clarification_documents()
    return Retriever.from_documents(documents.catalog, documents.passages, AS_OF, CAMPAIGN)


def inputs() -> IndexInputs:
    return IndexInputs(catalog_sha256=DIGEST, passages_sha256=DIGEST, as_of=AS_OF.isoformat(), active_campaign=CAMPAIGN)


def index_for(retriever: Retriever, embedder: Optional[KeywordEmbedder] = None) -> PassageEmbeddingIndex:
    return PassageEmbeddingIndex.build(retriever.indexed_documents(), embedder or KeywordEmbedder())


def manifest_for(retriever: Retriever, index: Optional[PassageEmbeddingIndex] = None) -> Dict[str, Any]:
    index = index or index_for(retriever)
    vectors = {passage_id: index.vector(passage_id) for passage_id in index.passage_ids}
    return build_manifest(index, spec(), inputs(), retriever.indexed_documents(), DIGEST, vectors_sha256(vectors))


def components_for(retriever: Retriever, embedder: Optional[KeywordEmbedder] = None, store: Any = None) -> HybridComponents:
    index = index_for(retriever)
    return HybridComponents(
        spec=spec(),
        embedder=embedder or KeywordEmbedder(),
        store=store or MemoryStore(index, manifest_for(retriever, index)),
        settings=settings(),
    )


@pytest.fixture
def captured_log():
    logger = logging.getLogger(LOGGER_NAME)
    previous = list(logger.handlers)
    logger.handlers.clear()
    stream = io.StringIO()
    configure_operational_logging(stream)
    try:
        yield stream
    finally:
        logger.handlers.clear()
        logger.handlers.extend(previous)


# --- Reciprocal Rank Fusion -------------------------------------------------------


def test_rrf_sums_one_over_k_plus_rank_across_lists() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]], rrf_k=60, depth=20))

    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["c"] == pytest.approx(1 / 62)


def test_rrf_orders_best_first_and_breaks_ties_by_ascending_id() -> None:
    fused = reciprocal_rank_fusion([["b", "a"], ["a", "b"]], rrf_k=60, depth=20)

    assert [passage_id for passage_id, _ in fused] == ["a", "b"]
    assert fused[0][1] == fused[1][1]


def test_rrf_truncates_each_list_to_depth_and_ignores_repeats() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "a", "b", "c"]], rrf_k=1, depth=2))

    assert fused == {"a": pytest.approx(1 / 2), "b": pytest.approx(1 / 3)}


def test_rrf_is_identical_across_repeated_runs() -> None:
    rankings = [["x", "y", "z"], ["z", "w", "x"]]

    assert reciprocal_rank_fusion(rankings, 60, 20) == reciprocal_rank_fusion(rankings, 60, 20)


def test_rrf_rejects_non_positive_parameters() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], rrf_k=0, depth=5)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], rrf_k=60, depth=0)


# --- Retriever seam -------------------------------------------------------------------


def test_an_identity_ranker_reproduces_the_default_bm25_search() -> None:
    retriever = retrieval_retriever()
    identity = retriever.with_ranker(type("Identity", (), {"rank": lambda self, q, lexical: lexical})())

    assert retriever.uses_ranker is False
    assert identity.uses_ranker is True
    assert identity.search("solicitud única", k=5) == retriever.search("solicitud única", k=5)


def test_a_ranker_returning_nothing_yields_no_candidates() -> None:
    # Fails toward abstention, never toward an unranked answer.
    assert retrieval_retriever().with_ranker(FixedRanker([])).search("solicitud única", k=5) == ()


def test_with_ranker_leaves_the_original_retriever_untouched() -> None:
    retriever = retrieval_retriever()
    before = retriever.search("solicitud", k=5)

    retriever.with_ranker(FixedRanker([("fixture-p-riego-olivar-1", 1.0)]))

    assert retriever.search("solicitud", k=5) == before
    assert retriever.uses_ranker is False


def test_a_ranker_can_reorder_and_add_admitted_passages_with_dense_ranks() -> None:
    retriever = retrieval_retriever().with_ranker(
        FixedRanker([("fixture-p-riego-olivar-1", 0.5), ("fixture-p-solicitud-1", 0.25)])
    )

    candidates = retriever.search("solicitud", k=5)

    assert [candidate.passage_id for candidate in candidates] == [
        "fixture-p-riego-olivar-1",
        "fixture-p-solicitud-1",
    ]
    assert [candidate.rank for candidate in candidates] == [1, 2]
    assert candidates[0].score == 0.5
    assert candidates[0].url  # citation metadata comes from the admitted record


def test_a_ranker_cannot_introduce_unknown_duplicate_or_non_finite_candidates() -> None:
    retriever = retrieval_retriever().with_ranker(
        FixedRanker(
            [
                ("not-an-admitted-passage", 9.0),
                ("fixture-p-solicitud-1", 1.0),
                ("fixture-p-solicitud-1", 0.9),
                ("fixture-p-solicitud-2", float("nan")),
                ("fixture-p-cuaderno-1", True),
                ("fixture-p-olivar-1", 0.1),
            ]
        )
    )

    candidates = retriever.search("solicitud", k=5)

    assert [candidate.passage_id for candidate in candidates] == ["fixture-p-solicitud-1", "fixture-p-olivar-1"]


def test_ranker_never_runs_for_a_question_without_lexical_match() -> None:
    ranker = FixedRanker([("fixture-p-solicitud-1", 1.0)])
    retriever = retrieval_retriever().with_ranker(ranker)

    assert retriever.search("zzzz qqqq", k=5) == ()
    assert retriever.search("   ", k=5) == ()
    assert retriever.search("solicitud", k=0) == ()
    assert ranker.calls == 0


def test_ranker_cannot_see_passages_of_an_excluded_campaign() -> None:
    other_campaign = Retriever.from_documents(
        load_catalog(RETRIEVAL / "catalog.json"),
        load_passage_set(RETRIEVAL / "passages.json"),
        AS_OF,
        active_campaign="2025",
    )
    excluded = {passage_id for passage_id, _ in retrieval_retriever().indexed_documents()} - {
        passage_id for passage_id, _ in other_campaign.indexed_documents()
    }
    assert excluded
    ranker = FixedRanker([(passage_id, 1.0) for passage_id in sorted(excluded)])

    candidates = other_campaign.with_ranker(ranker).search("solicitud", k=5)

    assert not {candidate.passage_id for candidate in candidates} & excluded


# --- HybridRanker -----------------------------------------------------------------------


def test_hybrid_ranker_fuses_bm25_with_vector_candidates() -> None:
    retriever = clarification_retriever()
    embedder = KeywordEmbedder()
    store = MemoryStore(index_for(retriever))
    ranker = HybridRanker(embedder, store, settings())

    candidates = retriever.with_ranker(ranker).search("riego en secano", k=5)

    ids = [candidate.passage_id for candidate in candidates]
    assert ids[0] == "fixture-clar-riego-secano-1"
    assert set(ids) <= {passage_id for passage_id, _ in retriever.indexed_documents()}
    assert ranker.last_trace.used_vector is True
    assert embedder.calls[-1] == ("riego en secano",)
    assert store.queries == 1


def test_hybrid_ranker_matches_rrf_over_both_lists() -> None:
    retriever = clarification_retriever()
    store = MemoryStore(index_for(retriever))
    embedder = KeywordEmbedder()
    question = "solicitud de riego"
    lexical = [candidate.passage_id for candidate in retriever.search(question, k=20)]
    vector = [match.passage_id for match in store.query(embedder.embed([question])[0], 20)]
    expected = [passage_id for passage_id, _ in reciprocal_rank_fusion([lexical, vector], 60, 20)]

    candidates = retriever.with_ranker(HybridRanker(embedder, store, settings())).search(question, k=20)

    assert [candidate.passage_id for candidate in candidates] == expected


def test_vector_matches_at_or_below_the_floor_are_ignored() -> None:
    retriever = clarification_retriever()
    store = MemoryStore(index_for(retriever))
    bm25 = retriever.search("secano", k=5)

    fused = retriever.with_ranker(
        HybridRanker(KeywordEmbedder(), store, settings(vector_min_similarity=0.9999))
    ).search("secano", k=5)

    assert [candidate.passage_id for candidate in fused] == [candidate.passage_id for candidate in bm25]


@pytest.mark.parametrize("embedder,store_type", [(FailingEmbedder(), MemoryStore), (KeywordEmbedder(), FailingStore)])
def test_hybrid_ranker_falls_back_to_the_bm25_ranking_on_failure(embedder, store_type, captured_log) -> None:
    retriever = clarification_retriever()
    ranker = HybridRanker(embedder, store_type(index_for(retriever)), settings())

    fused = retriever.with_ranker(ranker).search("riego en secano", k=5)

    assert fused == retriever.search("riego en secano", k=5)
    assert ranker.last_trace.used_vector is False
    assert ranker.last_trace.fallback_reason in {"encode_failed", "store_query_failed"}
    assert "hybrid_retrieval_fallback" in captured_log.getvalue()


def test_fallback_logs_never_echo_a_third_party_message(captured_log) -> None:
    retriever = clarification_retriever()
    ranker = HybridRanker(LeakyEmbedder(), MemoryStore(index_for(retriever)), settings())

    retriever.with_ranker(ranker).search(SECRET_QUESTION, k=5)

    log = captured_log.getvalue()
    assert ranker.last_trace.fallback_reason == "RuntimeError"
    assert "Josefa" not in log and "12345678Z" not in log and "solicitud" not in log


def test_failure_code_uses_fixed_codes_or_type_names_only() -> None:
    assert failure_code(VectorStoreError("store_open_failed")) == "store_open_failed"
    assert failure_code(HybridConfigError("hybrid_config_rrf_k")) == "hybrid_config_rrf_k"
    assert failure_code(ValueError("text with Josefa")) == "ValueError"


# --- hybrid configuration --------------------------------------------------------------


def valid_config() -> Dict[str, Any]:
    return json.loads(PINNED_HYBRID_CONFIG.read_text(encoding="utf-8"))


def test_pinned_hybrid_configuration_documents_rrf_with_k_60() -> None:
    loaded = load_hybrid_settings(PINNED_HYBRID_CONFIG)

    assert (loaded.rrf_k, loaded.candidate_depth, loaded.vector_min_similarity) == (60, 20, 0.0)
    assert len(loaded.config_sha256) == 64


@pytest.mark.parametrize(
    "key,value,code",
    [
        ("unexpected", 1, "hybrid_config_unknown_keys"),
        ("schema_version", "hybrid-retrieval-v0", "hybrid_config_schema_version"),
        ("fusion", "weighted_sum", "hybrid_config_fusion"),
        ("rrf_k", True, "hybrid_config_rrf_k"),
        ("rrf_k", 0, "hybrid_config_rrf_k"),
        ("rrf_k", 60.0, "hybrid_config_rrf_k"),
        ("candidate_depth", 101, "hybrid_config_candidate_depth"),
        ("candidate_depth", 0, "hybrid_config_candidate_depth"),
        ("vector_min_similarity", 1.0, "hybrid_config_vector_min_similarity"),
        ("vector_min_similarity", -0.1, "hybrid_config_vector_min_similarity"),
        ("vector_min_similarity", "0.2", "hybrid_config_vector_min_similarity"),
    ],
)
def test_hybrid_configuration_is_closed(key: str, value: Any, code: str) -> None:
    document = valid_config()
    document[key] = value

    with pytest.raises(HybridConfigError, match=code):
        validate_hybrid_config(document)


def test_unreadable_hybrid_configuration_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "hybrid.json"
    broken.write_text("{", encoding="utf-8")

    with pytest.raises(HybridConfigError, match="hybrid_config_unreadable"):
        load_hybrid_settings(broken)
    with pytest.raises(HybridConfigError, match="hybrid_config_unreadable"):
        load_hybrid_settings(tmp_path / "absent.json")


# --- store manifest and freshness --------------------------------------------------------


def write_manifest(directory: Path, manifest: Dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def test_manifest_records_pin_inputs_ids_and_digests_but_no_text() -> None:
    retriever = clarification_retriever()
    manifest = manifest_for(retriever)

    assert manifest["model"] == spec().index_metadata()
    assert manifest["passage_ids"] == sorted(passage_id for passage_id, _ in retriever.indexed_documents())
    assert manifest["inputs"]["documents_sha256"] == documents_sha256(retriever.indexed_documents())
    serialized = json.dumps(manifest, ensure_ascii=False)
    for _, text in retriever.indexed_documents():
        assert text not in serialized


def test_documents_digest_is_order_independent_and_text_sensitive() -> None:
    documents = [("b", "segundo"), ("a", "primero")]

    assert documents_sha256(documents) == documents_sha256(list(reversed(documents)))
    assert documents_sha256(documents) != documents_sha256([("b", "segundo"), ("a", "primero.")])


def test_vectors_digest_detects_a_changed_float32_value() -> None:
    assert vectors_sha256({"a": [0.5, 0.5]}) != vectors_sha256({"a": [0.5, 0.25]})
    assert vectors_sha256({"a": [0.5]}) == vectors_sha256({"a": (0.5,)})


def test_manifest_must_match_the_index_documents() -> None:
    retriever = clarification_retriever()
    index = index_for(retriever)

    with pytest.raises(VectorStoreError, match="store_documents_mismatch"):
        build_manifest(index, spec(), inputs(), retriever.indexed_documents()[1:], DIGEST, DIGEST)


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda m: m.pop("vectors_sha256"), "manifest_unknown_keys"),
        (lambda m: m.update(extra=1), "manifest_unknown_keys"),
        (lambda m: m.update(schema_version="chroma-passage-store-v0"), "manifest_schema_version"),
        (lambda m: m.update(collection="other"), "manifest_invalid"),
        (lambda m: m.update(distance="l2"), "manifest_invalid"),
        (lambda m: m["inputs"].update(documents_sha256="xyz"), "manifest_invalid"),
        (lambda m: m["inputs"].update(passage_count=True), "manifest_invalid"),
        (lambda m: m.update(passage_ids=m["passage_ids"][1:]), "manifest_count_mismatch"),
        (lambda m: m.update(passage_ids=list(reversed(m["passage_ids"]))), "manifest_unsorted_or_duplicate"),
        (lambda m: m["model"].update(embedding_dimension=0), "manifest_invalid"),
    ],
)
def test_manifest_contract_is_closed(mutate, code: str) -> None:
    manifest = manifest_for(clarification_retriever())
    mutate(manifest)

    with pytest.raises(VectorStoreError, match=code):
        validate_manifest(manifest)


def test_store_status_reports_missing_invalid_and_up_to_date(tmp_path: Path) -> None:
    retriever = clarification_retriever()
    documents = retriever.indexed_documents()

    missing = store_status(tmp_path / "absent", spec(), CAMPAIGN, documents)
    broken_dir = tmp_path / "broken"
    broken_dir.mkdir()
    (broken_dir / MANIFEST_NAME).write_text("not json", encoding="utf-8")
    invalid = store_status(broken_dir, spec(), CAMPAIGN, documents)
    good = write_manifest(tmp_path / "good", manifest_for(retriever))
    current = store_status(good, spec(), CAMPAIGN, documents)

    assert (missing.state, missing.reasons) == (STORE_MISSING, ("store_missing",))
    assert (invalid.state, invalid.reasons) == (STORE_INVALID, ("manifest_malformed",))
    assert current.state == STORE_UP_TO_DATE and current.up_to_date
    assert read_manifest(good)["passage_ids"]


def test_store_is_stale_when_campaign_documents_or_pin_change() -> None:
    retriever = clarification_retriever()
    manifest = manifest_for(retriever)
    documents = retriever.indexed_documents()
    edited = ((documents[0][0], documents[0][1] + " Texto añadido."),) + documents[1:]
    other_pin = dict(manifest, model=dict(manifest["model"], model_revision="f" * 40, config_sha256="b" * 64))

    campaign = manifest_status(manifest, spec(), "2027", documents)
    text = manifest_status(manifest, spec(), CAMPAIGN, edited)
    expired = manifest_status(manifest, spec(), CAMPAIGN, documents[1:])
    pin = manifest_status(other_pin, spec(), CAMPAIGN, documents)

    assert (campaign.state, campaign.reasons) == (STORE_STALE, ("active_campaign_changed",))
    assert text.reasons == ("documents_changed",)
    assert expired.reasons == ("documents_changed",)
    assert pin.state == STORE_STALE
    assert set(pin.reasons) == {"model_revision_changed", "model_config_changed"}


def test_store_write_refuses_knowledge_and_non_store_directories(tmp_path: Path) -> None:
    retriever = clarification_retriever()
    index = index_for(retriever)
    arbitrary = tmp_path / "operator-notes"
    arbitrary.mkdir()
    (arbitrary / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(VectorStoreError, match="unsafe_store_path"):
        write_store(BACKEND_ROOT.parent / "knowledge" / "store", index, spec(), inputs(), retriever.indexed_documents(), DIGEST)
    with pytest.raises(VectorStoreError, match="store_path_not_a_store"):
        write_store(arbitrary, index, spec(), inputs(), retriever.indexed_documents(), DIGEST)
    assert (arbitrary / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (BACKEND_ROOT.parent / "knowledge" / "store").exists()


# --- environment selection and backend --------------------------------------------------


def test_bm25_is_the_default_retrieval_mode() -> None:
    assert isinstance(backend_from_environment({}), Bm25Backend)
    assert backend_from_environment({"MANIJERO_RETRIEVAL_MODE": "bm25"}).mode == "bm25"


@pytest.mark.parametrize(
    "environ,reason",
    [
        ({"MANIJERO_RETRIEVAL_MODE": "vector"}, "retrieval_mode_invalid"),
        ({"MANIJERO_RETRIEVAL_MODE": "hybrid"}, "hybrid_not_configured"),
        ({"MANIJERO_RETRIEVAL_MODE": "hybrid", "MANIJERO_VECTOR_STORE": "/tmp/store"}, "hybrid_not_configured"),
        ({"MANIJERO_RETRIEVAL_MODE": "hybrid", "MANIJERO_EMBEDDING_ARTIFACT": "/tmp/model"}, "hybrid_not_configured"),
    ],
)
def test_incomplete_or_unknown_modes_fall_back_to_bm25(environ, reason: str, captured_log) -> None:
    backend = backend_from_environment(environ)

    assert isinstance(backend, Bm25Backend)
    assert backend.reason == reason
    assert reason in captured_log.getvalue()


def test_configured_hybrid_mode_defers_all_loading_to_the_first_request(tmp_path: Path) -> None:
    backend = backend_from_environment(
        {
            "MANIJERO_RETRIEVAL_MODE": "hybrid",
            "MANIJERO_VECTOR_STORE": str(tmp_path / "missing-store"),
            "MANIJERO_EMBEDDING_ARTIFACT": str(tmp_path / "missing-model"),
        }
    )
    retriever = clarification_retriever()

    assert isinstance(backend, HybridBackend)
    attached = backend.attach(retriever, CAMPAIGN)

    assert attached is retriever  # the missing store fails closed to BM25
    assert backend.status(retriever, CAMPAIGN).state == "invalid"


def test_hybrid_backend_attaches_a_ranker_only_while_fresh(captured_log) -> None:
    retriever = clarification_retriever()
    backend = HybridBackend(lambda: components_for(retriever))

    fresh = backend.attach(retriever, CAMPAIGN)
    stale_campaign = backend.attach(retriever, "2027")

    assert fresh.uses_ranker is True
    assert stale_campaign is retriever
    log = captured_log.getvalue()
    assert '"active":"hybrid"' in log and '"active":"bm25"' in log
    assert "active_campaign_changed" in log


def test_hybrid_backend_loads_once_and_remembers_a_failure() -> None:
    calls = []

    def loader() -> HybridComponents:
        calls.append(1)
        raise VectorStoreError("store_open_failed")

    backend = HybridBackend(loader)
    retriever = clarification_retriever()

    assert backend.attach(retriever, CAMPAIGN) is retriever
    assert backend.attach(retriever, CAMPAIGN) is retriever
    assert len(calls) == 1
    assert backend.status(retriever, CAMPAIGN).reasons == ("store_open_failed",)


def test_hybrid_backend_never_raises_from_attach() -> None:
    class Broken:
        manifest = {"inputs": {}}

    retriever = clarification_retriever()
    backend = HybridBackend(lambda: HybridComponents(spec=spec(), embedder=KeywordEmbedder(), store=Broken(), settings=settings()))

    assert backend.attach(retriever, CAMPAIGN) is retriever


def test_the_service_imports_no_vector_runtime_or_hybrid_module() -> None:
    code = (
        "import sys\n"
        "import app.main\n"
        "names = ['chromadb', 'torch', 'app.vector_store', 'app.hybrid_retrieval', 'app.embeddings']\n"
        "print([name for name in names if name in sys.modules])\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(BACKEND_ROOT))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_process_backend_is_built_once_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retrieval_backend, "_DEFAULT_BACKEND", None)
    monkeypatch.delenv("MANIJERO_RETRIEVAL_MODE", raising=False)

    first = get_retrieval_backend()

    assert first is get_retrieval_backend()
    assert isinstance(first, Bm25Backend)


# --- /ask contract with hybrid ranking --------------------------------------------------


@pytest.fixture
def ask_client():
    app.dependency_overrides[get_corpus_documents] = clarification_documents
    app.dependency_overrides[get_as_of_date] = lambda: AS_OF
    app.dependency_overrides[get_active_campaign] = lambda: CAMPAIGN
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def ask(client: TestClient, backend: Any, question: str, land_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    app.dependency_overrides[get_retrieval_backend] = lambda: backend
    response = client.post(
        "/ask",
        json={"question": question, "land_context": land_context or {"mode": "general", "lands": []}},
    )
    assert response.status_code == 200
    body = response.json()
    AskResponse.model_validate(body)
    return body


def test_hybrid_ask_keeps_the_response_contract_and_cites_admitted_sources(ask_client) -> None:
    retriever = clarification_retriever()
    hybrid = HybridBackend(lambda: components_for(retriever))

    body = ask(ask_client, hybrid, "¿Cuándo se presenta la solicitud anual de ejemplo?")

    assert body["status"] == "answered"
    assert set(body) == {"status", "answer", "sources", "land_scope", "land_ids_to_choose"}
    catalog_urls = {source["original_url"] for source in clarification_documents().catalog["sources"]}
    assert body["sources"] and all(source["url"] in catalog_urls for source in body["sources"])


@pytest.mark.parametrize(
    "question,land_context",
    [
        ("¿Cuándo se presenta la solicitud anual de ejemplo?", None),
        ("¿Qué ayuda de pesca me corresponde?", None),
        ("¿Cuándo se presenta la solicitud anual de 2031?", None),
        (
            "¿Puedo regar mi olivar de ejemplo?",
            {
                "mode": "all_active",
                "lands": [
                    {"id": "land-a", "water_regime": "irrigated"},
                    {"id": "land-b", "water_regime": "dryland"},
                ],
            },
        ),
    ],
)
def test_failing_hybrid_answers_exactly_like_bm25(ask_client, question: str, land_context) -> None:
    retriever = clarification_retriever()
    failing = HybridBackend(lambda: components_for(retriever, embedder=FailingEmbedder()))

    assert ask(ask_client, failing, question, land_context) == ask(ask_client, Bm25Backend(), question, land_context)


def test_hybrid_keeps_zero_evidence_abstention(ask_client) -> None:
    retriever = clarification_retriever()
    embedder = KeywordEmbedder()
    hybrid = HybridBackend(lambda: components_for(retriever, embedder=embedder))

    body = ask(ask_client, hybrid, "¿Qué ayuda de pesca me corresponde?")

    assert body["status"] == "abstained"
    assert body["sources"] == []
    assert embedder.calls == []  # no lexical match: the vector side never ran


# --- operator CLI (manifest-only paths) ------------------------------------------------


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, cwd=str(BACKEND_ROOT))


def check_arguments(store: Path, catalog: Path = CLARIFICATION / "catalog.json") -> List[str]:
    return [
        "check",
        "--config", str(FIXTURE_SPEC),
        "--catalog", str(catalog),
        "--passages", str(CLARIFICATION / "passages.json"),
        "--as-of", AS_OF.isoformat(),
        "--active-campaign", CAMPAIGN,
        "--store", str(store),
        "--json",
    ]


def test_cli_check_reports_missing_and_up_to_date_stores(tmp_path: Path) -> None:
    missing = run_cli(*check_arguments(tmp_path / "absent"))
    good = write_manifest(tmp_path / "store", manifest_for(clarification_retriever()))
    current = run_cli(*check_arguments(good))

    assert missing.returncode == 1 and json.loads(missing.stdout)["state"] == "missing"
    assert current.returncode == 0, current.stderr
    assert json.loads(current.stdout)["state"] == "up_to_date"


def test_cli_check_refuses_an_invalid_corpus(tmp_path: Path) -> None:
    broken = tmp_path / "catalog.json"
    broken.write_text("{", encoding="utf-8")

    result = run_cli(*check_arguments(tmp_path / "store", catalog=broken))

    assert result.returncode == 2
    assert result.stderr.strip() == "error: invalid_corpus"
