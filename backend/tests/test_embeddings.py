"""Focused tests for the pinned local embedding capability.

The fixtures under ``fixtures/embeddings/`` are synthetic: a four-dimension
"model" directory with pinned checksums, not a real model. They exercise the
pin, the fail-closed artifact gate, the pooling/normalization contract, the
derived-index rebuild boundary, and the operator CLI without downloading a
model or importing an optional runtime.

No test in this file claims retrieval quality, Spanish legal coverage, or a
measured latency/RAM figure.
"""

import dataclasses
import hashlib
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import embeddings  # noqa: E402  (path setup must run first)
from app.embedding_index import (  # noqa: E402
    INDEX_INVALID,
    INDEX_MISSING,
    INDEX_STALE,
    INDEX_UP_TO_DATE,
    EmbeddingIndexError,
    IndexInputs,
    PassageEmbeddingIndex,
    build_index_document,
    file_sha256,
    index_status,
    load_index,
    read_index_document,
    write_index_atomic,
)
from app.embeddings import (  # noqa: E402
    ArtifactFile,
    EmbeddingArtifactError,
    EmbeddingConfigError,
    EmbeddingExecutionError,
    EmbeddingInputError,
    EmbeddingModel,
    EmbeddingRuntimeUnavailable,
    EmbeddingModelSpec,
    LocalBgeM3Embedder,
    finalize_vectors,
    load_model_spec,
    validate_embedding_config,
    verify_artifact,
)
from app.retrieval import Retriever, load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "embeddings"
ARTIFACT = FIXTURES / "artifact"
PINNED_CONFIG = BACKEND_ROOT / "config" / "bge_m3_embedding.json"
RETRIEVAL_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retrieval"
SCRIPT = BACKEND_ROOT / "scripts" / "manage_embeddings.py"
AS_OF = "2026-10-13"
CAMPAIGN = "2026"


# --- helpers ----------------------------------------------------------------


def fixture(name: str) -> Path:
    return FIXTURES / name


def spec() -> EmbeddingModelSpec:
    return load_model_spec(fixture("spec.json"))


def config_document() -> dict:
    return json.loads(fixture("spec.json").read_text(encoding="utf-8"))


def test_config_document_validates() -> None:
    report = validate_embedding_config(config_document())
    assert report.ok
    assert report.schema_version == "embedding-model-v1"
    assert report.checked_files == 3


def test_pinned_bge_m3_config_is_frozen() -> None:
    pinned = load_model_spec(PINNED_CONFIG)
    assert pinned.model_id == "BAAI/bge-m3"
    assert pinned.model_revision == "5617a9f61b028005a4858fdac845db406aefb181"
    assert pinned.license == "MIT"
    assert pinned.embedding_dimension == 1024
    assert pinned.pooling == "cls"
    assert pinned.normalize is True
    weights = pinned.artifact_file("pytorch_model.bin")
    assert weights is not None
    assert weights.sha256 == "b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38"
    assert weights.size == 2_271_145_830
    assert pinned.config_sha256 == hashlib.sha256(
        json.dumps(
            json.loads(PINNED_CONFIG.read_text(encoding="utf-8")),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.pop("license"),
        lambda document: document.update({"unknown": 1}),
        lambda document: document.update({"model_revision": "main"}),
        lambda document: document.update({"model_revision": "a" * 39}),
        lambda document: document.update({"model_id": "bge-m3"}),
        lambda document: document.update({"source_url": "http://example.test/model"}),
        lambda document: document.update({"embedding_dimension": 0}),
        lambda document: document.update({"embedding_dimension": True}),
        lambda document: document.update({"max_tokens": 0}),
        lambda document: document.update({"batch_size": 0}),
        lambda document: document.update({"pooling": "max"}),
        lambda document: document.update({"normalize": "yes"}),
        lambda document: document.update({"dtype": "float16"}),
        lambda document: document.update({"files": []}),
        lambda document: document["files"][0].update({"path": "../config.json"}),
        lambda document: document["files"][0].update({"path": "/etc/passwd"}),
        lambda document: document["files"][0].update({"sha256": "A" * 64}),
        lambda document: document["files"][0].update({"size": -1}),
        lambda document: document["files"][0].pop("size"),
        lambda document: document["files"].append(dict(document["files"][0])),
        lambda document: document["files"].pop(0),
    ],
)
def test_invalid_configuration_fails_closed(mutate) -> None:
    document = config_document()
    mutate(document)
    report = validate_embedding_config(document)
    assert not report.ok
    assert report.issues


