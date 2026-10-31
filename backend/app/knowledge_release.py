"""Immutable, hash-verified knowledge releases with an atomic ``current`` pointer.

A *knowledge release* is one directory built from the canonical reviewed catalog,
passages, and evaluation cases, bound to human-approval evidence, gated, and described
by a closed ``knowledge-release-v1`` manifest written last. Layout of a release root::

    <root>/releases/<release_id>/   # immutable release directories
    <root>/current                  # relative symlink -> releases/<release_id>
    <root>/release-log.jsonl        # append-only publish/rollback events (timestamps)
    <root>/.release.lock            # exclusive lock held by publish/rollback

Publication is one ``os.replace`` of the ``current`` symlink, so the answer service
never sees a half-written corpus: every request resolves ``current`` once and reads
both files from that single directory after verifying their SHA-256 and the gate.

This module is stdlib-only at import time because the answer service imports it for the
opt-in read path (``MANIJERO_KNOWLEDGE_RELEASE_ROOT``). Gates, evaluation, FastAPI, and
the vector runtime are imported lazily by :func:`prepare_release` only. Errors carry a
fixed code; no file content, question, or land value is ever part of an error or log.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple

SCHEMA_VERSION = "knowledge-release-v1"
MERGE_RECORD_VERSION = "knowledge-update-merge-v1"

RELEASES_DIR = "releases"
CURRENT_LINK = "current"
LOG_NAME = "release-log.jsonl"
LOCK_NAME = ".release.lock"
MANIFEST_NAME = "release-manifest.json"

CATALOG_FILE = "source_catalog.json"
PASSAGES_FILE = "passages.json"
CASES_FILE = "pac_answer_eval.json"
BM25_FILE = "bm25-index.json"
EVALUATION_FILE = "evaluation-report.json"
EMBEDDING_INDEX_FILE = "embedding-index.json"
VECTOR_STORE_DIR = "vector-store"
VECTOR_STORE_MANIFEST = "manijero-vector-store.json"

INPUT_FILES = (CATALOG_FILE, PASSAGES_FILE, CASES_FILE)
DERIVED_FILES = (BM25_FILE, EVALUATION_FILE)

RETRIEVAL_K = 5
FILE_MODE = 0o644
DIR_MODE = 0o755

STATEMENT = (
    "Built from canonical reviewed artifacts. "
    "Not a legal-coverage or answer-quality claim."
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = REPOSITORY_ROOT / "knowledge"
DEFAULT_EMBEDDING_CONFIG = REPOSITORY_ROOT / "backend" / "config" / "bge_m3_embedding.json"

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2

RELEASE_ID_PATTERN = re.compile(r"^[0-9a-f]{16}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CAMPAIGN_PATTERN = re.compile(r"^\d{4}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "release_id", "inputs", "approval", "build", "files", "bm25", "vector", "gate", "statement"}
)
INPUT_KEYS = frozenset({"catalog_sha256", "passages_sha256", "cases_sha256", "as_of", "active_campaign"})
MERGE_APPROVAL_KEYS = frozenset({"kind", "package_id", "approved_on", "merge_record_sha256"})
BASELINE_APPROVAL_KEYS = frozenset({"kind", "revision"})
BUILD_KEYS = frozenset(
    {"code_revision", "python_version", "unicode_data_version", "bm25", "retrieval_k"}
)
BM25_PARAMETER_KEYS = frozenset({"k1", "b"})
FILE_ENTRY_KEYS = frozenset({"sha256", "bytes"})
BM25_KEYS = frozenset({"index_sha256", "document_count"})
VECTOR_KEYS = frozenset(
    {
        "model",
        "embedding_index_sha256",
        "store_manifest_sha256",
        "documents_sha256",
        "vectors_sha256",
        "chromadb_version",
    }
)
VECTOR_MODEL_KEYS = frozenset(
    {"model_id", "model_revision", "embedding_dimension", "pooling", "normalize", "dtype", "config_sha256"}
)
GATE_KEYS = frozenset({"passed", "failures", "baseline_release_id", "summary"})
SUMMARY_KEYS = frozenset({"cases", "expected_state_agreement", "unexpected_answers"})
MERGE_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "package_id",
        "reviewer",
        "approved_on",
        "catalog_sha256",
        "passages_sha256",
        "canonical_changes_applied",
        "reindex_required",
        "reindexed",
        "released",
        "statement",
    }
)
ROOT_ENTRIES = frozenset({RELEASES_DIR, CURRENT_LINK, LOG_NAME, LOCK_NAME})


class ReleaseError(Exception):
    """A release operation failed with a fixed code and a CLI exit code."""

    def __init__(self, code: str, exit_code: int = EXIT_REFUSED, release_id: Optional[str] = None) -> None:
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code
        self.release_id = release_id


# --- Canonical JSON, hashing, and the manifest contract -----------------------------------


def canonical_json(value: Any) -> bytes:
    """Compact, key-sorted UTF-8 JSON: the input of every content digest."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def document_bytes(value: Any) -> bytes:
    """Readable, deterministic file form of a derived JSON document."""

    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def content_id(manifest: Mapping[str, Any]) -> str:
    """The release id: first 16 hex of SHA-256 over the manifest without ``release_id``."""

    body = {key: value for key, value in manifest.items() if key != "release_id"}
    return sha256_bytes(canonical_json(body))[:16]


