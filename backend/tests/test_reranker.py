"""Offline tests for the optional local reranker: pin, artifact, ranking, selection, runtime.

No model, no network, no ``torch``, no ``chromadb``: a fake scorer, a fake hybrid loader, and a
synthetic labelled artifact (``tests/fixtures/reranker``) stand in for everything real. Nothing
here claims retrieval quality or a latency figure.
"""

import hashlib
import io
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import test_hybrid_retrieval as hyb  # noqa: E402  (path setup must run first)
from app import answer_cache, pinned_download, reranker, retrieval_backend  # noqa: E402
from app.hybrid_retrieval import HybridBackend  # noqa: E402
from app.pilot_logging import LOGGER_NAME, configure_operational_logging  # noqa: E402
from app.reranker import (  # noqa: E402
    LocalBgeReranker,
    RerankerBackend,
    RerankerError,
    RerankerSettings,
    RerankingRanker,
    check_pin_document,
    effective_state,
    load_reranker_settings,
    load_reranker_spec,
    verify_reranker_artifact,
)
from app.retrieval_backend import Bm25Backend, backend_from_environment  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "reranker"
FIXTURE_PIN = FIXTURES / "pin.json"
FIXTURE_ARTIFACT = FIXTURES / "artifact"
REAL_PIN = BACKEND_ROOT / "config" / "bge_reranker_v2_m3.json"
REAL_SETTINGS = BACKEND_ROOT / "config" / "reranker.json"
SECRET = "SENTINEL-passage-or-question-text-7731"


def settings(**overrides: Any) -> RerankerSettings:
    values: Dict[str, Any] = {
        "default_state": "off",
        "candidate_depth": 20,
        "max_tokens": 512,
        "batch_size": 8,
        "config_sha256": "b" * 64,
    }
    values.update(overrides)
    return RerankerSettings(**values)


def pin_document() -> Dict[str, Any]:
    return json.loads(FIXTURE_PIN.read_text(encoding="utf-8"))


class TextScorer:
    """Scores a passage by how many query words it contains, plus a fixed bonus table."""

    def __init__(self, bonus: Optional[Dict[str, float]] = None) -> None:
        self.bonus = bonus or {}
        self.calls: List[Tuple[str, Tuple[str, ...]]] = []

    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        self.calls.append((query, tuple(texts)))
        words = set(query.lower().split())
        return tuple(
            float(len(words & set(text.lower().split()))) + self.bonus.get(text, 0.0) for text in texts
        )


class FixedScorer:
    def __init__(self, scores: Sequence[Any]) -> None:
        self._scores = tuple(scores)

    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        return self._scores


class RaisingScorer:
    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        raise RuntimeError("scoring failed for: {} / {}".format(query, texts[0]))


def lexical(*ids: str) -> Tuple[Tuple[str, float], ...]:
    return tuple((passage_id, 10.0 - position) for position, passage_id in enumerate(ids))


def ranker_for(scorer: Any, texts: Dict[str, Optional[str]], **overrides: Any) -> RerankingRanker:
    return RerankingRanker(None, scorer, settings(**overrides), texts.get)


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


# --- 1. The pin is reviewed, closed, and fits the 5 GB limit ---------------------------------


def test_the_committed_pin_is_valid_pinned_and_under_five_gigabytes() -> None:
    spec = load_reranker_spec(REAL_PIN)

    assert spec.model_id == "BAAI/bge-reranker-v2-m3"
    assert len(spec.model_revision) == 40 and spec.model_revision != reranker.UNPINNED_REVISION
    assert spec.total_bytes <= reranker.MAX_MODEL_BYTES
    assert {item.path for item in spec.files} >= {"config.json", "model.safetensors"}
    kinds = {item.path: item.digest_kind for item in spec.files}
    assert kinds["model.safetensors"] == "sha256" and kinds["config.json"] == "git_blob_sha1"


def test_the_fixture_pin_is_valid() -> None:
    assert check_pin_document(pin_document()) == ()


