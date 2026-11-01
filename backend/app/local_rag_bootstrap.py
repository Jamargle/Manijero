"""One guided setup and one read-only status check for every local RAG artifact.

Operator-only and stdlib-only at import time; the answer service never imports this
module. It composes pieces that already exist and adds no runtime of its own:

* the shared hybrid environment (``scripts/python-env.sh hybrid``);
* the pinned ``bge-m3`` files (:mod:`app.pinned_download`, verified with
  :func:`app.embeddings.verify_artifact`);
* the passage index (``backend/scripts/manage_embeddings.py build``);
* a gated knowledge release with the Chroma store
  (``backend/scripts/knowledge_release.py prepare --with-vector-store`` then ``publish``);
* the pinned Ollama model (``ollama pull``, then the ``/api/tags`` digest).

Everything lives under one *local home* (default ``~/manijero/local``, see
:func:`local_paths`). :func:`inspect` reports one state per part (``OK``, ``MISSING``,
``PROBLEM``) with a fixed reason; :func:`make_plan` turns those states into ordered steps
and the bytes still to download; :func:`run_setup` checks every prerequisite before any
write, asks before any download, then runs only the unfinished steps; :func:`run_status`
only reads. Network access is limited to the pin-derived download URLs and loopback
Ollama. Every message is a fixed English sentence with no corpus text, question, or land
value; subprocess output goes only to the log file under ``<local home>/logs/``.

External effects go through injected ports (:class:`Ports`) so tests use fakes.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import traceback
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
)

from app import knowledge_release as kr
from app import pinned_download
from app.embedding_index import IndexInputs, index_status
from app.embeddings import EmbeddingError, EmbeddingModelSpec, load_model_spec, verify_artifact
from app.local_generation import (
    DEFAULT_RECORD_PATH,
    OLLAMA_BASE_URL,
    LocalModelRecord,
    evaluate_local_model_record,
    load_local_model_record,
    loopback_opener,
)
from app.vector_store import (
    MANIFEST_NAME as STORE_MANIFEST_NAME,
    VectorStoreError,
    manifest_status,
    read_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

SETUP_COMMAND = "./scripts/init.sh --local-rag-setup"
STATUS_COMMAND = "./scripts/init.sh --local-rag-status"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"

LOCAL_HOME_ENV = "MANIJERO_LOCAL_HOME"  # tests only
OLLAMA_CLI_ENV = "MANIJERO_OLLAMA_CLI"  # tests only
CAMPAIGN_KEY = "MANIJERO_ACTIVE_CAMPAIGN"
DEFAULT_CAMPAIGN = "2026"  # the same default as ./scripts/init.sh --backend

# The hybrid environment measured 1.2 GB on the development Mac (backend/README.md).
HYBRID_RUNTIME_BYTES = 1_200_000_000
FREE_SPACE_MARGIN_BYTES = 1_000_000_000
GIGABYTE = 1_000_000_000
LARGE_FILE_BYTES = 50_000_000
TAGS_TIMEOUT_SECONDS = 5.0
MAX_TAGS_BYTES = 1_048_576

KNOWLEDGE_FILES = (kr.CATALOG_FILE, kr.PASSAGES_FILE, kr.CASES_FILE)

OK = "OK"
MISSING = "MISSING"
PROBLEM = "PROBLEM"

PARTS: Tuple[Tuple[str, str], ...] = (
    ("software", "Search software"),
    ("model", "Search model (bge-m3)"),
    ("index", "Passage index"),
    ("store", "Vector store"),
    ("release", "Knowledge release"),
    ("drafting", "Drafting model"),
)
PART_LABELS = dict(PARTS)

_RUN_SETUP = "Run {}.".format(SETUP_COMMAND)
_REBUILD = "Run {} to rebuild it.".format(SETUP_COMMAND)

# reason -> (what it means, the first thing to do)
REASONS: Mapping[str, Tuple[str, str]] = {
    "ready": ("ready.", ""),
    "software_missing": ("not installed yet.", _RUN_SETUP),
    "model_missing": ("not downloaded yet.", _RUN_SETUP),
    "model_incomplete": ("the download is not finished.", "Run {} to continue it.".format(SETUP_COMMAND)),
    "model_damaged": (
        "a file is damaged or differs from the reviewed version.",
        "Run {}; it fetches only the bad files again.".format(SETUP_COMMAND),
    ),
    "index_missing": ("not built yet.", _RUN_SETUP),
    "index_stale": ("out of date for the current knowledge.", _REBUILD),
    "index_invalid": ("damaged.", _REBUILD),
    "store_missing": ("not built yet.", _RUN_SETUP),
    "store_stale": ("out of date for the current knowledge.", _REBUILD),
    "store_invalid": ("damaged.", _REBUILD),
    "in_damaged_release": ("part of a damaged knowledge release.", _REBUILD),
    "release_missing": ("no knowledge release is published yet.", _RUN_SETUP),
    "release_damaged": ("the published release is damaged.", "Run {} to build a new one.".format(SETUP_COMMAND)),
    "release_knowledge_changed": ("the knowledge files changed since it was built.", _REBUILD),
    "release_campaign_changed": ("it was built for a different campaign than the settings file.", _REBUILD),
    "release_not_ready": (
        "the reviewed knowledge is not valid for today's date.",
        "A developer must update the knowledge; setup cannot fix this.",
    ),
    "drafting_missing": ("not downloaded yet.", _RUN_SETUP),
    "drafting_mismatch": (
        "Ollama has a different version than the reviewed one.",
        "Run {}; if it still differs, a developer must review it.".format(SETUP_COMMAND),
    ),
    "ollama_not_running": ("Ollama is not running.", "Open the Ollama app, then run this command again."),
    "ollama_not_installed": (
        "Ollama is not installed.",
        "Install it from {}, then run this command again.".format(OLLAMA_DOWNLOAD_URL),
    ),
    "ollama_bad_answer": (
        "Ollama did not answer as expected.",
        "Quit and reopen the Ollama app, then run this command again.",
    ),
}

STEP_SOFTWARE = "software"
STEP_MODEL = "model"
STEP_INDEX = "index"
STEP_PREPARE = "prepare"
STEP_PUBLISH = "publish"
STEP_DRAFTING = "drafting"
STEP_TITLES = {
    STEP_SOFTWARE: "Installing the search software (this can take several minutes)",
    STEP_MODEL: "Downloading the search model bge-m3",
    STEP_INDEX: "Building the passage index",
    STEP_PREPARE: "Preparing a knowledge release with the vector store and checking it",
    STEP_PUBLISH: "Publishing the knowledge release",
    STEP_DRAFTING: "Downloading the drafting model with Ollama",
}
REBUILD_PARTS = ("index", "store", "release")

# Prerequisite stops (nothing has been changed yet).
MSG_OLLAMA_MISSING = (
    "Ollama is not installed on this computer. Install it from {}, open it once, "
    "then run {} again.".format(OLLAMA_DOWNLOAD_URL, SETUP_COMMAND)
)
MSG_OLLAMA_NOT_RUNNING = (
    "Ollama is installed but not running. Open the Ollama app, wait a few seconds, "
    "then run {} again.".format(SETUP_COMMAND)
)
MSG_OLLAMA_BAD_ANSWER = (
    "Ollama did not answer as expected. Quit and reopen the Ollama app, then run {} again.".format(SETUP_COMMAND)
)
MSG_KNOWLEDGE_DIRTY = (
    "The knowledge files in this checkout have changes that are not committed to Git. "
    "Ask a developer to commit or undo them, then run {} again.".format(SETUP_COMMAND)
)
MSG_LOCK_HELD = (
    "Another setup is already running on this computer. Wait for it to finish, "
    "then run {} again.".format(SETUP_COMMAND)
)

# Step failures (finished parts are kept).
MSG_SOFTWARE_FAILED = (
    "The search software could not be installed. Check the internet connection, then run {} again.".format(
        SETUP_COMMAND
    )
)
MSG_MODEL_NETWORK = (
    "The search model download stopped. Check the internet connection, then run {} again; "
    "finished files are kept.".format(SETUP_COMMAND)
)
MSG_MODEL_MISMATCH = (
    "The downloaded search model differs from the reviewed version, so it was discarded and "
    "nothing else was changed. A developer must review it before setup can continue."
)
MSG_MODEL_REDIRECT = (
    "The download server sent the search model request to an address that is not secure, so it "
    "was refused. A developer must review it before setup can continue."
)
MSG_INDEX_FAILED = (
    "The passage index could not be built. Run {} again; if it fails again, send the log file "
    "to a developer.".format(SETUP_COMMAND)
)
MSG_PREPARE_FAILED = (
    "The knowledge release could not be prepared, so the previous release stays in use. Run {} "
    "again; if it fails again, send the log file to a developer.".format(SETUP_COMMAND)
)
MSG_PUBLISH_FAILED = (
    "The new knowledge release could not be published, so the previous release stays in use. "
    "Run {} again; if it fails again, send the log file to a developer.".format(SETUP_COMMAND)
)
MSG_DRAFTING_FAILED = (
    "The drafting model download did not finish. Check the internet connection and that Ollama "
    "is open, then run {} again.".format(SETUP_COMMAND)
)
MSG_DRAFTING_MISMATCH = (
    "The drafting model Ollama downloaded differs from the reviewed version, so it is not used. "
    "Nothing in the reviewed settings was changed; a developer must review it."
)

# Release-gate failure code prefixes in plain words.
GATE_WORDS: Tuple[Tuple[str, str], ...] = (
    ("corpus_not_ready", "the reviewed knowledge is not valid for today's date or for the campaign in the settings file"),
    ("evaluation_regression", "an answer check got worse than with the release in use"),
    ("grounding_", "an answer did not cite the reviewed text correctly"),
    ("catalog_invalid", "the knowledge files are not valid"),
    ("passages_invalid", "the knowledge files are not valid"),
    ("passage_source_unresolved", "the knowledge files are not valid"),
    ("cases_", "the answer checks do not match the knowledge"),
    ("evaluation_failed", "the answer checks could not run"),
    ("bm25_nondeterministic", "the search index was not reproducible"),
    ("baseline_unreadable", "the release in use could not be read for comparison"),
)


# --- Errors -------------------------------------------------------------------------------


class BootstrapError(Exception):
    """A plain-language stop raised before anything is changed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SettingsError(BootstrapError):
    """The settings file is unreadable or has an invalid line."""


