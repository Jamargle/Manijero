"""Pinned, offline multilingual embeddings behind a replaceable interface.

This module owns the *embedding capability*, not retrieval policy. It loads one
locally pinned model (``BAAI/bge-m3`` by default) from an operator-managed
directory whose every required file is bound to a SHA-256 checksum and to an
immutable upstream revision. Nothing here downloads a file, opens a network
socket, or trusts a mutable model name: an unpinned or unverifiable artifact
fails closed before any text is embedded.

The narrow boundary is :class:`EmbeddingModel`. Consumers (a rebuild tool, a
future hybrid retriever) depend on that protocol only, so the model can be
replaced or withdrawn without touching the answer route. ``/ask`` keeps the
accepted BM25 retrieval: embeddings are **off by default** and are never read by
the answer path.

Privacy: no text being embedded, and no model output, is written to an error
message, a log, or an index file. Failures carry a stable reason code.

Durable evidence and operator instructions live in ``backend/README.md``; the
pinned expectation file is ``backend/config/bge_m3_embedding.json``.
"""

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import (
    Any,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from app.source_catalog import ValidationIssue, is_non_blank_string

EMBEDDING_CONFIG_SCHEMA_VERSION = "embedding-model-v1"

CONFIG_REQUIRED_KEYS: FrozenSet[str] = frozenset(
    {
        "schema_version",
        "model_id",
        "model_revision",
        "source_url",
        "license",
        "embedding_dimension",
        "max_tokens",
        "pooling",
        "normalize",
        "dtype",
        "batch_size",
        "files",
    }
)

ARTIFACT_FILE_REQUIRED_KEYS = frozenset({"path", "sha256", "size"})

POOLING_MODES = ("cls", "mean")
SUPPORTED_DTYPES = ("float32",)
SUPPORTED_DEVICES = ("cpu",)

MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
# An immutable commit id. A branch or tag name such as ``main`` is deliberately
# invalid: a mutable reference cannot pin an artifact.
MODEL_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
HTTPS_URL_PATTERN = re.compile(r"^https://[A-Za-z0-9.-]+(?:[^\s]*)$")

MAX_EMBEDDING_DIMENSION = 65_536
MAX_TOKENS_LIMIT = 1_048_576
MAX_BATCH_SIZE = 1_024
REQUIRED_ARTIFACT_PATH = "config.json"

# Forced before the optional runtime is imported. ``setdefault`` would let an
# exported variable re-enable hub access, so the offline flags always win.
OFFLINE_ENVIRONMENT = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}


class EmbeddingError(Exception):
    """Base class for embedding failures; messages carry fixed codes only."""


class EmbeddingConfigError(EmbeddingError):
    """The pinned embedding configuration is unreadable or invalid."""


class EmbeddingArtifactError(EmbeddingError):
    """The local model artifact does not match the pinned expectation."""


class EmbeddingRuntimeUnavailable(EmbeddingError):
    """The optional ``torch``/``transformers`` runtime is not installed."""


class EmbeddingInputError(EmbeddingError):
    """A caller passed text that cannot be embedded."""


class EmbeddingExecutionError(EmbeddingError):
    """The pinned model could not be loaded or executed."""


@dataclass(frozen=True)
class ArtifactFile:
    """One required artifact file with its pinned byte size and digest."""

    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class EmbeddingConfigReport:
    """Result of validating one embedding configuration document."""

    schema_version: Optional[str]
    checked_files: int
    issues: Tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def format_issues(self) -> str:
        return "\n".join(str(issue) for issue in self.issues)