def test_a_placeholder_revision_fails_with_its_own_code(tmp_path: Path) -> None:
    document = dict(pin_document(), model_revision="unpinned")
    target = tmp_path / "pin.json"
    target.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RerankerError, match="^reranker_pin_unpinned$"):
        load_reranker_spec(target)


@pytest.mark.parametrize(
    "mutate,fragment",
    [
        (lambda d: d.update(extra="x"), "$.extra"),
        (lambda d: d.pop("license"), "$.license"),
        (lambda d: d.update(license="  "), "$.license"),
        (lambda d: d.update(model_id="someone/else"), "$.model_id"),
        (lambda d: d.update(model_revision="main"), "$.model_revision"),
        (lambda d: d.update(source_url="http://huggingface.co/BAAI/bge-reranker-v2-m3"), "$.source_url"),
        (lambda d: d.update(source_url="https://example.com/x"), "$.source_url"),
        (lambda d: d.update(schema_version="reranker-model-v0"), "$.schema_version"),
        (lambda d: d["files"][0].update(sha256="a" * 64), "exactly one digest"),
        (lambda d: d["files"][0].pop("git_blob_sha1"), "exactly one digest"),
        (lambda d: d["files"][0].update(path="../config.json"), ".path"),
        (lambda d: d["files"][0].update(path="/abs/config.json"), ".path"),
        (lambda d: d["files"][1].update(path="config.json"), "duplicate path"),
        (lambda d: d["files"][0].update(size=-1), ".size"),
        (lambda d: d["files"][0].update(git_blob_sha1="XYZ"), "git_blob_sha1"),
        (lambda d: d["files"][1].update(sha256="short"), ".sha256"),
        (lambda d: d.update(files=[f for f in d["files"] if f["path"] != "config.json"]), "must pin 'config.json'"),
        (lambda d: d.update(files=[f for f in d["files"] if f["path"] != "model.safetensors"]), "weights"),
        (lambda d: d["files"][1].update(size=5_000_000_001), "must not exceed"),
        (lambda d: d["files"][0].update(unknown=1), "unknown key"),
    ],
)
def test_the_pin_contract_is_closed(mutate, fragment: str) -> None:
    document = pin_document()
    mutate(document)

    issues = check_pin_document(document)

    assert issues and any(fragment in str(issue) for issue in issues), [str(i) for i in issues]