class StepFailed(Exception):
    """A setup step failed after changes began; finished parts are kept."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class OllamaUnavailable(Exception):
    """Ollama did not answer: ``not_running`` or ``bad_answer``."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# --- Local home and settings --------------------------------------------------------------


@dataclass(frozen=True)
class LocalPaths:
    """Every path under one local home; ``local_full_rag_stack`` reuses this layout."""

    home: Path
    settings: Path
    models: Path
    bge_m3: Path
    work: Path
    embedding_index: Path
    releases: Path
    logs: Path
    lock: Path

    @property
    def current_release(self) -> Path:
        return self.releases / kr.CURRENT_LINK


def default_home() -> Path:
    configured = os.environ.get(LOCAL_HOME_ENV, "").strip()
    return Path(configured).expanduser() if configured else Path.home() / "manijero" / "local"


def local_paths(home: Optional[Path] = None) -> LocalPaths:
    root = Path(home) if home is not None else default_home()
    models = root / "models"
    work = root / "work"
    return LocalPaths(
        home=root,
        settings=root / "settings.env",
        models=models,
        bge_m3=models / "bge-m3",
        work=work,
        embedding_index=work / "embedding-index.json",
        releases=root / "knowledge-releases",
        logs=root / "logs",
        lock=root / ".setup.lock",
    )