def validate_manifest(document: Any) -> Dict[str, Any]:
    """Validate the closed ``knowledge-release-v1`` manifest; raise ``manifest_invalid``."""

    if not _manifest_is_valid(document):
        raise ReleaseError("manifest_invalid")
    return document


def _manifest_is_valid(document: Any) -> bool:
    if not isinstance(document, dict) or set(document) != TOP_LEVEL_KEYS:
        return False
    if document["schema_version"] != SCHEMA_VERSION or document["statement"] != STATEMENT:
        return False
    if not _matches(RELEASE_ID_PATTERN, document["release_id"]):
        return False
    inputs = document["inputs"]
    if not _closed(inputs, INPUT_KEYS):
        return False
    if not all(_matches(SHA256_PATTERN, inputs[key]) for key in ("catalog_sha256", "passages_sha256", "cases_sha256")):
        return False
    if not _is_iso_date(inputs["as_of"]) or not _matches(CAMPAIGN_PATTERN, inputs["active_campaign"]):
        return False
    if not _approval_is_valid(document["approval"]):
        return False
    build = document["build"]
    if not _closed(build, BUILD_KEYS):
        return False
    if not _matches(REVISION_PATTERN, build["code_revision"]):
        return False
    if not _non_blank(build["python_version"]) or not _non_blank(build["unicode_data_version"]):
        return False
    if not _closed(build["bm25"], BM25_PARAMETER_KEYS) or not all(
        _is_number(build["bm25"][key]) for key in BM25_PARAMETER_KEYS
    ):
        return False
    if not _is_int(build["retrieval_k"]) or build["retrieval_k"] < 1:
        return False
    gate = document["gate"]
    if not _gate_is_valid(gate):
        return False
    bm25 = document["bm25"]
    vector = document["vector"]
    expected_files = set(INPUT_FILES) | {EVALUATION_FILE}
    if bm25 is not None:
        if not _closed(bm25, BM25_KEYS) or not _matches(SHA256_PATTERN, bm25["index_sha256"]):
            return False
        if not _is_int(bm25["document_count"]) or bm25["document_count"] < 0:
            return False
        expected_files.add(BM25_FILE)
    elif gate["passed"]:
        return False
    if vector is not None:
        if not _vector_is_valid(vector) or not gate["passed"]:
            return False
        expected_files.add(EMBEDDING_INDEX_FILE)
    files = document["files"]
    if not isinstance(files, dict) or set(files) != expected_files:
        return False
    for entry in files.values():
        if not _closed(entry, FILE_ENTRY_KEYS) or not _matches(SHA256_PATTERN, entry["sha256"]):
            return False
        if not _is_int(entry["bytes"]) or entry["bytes"] < 0:
            return False
    if files[CATALOG_FILE]["sha256"] != inputs["catalog_sha256"]:
        return False
    if files[PASSAGES_FILE]["sha256"] != inputs["passages_sha256"]:
        return False
    if files[CASES_FILE]["sha256"] != inputs["cases_sha256"]:
        return False
    if bm25 is not None and files[BM25_FILE]["sha256"] != bm25["index_sha256"]:
        return False
    if vector is not None and files[EMBEDDING_INDEX_FILE]["sha256"] != vector["embedding_index_sha256"]:
        return False
    return document["release_id"] == content_id(document)