def test_a_pin_that_is_not_an_object_or_unreadable_fails_closed(tmp_path: Path) -> None:
    assert check_pin_document([]) != ()
    with pytest.raises(RerankerError, match="reranker_pin_unreadable"):
        load_reranker_spec(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(RerankerError, match="reranker_pin_malformed"):
        load_reranker_spec(broken)


# --- 2. Artifact verification ----------------------------------------------------------------


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    target = tmp_path / "artifact"
    shutil.copytree(FIXTURE_ARTIFACT, target)
    return target


def fixture_spec() -> reranker.RerankerSpec:
    return load_reranker_spec(FIXTURE_PIN)


def issue_map(report: Any) -> Dict[str, str]:
    return {issue.path: issue.code for issue in report.issues}


def test_a_matching_artifact_verifies_with_both_digest_kinds(artifact: Path) -> None:
    report = verify_reranker_artifact(artifact, fixture_spec())

    assert report.ok and report.checked_files == 6


def test_git_blob_digest_uses_the_blob_prefix() -> None:
    data = b"hello\n"
    hasher = reranker.new_hasher("git_blob_sha1", len(data))
    hasher.update(data)

    assert hasher.hexdigest() == hashlib.sha1(b"blob 6\0hello\n").hexdigest()
    assert hasher.hexdigest() == "ce013625030ba8dba906f756967f9e9ca394464a"  # git hash-object of "hello\n"


def test_a_changed_file_is_a_checksum_mismatch_even_at_the_same_size(artifact: Path) -> None:
    config = artifact / "config.json"
    config.write_bytes(config.read_bytes().replace(b"LABEL_0", b"LABEL_1"))
    weights = artifact / "model.safetensors"
    original = weights.read_bytes()
    weights.write_bytes(bytes(len(original)))

    problems = issue_map(verify_reranker_artifact(artifact, fixture_spec()))

    assert problems["config.json"] == "checksum_mismatch"
    assert problems["model.safetensors"] == "checksum_mismatch"


def test_missing_short_symlinked_and_escaping_files_are_rejected(artifact: Path, tmp_path: Path) -> None:
    (artifact / "tokenizer.json").unlink()
    (artifact / "special_tokens_map.json").write_bytes(b"x")
    outside = tmp_path / "outside.txt"
    outside.write_bytes((artifact / "tokenizer_config.json").read_bytes())
    (artifact / "tokenizer_config.json").unlink()
    (artifact / "tokenizer_config.json").symlink_to(outside)

    problems = issue_map(verify_reranker_artifact(artifact, fixture_spec()))

    assert problems["tokenizer.json"] == "file_missing"
    assert problems["special_tokens_map.json"] == "size_mismatch"
    assert problems["tokenizer_config.json"] == "path_escape"
    document = pin_document()
    document["files"][2]["path"] = "sub/../sentencepiece.bpe.model"
    assert check_pin_document(document)  # a path escape cannot even be pinned


def test_a_symlink_inside_the_folder_is_not_a_regular_file(artifact: Path) -> None:
    (artifact / "copy.bin").write_bytes((artifact / "tokenizer.json").read_bytes())
    (artifact / "tokenizer.json").unlink()
    (artifact / "tokenizer.json").symlink_to(artifact / "copy.bin")

    assert issue_map(verify_reranker_artifact(artifact, fixture_spec()))["tokenizer.json"] == "not_a_regular_file"


def test_a_missing_directory_is_reported(tmp_path: Path) -> None:
    report = verify_reranker_artifact(tmp_path / "nothing", fixture_spec())

    assert issue_map(report) == {"artifact_dir": "directory_missing"}


@pytest.mark.parametrize(
    "config,code",
    [
        ({"architectures": ["XLMRobertaModel"], "id2label": {"0": "L"}}, "architecture_mismatch"),
        ({"id2label": {"0": "L"}}, "architecture_mismatch"),
        ({"architectures": ["XLMRobertaForSequenceClassification"], "id2label": {"0": "A", "1": "B"}}, "label_count_mismatch"),
        ({"architectures": ["XLMRobertaForSequenceClassification"]}, "label_count_mismatch"),
    ],
)
def test_the_model_config_must_be_a_single_score_sequence_classifier(
    tmp_path: Path, config: Dict[str, Any], code: str
) -> None:
    target = tmp_path / "artifact"
    shutil.copytree(FIXTURE_ARTIFACT, target)
    data = json.dumps(config).encode("utf-8")
    (target / "config.json").write_bytes(data)
    document = pin_document()
    document["files"][0] = {
        "path": "config.json",
        "git_blob_sha1": hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(),
        "size": len(data),
    }
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps(document), encoding="utf-8")

    problems = issue_map(verify_reranker_artifact(target, load_reranker_spec(pin)))

    assert problems == {"config.json": code}


def test_num_labels_one_is_accepted(tmp_path: Path) -> None:
    target = tmp_path / "artifact"
    shutil.copytree(FIXTURE_ARTIFACT, target)
    data = json.dumps(
        {"architectures": ["XLMRobertaForSequenceClassification"], "num_labels": 1}
    ).encode("utf-8")
    (target / "config.json").write_bytes(data)
    document = pin_document()
    document["files"][0] = {
        "path": "config.json",
        "git_blob_sha1": hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(),
        "size": len(data),
    }
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps(document), encoding="utf-8")

    assert verify_reranker_artifact(target, load_reranker_spec(pin)).ok