@dataclass(frozen=True)
class Settings:
    active_campaign: str


SETTINGS_TEMPLATE = """\
# Manijero local settings.
#
# Created by {setup}. Lines that start with # are notes and are ignored.
# Change a value only after the word or number after the = sign, then run
# {status} to check that everything is still ready.

# The PAC campaign year the answers use: four digits, for example 2026.
{key}={campaign}
""".format(setup=SETUP_COMMAND, status=STATUS_COMMAND, key=CAMPAIGN_KEY, campaign=DEFAULT_CAMPAIGN)


def read_settings(path: Path) -> Optional[Settings]:
    """Parse the allowlisted ``KEY=VALUE`` settings file; ``None`` when it does not exist.

    The file is never executed or sourced. An unknown key, a repeated key, or an invalid
    value stops the command with a sentence naming the line to fix.
    """

    target = Path(path)
    if not target.exists():
        return None
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise SettingsError(
            "The settings file {} cannot be read. Make sure it is a plain text file, then run the "
            "same command again.".format(target)
        ) from error
    values: Dict[str, str] = {}
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise _line_error(target, number, "it must look like NAME=value")
        key, value = (part.strip() for part in line.split("=", 1))
        if key != CAMPAIGN_KEY:
            raise _line_error(target, number, "it is not a setting this tool knows")
        if key in values:
            raise _line_error(target, number, "this setting appears twice")
        value = _unquote(value)
        if len(value) != 4 or not value.isdigit():
            raise _line_error(target, number, "the campaign must be a four-digit year, for example 2026")
        values[key] = value
    if CAMPAIGN_KEY not in values:
        raise SettingsError(
            "The settings file {} does not set the campaign. Add the line {}={}, then run the same "
            "command again.".format(target, CAMPAIGN_KEY, DEFAULT_CAMPAIGN)
        )
    return Settings(active_campaign=values[CAMPAIGN_KEY])