def test_config_loader_rejects_unreadable_and_malformed(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingConfigError) as missing:
        load_model_spec(tmp_path / "absent.json")
    assert "config_unreadable" in str(missing.value)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    with pytest.raises(EmbeddingConfigError) as error:
        load_model_spec(malformed)
    assert "config_malformed" in str(error.value)


def test_verify_artifact_accepts_a_matching_pin() -> None:
    report = verify_artifact(ARTIFACT, spec())
    assert report.ok, report.format_issues()
    assert report.checked_files == 3
    assert report.ignored_files == 1
    assert report.ignored_bytes == len(b"not part of the pin\n")
    assert report.verified_bytes == sum(
        (ARTIFACT / name).stat().st_size
        for name in ("config.json", "1_Pooling/config.json", "weights.bin")
    )


def test_verify_artifact_rejects_a_checksum_mismatch() -> None:
    report = verify_artifact(ARTIFACT, load_model_spec(fixture("spec_bad_checksum.json")))
    assert not report.ok
    assert [str(issue) for issue in report.issues] == ["config.json: checksum_mismatch"]


def test_verify_artifact_rejects_a_missing_file() -> None:
    report = verify_artifact(ARTIFACT, load_model_spec(fixture("spec_missing_file.json")))
    assert not report.ok
    assert "missing.bin: file_missing" in report.format_issues()


def test_verify_artifact_rejects_a_dimension_mismatch() -> None:
    report = verify_artifact(
        ARTIFACT, load_model_spec(fixture("spec_dimension_mismatch.json"))
    )
    assert not report.ok
    assert "config.json: dimension_mismatch" in report.format_issues()


def test_verify_artifact_rejects_a_pooling_mismatch() -> None:
    report = verify_artifact(ARTIFACT, load_model_spec(fixture("spec_pooling_mismatch.json")))
    assert not report.ok
    assert "1_Pooling/config.json: pooling_mismatch" in report.format_issues()


def test_verify_artifact_rejects_a_too_small_context() -> None:
    report = verify_artifact(ARTIFACT, load_model_spec(fixture("spec_context_too_small.json")))
    assert not report.ok
    assert "config.json: context_too_small" in report.format_issues()


def test_verify_artifact_requires_a_directory(tmp_path: Path) -> None:
    report = verify_artifact(tmp_path / "absent", spec())
    assert not report.ok
    assert [str(issue) for issue in report.issues] == ["artifact_dir: directory_missing"]


def test_verify_artifact_rejects_an_escaping_path() -> None:
    unsafe = dataclasses.replace(
        spec(), files=spec().files + (ArtifactFile("../outside.json", "0" * 64, 0),)
    )
    report = verify_artifact(ARTIFACT, unsafe)
    assert not report.ok
    assert [str(issue) for issue in report.issues] == ["../outside.json: unsafe_path"]


def test_verify_artifact_rejects_a_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, root)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside bytes")
    link = root / "link-escape.bin"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not available on this platform")
    pinned = dataclasses.replace(
        spec(),
        files=spec().files
        + (ArtifactFile("link-escape.bin", hashlib.sha256(b"outside bytes").hexdigest(), 13),),
    )
    report = verify_artifact(root, pinned)
    assert not report.ok
    assert "link-escape.bin: path_escape" in report.format_issues()


# --- pooling and normalization ----------------------------------------------


def test_cls_pooling_and_normalization() -> None:
    vectors = finalize_vectors([[[3.0, 4.0], [100.0, 100.0]]], "cls", True)
    assert len(vectors) == 1
    assert vectors[0] == pytest.approx((0.6, 0.8))


def test_mean_pooling_ignores_padding() -> None:
    vectors = finalize_vectors(
        [[[1.0, 0.0], [0.0, 1.0], [9.0, 9.0]]],
        "mean",
        False,
        attention_mask=[[1, 1, 0]],
    )
    assert vectors[0] == pytest.approx((0.5, 0.5))