def test_the_cheap_presence_check_needs_every_file_at_its_size(artifact: Path) -> None:
    spec = fixture_spec()
    assert reranker.artifact_present(artifact, spec)
    (artifact / "model.safetensors").write_bytes(b"short")
    assert not reranker.artifact_present(artifact, spec)
    assert not reranker.artifact_present(artifact / "nowhere", spec)


# --- 3. The ranker only re-orders admitted candidates and fails closed ------------------------

TEXTS = {"a": "alpha text", "b": "beta riego text", "c": "gamma text", "d": "delta text"}


def test_it_orders_the_head_by_score_keeps_the_tail_and_never_adds_or_drops() -> None:
    scorer = FixedScorer([0.1, 0.9, 0.5])
    ranker = ranker_for(scorer, TEXTS, candidate_depth=3)

    result = ranker.rank("question", lexical("a", "b", "c", "d"))

    assert [passage_id for passage_id, _ in result] == ["b", "c", "a", "d"]
    assert dict(result) == dict(lexical("a", "b", "c", "d"))  # every id keeps the inner score


def test_ties_keep_the_earlier_rank() -> None:
    ranker = ranker_for(FixedScorer([1.0, 1.0, 1.0]), TEXTS)

    result = ranker.rank("question", lexical("c", "a", "b"))

    assert [passage_id for passage_id, _ in result] == ["c", "a", "b"]


def test_only_the_first_candidate_depth_ids_are_scored() -> None:
    scorer = TextScorer()
    ranker = ranker_for(scorer, TEXTS, candidate_depth=2)

    ranker.rank("riego", lexical("a", "b", "c", "d"))

    assert scorer.calls == [("riego", ("alpha text", "beta riego text"))]


def test_a_single_candidate_or_none_is_returned_without_scoring() -> None:
    scorer = TextScorer()
    ranker = ranker_for(scorer, TEXTS)

    assert ranker.rank("q", lexical("a")) == lexical("a")
    assert ranker.rank("q", ()) == ()
    assert scorer.calls == []


def test_duplicates_from_the_inner_ranking_are_dropped_once() -> None:
    ranker = ranker_for(FixedScorer([1.0, 2.0]), TEXTS)

    result = ranker.rank("q", (("a", 3.0), ("b", 2.0), ("a", 1.0)))

    assert [passage_id for passage_id, _ in result] == ["b", "a"]


@pytest.mark.parametrize(
    "scorer,reason",
    [
        (RaisingScorer(), "reranker_score_failed"),
        (FixedScorer([1.0]), "reranker_score_count"),
        (FixedScorer([1.0, float("nan")]), "reranker_score_not_finite"),
        (FixedScorer([float("inf"), 1.0]), "reranker_score_not_finite"),
        (FixedScorer([True, 1.0]), "reranker_score_not_finite"),
        (FixedScorer(["x", 1.0]), "reranker_score_not_finite"),
    ],
)
def test_any_scorer_problem_returns_the_input_ranking_with_a_fixed_log_code(
    captured_log: io.StringIO, scorer: Any, reason: str
) -> None:
    ranker = ranker_for(scorer, {"a": SECRET + " one", "b": SECRET + " two"})
    base = lexical("a", "b")

    with answer_cache.capture_generation_outcomes() as outcomes:
        result = ranker.rank(SECRET, base)

    assert result == base
    assert outcomes == [answer_cache.DEGRADED_RETRIEVAL]
    logged = captured_log.getvalue()
    assert reason in logged and SECRET not in logged


def test_a_passage_without_text_falls_back_without_scoring(captured_log: io.StringIO) -> None:
    scorer = TextScorer()
    ranker = ranker_for(scorer, {"a": "alpha", "b": None})
    base = lexical("a", "b")

    assert ranker.rank("q", base) == base
    assert scorer.calls == [] and "reranker_text_missing" in captured_log.getvalue()