@dataclass(frozen=True)
class EmbeddingModelSpec:
    """A validated, fully pinned embedding model expectation.

    ``config_sha256`` is the SHA-256 of the canonical JSON form of the whole
    expectation document. A derived index records it, so an index built under a
    different pin is reported as outdated instead of reused.
    """

    model_id: str
    model_revision: str
    source_url: str
    license: str
    embedding_dimension: int
    max_tokens: int
    pooling: str
    normalize: bool
    dtype: str
    batch_size: int
    files: Tuple[ArtifactFile, ...]
    config_sha256: str

    def index_metadata(self) -> Dict[str, Any]:
        """Return the model binding a derived index must record and match."""

        return {
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "embedding_dimension": self.embedding_dimension,
            "pooling": self.pooling,
            "normalize": self.normalize,
            "dtype": self.dtype,
            "config_sha256": self.config_sha256,
        }

    def required_paths(self) -> Tuple[str, ...]:
        return tuple(artifact_file.path for artifact_file in self.files)

    def artifact_file(self, path: str) -> Optional[ArtifactFile]:
        for artifact_file in self.files:
            if artifact_file.path == path:
                return artifact_file
        return None


@dataclass(frozen=True)
class ArtifactIssue:
    """One artifact mismatch, located by its configured relative path."""

    path: str
    code: str

    def __str__(self) -> str:
        return "{}: {}".format(self.path, self.code)