def create_settings(path: Path) -> bool:
    """Create the commented settings file with safe defaults; never overwrite one."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(SETTINGS_TEMPLATE)
    return True


def _line_error(path: Path, number: int, problem: str) -> SettingsError:
    return SettingsError(
        "The settings file {} has a problem on line {}: {}. Fix that line, then run the same "
        "command again.".format(path, number, problem)
    )


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1].strip()
    return value


# --- Ports --------------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class RunLog:
    """A log file under ``<local home>/logs/``, created only when something is written."""

    def __init__(self, directory: Path, command: str, now: Callable[[], datetime]) -> None:
        self._directory = Path(directory)
        self._command = command
        self._now = now
        self._path: Optional[Path] = None

    def ensure(self) -> Path:
        if self._path is None:
            self._directory.mkdir(parents=True, exist_ok=True)
            stamp = self._now().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            self._path = self._directory / "{}-{}.log".format(self._command, stamp)
            self._path.touch()
        return self._path

    def write(self, text: str) -> None:
        if not text:
            return
        with self.ensure().open("a", encoding="utf-8") as stream:
            stream.write(text if text.endswith("\n") else text + "\n")

    def write_traceback(self) -> Path:
        self.write(traceback.format_exc())
        return self.ensure()


class Ollama(Protocol):
    def cli_present(self) -> bool: ...

    def tags(self) -> List[Mapping[str, Any]]: ...

    def pull(self, model: str) -> int: ...


class Checkout(Protocol):
    def knowledge_dirty(self) -> bool: ...

    def head_revision(self) -> str: ...

    def hybrid_ready(self) -> bool: ...

    def venv_root(self) -> Path: ...


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], log: RunLog) -> CommandResult: ...


class Prompter(Protocol):
    def ask(self, question: str) -> Optional[str]: ...


class Disk(Protocol):
    def free_bytes(self, path: Path) -> int: ...

    def device(self, path: Path) -> int: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


@dataclass
class Ports:
    """Every external effect; tests pass fakes. ``opener`` serves the pinned downloads."""

    ollama: Ollama
    checkout: Checkout
    runner: CommandRunner
    prompter: Prompter
    disk: Disk
    clock: Clock
    opener: Any
    out: Callable[[str], None]

    def today(self) -> date:
        return self.clock.now().astimezone(timezone.utc).date()


@dataclass(frozen=True)
class Context:
    """Where the inputs and outputs live; tests point these at temporary copies."""

    repo_root: Path
    paths: LocalPaths
    knowledge_dir: Path
    embedding_config: Path
    generation_record: Path
    dev_python: str
    hybrid_python: str
    ollama_models: Path

    @property
    def python_env_script(self) -> Path:
        return self.repo_root / "scripts" / "python-env.sh"

    @property
    def embeddings_script(self) -> Path:
        return self.repo_root / "backend" / "scripts" / "manage_embeddings.py"

    @property
    def release_script(self) -> Path:
        return self.repo_root / "backend" / "scripts" / "knowledge_release.py"

    def knowledge_file(self, name: str) -> Path:
        return self.knowledge_dir / name


def default_context(dev_python: str, home: Optional[Path] = None) -> Context:
    configured = os.environ.get("OLLAMA_MODELS", "").strip()
    return Context(
        repo_root=REPOSITORY_ROOT,
        paths=local_paths(home),
        knowledge_dir=REPOSITORY_ROOT / "knowledge",
        embedding_config=kr.DEFAULT_EMBEDDING_CONFIG,
        generation_record=DEFAULT_RECORD_PATH,
        dev_python=dev_python,
        hybrid_python=str(REPOSITORY_ROOT / "backend" / ".venv-hybrid" / "bin" / "python"),
        ollama_models=Path(configured).expanduser() if configured else Path.home() / ".ollama" / "models",
    )


# --- Inspection ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PartState:
    part: str
    state: str
    reason: str

    @property
    def ok(self) -> bool:
        return self.state == OK


@dataclass(frozen=True)
class Inspection:
    parts: Tuple[PartState, ...]
    model_pending: Tuple[pinned_download.PendingFile, ...]

    def part(self, key: str) -> PartState:
        return next(state for state in self.parts if state.part == key)

    @property
    def all_ok(self) -> bool:
        return all(state.ok for state in self.parts)

    @property
    def ready_count(self) -> int:
        return sum(1 for state in self.parts if state.ok)


def load_pins(ctx: Context, today: date) -> Tuple[EmbeddingModelSpec, LocalModelRecord]:
    """Load the two reviewed pins; a broken pin is a developer problem, never edited here."""

    try:
        spec = load_model_spec(ctx.embedding_config)
    except EmbeddingError as error:
        raise BootstrapError(
            "The reviewed search-model pin {} is not valid. A developer must review it.".format(
                ctx.embedding_config
            )
        ) from error
    _, record = evaluate_local_model_record(load_local_model_record(ctx.generation_record), as_of=today)
    if record is None:
        raise BootstrapError(
            "The reviewed drafting-model record {} is not valid. A developer must review it.".format(
                ctx.generation_record
            )
        )
    return spec, record


def inspect(
    ctx: Context, ports: Ports, spec: EmbeddingModelSpec, record: LocalModelRecord, campaign: str
) -> Inspection:
    """Report one state per part; reads only (plus loopback Ollama)."""

    software = PartState("software", OK, "ready") if ports.checkout.hybrid_ready() else PartState(
        "software", MISSING, "software_missing"
    )
    model, pending = _inspect_model(ctx, spec)
    index, store, release = _inspect_release(ctx, spec, campaign, ports.today())
    drafting = _inspect_drafting(ports, record)
    return Inspection(parts=(software, model, index, store, release, drafting), model_pending=pending)


def _inspect_model(
    ctx: Context, spec: EmbeddingModelSpec
) -> Tuple[PartState, Tuple[pinned_download.PendingFile, ...]]:
    pending = pinned_download.pending_files(spec, ctx.paths.bge_m3)
    if not pending:
        return PartState("model", OK, "ready"), pending
    damaged = any((ctx.paths.bge_m3 / item.path).exists() for item in pending)
    if damaged:
        return PartState("model", PROBLEM, "model_damaged"), pending
    started = len(pending) < len(spec.files) or any(item.missing_bytes < item.size for item in pending)
    return PartState("model", MISSING, "model_incomplete" if started else "model_missing"), pending


def _inspect_release(
    ctx: Context, spec: EmbeddingModelSpec, campaign: str, today: date
) -> Tuple[PartState, PartState, PartState]:
    def trio(state: str, index_reason: str, store_reason: str, release_reason: str) -> Tuple[PartState, PartState, PartState]:
        return (
            PartState("index", state, index_reason),
            PartState("store", state, store_reason),
            PartState("release", state, release_reason),
        )

    root = ctx.paths.releases
    if not (root / kr.RELEASES_DIR).is_dir():
        return trio(MISSING, "index_missing", "store_missing", "release_missing")
    try:
        current = kr.current_release_id(root)
        manifest = kr.verify_release(root / kr.RELEASES_DIR / current) if current else None
    except kr.ReleaseError:
        return trio(PROBLEM, "in_damaged_release", "in_damaged_release", "release_damaged")
    if manifest is None:
        return trio(MISSING, "index_missing", "store_missing", "release_missing")
    release_dir = root / kr.RELEASES_DIR / manifest["release_id"]

    payloads = {name: ctx.knowledge_file(name).read_bytes() for name in KNOWLEDGE_FILES}
    catalog = json.loads(payloads[kr.CATALOG_FILE].decode("utf-8"))
    passages = json.loads(payloads[kr.PASSAGES_FILE].decode("utf-8"))
    release = PartState("release", OK, "ready")
    inputs = manifest["inputs"]
    if (
        inputs["catalog_sha256"] != kr.sha256_bytes(payloads[kr.CATALOG_FILE])
        or inputs["passages_sha256"] != kr.sha256_bytes(payloads[kr.PASSAGES_FILE])
        or inputs["cases_sha256"] != kr.sha256_bytes(payloads[kr.CASES_FILE])
    ):
        release = PartState("release", PROBLEM, "release_knowledge_changed")
    elif inputs["active_campaign"] != campaign:
        release = PartState("release", PROBLEM, "release_campaign_changed")
    elif not manifest["gate"]["passed"] or not _corpus_ready(catalog, passages, today, campaign):
        release = PartState("release", PROBLEM, "release_not_ready")

    if manifest["vector"] is None:
        return (PartState("index", MISSING, "index_missing"), PartState("store", MISSING, "store_missing"), release)
    index = _inspect_index(release_dir, spec, payloads, inputs["as_of"], campaign)
    store = _inspect_store(release_dir, spec, catalog, passages, today, campaign)
    return index, store, release


def _corpus_ready(catalog: Any, passages: Any, today: date, campaign: str) -> bool:
    from app.ask_api import CorpusDocuments  # lazy: FastAPI is in the dev environment only
    from app.readiness import evaluate_readiness

    return evaluate_readiness(CorpusDocuments(catalog=catalog, passages=passages), today, campaign).ready


def _inspect_index(
    release_dir: Path, spec: EmbeddingModelSpec, payloads: Mapping[str, bytes], as_of: str, campaign: str
) -> PartState:
    inputs = IndexInputs(
        catalog_sha256=kr.sha256_bytes(payloads[kr.CATALOG_FILE]),
        passages_sha256=kr.sha256_bytes(payloads[kr.PASSAGES_FILE]),
        as_of=as_of,
        active_campaign=campaign,
    )
    status = index_status(release_dir / kr.EMBEDDING_INDEX_FILE, spec, inputs)
    if status.up_to_date:
        return PartState("index", OK, "ready")
    if status.state == "missing":
        return PartState("index", MISSING, "index_missing")
    return PartState("index", PROBLEM, "index_stale" if status.state == "stale" else "index_invalid")


def _inspect_store(
    release_dir: Path, spec: EmbeddingModelSpec, catalog: Any, passages: Any, today: date, campaign: str
) -> PartState:
    from app.retrieval import Retriever  # stdlib-only

    store_dir = release_dir / kr.VECTOR_STORE_DIR
    if not (store_dir / STORE_MANIFEST_NAME).exists():
        return PartState("store", MISSING, "store_missing")
    try:
        manifest = read_manifest(store_dir)
    except VectorStoreError:
        return PartState("store", PROBLEM, "store_invalid")
    try:
        # The documents the answer service would admit today, as the hybrid backend checks.
        documents = Retriever.from_documents(catalog, passages, today, active_campaign=campaign).indexed_documents()
    except Exception:  # noqa: BLE001 - an invalid corpus cannot match a store
        return PartState("store", PROBLEM, "store_stale")
    if manifest_status(manifest, spec, campaign, documents).up_to_date:
        return PartState("store", OK, "ready")
    return PartState("store", PROBLEM, "store_stale")


def _inspect_drafting(ports: Ports, record: LocalModelRecord) -> PartState:
    try:
        models = ports.ollama.tags()
    except OllamaUnavailable as error:
        if error.code == "not_running":
            reason = "ollama_not_running" if ports.ollama.cli_present() else "ollama_not_installed"
        else:
            reason = "ollama_bad_answer"
        return PartState("drafting", PROBLEM, reason)
    entry = find_model(models, record.model)
    if entry is None:
        return PartState("drafting", MISSING, "drafting_missing")
    if entry.get("digest") != record.digest:
        return PartState("drafting", PROBLEM, "drafting_mismatch")
    return PartState("drafting", OK, "ready")


def find_model(models: Sequence[Mapping[str, Any]], tag: str) -> Optional[Mapping[str, Any]]:
    """The ``/api/tags`` entry for ``tag`` (matched like ``OllamaTransport``), if any."""

    return next(
        (item for item in models if isinstance(item, Mapping) and tag in (item.get("name"), item.get("model"))),
        None,
    )


# --- Plan ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Download:
    label: str
    size_bytes: int
    approximate: bool
    target: Path


@dataclass(frozen=True)
class Plan:
    steps: Tuple[str, ...]
    downloads: Tuple[Download, ...] = field(default=())

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.downloads)

    @property
    def empty(self) -> bool:
        return not self.steps


def make_plan(
    inspection: Inspection, ctx: Context, record: LocalModelRecord, venv_root: Path
) -> Plan:
    """Turn part states into ordered steps and the downloads they need (sizes from the pins)."""

    steps: List[str] = []
    downloads: List[Download] = []
    if not inspection.part("software").ok:
        steps.append(STEP_SOFTWARE)
        downloads.append(
            Download("Search software (hybrid environment)", HYBRID_RUNTIME_BYTES, True, venv_root)
        )
    if not inspection.part("model").ok:
        steps.append(STEP_MODEL)
        missing = sum(item.missing_bytes for item in inspection.model_pending)
        downloads.append(Download("Search model bge-m3", missing, False, ctx.paths.bge_m3))
    if any(not inspection.part(key).ok for key in REBUILD_PARTS):
        steps.extend((STEP_INDEX, STEP_PREPARE, STEP_PUBLISH))
    if not inspection.part("drafting").ok:
        steps.append(STEP_DRAFTING)
        downloads.append(
            Download("Drafting model ({})".format(record.model), record.size_bytes, False, ctx.ollama_models)
        )
    return Plan(steps=tuple(steps), downloads=tuple(downloads))


def format_size(size_bytes: int, approximate: bool = False) -> str:
    """Gigabytes with one decimal (``2.3 GB``), the unit the owner sees everywhere."""

    if size_bytes < GIGABYTE // 20:
        return "less than 0.1 GB"
    text = "{:.1f} GB".format(size_bytes / GIGABYTE)
    return "about " + text if approximate else text


def confirmation_lines(plan: Plan) -> List[str]:
    lines = ["Setup will download:"]
    for item in plan.downloads:
        lines.append("  - {}: {}".format(item.label, format_size(item.size_bytes, item.approximate)))
    approximate = any(item.approximate for item in plan.downloads)
    lines.append("  Total: {}".format(format_size(plan.total_bytes, approximate)))
    lines.append("Downloads can take a long time on a slow connection. If setup stops, finished parts are kept.")
    return lines


CONFIRMATION_QUESTION = "Type yes and press Enter to start (anything else cancels): "


# --- Prerequisites ------------------------------------------------------------------------


def _check_ollama(ports: Ports) -> None:
    if not ports.ollama.cli_present():
        raise BootstrapError(MSG_OLLAMA_MISSING)
    try:
        ports.ollama.tags()
    except OllamaUnavailable as error:
        raise BootstrapError(MSG_OLLAMA_NOT_RUNNING if error.code == "not_running" else MSG_OLLAMA_BAD_ANSWER)


def _check_disk(plan: Plan, ctx: Context, ports: Ports) -> None:
    targets: List[Tuple[Path, int]] = [(item.target, item.size_bytes) for item in plan.downloads]
    if plan.steps:
        targets.append((ctx.paths.home, 0))
    needed: Dict[int, List[Any]] = {}
    for target, size in targets:
        anchor = existing_anchor(target)
        device = ports.disk.device(anchor)
        entry = needed.setdefault(device, [anchor, 0])
        entry[1] += size
    for anchor, size in needed.values():
        required = size + FREE_SPACE_MARGIN_BYTES
        free = ports.disk.free_bytes(anchor)
        if free < required:
            raise BootstrapError(
                "There is not enough free space on the disk that holds {}: setup needs {} free and "
                "only {} is free. Free up space (for example, empty the Trash), then run {} "
                "again.".format(anchor, format_size(required), format_size(free), SETUP_COMMAND)
            )


def existing_anchor(path: Path) -> Path:
    """The nearest existing ancestor of ``path`` (the filesystem it will be written to)."""

    candidate = Path(path).expanduser().absolute()
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def lock_is_held(path: Path) -> bool:
    """Whether another setup holds the lock; never creates the lock file."""

    try:
        handle = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(handle, fcntl.LOCK_UN)
        return False
    finally:
        os.close(handle)


@contextmanager
def setup_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive ``flock`` on ``<local home>/.setup.lock`` for the whole setup."""

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BootstrapError(MSG_LOCK_HELD) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