def test_it_wraps_the_inner_ranking_it_is_given() -> None:
    inner = hyb.FixedRanker([("c", 0.3), ("a", 0.2), ("b", 0.1)])
    ranker = RerankingRanker(inner, FixedScorer([0.0, 0.0, 5.0]), settings(), TEXTS.get)

    result = ranker.rank("q", lexical("a", "b", "c"))

    assert inner.calls == 1
    assert [passage_id for passage_id, _ in result] == ["b", "c", "a"]
    assert ranker.inner is inner


# --- The lexical gate and the retriever stay in charge ---------------------------------------


def reranked_retriever(scorer: Any, base: Any = None, **overrides: Any) -> Any:
    retriever = base if base is not None else hyb.retrieval_retriever()
    return retriever.with_ranker(
        RerankingRanker(retriever.current_ranker, scorer, settings(**overrides), retriever.passage_text)
    )


def test_the_lexical_gate_still_returns_nothing_for_a_zero_match_question() -> None:
    scorer = TextScorer()
    retriever = reranked_retriever(scorer)

    assert retriever.search("pesca submarina marciana", k=5) == ()
    assert scorer.calls == []


def test_over_bm25_it_only_reorders_what_bm25_found() -> None:
    plain = hyb.retrieval_retriever()
    bm25 = plain.search("solicitud única", k=5)
    scorer = TextScorer()
    reranked = reranked_retriever(scorer).search("solicitud única", k=5)

    assert {c.passage_id for c in reranked} == {c.passage_id for c in bm25}
    assert len(reranked) == len(bm25)
    assert [c.rank for c in reranked] == list(range(1, len(reranked) + 1))
    assert scorer.calls and scorer.calls[0][0] == "solicitud única"


def test_a_scorer_that_prefers_the_last_candidate_moves_it_first() -> None:
    plain = hyb.retrieval_retriever()
    bm25 = plain.search("solicitud única", k=5)
    assert len(bm25) >= 2
    last = bm25[-1]
    scorer = TextScorer(bonus={last.excerpt: 100.0})

    reranked = reranked_retriever(scorer).search("solicitud única", k=5)

    assert reranked[0].passage_id == last.passage_id
    assert reranked[0].url == last.url  # citation metadata still comes from the admitted record


def test_over_a_hybrid_inner_ranker_the_reranker_scores_hybrid_candidates() -> None:
    retriever = hyb.retrieval_retriever()
    hybrid = HybridBackend(lambda: hyb.components_for(retriever))
    scorer = TextScorer()
    backend = RerankerBackend(hybrid, lambda: scorer, settings())

    attached = backend.attach(retriever, hyb.CAMPAIGN)

    assert attached.uses_ranker and isinstance(attached.current_ranker, RerankingRanker)
    assert isinstance(attached.current_ranker.inner, hyb.HybridRanker)
    assert attached.search("solicitud única", k=5)
    assert attached.search("pesca submarina marciana", k=5) == ()  # gate kept over hybrid too


def test_a_failing_scorer_over_the_backend_answers_like_the_unreranked_backend() -> None:
    retriever = hyb.retrieval_retriever()
    backend = RerankerBackend(Bm25Backend(), lambda: RaisingScorer(), settings())

    reranked = backend.attach(retriever, hyb.CAMPAIGN).search("solicitud única", k=5)

    assert reranked == retriever.search("solicitud única", k=5)


# --- 4. Off by default; on only by explicit, verified configuration ---------------------------


def test_unset_or_off_returns_todays_backend_and_imports_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(backend_from_environment({}), Bm25Backend)
    assert isinstance(backend_from_environment({"MANIJERO_RERANKER": "off"}), Bm25Backend)
    assert isinstance(backend_from_environment({"MANIJERO_RERANKER": " off "}), Bm25Backend)