@dataclass(frozen=True)
class ArtifactReport:
    """Result of verifying a local artifact directory against a pinned spec."""

    model_id: str
    model_revision: str
    checked_files: int
    verified_bytes: int
    ignored_files: int
    ignored_bytes: int
    issues: Tuple[ArtifactIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def format_issues(self) -> str:
        return "\n".join(str(issue) for issue in self.issues)


@runtime_checkable
class EmbeddingModel(Protocol):
    """Replaceable embedding boundary used by retrieval-side consumers.

    ``normalized`` tells a consumer whether cosine similarity is a plain dot
    product. ``dimension`` is checked before any vector is stored or compared.
    """

    @property
    def model_id(self) -> str:
        """Upstream model identity, for provenance only."""

    @property
    def model_revision(self) -> str:
        """Immutable upstream revision the local artifact was verified against."""

    @property
    def dimension(self) -> int:
        """Vector length every call returns."""

    @property
    def normalized(self) -> bool:
        """Whether returned vectors are unit length."""

    def embed(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        """Embed ``texts`` in order; raises :class:`EmbeddingError` on failure."""


def validate_embedding_config(document: Any) -> EmbeddingConfigReport:
    """Validate a parsed embedding configuration against the closed contract."""

    return _EmbeddingConfigValidator().validate(document)


def load_model_spec(path: Path) -> EmbeddingModelSpec:
    """Read, validate, and freeze one embedding configuration file.

    Raises :class:`EmbeddingConfigError` with a fixed code. The message contains
    no configuration value: only the violated JSON paths and rules.
    """

    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as error:
        raise EmbeddingConfigError("config_unreadable") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise EmbeddingConfigError("config_malformed") from error
    report = validate_embedding_config(document)
    if not report.ok:
        raise EmbeddingConfigError("config_invalid: {}".format(report.format_issues()))
    return _spec_from_document(document)


def verify_artifact(artifact_dir: Path, spec: EmbeddingModelSpec) -> ArtifactReport:
    """Verify every pinned file of ``artifact_dir`` without executing the model.

    The check is ordered and fail-closed: the directory must exist, every pinned
    file must be a regular file inside it (no absolute path, ``..``, or symlink
    escape), and both byte size and SHA-256 must match. Files present but not
    pinned are counted and ignored, so an operator can keep unrelated extras
    without weakening the pin.
    """

    root = Path(artifact_dir)
    issues: List[ArtifactIssue] = []
    verified_files = 0
    verified_bytes = 0

    if not root.is_dir():
        return ArtifactReport(
            model_id=spec.model_id,
            model_revision=spec.model_revision,
            checked_files=0,
            verified_bytes=0,
            ignored_files=0,
            ignored_bytes=0,
            issues=(ArtifactIssue("artifact_dir", "directory_missing"),),
        )

    resolved_root = root.resolve()
    for artifact_file in spec.files:
        relative = safe_relative_path(artifact_file.path)
        if relative is None:
            issues.append(ArtifactIssue(artifact_file.path, "unsafe_path"))
            continue
        candidate = root / relative
        if not path_stays_inside(candidate, resolved_root):
            issues.append(ArtifactIssue(artifact_file.path, "path_escape"))
            continue
        if not candidate.exists():
            issues.append(ArtifactIssue(artifact_file.path, "file_missing"))
            continue
        if not candidate.is_file() or candidate.is_symlink():
            issues.append(ArtifactIssue(artifact_file.path, "not_a_regular_file"))
            continue
        try:
            size = candidate.stat().st_size
        except OSError:
            issues.append(ArtifactIssue(artifact_file.path, "unreadable_file"))
            continue
        if size != artifact_file.size:
            issues.append(ArtifactIssue(artifact_file.path, "size_mismatch"))
            continue
        try:
            digest = _sha256_file(candidate)
        except OSError:
            issues.append(ArtifactIssue(artifact_file.path, "unreadable_file"))
            continue
        if digest != artifact_file.sha256:
            issues.append(ArtifactIssue(artifact_file.path, "checksum_mismatch"))
            continue
        verified_files += 1
        verified_bytes += size

    pinned_paths = set(spec.required_paths())
    ignored_files = 0
    ignored_bytes = 0
    for present in sorted(root.rglob("*")):
        if not present.is_file():
            continue
        relative_text = present.relative_to(root).as_posix()
        if relative_text in pinned_paths:
            continue
        ignored_files += 1
        try:
            ignored_bytes += present.stat().st_size
        except OSError:
            pass

    issues.extend(_check_artifact_metadata(root, spec, frozenset(pinned_paths)))
    return ArtifactReport(
        model_id=spec.model_id,
        model_revision=spec.model_revision,
        checked_files=verified_files,
        verified_bytes=verified_bytes,
        ignored_files=ignored_files,
        ignored_bytes=ignored_bytes,
        issues=tuple(issues),
    )


def safe_relative_path(value: Any) -> Optional[Path]:
    """Return ``value`` as a safe relative path, or ``None``.

    Rejects blanks, backslashes, absolute paths, and any ``.``/``..`` component.
    """

    if not is_non_blank_string(value):
        return None
    if "\\" in value or value.startswith("/"):
        return None
    candidate = PurePosixPath(value)
    if candidate.is_absolute():
        return None
    parts = candidate.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    return Path(*parts)


def path_stays_inside(candidate: Path, resolved_root: Path) -> bool:
    """Return whether ``candidate`` resolves to ``resolved_root`` or below it."""

    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError):
        return False
    return resolved == resolved_root or resolved_root in resolved.parents


def position_count_is_too_small(max_positions: int, spec: EmbeddingModelSpec) -> bool:
    """Return whether the model context cannot hold ``spec.max_tokens`` tokens."""

    return max_positions < spec.max_tokens


def finalize_vectors(
    hidden_states: Sequence[Sequence[Sequence[float]]],
    pooling: str,
    normalize: bool,
    attention_mask: Optional[Sequence[Sequence[int]]] = None,
) -> Tuple[Tuple[float, ...], ...]:
    """Turn raw token vectors into one embedding per input.

    Pooling and normalization are plain Python so this contract is testable
    without the optional runtime and identical on every platform. The caller is
    responsible for truncating each text to the configured token bound.
    """

    if pooling not in POOLING_MODES:
        raise EmbeddingExecutionError("unsupported_pooling")
    vectors: List[Tuple[float, ...]] = []
    for position, tokens in enumerate(hidden_states):
        if not tokens:
            raise EmbeddingExecutionError("empty_hidden_state")
        mask: Optional[Sequence[int]] = None
        if attention_mask is not None:
            if position >= len(attention_mask):
                raise EmbeddingExecutionError("attention_mask_mismatch")
            mask = attention_mask[position]
            if len(mask) != len(tokens):
                raise EmbeddingExecutionError("attention_mask_mismatch")
        if pooling == "cls":
            pooled = [float(value) for value in tokens[0]]
        else:
            pooled = _mean_pool(tokens, mask)
        if normalize:
            pooled = _l2_normalize(pooled)
        vectors.append(tuple(pooled))
    return tuple(vectors)


def _mean_pool(tokens: Sequence[Sequence[float]], mask: Optional[Sequence[int]]) -> List[float]:
    width = len(tokens[0])
    totals = [0.0] * width
    counted = 0
    for position, token in enumerate(tokens):
        if len(token) != width:
            raise EmbeddingExecutionError("vector_width_mismatch")
        if mask is not None and position < len(mask) and not mask[position]:
            continue
        counted += 1
        for index, value in enumerate(token):
            totals[index] += float(value)
    if counted == 0:
        raise EmbeddingInputError("empty_text")
    return [total / counted for total in totals]


def _l2_normalize(vector: Sequence[float]) -> List[float]:
    norm = 0.0
    numbers: List[float] = []
    for value in vector:
        number = float(value)
        if not math.isfinite(number):
            raise EmbeddingExecutionError("non_finite_vector")
        numbers.append(number)
        norm += number * number
    norm = math.sqrt(norm)
    if norm == 0.0:
        raise EmbeddingExecutionError("zero_vector")
    return [number / norm for number in numbers]


def _spec_from_document(document: Mapping[str, Any]) -> EmbeddingModelSpec:
    files = tuple(
        ArtifactFile(path=entry["path"], sha256=entry["sha256"], size=entry["size"])
        for entry in document["files"]
    )
    return EmbeddingModelSpec(
        model_id=document["model_id"],
        model_revision=document["model_revision"],
        source_url=document["source_url"],
        license=document["license"],
        embedding_dimension=document["embedding_dimension"],
        max_tokens=document["max_tokens"],
        pooling=document["pooling"],
        normalize=document["normalize"],
        dtype=document["dtype"],
        batch_size=document["batch_size"],
        files=files,
        config_sha256=_canonical_digest(document),
    )


def _canonical_digest(document: Mapping[str, Any]) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_artifact_json(path: Path) -> Optional[Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _check_artifact_metadata(
    root: Path, spec: EmbeddingModelSpec, pinned_paths: FrozenSet[str]
) -> List[ArtifactIssue]:
    """Cross-check the model's own configuration against the pinned expectation.

    The checksum already binds the bytes, so this is defense in depth: a
    configuration edited together with its checksum must still declare the
    dimension and context the rest of the system relies on.
    """

    issues: List[ArtifactIssue] = []
    model_config = _read_artifact_json(root / REQUIRED_ARTIFACT_PATH)
    if not isinstance(model_config, dict):
        issues.append(ArtifactIssue(REQUIRED_ARTIFACT_PATH, "config_unreadable"))
        return issues
    if model_config.get("hidden_size") != spec.embedding_dimension:
        issues.append(ArtifactIssue(REQUIRED_ARTIFACT_PATH, "dimension_mismatch"))
    max_positions = model_config.get("max_position_embeddings")
    if isinstance(max_positions, int) and not isinstance(max_positions, bool):
        if position_count_is_too_small(max_positions, spec):
            issues.append(ArtifactIssue(REQUIRED_ARTIFACT_PATH, "context_too_small"))
    else:
        issues.append(ArtifactIssue(REQUIRED_ARTIFACT_PATH, "context_unreadable"))

    pooling_path = "1_Pooling/config.json"
    if spec.artifact_file(pooling_path) is not None and pooling_path in pinned_paths:
        pooling_config = _read_artifact_json(root / "1_Pooling" / "config.json")
        if not isinstance(pooling_config, dict):
            issues.append(ArtifactIssue(pooling_path, "pooling_unreadable"))
        elif spec.pooling == "cls" and pooling_config.get("pooling_mode_cls_token") is not True:
            issues.append(ArtifactIssue(pooling_path, "pooling_mismatch"))
        elif spec.pooling == "mean" and pooling_config.get("pooling_mode_mean_tokens") is not True:
            issues.append(ArtifactIssue(pooling_path, "pooling_mismatch"))
    return issues


@dataclass(frozen=True)
class _Runtime:
    torch: Any
    auto_tokenizer: Any
    auto_model: Any


def _load_runtime() -> _Runtime:
    """Import the optional runtime with hub access forced off.

    Imported lazily so the rest of the backend and the default test suite do not
    need ``torch``/``transformers``.
    """

    for name, value in OFFLINE_ENVIRONMENT.items():
        os.environ[name] = value
    try:
        import torch  # type: ignore[import-not-found]
        from transformers import AutoModel, AutoTokenizer  # type: ignore[import-not-found]
    except ImportError as error:
        raise EmbeddingRuntimeUnavailable(
            "runtime_unavailable: install backend/requirements-embeddings.txt"
        ) from error
    return _Runtime(torch=torch, auto_tokenizer=AutoTokenizer, auto_model=AutoModel)


class LocalBgeM3Embedder:
    """The pinned local bge-m3 encoder implementing :class:`EmbeddingModel`.

    Construction verifies the artifact against the spec, then loads the model
    from that directory only. ``embed`` truncates each text to the configured
    token bound, pools the last hidden state (CLS or masked mean), and optionally
    L2-normalizes the result.
    """

    def __init__(self, spec: EmbeddingModelSpec, tokenizer: Any, model: Any, torch: Any) -> None:
        self._spec = spec
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch
        self._thread_count = int(torch.get_num_threads())

    @classmethod
    def load(
        cls,
        spec: EmbeddingModelSpec,
        artifact_dir: Path,
        *,
        device: str = "cpu",
        threads: Optional[int] = None,
    ) -> "LocalBgeM3Embedder":
        """Verify and load the local model, or fail closed.

        Raises :class:`EmbeddingArtifactError`,
        :class:`EmbeddingRuntimeUnavailable`, or
        :class:`EmbeddingExecutionError`; none of them includes model text.
        """

        if device not in SUPPORTED_DEVICES:
            raise EmbeddingExecutionError("unsupported_device")
        if spec.dtype not in SUPPORTED_DTYPES:
            raise EmbeddingExecutionError("unsupported_dtype")
        if threads is not None and threads < 1:
            raise EmbeddingExecutionError("invalid_threads")

        report = verify_artifact(artifact_dir, spec)
        if not report.ok:
            raise EmbeddingArtifactError("artifact_invalid: {}".format(report.format_issues()))

        runtime = _load_runtime()
        if threads is not None:
            runtime.torch.set_num_threads(threads)

        local_path = str(Path(artifact_dir))
        try:
            tokenizer = runtime.auto_tokenizer.from_pretrained(
                local_path,
                local_files_only=True,
                trust_remote_code=False,
            )
            model = runtime.auto_model.from_pretrained(
                local_path,
                local_files_only=True,
                trust_remote_code=False,
                dtype=runtime.torch.float32,
                use_safetensors=False,
            )
        except EmbeddingError:
            raise
        except Exception as error:  # noqa: BLE001 - fixed code, never model text
            raise EmbeddingExecutionError("model_load_failed") from error
        model.eval()
        return cls(spec=spec, tokenizer=tokenizer, model=model, torch=runtime.torch)

    @property
    def model_id(self) -> str:
        return self._spec.model_id

    @property
    def model_revision(self) -> str:
        return self._spec.model_revision

    @property
    def dimension(self) -> int:
        return self._spec.embedding_dimension

    @property
    def normalized(self) -> bool:
        return self._spec.normalize

    @property
    def max_tokens(self) -> int:
        return self._spec.max_tokens

    @property
    def thread_count(self) -> int:
        """Torch thread count in effect, recorded so a latency figure is reproducible."""

        return self._thread_count

    def embed(self, texts: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        """Embed ``texts`` in order with deterministic batching and arithmetic."""

        if isinstance(texts, (str, bytes)):
            raise EmbeddingInputError("invalid_text_input")
        batch: List[str] = []
        for text in texts:
            if not isinstance(text, str) or not text.strip():
                raise EmbeddingInputError("invalid_text_input")
            batch.append(text)
        if not batch:
            return ()

        vectors: List[Tuple[float, ...]] = []
        for start in range(0, len(batch), self._spec.batch_size):
            vectors.extend(self._encode(batch[start : start + self._spec.batch_size]))
        for vector in vectors:
            if len(vector) != self._spec.embedding_dimension:
                raise EmbeddingExecutionError("dimension_mismatch")
        return tuple(vectors)

    def _encode(self, batch: Sequence[str]) -> Tuple[Tuple[float, ...], ...]:
        try:
            encoded = self._tokenizer(
                list(batch),
                padding=True,
                truncation=True,
                max_length=self._spec.max_tokens,
                return_tensors="pt",
            )
            mask = encoded["attention_mask"].tolist()
            longest = max((len(row) for row in mask), default=0)
            if longest > self._spec.max_tokens:
                raise EmbeddingExecutionError("token_bound_exceeded")
            with self._torch.inference_mode():
                output = self._model(**encoded)
            hidden_states = output.last_hidden_state.detach().to(self._torch.float32).tolist()
            return finalize_vectors(
                hidden_states,
                pooling=self._spec.pooling,
                normalize=self._spec.normalize,
                attention_mask=mask,
            )
        except EmbeddingError:
            raise
        except Exception as error:  # noqa: BLE001 - fixed code, never input text
            raise EmbeddingExecutionError("encode_failed") from error


class _EmbeddingConfigValidator:
    """Accumulates every configuration violation instead of failing on the first."""

    def __init__(self) -> None:
        self._issues: List[ValidationIssue] = []

    def validate(self, document: Any) -> EmbeddingConfigReport:
        if not isinstance(document, dict):
            self._fail("$", "configuration must be a JSON object")
            return self._report(None, 0)
        self._check_keys(document, CONFIG_REQUIRED_KEYS, CONFIG_REQUIRED_KEYS, "$")

        schema_version = document.get("schema_version")
        if "schema_version" in document and schema_version != EMBEDDING_CONFIG_SCHEMA_VERSION:
            self._fail("$.schema_version", "must equal '{}'".format(EMBEDDING_CONFIG_SCHEMA_VERSION))

        model_id = document.get("model_id")
        if "model_id" in document and (
            not is_non_blank_string(model_id) or not MODEL_ID_PATTERN.match(model_id)
        ):
            self._fail("$.model_id", "must be an immutable 'owner/name' model identity")

        revision = document.get("model_revision")
        if "model_revision" in document and (
            not isinstance(revision, str) or not MODEL_REVISION_PATTERN.match(revision)
        ):
            self._fail("$.model_revision", "must be a 40-character commit id, never a branch or tag")

        source_url = document.get("source_url")
        if "source_url" in document and (
            not isinstance(source_url, str) or not HTTPS_URL_PATTERN.match(source_url)
        ):
            self._fail("$.source_url", "must be an https URL")

        if "license" in document and not is_non_blank_string(document["license"]):
            self._fail("$.license", "must be a non-blank artifact license identifier")

        self._check_int(
            document,
            "embedding_dimension",
            minimum=1,
            maximum=MAX_EMBEDDING_DIMENSION,
            rule="must be an integer between 1 and {}".format(MAX_EMBEDDING_DIMENSION),
        )
        self._check_int(
            document,
            "max_tokens",
            minimum=1,
            maximum=MAX_TOKENS_LIMIT,
            rule="must be an integer between 1 and {}".format(MAX_TOKENS_LIMIT),
        )
        self._check_int(
            document,
            "batch_size",
            minimum=1,
            maximum=MAX_BATCH_SIZE,
            rule="must be an integer between 1 and {}".format(MAX_BATCH_SIZE),
        )

        if "pooling" in document and document["pooling"] not in POOLING_MODES:
            self._fail("$.pooling", "must be one of: {}".format(", ".join(POOLING_MODES)))
        if "normalize" in document and not isinstance(document["normalize"], bool):
            self._fail("$.normalize", "must be true or false")
        if "dtype" in document and document["dtype"] not in SUPPORTED_DTYPES:
            self._fail("$.dtype", "must be one of: {}".format(", ".join(SUPPORTED_DTYPES)))

        checked_files = 0
        files = document.get("files")
        if isinstance(files, list):
            checked_files = len(files)
            self._check_files(files)
        elif "files" in document:
            self._fail("$.files", "must be a JSON array of file expectations")
        return self._report(_as_text(schema_version), checked_files)

    def _check_files(self, files: Sequence[Any]) -> None:
        if not files:
            self._fail("$.files", "must list at least the model config.json")
        seen: Dict[str, str] = {}
        for index, entry in enumerate(files):
            location = "$.files[{}]".format(index)
            if not isinstance(entry, dict):
                self._fail(location, "each file expectation must be a JSON object")
                continue
            self._check_keys(
                entry, ARTIFACT_FILE_REQUIRED_KEYS, ARTIFACT_FILE_REQUIRED_KEYS, location
            )
            path = entry.get("path")
            if "path" in entry:
                if safe_relative_path(path) is None:
                    self._fail(
                        location + ".path",
                        "must be a relative POSIX path without '.' or '..' components",
                    )
                elif path in seen:
                    self._fail(
                        location + ".path",
                        "duplicate path; already pinned by {}".format(seen[path]),
                    )
                else:
                    seen[path] = location
            sha256 = entry.get("sha256")
            if "sha256" in entry and (
                not isinstance(sha256, str) or not SHA256_PATTERN.match(sha256)
            ):
                self._fail(location + ".sha256", "must be 64 lowercase hexadecimal characters")
            if "size" in entry:
                size = entry["size"]
                if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                    self._fail(location + ".size", "must be a non-negative integer byte count")
        if files and REQUIRED_ARTIFACT_PATH not in seen:
            self._fail("$.files", "must pin '{}'".format(REQUIRED_ARTIFACT_PATH))

    def _check_int(
        self,
        document: Mapping[str, Any],
        key: str,
        *,
        minimum: int,
        maximum: int,
        rule: str,
    ) -> None:
        if key not in document:
            return
        value = document[key]
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            self._fail("$." + key, rule)

    def _check_keys(
        self,
        payload: Mapping[str, Any],
        required: FrozenSet[str],
        allowed: FrozenSet[str],
        location: str,
    ) -> None:
        for key in sorted(payload):
            if key not in allowed:
                self._fail(_join(location, key), "unknown key is not allowed")
        for key in sorted(required):
            if key not in payload:
                self._fail(_join(location, key), "required key is missing")

    def _fail(self, location: str, rule: str) -> None:
        self._issues.append(ValidationIssue(location, rule))

    def _report(
        self, schema_version: Optional[str], checked_files: int
    ) -> EmbeddingConfigReport:
        return EmbeddingConfigReport(
            schema_version=schema_version,
            checked_files=checked_files,
            issues=tuple(self._issues),
        )


def _join(location: str, key: str) -> str:
    return "$." + key if location == "$" else "{}.{}".format(location, key)


def _as_text(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() != "" else None