# --- Commands -----------------------------------------------------------------------------


def status_lines(inspection: Inspection) -> List[str]:
    lines = []
    for state in inspection.parts:
        meaning, action = REASONS[state.reason]
        text = "{:<8} {}: {}".format(state.state, PART_LABELS[state.part], meaning)
        if action and not state.ok:
            text += " " + action
        lines.append(text)
    return lines


def run_status(ctx: Context, ports: Ports) -> int:
    """Print six part lines and one result line; exit 0 only when all six are OK."""

    out = ports.out
    settings = read_settings(ctx.paths.settings)
    spec, record = load_pins(ctx, ports.today())
    campaign = settings.active_campaign if settings else DEFAULT_CAMPAIGN
    out("Local answer tools in {}:".format(ctx.paths.home))
    inspection = inspect(ctx, ports, spec, record, campaign)
    for line in status_lines(inspection):
        out(line)
    if settings is None:
        out("Result: setup has not run yet. Run {} to set everything up.".format(SETUP_COMMAND))
        return 1
    if inspection.all_ok:
        out("Result: all 6 parts are ready.")
        return 0
    out(
        "Result: {} of 6 parts are ready. Do the first step shown on the first line that is not OK.".format(
            inspection.ready_count
        )
    )
    return 1


def run_setup(ctx: Context, ports: Ports, log: RunLog) -> int:
    """Check prerequisites, show and confirm downloads, then run only the unfinished steps."""

    out = ports.out
    settings = read_settings(ctx.paths.settings)
    spec, record = load_pins(ctx, ports.today())
    campaign = settings.active_campaign if settings else DEFAULT_CAMPAIGN
    out("Checking this computer and what is already set up...")
    try:
        _check_ollama(ports)
        if ports.checkout.knowledge_dirty():
            raise BootstrapError(MSG_KNOWLEDGE_DIRTY)
        inspection = inspect(ctx, ports, spec, record, campaign)
        plan = make_plan(inspection, ctx, record, ports.checkout.venv_root())
        if plan.steps:
            _check_disk(plan, ctx, ports)
        if lock_is_held(ctx.paths.lock):
            raise BootstrapError(MSG_LOCK_HELD)
    except BootstrapError as stop:
        out(stop.message)
        out("Result: setup stopped before changing anything.")
        return 1

    if plan.empty and settings is not None:
        for line in status_lines(inspection):
            out(line)
        out("Result: everything is already set up. Nothing was downloaded or changed.")
        return 0

    if plan.downloads:
        for line in confirmation_lines(plan):
            out(line)
        answer = ports.prompter.ask(CONFIRMATION_QUESTION)
        if answer is None or answer.strip().lower() not in ("yes", "y"):
            out("Nothing was changed.")
            out("Result: setup cancelled. Run {} again when you are ready.".format(SETUP_COMMAND))
            return 1

    try:
        with setup_lock(ctx.paths.lock):
            if create_settings(ctx.paths.settings):
                out("Created the settings file {} (campaign {}).".format(ctx.paths.settings, campaign))
            settings = read_settings(ctx.paths.settings)
            campaign = settings.active_campaign if settings else DEFAULT_CAMPAIGN
            runner = _StepRunner(ctx, ports, log, spec, record, campaign)
            for number, step in enumerate(plan.steps, start=1):
                out("Step {} of {}: {}...".format(number, len(plan.steps), STEP_TITLES[step]))
                log.write("== step {} of {}: {} ==".format(number, len(plan.steps), step))
                runner.run(step)
    except BootstrapError as stop:
        out(stop.message)
        out("Result: setup stopped; nothing more was changed.")
        return 1
    except StepFailed as failure:
        out(failure.message)
        out("Details are in the log file: {}".format(log.ensure()))
        out("Result: setup stopped; finished parts are kept.")
        return 1

    final = inspect(ctx, ports, spec, record, campaign)
    for line in status_lines(final):
        out(line)
    if final.all_ok:
        out("Result: everything is set up. Check it any time with {}.".format(STATUS_COMMAND))
        return 0
    out("Result: setup finished, but not every part is ready; do the first step shown above.")
    return 1