def test_importing_the_service_imports_neither_the_reranker_nor_the_runtime() -> None:
    code = (
        "import sys\n"
        "import app.main\n"
        "names = ['app.reranker', 'app.reranker_measure', 'torch', 'transformers', 'chromadb']\n"
        "print([name for name in names if name in sys.modules])\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(BACKEND_ROOT))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_selecting_the_default_backend_with_the_reranker_off_does_not_import_it() -> None:
    code = (
        "import sys\n"
        "from app.retrieval_backend import backend_from_environment\n"
        "backend_from_environment({'MANIJERO_RERANKER': 'off'})\n"
        "backend_from_environment({})\n"
        "print('app.reranker' in sys.modules)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(BACKEND_ROOT))

    assert result.stdout.strip() == "False", result.stderr


def env_for(tmp_path: Path, **extra: str) -> Dict[str, str]:
    values = {
        "MANIJERO_RERANKER": "on",
        "MANIJERO_RERANKER_ARTIFACT": str(FIXTURE_ARTIFACT),
        "MANIJERO_RERANKER_CONFIG": str(FIXTURE_PIN),
        "MANIJERO_RERANKER_SETTINGS": str(REAL_SETTINGS),
    }
    values.update(extra)
    return values


def test_on_wraps_the_configured_backend_and_loads_nothing_yet(tmp_path: Path) -> None:
    backend = backend_from_environment(env_for(tmp_path))

    assert isinstance(backend, RerankerBackend)
    assert isinstance(backend.inner, Bm25Backend) and backend.mode == "bm25"
    assert backend.load_failure is None


def test_on_wraps_hybrid_when_hybrid_is_configured(tmp_path: Path) -> None:
    backend = backend_from_environment(
        env_for(
            tmp_path,
            MANIJERO_RETRIEVAL_MODE="hybrid",
            MANIJERO_VECTOR_STORE=str(tmp_path / "store"),
            MANIJERO_EMBEDDING_ARTIFACT=str(tmp_path / "bge-m3"),
        )
    )

    assert isinstance(backend, RerankerBackend) and backend.mode == "hybrid"
    assert isinstance(backend.inner, HybridBackend)


@pytest.mark.parametrize(
    "overrides",
    [
        {"MANIJERO_RERANKER": "maybe"},
        {"MANIJERO_RERANKER": "ON"},
        {"MANIJERO_RERANKER_ARTIFACT": ""},
        {"MANIJERO_RERANKER_CONFIG": "/nowhere/pin.json"},
        {"MANIJERO_RERANKER_SETTINGS": "/nowhere/settings.json"},
    ],
)
def test_a_missing_or_invalid_setting_keeps_the_unreranked_backend(
    tmp_path: Path, captured_log: io.StringIO, overrides: Dict[str, str]
) -> None:
    backend = backend_from_environment(env_for(tmp_path, **overrides))

    assert isinstance(backend, Bm25Backend)
    assert "reranker_mode" in captured_log.getvalue()


def test_an_unpinned_pin_keeps_the_unreranked_backend(tmp_path: Path) -> None:
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps(dict(pin_document(), model_revision="unpinned")), encoding="utf-8")

    backend = backend_from_environment(env_for(tmp_path, MANIJERO_RERANKER_CONFIG=str(pin)))

    assert isinstance(backend, Bm25Backend)


def test_the_model_loads_lazily_once_and_a_failure_is_remembered(captured_log: io.StringIO) -> None:
    retriever = hyb.retrieval_retriever()
    loads: List[int] = []

    def failing_loader() -> Any:
        loads.append(1)
        raise RerankerError("reranker_artifact_invalid: config.json: checksum_mismatch")

    backend = RerankerBackend(Bm25Backend(), failing_loader, settings())
    assert loads == []

    first = backend.attach(retriever, hyb.CAMPAIGN)
    second = backend.attach(retriever, hyb.CAMPAIGN)

    assert loads == [1] and first is retriever and second is retriever
    assert backend.load_failure == "reranker_artifact_invalid"
    assert "reranker_artifact_invalid" in captured_log.getvalue()
    assert "config.json" not in captured_log.getvalue()


def test_an_artifact_that_does_not_verify_keeps_the_unreranked_ranking(tmp_path: Path) -> None:
    retriever = hyb.retrieval_retriever()
    backend = backend_from_environment(env_for(tmp_path, MANIJERO_RERANKER_ARTIFACT=str(tmp_path / "empty")))

    attached = backend.attach(retriever, hyb.CAMPAIGN)

    assert attached is retriever and backend.load_failure == "reranker_artifact_invalid"


def test_a_verified_artifact_without_a_usable_runtime_keeps_the_unreranked_ranking(tmp_path: Path) -> None:
    # The fixture is not a real model: the runtime is missing (default environment) or refuses it.
    retriever = hyb.retrieval_retriever()
    backend = backend_from_environment(env_for(tmp_path))

    attached = backend.attach(retriever, hyb.CAMPAIGN)

    assert attached is retriever
    assert backend.load_failure in ("reranker_runtime_unavailable", "reranker_model_load_failed")


def test_a_working_loader_runs_once_across_requests() -> None:
    retriever = hyb.retrieval_retriever()
    loads: List[int] = []

    def loader() -> Any:
        loads.append(1)
        return TextScorer()

    backend = RerankerBackend(Bm25Backend(), loader, settings())
    backend.attach(retriever, hyb.CAMPAIGN)
    backend.attach(retriever, hyb.CAMPAIGN)

    assert loads == [1]


# --- 8. Effective state and settings ---------------------------------------------------------


def test_the_committed_settings_ship_the_reranker_off() -> None:
    loaded = load_reranker_settings(REAL_SETTINGS)

    assert loaded.default_state == "off"
    assert (loaded.candidate_depth, loaded.max_tokens, loaded.batch_size) == (20, 512, 8)


@pytest.mark.parametrize(
    "owner,default,expected",
    [(None, "off", "off"), (None, "on", "on"), ("off", "on", "off"), ("on", "off", "on"), ("bogus", "off", "off")],
)
def test_the_owner_line_wins_then_the_repository_default(owner, default, expected) -> None:
    assert effective_state(owner, default) == expected


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(extra=1),
        lambda d: d.pop("batch_size"),
        lambda d: d.update(schema_version="reranker-settings-v0"),
        lambda d: d.update(default_state="maybe"),
        lambda d: d.update(candidate_depth=0),
        lambda d: d.update(candidate_depth=101),
        lambda d: d.update(max_tokens=True),
        lambda d: d.update(batch_size="8"),
    ],
)
def test_settings_are_a_closed_contract(tmp_path: Path, mutate) -> None:
    document = json.loads(REAL_SETTINGS.read_text(encoding="utf-8"))
    mutate(document)
    target = tmp_path / "settings.json"
    target.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(RerankerError):
        load_reranker_settings(target)