def test_mean_pooling_requires_a_used_token() -> None:
    with pytest.raises(EmbeddingInputError) as error:
        finalize_vectors([[[1.0, 0.0]]], "mean", False, attention_mask=[[0]])
    assert "empty_text" in str(error.value)


@pytest.mark.parametrize(
    "hidden_states, pooling, normalize, mask, code",
    [
        ([[[1.0]]], "max", True, None, "unsupported_pooling"),
        ([[]], "cls", True, None, "empty_hidden_state"),
        ([[[1.0, 0.0]]], "cls", True, [[1, 0]], "attention_mask_mismatch"),
        ([[[0.0, 0.0]]], "cls", True, None, "zero_vector"),
        ([[[1.0, 0.0]]], "cls", True, [], "attention_mask_mismatch"),
        ([[[float("nan"), 0.0]]], "cls", True, None, "non_finite_vector"),
    ],
)
def test_pooling_failures_are_typed(hidden_states, pooling, normalize, mask, code) -> None:
    with pytest.raises(EmbeddingExecutionError) as error:
        finalize_vectors(hidden_states, pooling, normalize, mask)
    assert code in str(error.value)


# --- local embedder with an injected runtime --------------------------------


class _NullContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc_info: object) -> None:
        return None


class _FakeTorch:
    float32 = "float32"

    def __init__(self) -> None:
        self._threads = 4

    def inference_mode(self) -> _NullContext:
        return _NullContext()

    def get_num_threads(self) -> int:
        return self._threads

    def set_num_threads(self, value: int) -> None:
        self._threads = value


class _Rows:
    def __init__(self, rows) -> None:
        self._rows = rows

    def tolist(self):
        return self._rows

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, index: int):
        return self._rows[index]


class _FakeEncoded(dict):
    pass


def _ids_for(text: str):
    tokens = text.split()
    first = (len(text) % 5) + 1
    return [first, 2, 3][: max(1, min(3, len(tokens)))]


class _FakeTokenizer:
    last_call = None

    def __call__(self, texts, **kwargs):
        self.last_kwargs = kwargs
        rows = [_ids_for(text) for text in texts]
        mask = [[1] * len(row) for row in rows]
        return _FakeEncoded(input_ids=_Rows(rows), attention_mask=_Rows(mask))


class _FakeAutoTokenizer:
    last_call = None

    @classmethod
    def from_pretrained(cls, path, **kwargs):
        cls.last_call = {"path": path, **kwargs}
        return _FakeTokenizer()


class _FakeOutput:
    def __init__(self, hidden_states) -> None:
        self.last_hidden_state = hidden_states


class _Hidden:
    def __init__(self, values) -> None:
        self._values = values

    def detach(self):
        return self

    def to(self, dtype):
        return self

    def tolist(self):
        return self._values


class _FakeModel:
    def __init__(self) -> None:
        self.evaluated = False

    def eval(self):
        self.evaluated = True
        return self

    def __call__(self, **encoded):
        hidden = []
        for row in encoded["input_ids"].tolist():
            hidden.append(
                [
                    [float(token_id), float(position + 1), 1.0, 0.5]
                    for position, token_id in enumerate(row)
                ]
            )
        return _FakeOutput(_Hidden(hidden))


class _FakeAutoModel:
    last_call = None

    @classmethod
    def from_pretrained(cls, path, **kwargs):
        cls.last_call = {"path": path, **kwargs}
        return _FakeModel()


def fake_runtime() -> embeddings._Runtime:
    return embeddings._Runtime(
        torch=_FakeTorch(), auto_tokenizer=_FakeAutoTokenizer, auto_model=_FakeAutoModel
    )


def load_fake_embedder(monkeypatch: pytest.MonkeyPatch, spec_override=None) -> LocalBgeM3Embedder:
    monkeypatch.setattr(embeddings, "_load_runtime", lambda: fake_runtime())
    return LocalBgeM3Embedder.load(spec_override or spec(), ARTIFACT)