def _approval_is_valid(approval: Any) -> bool:
    if not isinstance(approval, dict):
        return False
    if approval.get("kind") == "merge_record":
        return (
            _closed(approval, MERGE_APPROVAL_KEYS)
            and _non_blank(approval["package_id"])
            and _is_iso_date(approval["approved_on"])
            and _matches(SHA256_PATTERN, approval["merge_record_sha256"])
        )
    if approval.get("kind") == "reviewed_git_baseline":
        return _closed(approval, BASELINE_APPROVAL_KEYS) and _matches(REVISION_PATTERN, approval["revision"])
    return False


def _gate_is_valid(gate: Any) -> bool:
    if not _closed(gate, GATE_KEYS) or not isinstance(gate["passed"], bool):
        return False
    failures = gate["failures"]
    if not isinstance(failures, list) or not all(_non_blank(code) for code in failures):
        return False
    if failures != sorted(set(failures)) or gate["passed"] != (not failures):
        return False
    baseline = gate["baseline_release_id"]
    if baseline is not None and not _matches(RELEASE_ID_PATTERN, baseline):
        return False
    summary = gate["summary"]
    if summary is None:
        return not gate["passed"]
    return _closed(summary, SUMMARY_KEYS) and all(_is_int(summary[key]) and summary[key] >= 0 for key in SUMMARY_KEYS)


def _vector_is_valid(vector: Any) -> bool:
    if not _closed(vector, VECTOR_KEYS) or not _closed(vector["model"], VECTOR_MODEL_KEYS):
        return False
    digests = ("embedding_index_sha256", "store_manifest_sha256", "documents_sha256", "vectors_sha256")
    return all(_matches(SHA256_PATTERN, vector[key]) for key in digests) and _non_blank(vector["chromadb_version"])


def _closed(value: Any, keys: frozenset) -> bool:
    return isinstance(value, dict) and set(value) == keys


