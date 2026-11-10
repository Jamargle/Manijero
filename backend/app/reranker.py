"""Optional local reranker: a second, more careful reading of the passages already found.

The reranker only **re-orders** passages the retriever already admitted. It never adds,
drops, or admits a passage, so the lexical gate (a question with no BM25 match returns no
candidate), citations, abstention, and every downstream step are unchanged. It is **off by
default**: this module is imported only when ``MANIJERO_RERANKER=on`` and is stdlib-only at
import time (``torch``/``transformers`` load lazily on the first scored request).

Fail-closed rule: any scorer exception, wrong score count, or non-finite score returns the
ranking it was given, logs only a fixed reason code, and marks retrieval degraded for the
answer cache. No question or passage text reaches a log or an error.

The model is pinned like ``bge-m3`` (``backend/config/bge_reranker_v2_m3.json``): an
immutable revision plus a size and one digest per file (SHA-256 for large-file-storage
files, git-blob SHA-1 for small text files). Nothing here downloads a file; the owner
command does (``backend/scripts/reranker.py``). Settings live in
``backend/config/reranker.json``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

from app import answer_cache
from app.embeddings import (
    OFFLINE_ENVIRONMENT,
    ArtifactIssue,
    ArtifactReport,
    path_stays_inside,
    safe_relative_path,
)
from app.pilot_logging import operational_log
from app.source_catalog import ValidationIssue, is_non_blank_string

PIN_SCHEMA_VERSION = "reranker-model-v1"
SETTINGS_SCHEMA_VERSION = "reranker-settings-v1"
UNPINNED_REVISION = "unpinned"
EXPECTED_MODEL_ID = "BAAI/bge-reranker-v2-m3"
EXPECTED_ARCHITECTURE = "XLMRobertaForSequenceClassification"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PIN_PATH = BACKEND_ROOT / "config" / "bge_reranker_v2_m3.json"
DEFAULT_SETTINGS_PATH = BACKEND_ROOT / "config" / "reranker.json"

STATE_ENV = "MANIJERO_RERANKER"
ARTIFACT_ENV = "MANIJERO_RERANKER_ARTIFACT"
PIN_ENV = "MANIJERO_RERANKER_CONFIG"
SETTINGS_ENV = "MANIJERO_RERANKER_SETTINGS"
STATE_ON = "on"
STATE_OFF = "off"
STATES = (STATE_ON, STATE_OFF)

MAX_MODEL_BYTES = 5_000_000_000
DIGEST_SHA256 = "sha256"
DIGEST_GIT_BLOB_SHA1 = "git_blob_sha1"

PIN_KEYS: FrozenSet[str] = frozenset(
    {"schema_version", "model_id", "model_revision", "source_url", "license", "files"}
)
SETTINGS_KEYS: FrozenSet[str] = frozenset(
    {"schema_version", "default_state", "candidate_depth", "max_tokens", "batch_size"}
)
FILE_BASE_KEYS = frozenset({"path", "size"})
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
HTTPS_URL_PATTERN = re.compile(r"^https://huggingface\.co/[A-Za-z0-9._/-]+$")
WEIGHTS_SUFFIXES = (".safetensors", ".bin")

# Fixed reason codes: the only text a failure may log.
REASON_SCORE_FAILED = "reranker_score_failed"
REASON_SCORE_COUNT = "reranker_score_count"
REASON_SCORE_NOT_FINITE = "reranker_score_not_finite"
REASON_TEXT_MISSING = "reranker_text_missing"
REASON_NOT_CONFIGURED = "reranker_not_configured"
REASON_STATE_INVALID = "reranker_state_invalid"


class RerankerError(Exception):
    """A reranker failure; messages are fixed codes and never carry text."""


# --- Pin ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class RerankerFile:
    """One pinned file: byte size and exactly one digest of a stated kind."""

    path: str
    size: int
    digest_kind: str
    digest: str


@dataclass(frozen=True)
class RerankerSpec:
    """A validated, fully pinned reranker model expectation."""

    model_id: str
    model_revision: str
    source_url: str
    license: str
    files: Tuple[RerankerFile, ...]
    config_sha256: str

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.files)

    def required_paths(self) -> Tuple[str, ...]:
        return tuple(item.path for item in self.files)

    def verify_artifact(self, artifact_dir: Path) -> ArtifactReport:
        return verify_reranker_artifact(artifact_dir, self)


@dataclass(frozen=True)
class RerankerSettings:
    """``reranker-settings-v1``: the repository default state and scoring bounds."""

    default_state: str
    candidate_depth: int
    max_tokens: int
    batch_size: int
    config_sha256: str


def is_unpinned(document: Any) -> bool:
    return isinstance(document, dict) and document.get("model_revision") == UNPINNED_REVISION


def check_pin_document(document: Any) -> Tuple[ValidationIssue, ...]:
    """Every violation of the closed ``reranker-model-v1`` contract."""

    issues: List[ValidationIssue] = []

    def fail(location: str, rule: str) -> None:
        issues.append(ValidationIssue(location, rule))

    if not isinstance(document, dict):
        return (ValidationIssue("$", "pin must be a JSON object"),)
    for key in sorted(set(document) - PIN_KEYS):
        fail("$." + key, "unknown key is not allowed")
    for key in sorted(PIN_KEYS - set(document)):
        fail("$." + key, "required key is missing")
    if "schema_version" in document and document["schema_version"] != PIN_SCHEMA_VERSION:
        fail("$.schema_version", "must equal '{}'".format(PIN_SCHEMA_VERSION))
    model_id = document.get("model_id")
    if "model_id" in document and (
        not isinstance(model_id, str) or not MODEL_ID_PATTERN.match(model_id) or model_id != EXPECTED_MODEL_ID
    ):
        fail("$.model_id", "must be '{}'".format(EXPECTED_MODEL_ID))
    revision = document.get("model_revision")
    if "model_revision" in document and (
        not isinstance(revision, str) or not REVISION_PATTERN.match(revision)
    ):
        fail("$.model_revision", "must be a 40-character commit id, never a branch, tag, or placeholder")
    source_url = document.get("source_url")
    if "source_url" in document and (
        not isinstance(source_url, str) or not HTTPS_URL_PATTERN.match(source_url)
    ):
        fail("$.source_url", "must be an https://huggingface.co/ URL")
    if "license" in document and not is_non_blank_string(document["license"]):
        fail("$.license", "must be a non-blank license identifier")
    files = document.get("files")
    if "files" in document and not isinstance(files, list):
        fail("$.files", "must be a JSON array of file expectations")
    elif isinstance(files, list):
        _check_files(files, fail)
    return tuple(issues)


def _check_files(files: Sequence[Any], fail: Callable[[str, str], None]) -> None:
    seen: Dict[str, None] = {}
    total = 0
    for index, entry in enumerate(files):
        location = "$.files[{}]".format(index)
        if not isinstance(entry, dict):
            fail(location, "each file expectation must be a JSON object")
            continue
        digest_keys = set(entry) & {DIGEST_SHA256, DIGEST_GIT_BLOB_SHA1}
        for key in sorted(set(entry) - FILE_BASE_KEYS - {DIGEST_SHA256, DIGEST_GIT_BLOB_SHA1}):
            fail(location + "." + key, "unknown key is not allowed")
        for key in sorted(FILE_BASE_KEYS - set(entry)):
            fail(location + "." + key, "required key is missing")
        if len(digest_keys) != 1:
            fail(location, "must carry exactly one digest: sha256 or git_blob_sha1")
        path = entry.get("path")
        if "path" in entry:
            if safe_relative_path(path) is None:
                fail(location + ".path", "must be a relative POSIX path without '.' or '..' components")
            elif path in seen:
                fail(location + ".path", "duplicate path")
            else:
                seen[path] = None
        if DIGEST_SHA256 in entry and (
            not isinstance(entry[DIGEST_SHA256], str) or not SHA256_PATTERN.match(entry[DIGEST_SHA256])
        ):
            fail(location + ".sha256", "must be 64 lowercase hexadecimal characters")
        if DIGEST_GIT_BLOB_SHA1 in entry and (
            not isinstance(entry[DIGEST_GIT_BLOB_SHA1], str)
            or not SHA1_PATTERN.match(entry[DIGEST_GIT_BLOB_SHA1])
        ):
            fail(location + ".git_blob_sha1", "must be 40 lowercase hexadecimal characters")
        size = entry.get("size")
        if "size" in entry:
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                fail(location + ".size", "must be a non-negative integer byte count")
            else:
                total += size
    if "config.json" not in seen:
        fail("$.files", "must pin 'config.json'")
    if not any(path.endswith(WEIGHTS_SUFFIXES) for path in seen):
        fail("$.files", "must pin the model weights file")
    if total > MAX_MODEL_BYTES:
        fail("$.files", "total size must not exceed {} bytes".format(MAX_MODEL_BYTES))


def load_reranker_spec(path: Path) -> RerankerSpec:
    """Read, validate, and freeze the pin. Raises :class:`RerankerError` with a fixed code."""

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise RerankerError("reranker_pin_unreadable") from error
    try:
        document = json.loads(text)
    except ValueError as error:
        raise RerankerError("reranker_pin_malformed") from error
    if is_unpinned(document):
        raise RerankerError("reranker_pin_unpinned")
    issues = check_pin_document(document)
    if issues:
        raise RerankerError("reranker_pin_invalid: " + "; ".join(str(issue) for issue in issues))
    files = tuple(
        RerankerFile(
            path=entry["path"],
            size=entry["size"],
            digest_kind=DIGEST_SHA256 if DIGEST_SHA256 in entry else DIGEST_GIT_BLOB_SHA1,
            digest=entry[DIGEST_SHA256] if DIGEST_SHA256 in entry else entry[DIGEST_GIT_BLOB_SHA1],
        )
        for entry in document["files"]
    )
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return RerankerSpec(
        model_id=document["model_id"],
        model_revision=document["model_revision"],
        source_url=document["source_url"],
        license=document["license"],
        files=files,
        config_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


# --- Digests and artifact verification --------------------------------------------------------


def new_hasher(digest_kind: str, size: int) -> Any:
    """A hasher for one file; the git-blob kind is primed with ``blob <size>\\0``."""

    if digest_kind == DIGEST_SHA256:
        return hashlib.sha256()
    if digest_kind == DIGEST_GIT_BLOB_SHA1:
        hasher = hashlib.sha1()
        hasher.update("blob {}\0".format(size).encode("ascii"))
        return hasher
    raise RerankerError("reranker_digest_kind_unknown")


def _file_digest(path: Path, item: RerankerFile) -> str:
    hasher = new_hasher(item.digest_kind, item.size)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_reranker_artifact(artifact_dir: Path, spec: RerankerSpec) -> ArtifactReport:
    """Verify every pinned file of ``artifact_dir`` without running the model.

    Same ordered, fail-closed checks as the embedding artifact, plus a cross-check that the
    model's own ``config.json`` is a single-score sequence classifier.
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
    for item in spec.files:
        relative = safe_relative_path(item.path)
        if relative is None:
            issues.append(ArtifactIssue(item.path, "unsafe_path"))
            continue
        candidate = root / relative
        if not path_stays_inside(candidate, resolved_root):
            issues.append(ArtifactIssue(item.path, "path_escape"))
            continue
        if not candidate.exists() and not candidate.is_symlink():
            issues.append(ArtifactIssue(item.path, "file_missing"))
            continue
        if candidate.is_symlink() or not candidate.is_file():
            issues.append(ArtifactIssue(item.path, "not_a_regular_file"))
            continue
        try:
            size = candidate.stat().st_size
        except OSError:
            issues.append(ArtifactIssue(item.path, "unreadable_file"))
            continue
        if size != item.size:
            issues.append(ArtifactIssue(item.path, "size_mismatch"))
            continue
        try:
            digest = _file_digest(candidate, item)
        except OSError:
            issues.append(ArtifactIssue(item.path, "unreadable_file"))
            continue
        if digest != item.digest:
            issues.append(ArtifactIssue(item.path, "checksum_mismatch"))
            continue
        verified_files += 1
        verified_bytes += size

    pinned = set(spec.required_paths())
    ignored_files = 0
    ignored_bytes = 0
    for present in sorted(root.rglob("*")):
        if not present.is_file() or present.relative_to(root).as_posix() in pinned:
            continue
        ignored_files += 1
        try:
            ignored_bytes += present.stat().st_size
        except OSError:
            pass
    issues.extend(_check_model_config(root))
    return ArtifactReport(
        model_id=spec.model_id,
        model_revision=spec.model_revision,
        checked_files=verified_files,
        verified_bytes=verified_bytes,
        ignored_files=ignored_files,
        ignored_bytes=ignored_bytes,
        issues=tuple(issues),
    )