def test_answer_route_never_imports_the_optional_embedding_runtime() -> None:
    code = (
        "import sys\n"
        "import app.main\n"
        "print('app.embeddings' in sys.modules or 'app.embedding_index' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_local_embedder_uses_the_injected_runtime_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAutoTokenizer.last_call = None
    _FakeAutoModel.last_call = None
    embedder = load_fake_embedder(monkeypatch)

    assert isinstance(embedder, EmbeddingModel)
    assert embedder.model_id == "fixture/embedding-model"
    assert embedder.dimension == 4
    assert embedder.normalized is True
    assert embedder.thread_count == 4

    tokenizer_call = _FakeAutoTokenizer.last_call
    assert tokenizer_call is not None
    assert tokenizer_call["local_files_only"] is True
    assert tokenizer_call["trust_remote_code"] is False
    model_call = _FakeAutoModel.last_call
    assert model_call is not None
    assert model_call["local_files_only"] is True
    assert model_call["trust_remote_code"] is False
    assert model_call["use_safetensors"] is False
    assert model_call["dtype"] == "float32"

    vectors = embedder.embed(["primera consulta", "segunda consulta"])
    assert len(vectors) == 2
    assert all(len(vector) == 4 for vector in vectors)
    for vector in vectors:
        assert sum(value * value for value in vector) == pytest.approx(1.0)


def test_embedder_batches_and_records_the_token_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = load_fake_embedder(monkeypatch)
    embedded = embedder.embed(["uno", "dos", "tres"])
    assert len(embedded) == 3


def test_local_embedder_sets_thread_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embeddings, "_load_runtime", lambda: fake_runtime())
    embedder = LocalBgeM3Embedder.load(spec(), ARTIFACT, threads=2)
    assert embedder.thread_count == 2


def test_local_embedder_rejects_artifact_mismatch_before_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        embeddings, "_load_runtime", lambda: pytest.fail("runtime must not be imported")
    )
    with pytest.raises(EmbeddingArtifactError) as error:
        LocalBgeM3Embedder.load(
            load_model_spec(fixture("spec_bad_checksum.json")), ARTIFACT
        )
    assert "artifact_invalid" in str(error.value)
    assert "checksum_mismatch" in str(error.value)


def test_local_embedder_reports_a_missing_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable():
        raise EmbeddingRuntimeUnavailable("runtime_unavailable")

    monkeypatch.setattr(embeddings, "_load_runtime", unavailable)
    with pytest.raises(EmbeddingRuntimeUnavailable):
        LocalBgeM3Embedder.load(spec(), ARTIFACT)


def test_runtime_import_forces_offline_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    with pytest.raises(EmbeddingRuntimeUnavailable) as error:
        embeddings._load_runtime()
    assert "runtime_unavailable" in str(error.value)
    assert embeddings.OFFLINE_ENVIRONMENT["HF_HUB_OFFLINE"] == "1"
    import os

    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


@pytest.mark.parametrize("texts", [["  "], [""], [None], "texto", b"texto"])
def test_embedder_rejects_invalid_input(monkeypatch: pytest.MonkeyPatch, texts) -> None:
    embedder = load_fake_embedder(monkeypatch)
    with pytest.raises(EmbeddingInputError) as error:
        embedder.embed(texts)
    assert "invalid_text_input" in str(error.value)
    assert "texto" not in str(error.value)


def test_embedder_returns_empty_for_no_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = load_fake_embedder(monkeypatch)
    assert embedder.embed([]) == ()


def test_embedder_failure_hides_the_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embeddings, "_load_runtime", lambda: fake_runtime())
    embedder = LocalBgeM3Embedder.load(spec(), ARTIFACT)

    def broken(**encoded):
        raise RuntimeError("secret personal detail: parcela de Juan")

    embedder._model = broken  # type: ignore[assignment]
    with pytest.raises(EmbeddingExecutionError) as error:
        embedder.embed(["datos personales de la parcela"])
    message = str(error.value)
    assert "encode_failed" in message
    assert "datos personales" not in message
    assert "Juan" not in message


def test_embedder_does_not_open_a_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embeddings, "_load_runtime", lambda: fake_runtime())
    embedder = LocalBgeM3Embedder.load(spec(), ARTIFACT)

    def forbid(*args, **kwargs):
        raise AssertionError("embedding must not use the network")

    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    assert embedder.embed(["consulta local"]) != ()


