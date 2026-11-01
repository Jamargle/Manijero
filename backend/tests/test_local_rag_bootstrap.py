"""Local RAG bootstrap: guided setup, status, plan, and the pinned downloader.

Offline and fake-backed: no network, no Ollama, no model, no ``torch``/``chromadb``. The
search model is the synthetic four-dimension fixture under ``fixtures/embeddings/``, served
by a fake opener. The fake runner stands in for the hybrid-environment CLIs: it writes a
real ``passage-embedding-index-v1`` file with synthetic vectors, and runs the real
``knowledge_release.py prepare``/``publish`` in process with the Chroma write replaced by
a manifest-only store. Every local home is a temporary directory.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import types
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest

from app import knowledge_release as kr
from app import local_rag_bootstrap as lrb
from app import pinned_download as pd
from app import release_gates
from app import vector_store
from app.embedding_index import IndexInputs, PassageEmbeddingIndex, build_index_document, load_index, write_index_atomic
from app.embeddings import load_model_spec
from app.retrieval import Retriever

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
KNOWLEDGE = REPO_ROOT / "knowledge"
FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "embeddings"
FIXTURE_SPEC = FIXTURES / "spec.json"
FIXTURE_ARTIFACT = FIXTURES / "artifact"
REAL_SPEC = BACKEND_ROOT / "config" / "bge_m3_embedding.json"
RECORD_PATH = BACKEND_ROOT / "config" / "local_generation_model.json"
RECORD = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=timezone.utc)
REVISION = "0123456789abcdef0123456789abcdef01234567"
DEV_PYTHON = "/fake/dev/python"
HYBRID_PYTHON = "/fake/hybrid/python"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


release_cli = _load("knowledge_release_cli_for_bootstrap", BACKEND_ROOT / "scripts" / "knowledge_release.py")
local_cli = _load("local_rag_cli", BACKEND_ROOT / "scripts" / "local_rag.py")


# --- Fakes ---------------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, headers: Optional[Dict[str, str]] = None, cut_after: Optional[int] = None) -> None:
        self._body = body
        self._position = 0
        self.status = status
        self.headers = headers or {}
        self._cut_after = cut_after

    def getcode(self) -> int:
        return self.status

    def read(self, size: int = -1) -> bytes:
        limit = len(self._body) if self._cut_after is None else self._cut_after
        if self._position >= limit:
            if self._cut_after is not None:
                raise ConnectionResetError("simulated network drop")
            return b""
        end = limit if size < 0 else min(limit, self._position + size)
        chunk = self._body[self._position:end]
        self._position = end
        return chunk

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class FakeOpener:
    """Serves the fixture artifact at its pin-derived URLs; records every request."""

    def __init__(self, spec_path: Path, artifact: Path) -> None:
        spec = load_model_spec(spec_path)
        self.files = {pd.file_url(spec, item.path): (artifact / item.path).read_bytes() for item in spec.files}
        self.requests: List[tuple] = []
        self.corrupt: set = set()
        self.cut: Dict[str, int] = {}
        self.ignore_range = False

    def open(self, request: urllib.request.Request, timeout: Optional[float] = None) -> FakeResponse:
        url = request.full_url
        byte_range = request.get_header("Range")
        self.requests.append((url, byte_range))
        if url not in self.files:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        body = self.files[url]
        name = url.rsplit("/", 1)[-1]
        if name in self.corrupt:
            body = bytes(len(body))
        cut = self.cut.get(name)
        if byte_range and not self.ignore_range:
            offset = int(byte_range.split("=", 1)[1].rstrip("-"))
            headers = {"Content-Range": "bytes {}-{}/{}".format(offset, len(body) - 1, len(body))}
            return FakeResponse(body[offset:], 206, headers, cut)
        return FakeResponse(body, 200, {}, cut)


class FakeOllama:
    def __init__(self, cli: bool = True, running: bool = True, installed: bool = False, pulled_digest: str = RECORD["digest"], pull_code: int = 0) -> None:
        self.cli = cli
        self.running = running
        self.models: List[Dict[str, Any]] = []
        if installed:
            self._install(RECORD["digest"])
        self.pulled_digest = pulled_digest
        self.pull_code = pull_code
        self.pulls: List[str] = []
        self.on_pull = None

    def _install(self, digest: str) -> None:
        self.models = [{"name": RECORD["model"], "model": RECORD["model"], "digest": digest}]

    def cli_present(self) -> bool:
        return self.cli

    def tags(self) -> List[Dict[str, Any]]:
        if not self.running:
            raise lrb.OllamaUnavailable("not_running")
        return list(self.models)

    def pull(self, model: str) -> int:
        self.pulls.append(model)
        if self.on_pull is not None:
            self.on_pull()
        if self.pull_code:
            return self.pull_code
        self._install(self.pulled_digest)
        return 0


class FakeCheckout:
    def __init__(self, venv_root: Path) -> None:
        self.dirty = False
        self.hybrid = False
        self.root = venv_root

    def knowledge_dirty(self) -> bool:
        return self.dirty

    def head_revision(self) -> str:
        return REVISION

    def hybrid_ready(self) -> bool:
        return self.hybrid

    def venv_root(self) -> Path:
        return self.root


def _options(argv: Sequence[str]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for position, item in enumerate(argv):
        if item.startswith("--") and position + 1 < len(argv) and not argv[position + 1].startswith("--"):
            values[item] = argv[position + 1]
    return values


def fake_package_vectors(plan: Any, store_dir: Path) -> tuple:
    """The release packaging step without Chroma: a validated store manifest only."""

    index = load_index(plan.index_document, plan.spec)
    documents = Retriever.from_documents(plan.catalog, plan.passages, plan.as_of, active_campaign=plan.active_campaign).indexed_documents()
    vectors = {passage_id: index.vector(passage_id) for passage_id in index.passage_ids}
    manifest = vector_store.build_manifest(
        index, plan.spec, plan.inputs, documents, kr.sha256_bytes(plan.index_bytes), vector_store.vectors_sha256(vectors)
    )
    Path(store_dir).mkdir()
    payload = json.dumps(manifest, sort_keys=True).encode("utf-8")
    (Path(store_dir) / vector_store.MANIFEST_NAME).write_bytes(payload)
    vector = {
        "model": plan.spec.index_metadata(),
        "embedding_index_sha256": kr.sha256_bytes(plan.index_bytes),
        "store_manifest_sha256": kr.sha256_bytes(payload),
        "documents_sha256": manifest["inputs"]["documents_sha256"],
        "vectors_sha256": manifest["vectors_sha256"],
        "chromadb_version": manifest["chromadb_version"],
    }
    return vector, plan.index_bytes


class FakeRunner:
    """Stands in for the hybrid-environment commands the setup composes."""

    def __init__(self, checkout: FakeCheckout) -> None:
        self.checkout = checkout
        self.calls: List[List[str]] = []
        self.fail: set = set()

    def kind(self, argv: Sequence[str]) -> str:
        if argv[0].endswith("python-env.sh"):
            return "software"
        if argv[1].endswith("manage_embeddings.py"):
            return "index"
        return argv[2]  # knowledge_release.py prepare | publish

    def run(self, argv: Sequence[str], log: lrb.RunLog) -> lrb.CommandResult:
        argv = [str(item) for item in argv]
        self.calls.append(argv)
        log.write("$ " + " ".join(argv))
        kind = self.kind(argv)
        if kind in self.fail:
            log.write("Traceback (most recent call last):\nRuntimeError: simulated failure")
            return lrb.CommandResult(2, "", "simulated failure")
        try:
            result = getattr(self, "_" + kind)(argv)
        except Exception as error:  # like the real CLIs: a fixed error and exit 2
            log.write("error: {}".format(type(error).__name__))
            return lrb.CommandResult(2, "", "error")
        log.write(result.stdout + result.stderr)
        return result

    def _software(self, argv: List[str]) -> lrb.CommandResult:
        self.checkout.hybrid = True
        return lrb.CommandResult(0, "backend/.venv-hybrid -> shared\n", "")

    def _index(self, argv: List[str]) -> lrb.CommandResult:
        options = _options(argv)
        spec = load_model_spec(Path(options["--config"]))
        catalog_path, passages_path = Path(options["--catalog"]), Path(options["--passages"])
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        passages = json.loads(passages_path.read_text(encoding="utf-8"))
        as_of = date.fromisoformat(options["--as-of"])
        campaign = options["--active-campaign"]
        documents = Retriever.from_documents(catalog, passages, as_of, active_campaign=campaign).indexed_documents()
        vectors = {}
        for position, (passage_id, _) in enumerate(sorted(documents)):
            vector = [0.0] * spec.embedding_dimension
            vector[position % spec.embedding_dimension] = 1.0
            vectors[passage_id] = tuple(vector)
        inputs = IndexInputs(kr.sha256_bytes(catalog_path.read_bytes()), kr.sha256_bytes(passages_path.read_bytes()), as_of.isoformat(), campaign)
        index = PassageEmbeddingIndex(spec.embedding_dimension, vectors)
        write_index_atomic(Path(options["--index"]), build_index_document(index, spec, inputs), spec)
        return lrb.CommandResult(0, "indexed_passages: {}\n".format(len(vectors)), "")

    def _release_cli(self, args: List[str]) -> lrb.CommandResult:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = release_cli.main(args, clock=lambda: NOW)
        return lrb.CommandResult(code, stdout.getvalue(), stderr.getvalue())

    def _prepare(self, argv: List[str]) -> lrb.CommandResult:
        with pytest.MonkeyPatch.context() as patch:
            patch.setitem(sys.modules, "chromadb", types.ModuleType("chromadb"))
            patch.setattr(release_gates, "package_vectors", fake_package_vectors)
            return self._release_cli(argv[2:])

    def _publish(self, argv: List[str]) -> lrb.CommandResult:
        return self._release_cli(argv[2:])


class FakePrompter:
    def __init__(self) -> None:
        self.answers: List[Optional[str]] = []
        self.questions: List[str] = []

    def ask(self, question: str) -> Optional[str]:
        self.questions.append(question)
        return self.answers.pop(0) if self.answers else None


class FakeDisk:
    def __init__(self) -> None:
        self.free = 10 ** 13
        self.devices: Dict[str, int] = {}

    def free_bytes(self, path: Path) -> int:
        return self.free

    def device(self, path: Path) -> int:
        return self.devices.get(str(path), 1)


class FakeClock:
    def now(self) -> datetime:
        return NOW


class Env:
    """One temporary local home, a knowledge copy, and every fake port."""

    def __init__(self, tmp_path: Path, embedding_config: Path = FIXTURE_SPEC) -> None:
        self.tmp = tmp_path
        self.knowledge = tmp_path / "knowledge"
        self.knowledge.mkdir()
        for name in lrb.KNOWLEDGE_FILES:
            (self.knowledge / name).write_bytes((KNOWLEDGE / name).read_bytes())
        self.ctx = lrb.Context(
            repo_root=REPO_ROOT,
            paths=lrb.local_paths(tmp_path / "home"),
            knowledge_dir=self.knowledge,
            embedding_config=embedding_config,
            generation_record=RECORD_PATH,
            dev_python=DEV_PYTHON,
            hybrid_python=HYBRID_PYTHON,
            ollama_models=tmp_path / "ollama-models",
        )
        self.lines: List[str] = []
        self.checkout = FakeCheckout(tmp_path / "venvs")
        self.ollama = FakeOllama()
        self.runner = FakeRunner(self.checkout)
        self.prompter = FakePrompter()
        self.disk = FakeDisk()
        self.opener = FakeOpener(FIXTURE_SPEC, FIXTURE_ARTIFACT)
        self.ports = lrb.Ports(
            ollama=self.ollama,
            checkout=self.checkout,
            runner=self.runner,
            prompter=self.prompter,
            disk=self.disk,
            clock=FakeClock(),
            opener=self.opener,
            out=self.lines.append,
        )
        self.all_output: List[str] = []

    @property
    def paths(self) -> lrb.LocalPaths:
        return self.ctx.paths

    @property
    def output(self) -> str:
        return "\n".join(self.lines)

    def _reset(self) -> None:
        self.all_output.extend(self.lines)
        self.lines.clear()

    def setup(self, *answers: Optional[str]) -> int:
        self._reset()
        self.prompter.answers = list(answers)
        return lrb.run_setup(self.ctx, self.ports, lrb.RunLog(self.paths.logs, "setup", FakeClock().now))

    def status(self) -> int:
        self._reset()
        return lrb.run_status(self.ctx, self.ports)

    def forget_calls(self) -> None:
        self.runner.calls.clear()
        self.opener.requests.clear()
        self.ollama.pulls.clear()
        self.prompter.questions.clear()

    def no_side_calls(self) -> bool:
        return not (self.runner.calls or self.opener.requests or self.ollama.pulls or self.prompter.questions)


def snapshot(root: Path) -> Dict[str, str]:
    if not root.exists():
        return {}
    entries = {}
    for current, directories, names in os.walk(root):
        for name in directories + names:
            path = Path(current) / name
            relative = str(path.relative_to(root))
            if path.is_symlink():
                entries[relative] = "link:" + os.readlink(path)
            elif path.is_file():
                entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                entries[relative] = "dir"
    return entries


def status_states(output: str) -> List[str]:
    return [line.split()[0] for line in output.splitlines() if line.split() and line.split()[0] in ("OK", "MISSING", "PROBLEM")]


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


@pytest.fixture
def ready(env: Env) -> Env:
    assert env.setup("yes") == 0, env.output
    env.forget_calls()
    return env


# --- 1. First run --------------------------------------------------------------------------


def test_first_run_shows_downloads_asks_then_builds_everything_in_order(env: Env) -> None:
    code = env.setup("yes")

    assert code == 0, env.output
    assert len(env.prompter.questions) == 1
    out = env.output
    assert out.index("Setup will download:") < out.index("Step 1 of 6")
    assert [env.runner.kind(call) for call in env.runner.calls] == ["software", "index", "prepare", "publish"]
    assert env.ollama.pulls == [RECORD["model"]]
    spec = load_model_spec(FIXTURE_SPEC)
    assert sorted(url for url, _ in env.opener.requests) == sorted(pd.file_url(spec, item.path) for item in spec.files)
    for number, title in enumerate(lrb.STEP_TITLES.values(), start=1):
        assert "Step {} of 6: {}...".format(number, title) in out

    settings_text = env.paths.settings.read_text(encoding="utf-8")
    assert settings_text.startswith("# ") and "MANIJERO_ACTIVE_CAMPAIGN=2026" in settings_text
    assert lrb.read_settings(env.paths.settings) == lrb.Settings("2026")

    prepare = next(call for call in env.runner.calls if env.runner.kind(call) == "prepare")
    assert prepare[0] == HYBRID_PYTHON
    options = _options(prepare)
    assert options["--embedding-index"] == str(env.paths.embedding_index)
    assert "--with-vector-store" in prepare
    assert options["--code-revision"] == REVISION and options["--reviewed-baseline-revision"] == REVISION
    assert options["--as-of"] == "2026-11-01" and options["--active-campaign"] == "2026"
    publish = env.runner.calls[-1]
    assert publish[0] == DEV_PYTHON and kr.current_release_id(env.paths.releases) == _options(publish)["--release-id"]

    assert status_states(out) == ["OK"] * 6
    assert out.splitlines()[-1].startswith("Result: everything is set up.")


def test_confirmation_sizes_come_from_the_pins(tmp_path: Path) -> None:
    env = Env(tmp_path, embedding_config=REAL_SPEC)

    code = env.setup("no")

    assert code == 1
    out = env.output
    assert "  - Search software (hybrid environment): about 1.2 GB" in out
    assert "  - Search model bge-m3: 2.3 GB" in out
    assert "  - Drafting model ({}): 15.2 GB".format(RECORD["model"]) in out
    assert "  Total: about 18.7 GB" in out
    assert not env.paths.home.exists()

    # Without the hybrid line the total is exact, and a different pin changes the figure.
    record = dict(RECORD, size_bytes=5_000_000_000)
    edited = tmp_path / "record.json"
    edited.write_text(json.dumps(record), encoding="utf-8")
    spec, loaded = lrb.load_pins(dataclasses.replace(env.ctx, generation_record=edited), NOW.date())
    env.checkout.hybrid = True
    inspection = lrb.inspect(env.ctx, env.ports, spec, loaded, "2026")
    lines = lrb.confirmation_lines(lrb.make_plan(inspection, env.ctx, loaded, tmp_path))
    assert lines[1:4] == ["  - Search model bge-m3: 2.3 GB", "  - Drafting model ({}): 5.0 GB".format(RECORD["model"]), "  Total: 7.3 GB"]


# --- 2-4. Prerequisites --------------------------------------------------------------------


def _hold_lock(env: Env) -> int:
    env.paths.home.mkdir(parents=True)
    handle = os.open(env.paths.lock, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


@pytest.mark.parametrize(
    "arrange, expected",
    [
        (lambda env: setattr(env.ollama, "cli", False), "Install it from https://ollama.com/download"),
        (lambda env: setattr(env.ollama, "running", False), "Open the Ollama app"),
        (lambda env: setattr(env.checkout, "dirty", True), "not committed to Git"),
        (lambda env: setattr(env.disk, "free", 3_000_000_000), "not enough free space"),
        (_hold_lock, "Another setup is already running"),
    ],
    ids=["ollama-missing", "ollama-closed", "knowledge-dirty", "low-disk", "lock-held"],
)
def test_a_missing_prerequisite_stops_before_any_change(env: Env, arrange, expected) -> None:
    held = arrange(env)
    before = snapshot(env.tmp)

    code = env.setup("yes")

    assert code == 1
    assert expected in env.output
    assert env.lines[-1] == "Result: setup stopped before changing anything."
    assert snapshot(env.tmp) == before
    assert env.no_side_calls()
    if isinstance(held, int):
        os.close(held)


def test_free_space_is_checked_per_filesystem(env: Env) -> None:
    # The drafting model goes to Ollama's disk, which alone lacks room for 15.2 GB + 1 GB.
    env.ctx.ollama_models.mkdir()
    env.disk.devices[str(env.ctx.ollama_models)] = 2
    free = {1: 10 ** 13, 2: 16_000_000_000}
    env.disk.free_bytes = lambda path: free[env.disk.device(path)]  # type: ignore[assignment]

    assert env.setup("yes") == 1
    assert "needs 16.2 GB free and only 16.0 GB is free" in env.output


# --- 5. Declining --------------------------------------------------------------------------


@pytest.mark.parametrize("answer", ["no", "", "  nope ", None])
def test_declining_changes_nothing(env: Env, answer: Optional[str]) -> None:
    code = env.setup(answer)

    assert code == 1
    assert "Nothing was changed." in env.output
    assert not env.paths.home.exists()
    assert not env.runner.calls and not env.opener.requests and not env.ollama.pulls


# --- 6. Re-run when current ----------------------------------------------------------------


def test_rerun_when_everything_is_current_asks_and_downloads_nothing(ready: Env) -> None:
    before = snapshot(ready.tmp)

    code = ready.setup()

    assert code == 0
    assert ready.no_side_calls()
    assert status_states(ready.output) == ["OK"] * 6
    assert ready.lines[-1] == "Result: everything is already set up. Nothing was downloaded or changed."
    assert snapshot(ready.tmp) == before


def test_existing_settings_file_is_never_overwritten(env: Env) -> None:
    env.paths.home.mkdir(parents=True)
    custom = "# my note\nMANIJERO_ACTIVE_CAMPAIGN = \"2026\"\n\n# trailing note\n"
    env.paths.settings.write_text(custom, encoding="utf-8")

    assert env.setup("yes") == 0
    assert env.paths.settings.read_text(encoding="utf-8") == custom
    assert "Created the settings file" not in env.output


# --- 7. Interrupted or damaged model files -------------------------------------------------


def test_only_missing_or_damaged_model_files_are_listed_and_fetched(ready: Env) -> None:
    config = ready.paths.bge_m3 / "config.json"
    kept = (config.stat().st_ino, config.stat().st_mtime_ns)
    (ready.paths.bge_m3 / "weights.bin").unlink()
    (ready.paths.bge_m3 / "1_Pooling" / "config.json").write_text("{}", encoding="utf-8")
    spec, record = lrb.load_pins(ready.ctx, NOW.date())
    inspection = lrb.inspect(ready.ctx, ready.ports, spec, record, "2026")
    assert inspection.part("model").state == lrb.PROBLEM
    plan = lrb.make_plan(inspection, ready.ctx, record, ready.tmp)
    assert plan.steps == (lrb.STEP_MODEL,)
    assert [(item.label, item.size_bytes) for item in plan.downloads] == [("Search model bge-m3", 26 + 112)]

    code = ready.setup("yes")

    assert code == 0, ready.output
    assert sorted(url.rsplit("/", 1)[-1] for url, _ in ready.opener.requests) == ["config.json", "weights.bin"]
    assert all("1_Pooling" in url or url.endswith("weights.bin") for url, _ in ready.opener.requests)
    assert (config.stat().st_ino, config.stat().st_mtime_ns) == kept
    assert "Step 1 of 1: Downloading the search model bge-m3..." in ready.output


def test_a_network_drop_keeps_finished_files_and_the_rerun_resumes(env: Env) -> None:
    env.opener.cut["weights.bin"] = 10

    code = env.setup("yes")

    assert code == 1
    assert lrb.MSG_MODEL_NETWORK in env.output
    log_line = next(line for line in env.lines if line.startswith("Details are in the log file: "))
    log_path = Path(log_line.split(": ", 1)[1])
    assert log_path.parent == env.paths.logs and log_path.is_file()
    assert "Traceback" not in env.output
    assert (env.paths.bge_m3 / "config.json").is_file()
    assert (env.paths.bge_m3 / "weights.bin.part").stat().st_size == 10
    assert not (env.paths.bge_m3 / "weights.bin").exists()
    assert env.lines[-1] == "Result: setup stopped; finished parts are kept."

    spec, record = lrb.load_pins(env.ctx, NOW.date())
    inspection = lrb.inspect(env.ctx, env.ports, spec, record, "2026")
    assert inspection.part("model").reason == "model_incomplete"
    assert [item.missing_bytes for item in inspection.model_pending] == [16]

    del env.opener.cut["weights.bin"]
    env.forget_calls()
    code = env.setup("yes")

    assert code == 0, env.output
    weights_requests = [byte_range for url, byte_range in env.opener.requests if url.endswith("weights.bin")]
    assert weights_requests == ["bytes=10-"]
    assert len(env.opener.requests) == 1  # finished files are not fetched again
    assert [env.runner.kind(call) for call in env.runner.calls] == ["index", "prepare", "publish"]


# --- 8. Knowledge changed ------------------------------------------------------------------


def test_changed_knowledge_rebuilds_without_asking_and_publishes(ready: Env) -> None:
    previous = kr.current_release_id(ready.paths.releases)
    passages = ready.knowledge / kr.PASSAGES_FILE
    passages.write_text(json.dumps(json.loads(passages.read_text(encoding="utf-8")), ensure_ascii=False, indent=4), encoding="utf-8")
    assert ready.status() == 1
    assert "PROBLEM  Knowledge release: the knowledge files changed since it was built." in ready.output

    code = ready.setup()

    assert code == 0, ready.output
    assert not ready.prompter.questions and not ready.opener.requests and not ready.ollama.pulls
    assert [ready.runner.kind(call) for call in ready.runner.calls] == ["index", "prepare", "publish"]
    current = kr.current_release_id(ready.paths.releases)
    assert current not in (None, previous)
    assert status_states(ready.output) == ["OK"] * 6


def test_a_failed_release_gate_keeps_the_previous_release(ready: Env) -> None:
    previous = kr.current_release_id(ready.paths.releases)
    cases_path = ready.knowledge / kr.CASES_FILE
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    case = next(item for item in cases["cases"] if item.get("expected_passage_ids"))
    case["expected_passage_ids"] = ["pasaje-inexistente"]
    cases_path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")

    code = ready.setup()

    assert code == 1
    assert not ready.prompter.questions
    assert "did not pass its checks: the answer checks do not match the knowledge" in ready.output
    assert "The previous release stays in use." in ready.output
    assert any(line.startswith("Details are in the log file: ") for line in ready.lines)
    assert kr.current_release_id(ready.paths.releases) == previous
    assert [ready.runner.kind(call) for call in ready.runner.calls] == ["index", "prepare"]


def test_a_campaign_change_in_the_settings_triggers_a_rebuild(ready: Env) -> None:
    ready.paths.settings.write_text("MANIJERO_ACTIVE_CAMPAIGN=2027\n", encoding="utf-8")
    assert ready.status() == 1
    assert "it was built for a different campaign than the settings file" in ready.output

    code = ready.setup()

    assert code == 1
    assert not ready.prompter.questions and not ready.opener.requests
    assert "index" in [ready.runner.kind(call) for call in ready.runner.calls]
    assert "Result: setup stopped; finished parts are kept." == ready.lines[-1]
    assert kr.read_manifest(ready.paths.current_release.resolve())["inputs"]["active_campaign"] == "2026"


# --- 9. Mismatch with a pin ----------------------------------------------------------------


def test_a_downloaded_file_that_differs_from_the_pin_is_discarded(env: Env) -> None:
    pin_before = FIXTURE_SPEC.read_bytes()
    env.opener.corrupt.add("weights.bin")

    code = env.setup("yes")

    assert code == 1
    assert lrb.MSG_MODEL_MISMATCH in env.output
    assert not (env.paths.bge_m3 / "weights.bin").exists()
    assert not (env.paths.bge_m3 / "weights.bin.part").exists()
    assert (env.paths.bge_m3 / "config.json").is_file() and (env.paths.bge_m3 / "1_Pooling" / "config.json").is_file()
    assert FIXTURE_SPEC.read_bytes() == pin_before
    assert not env.ollama.pulls


def test_an_ollama_digest_mismatch_fails_closed_without_editing_the_record(env: Env) -> None:
    record_before = RECORD_PATH.read_bytes()
    env.ollama.pulled_digest = "f" * 64

    code = env.setup("yes")

    assert code == 1
    assert lrb.MSG_DRAFTING_MISMATCH in env.output
    assert RECORD_PATH.read_bytes() == record_before
    assert env.status() == 1
    assert "PROBLEM  Drafting model: Ollama has a different version than the reviewed one." in env.output


# --- 10. Unexpected failures ---------------------------------------------------------------


def test_a_failed_environment_build_names_the_step_and_the_log(env: Env) -> None:
    env.runner.fail.add("software")

    code = env.setup("yes")

    assert code == 1
    assert lrb.MSG_SOFTWARE_FAILED in env.output
    assert "Traceback" not in env.output and "simulated failure" not in env.output
    log_path = Path(next(line for line in env.lines if line.startswith("Details")).split(": ", 1)[1])
    assert "simulated failure" in log_path.read_text(encoding="utf-8")
    assert not env.opener.requests  # later steps never started


def test_an_unexpected_exception_prints_one_sentence_and_logs_the_traceback(env: Env) -> None:
    def explode() -> List[Dict[str, Any]]:
        raise RuntimeError("internal detail that must stay in the log")

    env.ollama.tags = explode  # type: ignore[assignment]

    code = local_cli.main(["setup"], ctx=env.ctx, ports=env.ports)

    assert code == 1
    assert "Something unexpected went wrong." in env.output
    assert "internal detail" not in env.output and "Traceback" not in env.output
    log_path = Path(env.output.split("send this log file to a developer: ", 1)[1].splitlines()[0])
    assert log_path.parent == env.paths.logs
    assert "Traceback" in log_path.read_text(encoding="utf-8")


def test_ctrl_c_keeps_finished_parts_and_says_to_run_again(env: Env) -> None:
    def interrupt() -> None:
        raise KeyboardInterrupt

    env.ollama.on_pull = interrupt
    env.prompter.answers = ["yes"]

    code = local_cli.main(["setup"], ctx=env.ctx, ports=env.ports)

    assert code == 1
    assert "Finished parts are kept; run ./scripts/init.sh --local-rag-setup again to continue." in env.output
    assert kr.current_release_id(env.paths.releases) is not None
    assert not lrb.lock_is_held(env.paths.lock)


# --- 11. Status ----------------------------------------------------------------------------


def test_status_before_setup_names_the_setup_command_and_writes_nothing(env: Env) -> None:
    before = snapshot(env.tmp)

    code = env.status()

    assert code == 1
    assert status_states(env.output) == ["MISSING"] * 6
    assert env.lines[-1] == "Result: setup has not run yet. Run ./scripts/init.sh --local-rag-setup to set everything up."
    assert snapshot(env.tmp) == before
    assert env.no_side_calls()


def test_status_after_setup_is_all_ok_and_read_only(ready: Env) -> None:
    before = snapshot(ready.tmp)

    code = ready.status()

    assert code == 0
    assert status_states(ready.output) == ["OK"] * 6
    assert [line.split(":", 1)[0].split(None, 1)[1] for line in ready.lines[1:7]] == [label for _, label in lrb.PARTS]
    assert ready.lines[-1] == "Result: all 6 parts are ready."
    assert snapshot(ready.tmp) == before
    assert ready.no_side_calls()


@pytest.mark.parametrize(
    "arrange, line",
    [
        (lambda env: setattr(env.ollama, "running", False), "PROBLEM  Drafting model: Ollama is not running. Open the Ollama app"),
        (
            lambda env: (setattr(env.ollama, "running", False), setattr(env.ollama, "cli", False)),
            "PROBLEM  Drafting model: Ollama is not installed. Install it from https://ollama.com/download",
        ),
        (lambda env: setattr(env.ollama, "models", []), "MISSING  Drafting model: not downloaded yet."),
        (lambda env: setattr(env.checkout, "hybrid", False), "MISSING  Search software: not installed yet."),
        (
            lambda env: (env.paths.bge_m3 / "weights.bin").write_bytes(b"x" * 26),
            "PROBLEM  Search model (bge-m3): a file is damaged or differs from the reviewed version.",
        ),
        (
            lambda env: (env.paths.current_release.resolve() / kr.PASSAGES_FILE).write_text("{}", encoding="utf-8"),
            "PROBLEM  Knowledge release: the published release is damaged.",
        ),
    ],
    ids=["ollama-closed", "ollama-missing", "model-not-pulled", "software-missing", "model-damaged", "release-damaged"],
)
def test_status_reports_each_problem_in_plain_words(ready: Env, arrange, line: str) -> None:
    arrange(ready)
    before = snapshot(ready.tmp)

    code = ready.status()

    assert code == 1
    assert any(item.startswith(line) for item in ready.lines), ready.output
    states = status_states(ready.output)
    assert len(states) == 6 and states.count("OK") < 6
    assert ready.lines[-1].startswith("Result: {} of 6 parts are ready.".format(states.count("OK")))
    assert snapshot(ready.tmp) == before


def test_status_runs_without_torch_or_chromadb(tmp_path: Path) -> None:
    script = (
        "import runpy, sys\n"
        "sys.modules['torch'] = None\n"
        "sys.modules['chromadb'] = None\n"
        "sys.modules['transformers'] = None\n"
        "sys.argv = ['local_rag.py', 'status']\n"
        "runpy.run_path(sys.argv_path, run_name='__main__')\n"
    ).replace("sys.argv_path", repr(str(BACKEND_ROOT / "scripts" / "local_rag.py")))
    environment = dict(os.environ, MANIJERO_LOCAL_HOME=str(tmp_path / "home"), MANIJERO_VENV_ROOT=str(tmp_path / "venvs"))
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=environment, timeout=120, check=False)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "Something unexpected" not in completed.stdout and not completed.stderr
    assert len(status_states(completed.stdout)) == 6
    assert not (tmp_path / "home").exists()


# --- Settings ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, line, problem",
    [
        ("# note\n\nMANIJERO_ACTIVE_CAMPAIGN=26\n", 3, "four-digit year"),
        ("MANIJERO_ACTIVE_CAMPAIGN=2026\nMANIJERO_ACTIVE_CAMPAIGN=2027\n", 2, "appears twice"),
        ("OTHER=1\n", 1, "not a setting this tool knows"),
        ("export $(rm -rf /)\n", 1, "NAME=value"),
    ],
)
def test_an_invalid_settings_line_is_named(env: Env, text: str, line: int, problem: str) -> None:
    env.paths.home.mkdir(parents=True)
    env.paths.settings.write_text(text, encoding="utf-8")
    before = snapshot(env.tmp)

    for command in ("setup", "status"):
        env.lines.clear()
        assert local_cli.main([command], ctx=env.ctx, ports=env.ports) == 1
        assert "has a problem on line {}".format(line) in env.output and problem in env.output
        assert env.lines[-1].endswith("stopped before changing anything.")
    assert snapshot(env.tmp) == before
    assert env.no_side_calls()


def test_settings_without_the_campaign_say_which_line_to_add(env: Env) -> None:
    env.paths.home.mkdir(parents=True)
    env.paths.settings.write_text("# empty\n", encoding="utf-8")

    with pytest.raises(lrb.SettingsError, match="Add the line MANIJERO_ACTIVE_CAMPAIGN=2026"):
        lrb.read_settings(env.paths.settings)


def test_local_paths_layout() -> None:
    paths = lrb.local_paths(Path("/x/home"))
    assert paths.settings == Path("/x/home/settings.env")
    assert paths.bge_m3 == Path("/x/home/models/bge-m3")
    assert paths.embedding_index == Path("/x/home/work/embedding-index.json")
    assert paths.releases == Path("/x/home/knowledge-releases")
    assert paths.logs == Path("/x/home/logs") and paths.lock == Path("/x/home/.setup.lock")


# --- Privacy -------------------------------------------------------------------------------


def test_no_message_contains_corpus_text(ready: Env) -> None:
    ready.status()
    ready.ollama.running = False
    ready.status()
    (ready.knowledge / kr.CASES_FILE).write_text("{}", encoding="utf-8")
    ready.setup()
    output = "\n".join(ready.all_output + ready.lines)
    passages = json.loads((KNOWLEDGE / kr.PASSAGES_FILE).read_text(encoding="utf-8"))["passages"]
    for passage in passages:
        assert passage["text"][:40] not in output


# --- Pinned downloader ---------------------------------------------------------------------


def test_download_urls_are_built_only_from_the_pin() -> None:
    spec = load_model_spec(REAL_SPEC)
    assert pd.file_url(spec, "1_Pooling/config.json") == (
        "https://huggingface.co/BAAI/bge-m3/resolve/5617a9f61b028005a4858fdac845db406aefb181/1_Pooling/config.json"
    )


def test_fetch_writes_only_verified_files_and_skips_matching_ones(tmp_path: Path) -> None:
    spec = load_model_spec(FIXTURE_SPEC)
    opener = FakeOpener(FIXTURE_SPEC, FIXTURE_ARTIFACT)
    progress: List[tuple] = []

    fetched = pd.fetch_pinned_files(spec, tmp_path / "model", opener=opener, progress=lambda *item: progress.append(item))

    assert [item.path for item in fetched] == [item.path for item in spec.files]
    for item in spec.files:
        assert (tmp_path / "model" / item.path).read_bytes() == (FIXTURE_ARTIFACT / item.path).read_bytes()
    assert progress[-1] == ("weights.bin", 26, 26)
    opener.requests.clear()
    assert pd.fetch_pinned_files(spec, tmp_path / "model", opener=opener) == ()
    assert opener.requests == []


def test_a_server_that_ignores_the_range_restarts_the_file(tmp_path: Path) -> None:
    spec = load_model_spec(FIXTURE_SPEC)
    opener = FakeOpener(FIXTURE_SPEC, FIXTURE_ARTIFACT)
    target = tmp_path / "model"
    target.mkdir()
    (target / "weights.bin.part").write_bytes(b"garbage")
    opener.ignore_range = True

    pd.fetch_pinned_files(spec, target, opener=opener)

    assert (target / "weights.bin").read_bytes() == (FIXTURE_ARTIFACT / "weights.bin").read_bytes()
    assert not (target / "weights.bin.part").exists()


def test_an_oversized_download_is_discarded(tmp_path: Path) -> None:
    spec = load_model_spec(FIXTURE_SPEC)
    opener = FakeOpener(FIXTURE_SPEC, FIXTURE_ARTIFACT)
    url = pd.file_url(spec, "weights.bin")
    opener.files[url] = opener.files[url] + b"extra"

    with pytest.raises(pd.DownloadError) as caught:
        pd.fetch_pinned_files(spec, tmp_path / "model", opener=opener)

    assert caught.value.code == pd.SIZE_MISMATCH and caught.value.path == "weights.bin"
    assert not (tmp_path / "model" / "weights.bin.part").exists()


def test_redirects_to_plain_http_are_refused_and_https_is_followed() -> None:
    handler = pd.HttpsOnlyRedirects()
    request = urllib.request.Request("https://huggingface.co/BAAI/bge-m3/resolve/x/config.json", headers={"Range": "bytes=5-"})

    with pytest.raises(pd.DownloadError) as caught:
        handler.redirect_request(request, None, 302, "Found", {}, "http://cdn.example.test/config.json")
    assert caught.value.code == pd.REDIRECT_REFUSED

    followed = handler.redirect_request(request, None, 302, "Found", {}, "https://cdn.example.test/config.json")
    assert followed.full_url == "https://cdn.example.test/config.json"
    assert followed.get_header("Range") == "bytes=5-"


def test_the_download_opener_has_no_plain_http_handler() -> None:
    with pytest.raises(urllib.error.URLError, match="unknown url type"):
        pd.https_opener().open("http://example.test/config.json", timeout=1)