def test_unreadable_settings_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(RerankerError, match="reranker_settings_unreadable"):
        load_reranker_settings(tmp_path / "nope.json")


# --- The local runtime (fake torch / transformers) -------------------------------------------


class FakeTensor:
    def __init__(self, values: Sequence[float]) -> None:
        self._values = list(values)

    def detach(self) -> "FakeTensor":
        return self

    def to(self, dtype: Any) -> "FakeTensor":
        return self

    def reshape(self, *shape: int) -> "FakeTensor":
        return self

    def tolist(self) -> List[float]:
        return list(self._values)


class FakeTorch:
    float32 = "float32"

    class _Mode:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *exc: object) -> None:
            return None

    def inference_mode(self) -> "_Mode":
        return self._Mode()


class FakeTokenizer:
    calls: List[Dict[str, Any]] = []

    @classmethod
    def from_pretrained(cls, path: str, **kwargs: Any) -> "FakeTokenizer":
        cls.loaded = (path, kwargs)
        return cls()

    def __call__(self, queries: Sequence[str], texts: Sequence[str], **kwargs: Any) -> Dict[str, Any]:
        FakeTokenizer.calls.append(dict(kwargs, queries=list(queries), texts=list(texts)))
        return {"texts": list(texts)}


class FakeModel:
    @classmethod
    def from_pretrained(cls, path: str, **kwargs: Any) -> "FakeModel":
        cls.loaded = (path, kwargs)
        return cls()

    def eval(self) -> None:
        return None

    def __call__(self, texts: Sequence[str]) -> Any:
        # The raw logit is the text length: no sigmoid, so ordering by logit is observable.
        return type("Output", (), {"logits": FakeTensor([float(len(text)) for text in texts])})()