# --- derived index ----------------------------------------------------------


class _StaticModel:
    def __init__(self, mapping, dimension: int = 4) -> None:
        self._mapping = mapping
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        return "fixture/embedding-model"

    @property
    def model_revision(self) -> str:
        return "0123456789abcdef0123456789abcdef01234567"

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def normalized(self) -> bool:
        return True

    def embed(self, texts):
        return tuple(tuple(self._mapping.get(text, (1.0, 0.0, 0.0, 0.0))) for text in texts)


def test_retriever_exposes_only_eligible_documents() -> None:
    retriever = Retriever.from_documents(
        load_catalog(RETRIEVAL_FIXTURES / "catalog.json"),
        load_passage_set(RETRIEVAL_FIXTURES / "passages.json"),
        date.fromisoformat(AS_OF),
        active_campaign=CAMPAIGN,
    )
    documents = retriever.indexed_documents()
    assert len(documents) == retriever.indexed_passage_count
    assert [passage_id for passage_id, _ in documents] == sorted(
        passage_id for passage_id, _ in documents
    )
    assert all(text.strip() for _, text in documents)


def test_index_builds_and_searches_deterministically() -> None:
    model = _StaticModel({"consulta": (1.0, 0.0, 0.0, 0.0)})
    index = PassageEmbeddingIndex.build(
        (("b-passage", "texto dos"), ("a-passage", "texto uno")), model
    )
    assert index.passage_ids == ("a-passage", "b-passage")
    # Both documents fall back to the same vector, so the tie breaks by id.
    matches = index.search_text(model, "consulta")
    assert [match.passage_id for match in matches] == ["a-passage", "b-passage"]
    assert [match.rank for match in matches] == [1, 2]
    assert model.dimension == index.dimension


def test_index_rejects_duplicate_or_blank_documents() -> None:
    with pytest.raises(EmbeddingIndexError) as error:
        PassageEmbeddingIndex.build(
            (("a", "texto"), ("a", "texto")), _StaticModel({})
        )
    assert "index_duplicate_id" in str(error.value)
    with pytest.raises(EmbeddingIndexError) as blank:
        PassageEmbeddingIndex.build((("a", "  "),), _StaticModel({}))
    assert "index_invalid_document" in str(blank.value)


def test_index_search_fails_closed_on_bad_vectors() -> None:
    index = PassageEmbeddingIndex.build((("a", "texto"),), _StaticModel({"texto": (1, 0, 0, 0)}))
    with pytest.raises(EmbeddingIndexError) as error:
        index.search_vector([1.0, 0.0])
    assert "query_dimension_mismatch" in str(error.value)
    with pytest.raises(EmbeddingIndexError) as zero:
        index.search_vector([0.0, 0.0, 0.0, 0.0])
    assert "query_zero_vector" in str(zero.value)
    assert index.search_vector((1, 0, 0, 0), k=0) == ()


def test_index_document_records_the_pin_and_inputs_and_no_text(tmp_path: Path) -> None:
    model = _StaticModel({})
    index = PassageEmbeddingIndex.build(
        (("a-passage", "contenido revisado uno"), ("b-passage", "texto dos")), model
    )
    inputs = IndexInputs("a" * 64, "b" * 64, AS_OF, CAMPAIGN)
    document = build_index_document(index, spec(), inputs)
    serialized = json.dumps(document)
    assert "texto dos" not in serialized
    assert "texto uno" not in serialized
    assert document["model"]["model_revision"] == spec().model_revision
    assert document["inputs"]["indexed_passage_count"] == 2

    target = tmp_path / "embedding-index.json"
    write_index_atomic(target, document, spec())
    assert not (tmp_path / "embedding-index.json.tmp").exists()
    assert index_status(target, spec(), inputs).state == INDEX_UP_TO_DATE
    reloaded = load_index(read_index_document(target), spec())
    assert reloaded.passage_ids == index.passage_ids