def _check_model_config(root: Path) -> List[ArtifactIssue]:
    """Defense in depth: the config must declare a one-label sequence classifier."""

    try:
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [ArtifactIssue("config.json", "config_unreadable")]
    if not isinstance(config, dict):
        return [ArtifactIssue("config.json", "config_unreadable")]
    architectures = config.get("architectures")
    if not isinstance(architectures, list) or EXPECTED_ARCHITECTURE not in architectures:
        return [ArtifactIssue("config.json", "architecture_mismatch")]
    labels = config.get("id2label")
    num_labels = config.get("num_labels")
    one_label = (isinstance(labels, dict) and len(labels) == 1) or (
        num_labels == 1 and not isinstance(num_labels, bool)
    )
    return [] if one_label else [ArtifactIssue("config.json", "label_count_mismatch")]


def artifact_present(artifact_dir: Path, spec: RerankerSpec) -> bool:
    """Cheap check (every pinned file exists with its pinned size); no hashing."""

    root = Path(artifact_dir)
    for item in spec.files:
        relative = safe_relative_path(item.path)
        if relative is None:
            return False
        target = root / relative
        try:
            if target.is_symlink() or not target.is_file() or target.stat().st_size != item.size:
                return False
        except OSError:
            return False
    return True


# --- Settings -----------------------------------------------------------------------------------