def _matches(pattern: "re.Pattern[str]", value: Any) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_iso_date(value: Any) -> bool:
    if not _matches(DATE_PATTERN, value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


# --- Reading and verifying a release ------------------------------------------------------


def read_manifest(release_dir: Path) -> Dict[str, Any]:
    """Read and validate one release's manifest."""

    try:
        payload = (Path(release_dir) / MANIFEST_NAME).read_bytes()
    except FileNotFoundError as error:
        raise ReleaseError("release_not_found") from error
    except OSError as error:
        raise ReleaseError("manifest_invalid") from error
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ReleaseError("manifest_invalid") from error
    manifest = validate_manifest(document)
    if Path(release_dir).name != manifest["release_id"]:
        raise ReleaseError("manifest_invalid")
    return manifest


def verify_release(release_dir: Path) -> Dict[str, Any]:
    """Re-check every recorded file hash and size (and the store manifest when present)."""

    manifest = read_manifest(release_dir)
    for name, entry in manifest["files"].items():
        _check_file(Path(release_dir) / name, entry["sha256"], entry["bytes"])
    vector = manifest["vector"]
    if vector is not None:
        store_manifest = Path(release_dir) / VECTOR_STORE_DIR / VECTOR_STORE_MANIFEST
        try:
            payload = store_manifest.read_bytes()
            recorded = json.loads(payload.decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise ReleaseError("integrity_mismatch", release_id=manifest["release_id"]) from error
        inputs = recorded.get("inputs") if isinstance(recorded, dict) else None
        if (
            sha256_bytes(payload) != vector["store_manifest_sha256"]
            or not isinstance(inputs, dict)
            or inputs.get("documents_sha256") != vector["documents_sha256"]
            or recorded.get("vectors_sha256") != vector["vectors_sha256"]
        ):
            raise ReleaseError("integrity_mismatch", release_id=manifest["release_id"])
    return manifest


def _check_file(path: Path, expected_sha256: str, expected_bytes: int) -> bytes:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ReleaseError("integrity_mismatch", release_id=path.parent.name) from error
    if len(payload) != expected_bytes or sha256_bytes(payload) != expected_sha256:
        raise ReleaseError("integrity_mismatch", release_id=path.parent.name)
    return payload


def load_published_corpus(root: Path) -> Tuple[Any, Any, str]:
    """Return ``(catalog, passages, release_id)`` of the verified published release.

    Resolves ``current`` once, requires the target to be a direct child of
    ``<root>/releases``, validates the manifest and ``gate.passed``, and verifies and
    parses the catalog and passages from that one directory, so a concurrent publish
    can never mix two releases in one request.
    """

    release_dir = _resolve_current(Path(root))
    if release_dir is None:
        raise ReleaseError("no_current_release", EXIT_FAILED)
    manifest = read_manifest(release_dir)
    release_id = manifest["release_id"]
    if not manifest["gate"]["passed"]:
        raise ReleaseError("gate_failed", release_id=release_id)
    files = manifest["files"]
    catalog_bytes = _check_file(release_dir / CATALOG_FILE, files[CATALOG_FILE]["sha256"], files[CATALOG_FILE]["bytes"])
    passages_bytes = _check_file(
        release_dir / PASSAGES_FILE, files[PASSAGES_FILE]["sha256"], files[PASSAGES_FILE]["bytes"]
    )
    try:
        catalog = json.loads(catalog_bytes.decode("utf-8"))
        passages = json.loads(passages_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise ReleaseError("integrity_mismatch", release_id=release_id) from error
    return catalog, passages, release_id


# --- Root layout, safety, and the current pointer -----------------------------------------


def _inside(path: Path, directory: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(directory)))
    except ValueError:
        return False
    return True


def _check_root_location(root: Path) -> None:
    if _inside(root, KNOWLEDGE_ROOT) or _inside(KNOWLEDGE_ROOT, root):
        raise ReleaseError("unsafe_release_root")


def prepare_root(root: Path) -> Path:
    """Create or accept a release root (an empty directory or an existing release root)."""

    target = Path(root)
    _check_root_location(target)
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ReleaseError("unsafe_release_root")
    if target.exists():
        unexpected = [
            name for name in os.listdir(target) if name not in ROOT_ENTRIES and not name.startswith(".current-")
        ]
        if unexpected:
            raise ReleaseError("unsafe_release_root")
    else:
        try:
            target.mkdir(mode=DIR_MODE, parents=True)
            os.chmod(target, DIR_MODE)
        except OSError as error:
            raise ReleaseError("unsafe_release_root") from error
    releases = target / RELEASES_DIR
    if releases.is_symlink() or (releases.exists() and not releases.is_dir()):
        raise ReleaseError("unsafe_release_root")
    releases.mkdir(mode=DIR_MODE, exist_ok=True)
    os.chmod(releases, DIR_MODE)
    return target


def existing_root(root: Path) -> Path:
    target = Path(root)
    _check_root_location(target)
    if target.is_symlink() or not (target / RELEASES_DIR).is_dir() or (target / RELEASES_DIR).is_symlink():
        raise ReleaseError("unsafe_release_root")
    return target


def _resolve_current(root: Path) -> Optional[Path]:
    link = root / CURRENT_LINK
    if not os.path.lexists(link):
        return None
    resolved = Path(os.path.realpath(link))
    releases = Path(os.path.realpath(root / RELEASES_DIR))
    if resolved.parent != releases or not RELEASE_ID_PATTERN.fullmatch(resolved.name):
        raise ReleaseError("current_outside_releases")
    if not resolved.is_dir():
        raise ReleaseError("release_not_found", release_id=resolved.name)
    return resolved


def current_release_id(root: Path) -> Optional[str]:
    resolved = _resolve_current(Path(root))
    return None if resolved is None else resolved.name


def release_dir(root: Path, release_id: str) -> Path:
    if not RELEASE_ID_PATTERN.fullmatch(release_id or ""):
        raise ReleaseError("release_not_found")
    target = Path(root) / RELEASES_DIR / release_id
    if target.is_symlink() or not target.is_dir():
        raise ReleaseError("release_not_found", release_id=release_id)
    return target


@contextmanager
def release_lock(root: Path) -> Iterator[None]:
    """Exclusive ``O_CREAT|O_EXCL`` lock file; a held lock refuses with ``release_locked``."""

    path = Path(root) / LOCK_NAME
    try:
        handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, FILE_MODE)
    except FileExistsError as error:
        raise ReleaseError("release_locked") from error
    except OSError as error:
        raise ReleaseError("publish_failed") from error
    os.close(handle)
    try:
        yield
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _fsync_directory(directory: Path) -> None:
    try:
        handle = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)