def fake_runtime() -> Any:
    return reranker._Runtime(torch=FakeTorch(), auto_tokenizer=FakeTokenizer, auto_model=FakeModel)


def test_the_local_reranker_batches_truncates_and_returns_raw_logits(artifact: Path) -> None:
    FakeTokenizer.calls = []
    loaded = LocalBgeReranker.load(
        fixture_spec(), artifact, settings(batch_size=2, max_tokens=64), runtime_loader=fake_runtime
    )

    scores = loaded.score("question", ["a", "bbb", "cc", "dddd", "e"])

    assert scores == (1.0, 3.0, 2.0, 4.0, 1.0)
    assert [len(call["texts"]) for call in FakeTokenizer.calls] == [2, 2, 1]
    assert all(call["max_length"] == 64 and call["truncation"] is True for call in FakeTokenizer.calls)
    assert all(call["queries"] == ["question"] * len(call["texts"]) for call in FakeTokenizer.calls)
    assert FakeModel.loaded[1]["local_files_only"] is True
    assert FakeModel.loaded[1]["trust_remote_code"] is False
    assert FakeModel.loaded[1]["use_safetensors"] is True


def test_the_local_reranker_refuses_an_artifact_that_does_not_verify(artifact: Path) -> None:
    (artifact / "model.safetensors").write_bytes(b"tampered")

    with pytest.raises(RerankerError, match="^reranker_artifact_invalid"):
        LocalBgeReranker.load(fixture_spec(), artifact, settings(), runtime_loader=fake_runtime)


def test_a_missing_runtime_is_a_fixed_code(artifact: Path) -> None:
    def no_runtime() -> Any:
        raise RerankerError("reranker_runtime_unavailable")

    with pytest.raises(RerankerError, match="reranker_runtime_unavailable"):
        LocalBgeReranker.load(fixture_spec(), artifact, settings(), runtime_loader=no_runtime)


def test_a_model_that_cannot_load_raises_a_fixed_code_without_its_text(artifact: Path) -> None:
    class Exploding:
        @classmethod
        def from_pretrained(cls, path: str, **kwargs: Any) -> Any:
            raise OSError(SECRET)

    runtime = reranker._Runtime(torch=FakeTorch(), auto_tokenizer=FakeTokenizer, auto_model=Exploding)

    with pytest.raises(RerankerError) as caught:
        LocalBgeReranker.load(fixture_spec(), artifact, settings(), runtime_loader=lambda: runtime)

    assert str(caught.value) == "reranker_model_load_failed" and SECRET not in str(caught.value)


# --- The shared downloader handles both digest kinds ------------------------------------------


def test_pending_files_carry_the_digest_kind_and_nothing_pending_when_verified(artifact: Path) -> None:
    spec = fixture_spec()
    assert pinned_download.pending_files(spec, artifact) == ()
    (artifact / "config.json").unlink()

    pending = pinned_download.pending_files(spec, artifact)

    assert [(item.path, item.digest_kind) for item in pending] == [("config.json", "git_blob_sha1")]


def test_the_download_url_comes_only_from_the_pin() -> None:
    spec = load_reranker_spec(REAL_PIN)

    assert pinned_download.file_url(spec, "model.safetensors") == (
        "https://huggingface.co/BAAI/bge-reranker-v2-m3/resolve/"
        "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e/model.safetensors"
    )