def validate_settings(document: Any) -> RerankerSettings:
    if not isinstance(document, dict) or set(document) != SETTINGS_KEYS:
        raise RerankerError("reranker_settings_unknown_keys")
    if document["schema_version"] != SETTINGS_SCHEMA_VERSION:
        raise RerankerError("reranker_settings_schema_version")
    if document["default_state"] not in STATES:
        raise RerankerError("reranker_settings_default_state")
    bounds = {"candidate_depth": (1, 100), "max_tokens": (8, 8192), "batch_size": (1, 64)}
    for key, (low, high) in bounds.items():
        value = document[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise RerankerError("reranker_settings_" + key)
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return RerankerSettings(
        default_state=document["default_state"],
        candidate_depth=document["candidate_depth"],
        max_tokens=document["max_tokens"],
        batch_size=document["batch_size"],
        config_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def load_reranker_settings(path: Path = DEFAULT_SETTINGS_PATH) -> RerankerSettings:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RerankerError("reranker_settings_unreadable") from error
    return validate_settings(document)


def effective_state(owner_state: Optional[str], default_state: str) -> str:
    """The owner's settings line wins; without one the repository default applies."""

    return owner_state if owner_state in STATES else default_state


# --- Ranking ------------------------------------------------------------------------------------


class RerankScorer(Protocol):
    """Scores ``(query, passage text)`` pairs; higher means more relevant."""

    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        """Return one finite score per text, in order."""


class _Ranking(Protocol):
    def rank(
        self, question: str, lexical: Tuple[Tuple[str, float], ...]
    ) -> Sequence[Tuple[str, float]]: ...


class RerankingRanker:
    """A :class:`app.retrieval.CandidateRanker` that re-orders the first ``candidate_depth`` ids.

    ``inner`` is the ranking to wrap (hybrid) or ``None`` for plain BM25. Ids after the
    depth keep their order behind the re-ordered head, ties keep the earlier rank, and no
    id is added or dropped. Each id keeps the score the inner ranking gave it; only the
    order changes.
    """

    def __init__(
        self,
        inner: Optional[_Ranking],
        scorer: RerankScorer,
        settings: RerankerSettings,
        text_for: Callable[[str], Optional[str]],
        lock: Optional[threading.Lock] = None,
    ) -> None:
        self._inner = inner
        self._scorer = scorer
        self._settings = settings
        self._text_for = text_for
        self._lock = lock or threading.Lock()

    @property
    def inner(self) -> Optional[_Ranking]:
        return self._inner

    def rank(
        self, question: str, lexical: Tuple[Tuple[str, float], ...]
    ) -> Sequence[Tuple[str, float]]:
        base = tuple(lexical) if self._inner is None else tuple(self._inner.rank(question, lexical))
        ordered: List[Tuple[str, float]] = []
        seen: Dict[str, None] = {}
        for passage_id, score in base:
            if passage_id not in seen:
                seen[passage_id] = None
                ordered.append((passage_id, score))
        head = ordered[: self._settings.candidate_depth]
        if len(head) < 2:
            return base
        texts: List[str] = []
        for passage_id, _ in head:
            text = self._text_for(passage_id)
            if not isinstance(text, str) or not text.strip():
                return self._fallback(base, REASON_TEXT_MISSING)
            texts.append(text)
        try:
            with self._lock:
                scores = tuple(self._scorer.score(question, texts))
        except Exception:  # noqa: BLE001 - fixed reason only; the error may echo text
            return self._fallback(base, REASON_SCORE_FAILED)
        if len(scores) != len(head):
            return self._fallback(base, REASON_SCORE_COUNT)
        for value in scores:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                return self._fallback(base, REASON_SCORE_NOT_FINITE)
        order = sorted(range(len(head)), key=lambda position: -scores[position])  # stable
        return tuple(head[position] for position in order) + tuple(ordered[len(head) :])

    @staticmethod
    def _fallback(base: Tuple[Tuple[str, float], ...], reason: str) -> Tuple[Tuple[str, float], ...]:
        operational_log("reranker_fallback", reason=reason)
        answer_cache.note_degraded_retrieval()
        return base


class RerankerBackend:
    """Wraps a retrieval backend: its ranking, then the reranker over that same ranking.

    ``loader`` runs once, lazily, on the first request. A load failure is remembered and the
    service keeps answering with the unreranked ranking until it restarts.
    """

    def __init__(
        self,
        inner: Any,
        loader: Callable[[], RerankScorer],
        settings: RerankerSettings,
    ) -> None:
        self._inner = inner
        self._loader = loader
        self._settings = settings
        self._lock = threading.Lock()
        self._score_lock = threading.Lock()
        self._scorer: Optional[RerankScorer] = None
        self._loaded = False
        self._load_failure: Optional[str] = None

    @property
    def mode(self) -> str:
        return self._inner.mode

    @property
    def inner(self) -> Any:
        return self._inner

    @property
    def load_failure(self) -> Optional[str]:
        return self._load_failure

    def attach(self, retriever: Any, active_campaign: Optional[str]) -> Any:
        attached = self._inner.attach(retriever, active_campaign)
        try:
            scorer = self._ensure_loaded()
            if scorer is None:
                return attached
            return attached.with_ranker(
                RerankingRanker(
                    attached.current_ranker,
                    scorer,
                    self._settings,
                    attached.passage_text,
                    lock=self._score_lock,
                )
            )
        except Exception:  # noqa: BLE001 - never let ranking setup fail a request
            operational_log("reranker_fallback", reason=REASON_SCORE_FAILED)
            return attached

    def _ensure_loaded(self) -> Optional[RerankScorer]:
        with self._lock:
            if not self._loaded:
                self._loaded = True
                try:
                    self._scorer = self._loader()
                except Exception as error:  # noqa: BLE001
                    code = str(error).split(":", 1)[0] if isinstance(error, RerankerError) else type(error).__name__
                    self._load_failure = code
                    self._scorer = None
                    operational_log("reranker_fallback", reason=code)
                    answer_cache.note_degraded_retrieval()
            return self._scorer


def backend_from_environment(environ: Mapping[str, str], inner: Any) -> Any:
    """Wrap ``inner`` when ``MANIJERO_RERANKER=on`` and everything it needs is valid.

    Any other state keeps ``inner`` unchanged. Nothing is loaded here: the pin, settings, and
    artifact path are read now; the model itself loads on the first request.
    """

    state = (environ.get(STATE_ENV) or STATE_OFF).strip()
    if state == STATE_OFF:
        return inner
    if state != STATE_ON:
        operational_log("reranker_mode", active=STATE_OFF, reason=REASON_STATE_INVALID)
        return inner
    artifact = environ.get(ARTIFACT_ENV, "").strip()
    if not artifact:
        operational_log("reranker_mode", active=STATE_OFF, reason=REASON_NOT_CONFIGURED)
        return inner
    try:
        spec = load_reranker_spec(Path(environ.get(PIN_ENV, "").strip() or DEFAULT_PIN_PATH))
        settings = load_reranker_settings(Path(environ.get(SETTINGS_ENV, "").strip() or DEFAULT_SETTINGS_PATH))
    except RerankerError as error:
        operational_log("reranker_mode", active=STATE_OFF, reason=str(error).split(":", 1)[0])
        return inner
    return RerankerBackend(
        inner, lambda: LocalBgeReranker.load(spec, Path(artifact), settings), settings
    )


# --- Local model --------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Runtime:
    torch: Any
    auto_tokenizer: Any
    auto_model: Any


def _load_runtime() -> _Runtime:
    """Import the optional runtime with hub access forced off."""

    for name, value in OFFLINE_ENVIRONMENT.items():
        os.environ[name] = value
    try:
        import torch  # type: ignore[import-not-found]
        from transformers import (  # type: ignore[import-not-found]
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
    except ImportError as error:
        raise RerankerError("reranker_runtime_unavailable") from error
    return _Runtime(torch=torch, auto_tokenizer=AutoTokenizer, auto_model=AutoModelForSequenceClassification)


class LocalBgeReranker:
    """The pinned local bge-reranker-v2-m3 cross-encoder (CPU, float32, raw logits)."""

    def __init__(self, settings: RerankerSettings, tokenizer: Any, model: Any, torch: Any) -> None:
        self._settings = settings
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch

    @classmethod
    def load(
        cls,
        spec: RerankerSpec,
        artifact_dir: Path,
        settings: RerankerSettings,
        *,
        runtime_loader: Callable[[], Any] = _load_runtime,
    ) -> "LocalBgeReranker":
        """Verify the artifact, then load it from that directory only, or fail closed."""

        report = verify_reranker_artifact(artifact_dir, spec)
        if not report.ok:
            raise RerankerError("reranker_artifact_invalid: " + report.format_issues())
        runtime = runtime_loader()
        local_path = str(Path(artifact_dir))
        try:
            tokenizer = runtime.auto_tokenizer.from_pretrained(
                local_path, local_files_only=True, trust_remote_code=False
            )
            model = runtime.auto_model.from_pretrained(
                local_path,
                local_files_only=True,
                trust_remote_code=False,
                dtype=runtime.torch.float32,
                use_safetensors=True,
            )
        except Exception as error:  # noqa: BLE001 - fixed code, never model text
            raise RerankerError("reranker_model_load_failed") from error
        model.eval()
        return cls(settings, tokenizer, model, runtime.torch)

    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        batch_size = self._settings.batch_size
        scores: List[float] = []
        for start in range(0, len(texts), batch_size):
            chunk = list(texts[start : start + batch_size])
            encoded = self._tokenizer(
                [query] * len(chunk),
                chunk,
                padding=True,
                truncation=True,
                max_length=self._settings.max_tokens,
                return_tensors="pt",
            )
            with self._torch.inference_mode():
                output = self._model(**encoded)
            scores.extend(
                float(value)
                for value in output.logits.detach().to(self._torch.float32).reshape(-1).tolist()
            )
        return tuple(scores)