def _point_current(root: Path, release_id: Optional[str]) -> None:
    """Atomically point ``current`` at ``releases/<release_id>`` (or remove it for ``None``)."""

    link = root / CURRENT_LINK
    if release_id is None:
        os.unlink(link)
        _fsync_directory(root)
        return
    temporary = root / ".current-{}".format(uuid.uuid4().hex)
    os.symlink(os.path.join(RELEASES_DIR, release_id), temporary)
    try:
        os.replace(temporary, link)
    except OSError:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    _fsync_directory(root)


# --- Release log ---------------------------------------------------------------------------


def read_log(root: Path) -> List[Dict[str, Any]]:
    path = Path(root) / LOG_NAME
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ReleaseError("log_unreadable") from error
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise ReleaseError("log_unreadable") from error
        if isinstance(event, dict):
            events.append(event)
    return events


def append_log(root: Path, event: Mapping[str, Any]) -> None:
    path = Path(root) / LOG_NAME
    line = json.dumps(dict(event), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    handle = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, FILE_MODE)
    try:
        _write_all(handle, line.encode("utf-8"))
        os.fsync(handle)
    finally:
        os.close(handle)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --- Publish, rollback, status, verify, compare --------------------------------------------


@dataclass(frozen=True)
class SwitchResult:
    """The outcome of a publish or rollback."""

    event: str
    release_id: str
    previous_release_id: Optional[str]
    already_current: bool = False


def _check_publishable(root: Path, release_id: str, as_of: date, campaign: str) -> Dict[str, Any]:
    target = release_dir(root, release_id)
    manifest = verify_release(target)
    if not manifest["gate"]["passed"]:
        raise ReleaseError("gate_failed", release_id=release_id)
    from app.readiness import evaluate_readiness  # lazy: the CLI path only

    from app.ask_api import CorpusDocuments

    catalog, passages = _parse_release_corpus(target, manifest)
    verdict = evaluate_readiness(CorpusDocuments(catalog=catalog, passages=passages), as_of, campaign)
    if not verdict.ready:
        raise ReleaseError("corpus_not_ready:{}".format(verdict.problems[0]), EXIT_FAILED, release_id=release_id)
    return manifest