class _StepRunner:
    """Runs one setup step; failures raise :class:`StepFailed` with a fixed sentence."""

    def __init__(
        self,
        ctx: Context,
        ports: Ports,
        log: RunLog,
        spec: EmbeddingModelSpec,
        record: LocalModelRecord,
        campaign: str,
    ) -> None:
        self._ctx = ctx
        self._ports = ports
        self._log = log
        self._spec = spec
        self._record = record
        self._campaign = campaign
        self._release_id: Optional[str] = None

    def run(self, step: str) -> None:
        getattr(self, "_" + step)()

    def _software(self) -> None:
        result = self._ports.runner.run([str(self._ctx.python_env_script), "hybrid"], self._log)
        if result.returncode != 0 or not self._ports.checkout.hybrid_ready():
            raise StepFailed(MSG_SOFTWARE_FAILED)

    def _model(self) -> None:
        progress = DownloadProgress(self._ports.out)
        try:
            pinned_download.fetch_pinned_files(
                self._spec, self._ctx.paths.bge_m3, opener=self._ports.opener, progress=progress
            )
        except pinned_download.DownloadError as error:
            self._log.write("download error: {}".format(error))
            if error.code in (pinned_download.CHECKSUM_MISMATCH, pinned_download.SIZE_MISMATCH):
                raise StepFailed(MSG_MODEL_MISMATCH) from None
            if error.code == pinned_download.REDIRECT_REFUSED:
                raise StepFailed(MSG_MODEL_REDIRECT) from None
            raise StepFailed(MSG_MODEL_NETWORK) from None
        report = verify_artifact(self._ctx.paths.bge_m3, self._spec)
        if not report.ok:
            self._log.write("verify issues:\n" + report.format_issues())
            raise StepFailed(MSG_MODEL_MISMATCH)

    def _index(self) -> None:
        self._ctx.paths.work.mkdir(parents=True, exist_ok=True)
        argv = [
            self._ctx.hybrid_python, str(self._ctx.embeddings_script), "build",
            "--config", str(self._ctx.embedding_config),
            "--artifact", str(self._ctx.paths.bge_m3),
            "--catalog", str(self._ctx.knowledge_file(kr.CATALOG_FILE)),
            "--passages", str(self._ctx.knowledge_file(kr.PASSAGES_FILE)),
            "--as-of", self._ports.today().isoformat(),
            "--active-campaign", self._campaign,
            "--index", str(self._ctx.paths.embedding_index),
        ]
        if self._ports.runner.run(argv, self._log).returncode != 0:
            raise StepFailed(MSG_INDEX_FAILED)

    def _prepare(self) -> None:
        head = self._ports.checkout.head_revision()
        argv = [
            self._ctx.hybrid_python, str(self._ctx.release_script), "prepare",
            "--root", str(self._ctx.paths.releases),
            "--catalog", str(self._ctx.knowledge_file(kr.CATALOG_FILE)),
            "--passages", str(self._ctx.knowledge_file(kr.PASSAGES_FILE)),
            "--cases", str(self._ctx.knowledge_file(kr.CASES_FILE)),
            "--as-of", self._ports.today().isoformat(),
            "--active-campaign", self._campaign,
            "--code-revision", head,
            "--reviewed-baseline-revision", head,
            "--embedding-index", str(self._ctx.paths.embedding_index),
            "--with-vector-store",
            "--embedding-config", str(self._ctx.embedding_config),
            "--json",
        ]
        result = self._ports.runner.run(argv, self._log)
        document = last_json_object(result.stdout)
        if result.returncode == 0 and document.get("gate") == "passed" and document.get("release_id"):
            self._release_id = str(document["release_id"])
            return
        if result.returncode == 1 and document.get("gate") == "failed":
            raise StepFailed(gate_failure_message(str(document.get("failures", ""))))
        raise StepFailed(MSG_PREPARE_FAILED)

    def _publish(self) -> None:
        if self._release_id is None:
            raise StepFailed(MSG_PUBLISH_FAILED)
        argv = [
            self._ctx.dev_python, str(self._ctx.release_script), "publish",
            "--root", str(self._ctx.paths.releases),
            "--release-id", self._release_id,
            "--active-campaign", self._campaign,
            "--as-of", self._ports.today().isoformat(),
            "--json",
        ]
        if self._ports.runner.run(argv, self._log).returncode != 0:
            raise StepFailed(MSG_PUBLISH_FAILED)

    def _drafting(self) -> None:
        code = self._ports.ollama.pull(self._record.model)
        self._log.write("ollama pull exit {}".format(code))
        if code != 0:
            raise StepFailed(MSG_DRAFTING_FAILED)
        try:
            entry = find_model(self._ports.ollama.tags(), self._record.model)
        except OllamaUnavailable:
            raise StepFailed(MSG_DRAFTING_FAILED) from None
        if entry is None:
            raise StepFailed(MSG_DRAFTING_FAILED)
        if entry.get("digest") != self._record.digest:
            self._log.write("ollama digest differs from the reviewed record")
            raise StepFailed(MSG_DRAFTING_MISMATCH)