def test_index_status_reports_missing_stale_and_invalid(tmp_path: Path) -> None:
    target = tmp_path / "embedding-index.json"
    inputs = IndexInputs("a" * 64, "b" * 64, AS_OF, CAMPAIGN)
    assert index_status(target, spec(), inputs).state == INDEX_MISSING

    index = PassageEmbeddingIndex.build((("a-passage", "texto"),), _StaticModel({}))
    document = build_index_document(index, spec(), inputs)
    write_index_atomic(target, document, spec())
    assert index_status(target, spec(), inputs).state == INDEX_UP_TO_DATE

    changed_passages = dataclasses.replace(inputs, passages_sha256="c" * 64)
    status = index_status(target, spec(), changed_passages)
    assert status.state == INDEX_STALE
    assert status.reasons == ("passages_changed",)

    changed_campaign = dataclasses.replace(inputs, active_campaign="2027")
    status = index_status(target, spec(), changed_campaign)
    assert status.reasons == ("active_campaign_changed",)

    changed_model = dataclasses.replace(spec(), model_revision="f" * 40)
    status = index_status(target, changed_model, inputs)
    assert status.state == INDEX_STALE
    assert status.reasons == ("model_revision_changed",)

    changed_dimension = dataclasses.replace(spec(), embedding_dimension=8)
    status = index_status(target, changed_dimension, inputs)
    assert status.state == INDEX_STALE
    assert status.reasons == ("dimension_changed",)

    target.write_text("{not json", encoding="utf-8")
    status = index_status(target, spec(), inputs)
    assert status.state == INDEX_INVALID
    assert status.reasons == ("index_malformed",)


def test_index_document_validation_is_closed(tmp_path: Path) -> None:
    index = PassageEmbeddingIndex.build((("a-passage", "texto"),), _StaticModel({}))
    inputs = IndexInputs("a" * 64, "b" * 64, AS_OF, CAMPAIGN)
    document = build_index_document(index, spec(), inputs)

    cases = []
    tampered = json.loads(json.dumps(document))
    tampered["unknown"] = True
    cases.append((tampered, "index_unknown_keys"))
    tampered = json.loads(json.dumps(document))
    tampered["schema_version"] = "other"
    cases.append((tampered, "index_schema_version"))
    tampered = json.loads(json.dumps(document))
    tampered["inputs"]["indexed_passage_count"] = 2
    cases.append((tampered, "index_count_mismatch"))
    tampered = json.loads(json.dumps(document))
    tampered["passages"][0]["vector"] = [1.0, 0.0]
    cases.append((tampered, "vector_length_mismatch"))
    tampered = json.loads(json.dumps(document))
    tampered["passages"][0]["vector"] = [1.0, 0.0, 0.0, "x"]
    cases.append((tampered, "vector_not_numeric"))
    tampered = json.loads(json.dumps(document))
    tampered["passages"][0]["vector"] = [1.0, 0.0, 0.0, 1e309]
    cases.append((tampered, "vector_not_finite"))
    tampered = json.loads(json.dumps(document))
    tampered["inputs"]["catalog_sha256"] = "not-a-digest"
    cases.append((tampered, "index_invalid"))
    tampered = json.loads(json.dumps(document))
    tampered["model"]["config_sha256"] = "0" * 64
    cases.append((tampered, "model_config_mismatch"))

    for tampered_document, code in cases:
        with pytest.raises(EmbeddingIndexError) as error:
            write_index_atomic(tmp_path / "index.json", tampered_document, spec())
        assert code in str(error.value), code
        assert not (tmp_path / "index.json").exists()


def test_write_refuses_a_knowledge_path() -> None:
    index = PassageEmbeddingIndex.build((("a-passage", "texto"),), _StaticModel({}))
    document = build_index_document(index, spec(), IndexInputs("a" * 64, "b" * 64, AS_OF, CAMPAIGN))
    target = REPO_ROOT / "knowledge" / "embedding-index.json"
    with pytest.raises(EmbeddingIndexError) as error:
        write_index_atomic(target, document, spec())
    assert "unsafe_index_path" in str(error.value)
    assert not target.exists()


# --- operator CLI -----------------------------------------------------------


def load_cli_module():
    spec_ = importlib.util.spec_from_file_location("manage_embeddings", SCRIPT)
    assert spec_ is not None and spec_.loader is not None
    module = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(module)
    return module


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def test_cli_verify_reports_a_matching_pin() -> None:
    result = run_cli(
        "verify", "--config", str(fixture("spec.json")), "--artifact", str(ARTIFACT)
    )
    assert result.returncode == 0, result.stderr
    assert "model_revision: 0123456789abcdef0123456789abcdef01234567" in result.stdout
    assert "checked_files: 3" in result.stdout
    assert "texto" not in result.stdout