def _parse_release_corpus(target: Path, manifest: Mapping[str, Any]) -> Tuple[Any, Any]:
    try:
        catalog = json.loads((target / CATALOG_FILE).read_text(encoding="utf-8"))
        passages = json.loads((target / PASSAGES_FILE).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ReleaseError("integrity_mismatch", release_id=manifest["release_id"]) from error
    return catalog, passages


def _switch(
    root: Path,
    event: str,
    release_id: str,
    as_of: date,
    campaign: str,
    clock: Callable[[], datetime],
) -> SwitchResult:
    _check_publishable(root, release_id, as_of, campaign)
    previous = current_release_id(root)
    if previous == release_id:
        events = read_log(root)
        if not events or events[-1].get("release_id") != release_id:
            append_log(root, _event(event, release_id, None, clock))
        return SwitchResult(event, release_id, None, already_current=True)
    try:
        _point_current(root, release_id)
    except OSError as error:
        raise ReleaseError("publish_failed", release_id=release_id) from error
    try:
        append_log(root, _event(event, release_id, previous, clock))
    except OSError as error:
        try:
            _point_current(root, previous)
        except OSError:
            pass
        raise ReleaseError("publish_failed", release_id=release_id) from error
    return SwitchResult(event, release_id, previous)


def _event(event: str, release_id: str, previous: Optional[str], clock: Callable[[], datetime]) -> Dict[str, Any]:
    return {
        "event": event,
        "release_id": release_id,
        "previous_release_id": previous,
        "at": clock().astimezone(timezone.utc).isoformat(timespec="seconds"),
    }


def publish(
    root: Path,
    release_id: str,
    as_of: date,
    active_campaign: str,
    clock: Callable[[], datetime] = _utc_now,
) -> SwitchResult:
    """Verify a passed, ready release and atomically make it ``current``."""

    target_root = existing_root(root)
    with release_lock(target_root):
        return _switch(target_root, "publish", release_id, as_of, active_campaign, clock)


def rollback(
    root: Path,
    as_of: date,
    active_campaign: str,
    to: Optional[str] = None,
    clock: Callable[[], datetime] = _utc_now,
) -> SwitchResult:
    """Return ``current`` to the release it replaced at its latest publish (or ``to``)."""

    target_root = existing_root(root)
    with release_lock(target_root):
        current = current_release_id(target_root)
        if current is None:
            raise ReleaseError("no_current_release", EXIT_FAILED)
        target = to
        if target is None:
            publishes = [
                event
                for event in read_log(target_root)
                if event.get("event") == "publish" and event.get("release_id") == current
            ]
            target = publishes[-1].get("previous_release_id") if publishes else None
            if not isinstance(target, str):
                raise ReleaseError("no_previous_release", EXIT_FAILED)
        return _switch(target_root, "rollback", target, as_of, active_campaign, clock)


@dataclass(frozen=True)
class StatusReport:
    current_release_id: Optional[str]
    gate_passed: Optional[bool]
    integrity: str
    log_in_sync: bool


def status(root: Path) -> StatusReport:
    """Report the current release, its gate, integrity, and log consistency."""

    target_root = existing_root(root)
    current = current_release_id(target_root)
    events = read_log(target_root)
    last = events[-1].get("release_id") if events else None
    if current is None:
        return StatusReport(None, None, "no_current_release", last is None)
    try:
        manifest = verify_release(target_root / RELEASES_DIR / current)
    except ReleaseError as error:
        return StatusReport(current, None, error.code, last == current)
    return StatusReport(current, manifest["gate"]["passed"], "ok", last == current)


def verify(root: Path, release_id: Optional[str] = None) -> Dict[str, Any]:
    """Verify hashes and rebuild the BM25 fingerprint from the release's own files."""

    target_root = existing_root(root)
    if release_id is None:
        release_id = current_release_id(target_root)
        if release_id is None:
            raise ReleaseError("no_current_release", EXIT_FAILED)
    target = release_dir(target_root, release_id)
    manifest = verify_release(target)
    bm25 = manifest["bm25"]
    if bm25 is not None:
        from app.release_gates import bm25_fingerprint  # lazy: not needed by the service

        catalog, passages = _parse_release_corpus(target, manifest)
        inputs = manifest["inputs"]
        try:
            rebuilt = bm25_fingerprint(
                catalog, passages, date.fromisoformat(inputs["as_of"]), inputs["active_campaign"]
            )
        except Exception as error:  # an invalid corpus can't match a recorded fingerprint
            raise ReleaseError("bm25_mismatch", EXIT_FAILED, release_id=release_id) from error
        if sha256_bytes(document_bytes(rebuilt)) != bm25["index_sha256"]:
            raise ReleaseError("bm25_mismatch", EXIT_FAILED, release_id=release_id)
    return manifest


def compare_releases(a: Path, b: Path) -> List[Tuple[str, str]]:
    """Return ``(tag, dotted_path)`` for every differing manifest field.

    Vector fields are tagged ``vector_digest_differs`` (they may legitimately differ
    across hosts and runtimes); everything else is tagged ``differs``.
    """

    first = read_manifest(Path(a))
    second = read_manifest(Path(b))
    differences: List[Tuple[str, str]] = []
    for path in sorted(set(_flatten(first)) | set(_flatten(second))):
        if _flatten(first).get(path, _MISSING) != _flatten(second).get(path, _MISSING):
            tag = "vector_digest_differs" if path == "vector" or path.startswith("vector.") else "differs"
            differences.append((tag, path))
    return differences


_MISSING = object()


def _flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(value, dict) and value:
        flat: Dict[str, Any] = {}
        for key, item in value.items():
            flat.update(_flatten(item, "{}.{}".format(prefix, key) if prefix else key))
        return flat
    return {prefix: json.dumps(value, sort_keys=True)}


# --- Prepare --------------------------------------------------------------------------------


@dataclass(frozen=True)
class PrepareResult:
    release_id: str
    passed: bool
    failures: Tuple[str, ...]
    baseline_release_id: Optional[str]
    manifest: Dict[str, Any] = field(repr=False)
    already_prepared: bool = False


def approval_from_options(
    merge_record: Optional[Path],
    reviewed_baseline_revision: Optional[str],
    catalog_sha256: str,
    passages_sha256: str,
) -> Dict[str, Any]:
    """Bind the candidate to exactly one kind of human-approval evidence."""

    if merge_record is None and reviewed_baseline_revision is None:
        raise ReleaseError("approval_evidence_required")
    if merge_record is not None and reviewed_baseline_revision is not None:
        raise ReleaseError("approval_evidence_ambiguous")
    if reviewed_baseline_revision is not None:
        if not REVISION_PATTERN.fullmatch(reviewed_baseline_revision):
            raise ReleaseError("approval_evidence_invalid")
        # An operator assertion: the tool cannot verify that this revision was reviewed.
        return {"kind": "reviewed_git_baseline", "revision": reviewed_baseline_revision}
    try:
        payload = Path(merge_record).read_bytes()  # type: ignore[arg-type]
        record = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ReleaseError("merge_record_invalid") from error
    if (
        not isinstance(record, dict)
        or set(record) != MERGE_RECORD_KEYS
        or record["schema_version"] != MERGE_RECORD_VERSION
        or record["canonical_changes_applied"] is not True
        or not _non_blank(record["package_id"])
        or not _is_iso_date(record["approved_on"])
        or not _matches(SHA256_PATTERN, record["catalog_sha256"])
        or not _matches(SHA256_PATTERN, record["passages_sha256"])
    ):
        raise ReleaseError("merge_record_invalid")
    if record["catalog_sha256"] != catalog_sha256 or record["passages_sha256"] != passages_sha256:
        raise ReleaseError("approval_mismatch")
    # The reviewer name stays in the review package (data minimization).
    return {
        "kind": "merge_record",
        "package_id": record["package_id"],
        "approved_on": record["approved_on"],
        "merge_record_sha256": sha256_bytes(payload),
    }


def _read_input(path: Path) -> bytes:
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise ReleaseError("input_unreadable") from error


def _baseline(root: Path) -> Tuple[Optional[str], Optional[Dict[str, Any]], List[str]]:
    """The currently published release's evaluation report, or ``baseline_unreadable``."""

    try:
        current = current_release_id(root)
    except ReleaseError:
        return None, None, ["baseline_unreadable"]
    if current is None:
        return None, None, []
    try:
        verify_release(root / RELEASES_DIR / current)
        report = json.loads((root / RELEASES_DIR / current / EVALUATION_FILE).read_text(encoding="utf-8"))
    except (ReleaseError, OSError, UnicodeDecodeError, ValueError):
        return current, None, ["baseline_unreadable"]
    return current, report, []


def prepare_release(
    *,
    root: Path,
    catalog: Path,
    passages: Path,
    cases: Path,
    as_of: date,
    active_campaign: str,
    code_revision: str,
    merge_record: Optional[Path] = None,
    reviewed_baseline_revision: Optional[str] = None,
    embedding_index: Optional[Path] = None,
    with_vector_store: bool = False,
    embedding_config: Path = DEFAULT_EMBEDDING_CONFIG,
) -> PrepareResult:
    """Build, gate, and write one release directory; the manifest is written last.

    Raises :class:`ReleaseError` (nothing written) for refused input. A candidate that
    fails a gate is still written with ``gate.passed: false`` so the operator can
    inspect it; it can never be published, rolled back to, or served.
    """

    if not REVISION_PATTERN.fullmatch(code_revision or ""):
        raise ReleaseError("code_revision_invalid")
    if not CAMPAIGN_PATTERN.fullmatch(active_campaign or ""):
        raise ReleaseError("active_campaign_invalid")
    if (embedding_index is None) != (not with_vector_store):
        raise ReleaseError("vector_options_incomplete")
    catalog_bytes = _read_input(catalog)
    passages_bytes = _read_input(passages)
    cases_bytes = _read_input(cases)
    approval = approval_from_options(
        merge_record, reviewed_baseline_revision, sha256_bytes(catalog_bytes), sha256_bytes(passages_bytes)
    )

    from app import release_gates  # lazy: FastAPI, evaluation, and optional vector tooling

    vector_plan = None
    if embedding_index is not None:
        vector_plan = release_gates.plan_vector_packaging(
            Path(embedding_index), Path(embedding_config), catalog_bytes, passages_bytes, as_of, active_campaign
        )

    target_root = prepare_root(Path(root))
    baseline_id, baseline_report, baseline_failures = _baseline(target_root)
    releases = target_root / RELEASES_DIR
    staging = releases / ".staging-{}".format(uuid.uuid4().hex)
    try:
        staging.mkdir(mode=DIR_MODE)
        for name, payload in ((CATALOG_FILE, catalog_bytes), (PASSAGES_FILE, passages_bytes), (CASES_FILE, cases_bytes)):
            _write_file(staging / name, payload)
        outcome = release_gates.run_gates(
            staging / CATALOG_FILE,
            staging / PASSAGES_FILE,
            staging / CASES_FILE,
            as_of=as_of,
            active_campaign=active_campaign,
            retrieval_k=RETRIEVAL_K,
            baseline_release_id=baseline_id,
            baseline_report=baseline_report,
        )
        failures = sorted(set(outcome.failures) | set(baseline_failures))
        files: Dict[str, Dict[str, Any]] = {
            name: _entry(payload)
            for name, payload in ((CATALOG_FILE, catalog_bytes), (PASSAGES_FILE, passages_bytes), (CASES_FILE, cases_bytes))
        }
        bm25 = None
        if outcome.bm25_document is not None:
            bm25_bytes = document_bytes(outcome.bm25_document)
            _write_file(staging / BM25_FILE, bm25_bytes)
            files[BM25_FILE] = _entry(bm25_bytes)
            bm25 = {"index_sha256": sha256_bytes(bm25_bytes), "document_count": outcome.bm25_document_count}
        evaluation_bytes = document_bytes(outcome.evaluation_document)
        _write_file(staging / EVALUATION_FILE, evaluation_bytes)
        files[EVALUATION_FILE] = _entry(evaluation_bytes)
        vector = None
        if vector_plan is not None and not failures:
            vector, index_bytes = release_gates.package_vectors(vector_plan, staging / VECTOR_STORE_DIR)
            _write_file(staging / EMBEDDING_INDEX_FILE, index_bytes)
            files[EMBEDDING_INDEX_FILE] = _entry(index_bytes)
        manifest: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "inputs": {
                "catalog_sha256": files[CATALOG_FILE]["sha256"],
                "passages_sha256": files[PASSAGES_FILE]["sha256"],
                "cases_sha256": files[CASES_FILE]["sha256"],
                "as_of": as_of.isoformat(),
                "active_campaign": active_campaign,
            },
            "approval": approval,
            "build": build_metadata(code_revision),
            "files": files,
            "bm25": bm25,
            "vector": vector,
            "gate": {
                "passed": not failures,
                "failures": failures,
                "baseline_release_id": baseline_id,
                "summary": outcome.summary,
            },
            "statement": STATEMENT,
        }
        manifest["release_id"] = content_id(manifest)
        validate_manifest(manifest)
        manifest_bytes = document_bytes(manifest)
        _write_file(staging / MANIFEST_NAME, manifest_bytes)
        _normalize_modes(staging)
        release_id = manifest["release_id"]
        final = releases / release_id
        already = False
        if os.path.lexists(final):
            try:
                existing = (final / MANIFEST_NAME).read_bytes()
            except OSError:
                existing = b""
            if existing != manifest_bytes:
                raise ReleaseError("release_conflict", release_id=release_id)
            already = True
            shutil.rmtree(staging, ignore_errors=True)
        else:
            os.rename(staging, final)
            _fsync_directory(releases)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return PrepareResult(
        release_id=release_id,
        passed=not failures,
        failures=tuple(failures),
        baseline_release_id=baseline_id,
        manifest=manifest,
        already_prepared=already,
    )


def build_metadata(code_revision: str) -> Dict[str, Any]:
    from app.retrieval import BM25_B, BM25_K1  # stdlib-only module

    return {
        "code_revision": code_revision,
        "python_version": "{}.{}.{}".format(*sys.version_info[:3]),
        "unicode_data_version": unicodedata.unidata_version,
        "bm25": {"k1": BM25_K1, "b": BM25_B},
        "retrieval_k": RETRIEVAL_K,
    }


def _entry(payload: bytes) -> Dict[str, Any]:
    return {"sha256": sha256_bytes(payload), "bytes": len(payload)}


def _write_file(path: Path, payload: bytes) -> None:
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    try:
        _write_all(handle, payload)
        os.fsync(handle)
    finally:
        os.close(handle)
    os.chmod(path, FILE_MODE)


def _write_all(handle: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(handle, view)
        view = view[written:]


def _normalize_modes(directory: Path) -> None:
    os.chmod(directory, DIR_MODE)
    for current, directories, names in os.walk(directory):
        for name in directories:
            os.chmod(os.path.join(current, name), DIR_MODE)
        for name in names:
            os.chmod(os.path.join(current, name), FILE_MODE)