def gate_failure_message(failures: str) -> str:
    codes = [code for code in failures.split(",") if code and code != "none"]
    words: List[str] = []
    for code in codes:
        phrase = next((text for prefix, text in GATE_WORDS if code.startswith(prefix)), "a release check failed")
        if phrase not in words:
            words.append(phrase)
    detail = "; ".join(words) if words else "a release check failed"
    return (
        "The new knowledge release did not pass its checks: {}. The previous release stays in use. "
        "If you changed the campaign in the settings file, check it; otherwise a developer must review "
        "the knowledge.".format(detail)
    )


def last_json_object(text: str) -> Dict[str, Any]:
    for line in reversed((text or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                document = json.loads(line)
            except ValueError:
                continue
            if isinstance(document, dict):
                return document
    return {}


class DownloadProgress:
    """Prints one line per small file and every 10% of a large one."""

    def __init__(self, out: Callable[[str], None]) -> None:
        self._out = out
        self._shown: Dict[str, int] = {}

    def __call__(self, path: str, done: int, total: int) -> None:
        if total < LARGE_FILE_BYTES:
            if done >= total:
                self._out("  Downloaded {}.".format(path))
            return
        tenth = min(10, done * 10 // total)
        if tenth > self._shown.get(path, 0):
            self._shown[path] = tenth
            self._out("  {}: {}% of {}".format(path, tenth * 10, format_size(total)))


# --- Real ports ---------------------------------------------------------------------------


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class TerminalPrompter:
    def ask(self, question: str) -> Optional[str]:
        try:
            return input(question)
        except EOFError:
            return None


class LocalDisk:
    def free_bytes(self, path: Path) -> int:
        return shutil.disk_usage(path).free

    def device(self, path: Path) -> int:
        return os.stat(path).st_dev


class LoggedRunner:
    """Runs a command with its output captured into the log file only."""

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    def run(self, argv: Sequence[str], log: RunLog) -> CommandResult:
        log.write("$ " + " ".join(str(part) for part in argv))
        completed = subprocess.run(
            [str(part) for part in argv], cwd=self._cwd, capture_output=True, text=True, check=False
        )
        log.write(completed.stdout)
        log.write(completed.stderr)
        log.write("exit {}".format(completed.returncode))
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)


class OllamaClient:
    """The Ollama command plus loopback ``/api/tags`` (no proxy, no redirect)."""

    def __init__(self, cli: Optional[str] = None, opener: Any = None) -> None:
        self._cli = cli or os.environ.get(OLLAMA_CLI_ENV, "").strip() or "ollama"
        self._opener = opener if opener is not None else loopback_opener()

    def cli_present(self) -> bool:
        return shutil.which(self._cli) is not None

    def tags(self) -> List[Mapping[str, Any]]:
        request = urllib.request.Request(OLLAMA_BASE_URL + "/api/tags", method="GET")
        try:
            with self._opener.open(request, timeout=TAGS_TIMEOUT_SECONDS) as response:
                raw = response.read(MAX_TAGS_BYTES + 1)
        except urllib.error.HTTPError as error:
            error.close()
            raise OllamaUnavailable("bad_answer") from None
        except Exception:  # noqa: BLE001 - refused, timeout, reset: Ollama is not serving
            raise OllamaUnavailable("not_running") from None
        try:
            document = json.loads(raw.decode("utf-8")) if len(raw) <= MAX_TAGS_BYTES else None
        except ValueError:
            document = None
        models = document.get("models") if isinstance(document, dict) else None
        if not isinstance(models, list):
            raise OllamaUnavailable("bad_answer")
        return [item for item in models if isinstance(item, dict)]

    def pull(self, model: str) -> int:
        executable = shutil.which(self._cli)
        if executable is None:
            return 127
        # Ollama's own progress bar is shown to the owner; only the exit code is logged.
        return subprocess.run([executable, "pull", model], check=False).returncode


class GitCheckout:
    """Git and shared-environment facts about this checkout."""

    def __init__(self, repo_root: Path, knowledge_dir: Path) -> None:
        self._root = Path(repo_root)
        self._knowledge_dir = Path(knowledge_dir)

    def _git(self, *args: str) -> str:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self._root), *args], capture_output=True, text=True, check=False
            )
        except FileNotFoundError:
            raise BootstrapError(
                "Git is not available on this computer. Install the Xcode command line tools "
                "(run xcode-select --install), then run the same command again."
            ) from None
        if completed.returncode != 0:
            raise BootstrapError(
                "This folder is not a complete Manijero checkout. Run the command from the Manijero "
                "folder a developer prepared for you."
            )
        return completed.stdout

    def knowledge_dirty(self) -> bool:
        paths = [str(self._knowledge_dir / name) for name in KNOWLEDGE_FILES]
        return bool(self._git("status", "--porcelain", "--", *paths).strip())

    def head_revision(self) -> str:
        return self._git("rev-parse", "HEAD").strip()

    def hybrid_ready(self) -> bool:
        completed = subprocess.run(
            [str(self._root / "scripts" / "python-env.sh"), "hybrid", "--if-present"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return completed.returncode == 0

    def venv_root(self) -> Path:
        configured = os.environ.get("MANIJERO_VENV_ROOT", "").strip()
        if configured:
            return Path(configured)
        common = self._git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
        return Path(common) / "manijero-venvs"