def test_cli_verify_fails_on_a_checksum_mismatch() -> None:
    result = run_cli(
        "verify",
        "--config",
        str(fixture("spec_bad_checksum.json")),
        "--artifact",
        str(ARTIFACT),
    )
    assert result.returncode == 1
    assert "checksum_mismatch" in result.stdout


def test_cli_verify_measure_fails_closed_without_the_optional_runtime() -> None:
    result = run_cli(
        "verify",
        "--config",
        str(fixture("spec.json")),
        "--artifact",
        str(ARTIFACT),
        "--measure",
    )
    assert result.returncode == 2
    assert "error:" in result.stderr


def test_cli_check_reports_a_missing_index(tmp_path: Path) -> None:
    result = run_cli(
        "check",
        "--config",
        str(fixture("spec.json")),
        "--catalog",
        str(RETRIEVAL_FIXTURES / "catalog.json"),
        "--passages",
        str(RETRIEVAL_FIXTURES / "passages.json"),
        "--as-of",
        AS_OF,
        "--active-campaign",
        CAMPAIGN,
        "--index",
        str(tmp_path / "embedding-index.json"),
    )
    assert result.returncode == 1
    assert "state: missing" in result.stdout


def test_cli_build_and_check_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_cli_module()
    model = _StaticModel({})

    class _Loader:
        @classmethod
        def load(cls, spec_, artifact_dir, *, device="cpu", threads=None):
            return model

    monkeypatch.setattr(module, "LocalBgeM3Embedder", _Loader)
    index_path = tmp_path / "embedding-index.json"
    arguments = [
        "--config",
        str(fixture("spec.json")),
        "--artifact",
        str(ARTIFACT),
        "--catalog",
        str(RETRIEVAL_FIXTURES / "catalog.json"),
        "--passages",
        str(RETRIEVAL_FIXTURES / "passages.json"),
        "--as-of",
        AS_OF,
        "--active-campaign",
        CAMPAIGN,
        "--index",
        str(index_path),
    ]
    assert module.main(["build", *arguments]) == 0
    assert index_path.exists()
    check_arguments = [
        argument
        for argument in arguments
        if argument not in {"--artifact", str(ARTIFACT)}
    ]
    assert module.main(["check", *check_arguments]) == 0

    stale = list(check_arguments)
    stale[stale.index("--active-campaign") + 1] = "2027"
    assert module.main(["check", *stale]) == 1


def test_cli_build_refuses_a_knowledge_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_cli_module()

    class _Loader:
        @classmethod
        def load(cls, spec_, artifact_dir, *, device="cpu", threads=None):
            return _StaticModel({})

    monkeypatch.setattr(module, "LocalBgeM3Embedder", _Loader)
    target = REPO_ROOT / "knowledge" / "embedding-index.json"
    assert target.exists() is False
    result = module.main(
        [
            "build",
            "--config",
            str(fixture("spec.json")),
            "--artifact",
            str(ARTIFACT),
            "--catalog",
            str(RETRIEVAL_FIXTURES / "catalog.json"),
            "--passages",
            str(RETRIEVAL_FIXTURES / "passages.json"),
            "--as-of",
            AS_OF,
            "--active-campaign",
            CAMPAIGN,
            "--index",
            str(target),
        ]
    )
    assert result == 2
    assert target.exists() is False


def test_cli_check_rejects_an_invalid_corpus(tmp_path: Path) -> None:
    result = run_cli(
        "check",
        "--config",
        str(fixture("spec.json")),
        "--catalog",
        str(RETRIEVAL_FIXTURES / "catalog.json"),
        "--passages",
        str(RETRIEVAL_FIXTURES / "passages_unknown_source.json"),
        "--as-of",
        AS_OF,
        "--active-campaign",
        CAMPAIGN,
        "--index",
        str(tmp_path / "embedding-index.json"),
    )
    assert result.returncode == 2
    assert "invalid_corpus" in result.stderr
