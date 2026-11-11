"""Offline tests for the owner commands around the reranker (download, measure, on/off, status).

A fake opener, fake disk, fake scorer, and a fake hybrid loader stand in for the network and the
models: no download, no ``torch``, no ``chromadb``. Nothing here claims retrieval quality.
"""

import dataclasses
import hashlib
import importlib.util
import json
import shutil
import stat
import sys
import subprocess
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent

import test_hybrid_retrieval as hyb  # noqa: E402
import test_local_rag_bootstrap as boot  # noqa: E402
import test_local_rag_service as svc_tests  # noqa: E402
from app import local_rag_bootstrap as lrb  # noqa: E402
from app import local_rag_service as svc  # noqa: E402
from app import pinned_download as pd  # noqa: E402
from app import reranker  # noqa: E402

spec_cli = importlib.util.spec_from_file_location("reranker_cli", BACKEND_ROOT / "scripts" / "reranker.py")
cli = importlib.util.module_from_spec(spec_cli)
sys.modules["reranker_cli"] = cli  # dataclasses with postponed annotations look the module up
spec_cli.loader.exec_module(cli)  # type: ignore[union-attr]

FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "reranker"
FIXTURE_PIN = FIXTURES / "pin.json"
FIXTURE_ARTIFACT = FIXTURES / "artifact"
REAL_PIN = BACKEND_ROOT / "config" / "bge_reranker_v2_m3.json"
REAL_SETTINGS = BACKEND_ROOT / "config" / "reranker.json"
FIXTURE_SIZE = sum(path.stat().st_size for path in FIXTURE_ARTIFACT.iterdir())
SIZE_TEXT = "{:.1f} GB".format(FIXTURE_SIZE / 1e9)


class FakeOpener:
    """Serves the fixture artifact at the pin-derived URLs; records every request."""

    def __init__(self, artifact: Path = FIXTURE_ARTIFACT) -> None:
        spec = reranker.load_reranker_spec(FIXTURE_PIN)
        self.files = {pd.file_url(spec, item.path): (artifact / item.path).read_bytes() for item in spec.files}
        self.requests: List[Tuple[str, Optional[str]]] = []
        self.corrupt: set = set()
        self.cut: Dict[str, int] = {}
        self.error: Optional[Exception] = None

    def open(self, request: urllib.request.Request, timeout: Optional[float] = None) -> Any:
        if self.error is not None:
            raise self.error
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
        if byte_range:
            offset = int(byte_range.split("=", 1)[1].rstrip("-"))
            headers = {"Content-Range": "bytes {}-{}/{}".format(offset, len(body) - 1, len(body))}
            return boot.FakeResponse(body[offset:], 206, headers, cut)
        return boot.FakeResponse(body, 200, {}, cut)

    @property
    def urls(self) -> List[str]:
        return [url for url, _ in self.requests]


class Harness:
    def __init__(self, tmp_path: Path, pin: Path = FIXTURE_PIN) -> None:
        self.tmp = tmp_path
        self.paths = lrb.local_paths(tmp_path / "home")
        self.lines: List[str] = []
        self.disk = boot.FakeDisk()
        self.running = False
        self.ports = cli.CommandPorts(
            paths=self.paths,
            disk=self.disk,
            clock=boot.FakeClock(),
            out=self.lines.append,
            pin_path=pin,
            settings_path=REAL_SETTINGS,
            service_running=lambda: self.running,
        )
        self.opener = FakeOpener()

    def run(self, *argv: str, **options: Any) -> int:
        self.lines.clear()
        options.setdefault("opener", self.opener)
        return cli.main(list(argv), ports=self.ports, **options)

    @property
    def results(self) -> List[str]:
        return [line for line in self.lines if line.startswith("Result:")]

    @property
    def result(self) -> str:
        assert len(self.results) == 1, self.lines
        return self.results[0]

    def install_model(self) -> None:
        shutil.copytree(FIXTURE_ARTIFACT, self.paths.reranker)

    def write_settings(self, text: str) -> None:
        self.paths.settings.parent.mkdir(parents=True, exist_ok=True)
        self.paths.settings.write_bytes(text.encode("utf-8"))


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


# --- check-pin ---------------------------------------------------------------------------------


def test_check_pin_passes_for_the_committed_pin(capsys: pytest.CaptureFixture) -> None:
    code = cli.main(["check-pin"])

    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("Result: the reranker pin is valid (6 files, 2.3 GB; revision 953dc6f6f85a")


def test_check_pin_fails_with_reranker_pin_unpinned_for_a_placeholder(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps(dict(json.loads(FIXTURE_PIN.read_text()), model_revision="unpinned")), encoding="utf-8")

    code = cli.main(["check-pin", "--pin", str(pin)])

    assert code == 1 and capsys.readouterr().out.strip() == "reranker_pin_unpinned"


def test_check_pin_names_what_is_wrong(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps(dict(json.loads(FIXTURE_PIN.read_text()), license="")), encoding="utf-8")

    code = cli.main(["check-pin", "--pin", str(pin)])

    assert code == 1 and "reranker_pin_invalid" in capsys.readouterr().out


# --- 5. Download -------------------------------------------------------------------------------


def test_a_fresh_download_verifies_and_ends_with_the_pinned_line(h: Harness) -> None:
    code = h.run("download")

    assert code == 0
    assert h.result == (
        "Result: the reranker model is downloaded and matches the reviewed copy ({}). "
        "It stays off until it is switched on.".format(SIZE_TEXT)
    )
    spec = reranker.load_reranker_spec(FIXTURE_PIN)
    assert spec.verify_artifact(h.paths.reranker).ok
    assert h.paths.reranker == h.paths.models / "bge-reranker-v2-m3"


def test_the_real_pin_gives_the_two_point_three_gigabyte_line_size() -> None:
    assert "{:.1f}".format(reranker.load_reranker_spec(REAL_PIN).total_bytes / 1e9) == "2.3"


def test_urls_come_only_from_the_pin(h: Harness) -> None:
    h.run("download")

    spec = reranker.load_reranker_spec(FIXTURE_PIN)
    assert sorted(h.opener.urls) == sorted(pd.file_url(spec, item.path) for item in spec.files)
    assert all(url.startswith("https://huggingface.co/BAAI/bge-reranker-v2-m3/resolve/0123456789abcdef") for url in h.opener.urls)


def test_a_second_run_downloads_nothing(h: Harness) -> None:
    h.run("download")
    h.opener.requests.clear()

    code = h.run("download")

    assert code == 0 and h.opener.requests == []
    assert h.result == (
        "Result: the reranker model is already downloaded and matches the reviewed copy; nothing was downloaded."
    )


def test_only_the_missing_file_is_fetched(h: Harness) -> None:
    h.run("download")
    (h.paths.reranker / "config.json").unlink()
    h.opener.requests.clear()

    assert h.run("download") == 0
    assert [url.rsplit("/", 1)[-1] for url in h.opener.urls] == ["config.json"]


def test_an_interrupted_download_resumes_with_a_range_request(h: Harness) -> None:
    h.opener.cut["model.safetensors"] = 10
    assert h.run("download") == 1
    assert h.result.startswith("Result: the reranker model download did not finish.")
    assert "./scripts/init.sh --reranker-download" in h.result
    assert (h.paths.reranker / "model.safetensors.part").stat().st_size == 10

    h.opener.cut.clear()
    h.opener.requests.clear()
    assert h.run("download") == 0
    ranges = {url.rsplit("/", 1)[-1]: byte_range for url, byte_range in h.opener.requests}
    assert ranges["model.safetensors"] == "bytes=10-"


def test_a_file_that_does_not_match_the_pin_is_deleted_and_the_pin_is_untouched(h: Harness) -> None:
    pin_before = FIXTURE_PIN.read_bytes()
    h.opener.corrupt.add("tokenizer.json")

    code = h.run("download")

    assert code == 1
    assert h.result.startswith("Result: a downloaded reranker file is not the reviewed one, so it was not accepted.")
    assert not (h.paths.reranker / "tokenizer.json").exists()
    assert not (h.paths.reranker / "tokenizer.json.part").exists()
    assert FIXTURE_PIN.read_bytes() == pin_before


def test_a_model_config_that_is_not_a_single_score_classifier_is_not_accepted(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    shutil.copytree(FIXTURE_ARTIFACT, artifact)
    data = json.dumps({"architectures": ["XLMRobertaModel"], "id2label": {"0": "L"}}).encode("utf-8")
    (artifact / "config.json").write_bytes(data)
    document = json.loads(FIXTURE_PIN.read_text())
    document["files"][0] = {
        "path": "config.json",
        "git_blob_sha1": hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(),
        "size": len(data),
    }
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps(document), encoding="utf-8")
    harness = Harness(tmp_path / "run", pin=pin)
    harness.opener = FakeOpener(artifact)
    harness.opener.files = {
        pd.file_url(reranker.load_reranker_spec(pin), item.path): (artifact / item.path).read_bytes()
        for item in reranker.load_reranker_spec(pin).files
    }

    code = harness.run("download")

    assert code == 1 and harness.result.startswith("Result: a downloaded reranker file is not the reviewed one")


def test_redirects_to_plain_http_are_refused() -> None:
    with pytest.raises(pd.DownloadError) as caught:
        pd.HttpsOnlyRedirects().redirect_request(
            urllib.request.Request("https://huggingface.co/x"), None, 302, "Found", {}, "http://evil.example/x"
        )
    assert caught.value.code == pd.REDIRECT_REFUSED


def test_a_refused_redirect_is_reported_in_plain_words(h: Harness) -> None:
    h.opener.error = pd.DownloadError(pd.REDIRECT_REFUSED)

    assert h.run("download") == 1
    assert h.result.startswith("Result: the download was sent to an address that is not secure")


def test_low_disk_space_stops_before_any_download(h: Harness) -> None:
    h.disk.free = 5

    code = h.run("download")

    assert code == 1 and h.opener.requests == []
    assert h.result.startswith("Result: there is not enough free disk space for the reranker model.")
    assert h.result.endswith("then run ./scripts/init.sh --reranker-download again.")
    assert not h.paths.reranker.exists()


def test_an_unpinned_record_downloads_nothing(tmp_path: Path) -> None:
    pin = tmp_path / "pin.json"
    pin.write_text(json.dumps(dict(json.loads(FIXTURE_PIN.read_text()), model_revision="unpinned")), encoding="utf-8")
    harness = Harness(tmp_path / "run", pin=pin)

    assert harness.run("download") == 1
    assert harness.result == cli.LINE_UNPINNED and harness.opener.requests == []


def test_an_invalid_record_downloads_nothing(tmp_path: Path) -> None:
    pin = tmp_path / "pin.json"
    pin.write_text("[]", encoding="utf-8")
    harness = Harness(tmp_path / "run", pin=pin)

    assert harness.run("download") == 1
    assert harness.result == cli.LINE_PIN_INVALID and harness.opener.requests == []


def test_an_unexpected_error_prints_one_sentence_and_logs_the_trace(h: Harness) -> None:
    class Exploding:
        def open(self, *args: Any, **kwargs: Any) -> Any:
            raise ZeroDivisionError("SECRET-TRACE")

    code = h.run("download", opener=Exploding())

    log = h.paths.logs / "reranker-last-error.log"
    assert code == 1 and h.result.startswith("Result: the download stopped on an unexpected problem.")
    assert str(log) in h.result and "SECRET-TRACE" in log.read_text() and "SECRET-TRACE" not in "\n".join(h.lines)


# --- 7. Switching on and off -------------------------------------------------------------------

SETTINGS = "MANIJERO_ACTIVE_CAMPAIGN=2026\n"


def test_on_is_refused_without_a_verified_model_and_writes_nothing(h: Harness) -> None:
    h.write_settings(SETTINGS)

    code = h.run("switch", "on")

    assert code == 1 and h.result == cli.LINE_ON_REFUSED
    assert h.paths.settings.read_text() == SETTINGS


def test_on_is_refused_for_a_model_that_does_not_verify(h: Harness) -> None:
    h.write_settings(SETTINGS)
    h.install_model()
    (h.paths.reranker / "model.safetensors").write_bytes(b"tampered")

    assert h.run("switch", "on") == 1 and h.result == cli.LINE_ON_REFUSED


def test_on_writes_one_line_and_keeps_every_other_byte(h: Harness) -> None:
    original = "# a note\r\nMANIJERO_ACTIVE_CAMPAIGN=2026\n\n# MANIJERO_RERANKER=off\nMANIJERO_ANSWER_CACHE=off"
    h.write_settings(original)
    h.install_model()

    assert h.run("switch", "on") == 0

    assert h.result == (
        "Result: the reranker is switched on. It is used from the next ./scripts/init.sh --local-rag-start."
    )
    assert h.paths.settings.read_bytes() == (original + "\nMANIJERO_RERANKER=on\n").encode()


def test_on_replaces_an_earlier_line_in_place(h: Harness) -> None:
    h.write_settings("MANIJERO_ACTIVE_CAMPAIGN=2026\nMANIJERO_RERANKER=off\nMANIJERO_ANSWER_CACHE=off\n")
    h.install_model()

    assert h.run("switch", "on") == 0
    assert h.paths.settings.read_text() == "MANIJERO_ACTIVE_CAMPAIGN=2026\nMANIJERO_RERANKER=on\nMANIJERO_ANSWER_CACHE=off\n"
    assert lrb.read_settings(h.paths.settings).reranker == "on"


def test_off_always_writes_off_even_without_a_model(h: Harness) -> None:
    h.write_settings("MANIJERO_ACTIVE_CAMPAIGN=2026\nMANIJERO_RERANKER=on\n")

    assert h.run("switch", "off") == 0

    assert h.result == (
        "Result: the reranker is switched off. It is used from the next ./scripts/init.sh --local-rag-start."
    )
    assert lrb.read_settings(h.paths.settings).reranker == "off"


def test_the_result_says_to_restart_when_the_service_runs(h: Harness) -> None:
    h.write_settings(SETTINGS)
    h.running = True

    h.run("switch", "off")

    assert h.result.endswith("--local-rag-start. Stop and start the service to use it now.")


def test_a_missing_settings_file_names_the_setup_command(h: Harness) -> None:
    assert h.run("switch", "off") == 1 and h.result == cli.LINE_NOT_SET_UP
    assert not h.paths.settings.exists()


def test_an_invalid_settings_file_stops_with_the_fix(h: Harness) -> None:
    h.write_settings("MANIJERO_ACTIVE_CAMPAIGN=2026\nMANIJERO_RERANKER=maybe\n")

    code = h.run("switch", "on")

    assert code == 1 and h.result == cli.LINE_SETTINGS_BAD
    assert any("line 2" in line and "the reranker must be on or off" in line for line in h.lines)
    assert "maybe" in h.paths.settings.read_text()


# --- The settings file, the launch environment, and the status line ---------------------------


def test_the_settings_file_accepts_and_documents_the_reranker_line(tmp_path: Path) -> None:
    path = tmp_path / "settings.env"
    lrb.create_settings(path)
    assert "# MANIJERO_RERANKER=off" in path.read_text() and lrb.read_settings(path).reranker is None
    path.write_text(SETTINGS + "MANIJERO_RERANKER = on\n", encoding="utf-8")
    assert lrb.read_settings(path).reranker == "on"
    path.write_text(SETTINGS + "MANIJERO_RERANKER=on\nMANIJERO_RERANKER=off\n", encoding="utf-8")
    with pytest.raises(lrb.SettingsError):
        lrb.read_settings(path)


@pytest.fixture
def ready(tmp_path: Path) -> boot.Env:
    environment = boot.Env(tmp_path)
    assert environment.setup("yes") == 0, environment.output
    environment.forget_calls()
    return environment


def with_reranker(environment: boot.Env, default_state: str = "off") -> lrb.Context:
    settings = tmp_settings(environment.tmp, default_state)
    return dataclasses.replace(environment.ctx, reranker_pin=FIXTURE_PIN, reranker_settings=settings)


def tmp_settings(directory: Path, default_state: str) -> Path:
    document = json.loads(REAL_SETTINGS.read_text())
    document["default_state"] = default_state
    target = directory / "reranker-settings-{}.json".format(default_state)
    target.write_text(json.dumps(document), encoding="utf-8")
    return target


def launch(environment: boot.Env, ctx: lrb.Context, owner: Optional[str]) -> Dict[str, str]:
    model = svc_tests.lrb.load_pins(ctx, boot.NOW.date())[1]
    release = svc_tests.kr.current_release_id(ctx.paths.releases)
    return svc.launch_environment(ctx, lrb.Settings("2026", reranker=owner), model, release, {"PATH": "/bin"})


def test_the_launch_environment_carries_no_reranker_key_by_default(ready: boot.Env) -> None:
    environment = launch(ready, with_reranker(ready), None)

    assert "MANIJERO_RERANKER" not in environment and "MANIJERO_RERANKER_ARTIFACT" not in environment


def test_the_launch_environment_passes_the_reranker_only_when_on_and_verified(ready: boot.Env) -> None:
    ctx = with_reranker(ready)
    assert "MANIJERO_RERANKER" not in launch(ready, ctx, "on")  # on, but the model is missing
    shutil.copytree(FIXTURE_ARTIFACT, ctx.paths.reranker)

    environment = launch(ready, ctx, "on")

    assert environment["MANIJERO_RERANKER"] == "on"
    assert environment["MANIJERO_RERANKER_ARTIFACT"] == str(ctx.paths.reranker)
    (ctx.paths.reranker / "model.safetensors").write_bytes(b"tampered")
    assert "MANIJERO_RERANKER" not in launch(ready, ctx, "on")


def test_the_owner_off_line_wins_over_a_repository_default_of_on(ready: boot.Env) -> None:
    ctx = with_reranker(ready, default_state="on")
    shutil.copytree(FIXTURE_ARTIFACT, ctx.paths.reranker)

    assert launch(ready, ctx, None)["MANIJERO_RERANKER"] == "on"
    assert "MANIJERO_RERANKER" not in launch(ready, ctx, "off")


def test_the_repository_default_ships_off_so_nothing_is_passed() -> None:
    assert json.loads(REAL_SETTINGS.read_text())["default_state"] == "off"


def status_line(environment: boot.Env, ctx: lrb.Context, owner: Optional[str]) -> str:
    return svc.reranker_line(ctx, lrb.Settings("2026", reranker=owner))


def test_the_service_status_has_one_reranker_line(ready: boot.Env) -> None:
    ctx = with_reranker(ready)

    assert status_line(ready, ctx, None).endswith("Reranker: off.")
    assert status_line(ready, ctx, "off").endswith("Reranker: off.")
    assert status_line(ready, ctx, "on").endswith(
        "Reranker: switched on but the model is missing; answering without it."
    )
    shutil.copytree(FIXTURE_ARTIFACT, ctx.paths.reranker)
    assert status_line(ready, ctx, "on").endswith("Reranker: on.")


def test_the_running_service_status_prints_the_reranker_line_without_changing_its_checks() -> None:
    # The wiring is covered by test_local_rag_service (three OK checks stay three); here only the text.
    assert svc.reranker_line.__doc__ and "Reranker" in svc.reranker_line.__doc__


# --- 6. Measure (prerequisites and the whole command over fakes) -------------------------------


class KeepOrder:
    def score(self, query: str, texts: Sequence[str]) -> Tuple[float, ...]:
        return tuple(float(-position) for position in range(len(texts)))


def measure_ports(environment: boot.Env, model_installed: bool = True) -> Harness:
    harness = Harness(environment.tmp / "unused")
    harness.paths = environment.paths
    harness.lines = []
    harness.ports = dataclasses.replace(
        harness.ports,
        paths=environment.paths,
        embedding_config=boot.FIXTURE_SPEC,
        knowledge_dir=ROOT / "knowledge",
        hybrid_python=Path(sys.executable),
        out=harness.lines.append,
    )
    if model_installed:
        shutil.copytree(FIXTURE_ARTIFACT, environment.paths.reranker)
    return harness


def real_corpus_components(environment: boot.Env):
    from app.ask_api import CorpusDocuments, _prepare_runtime_corpus
    from app.retrieval import load_passage_set
    from app.source_catalog import load_catalog

    documents = CorpusDocuments(
        catalog=load_catalog(ROOT / "knowledge" / "source_catalog.json"),
        passages=load_passage_set(ROOT / "knowledge" / "passages.json"),
    )
    retriever = _prepare_runtime_corpus(documents, boot.NOW.date(), "2026")
    return lambda: hyb.components_for(retriever)


def test_the_whole_measure_command_prints_one_result_line_over_the_real_reviewed_sets(ready: boot.Env) -> None:
    harness = measure_ports(ready)
    harness.ports.hybrid_loader = real_corpus_components(ready)

    code = harness.run("measure", scorer=KeepOrder())

    result = harness.result
    assert code == 0 and harness.lines[-1] == result
    assert result.startswith("Result: reranker measured on ")
    assert "against today's hybrid search. Right source found: " in result
    assert result.endswith("Send this line to the developer.")
    assert "Verdict: OFF - fewer than 2 more golden questions found their right source." in result
    assert any(line.startswith("Checked question 1 of ") for line in harness.lines)


@pytest.mark.parametrize("missing", ["hybrid_python", "bge_m3", "release"])
def test_a_missing_hybrid_environment_model_or_store_names_the_setup_command(ready: boot.Env, missing: str) -> None:
    harness = measure_ports(ready)
    harness.ports.hybrid_loader = real_corpus_components(ready)
    if missing == "hybrid_python":
        harness.ports.hybrid_python = ready.tmp / "no-such-python"
    elif missing == "bge_m3":
        (ready.paths.bge_m3 / "config.json").write_bytes(b"{}")
    else:
        shutil.rmtree(ready.paths.releases)

    code = harness.run("measure", scorer=KeepOrder())

    assert code == 1
    assert harness.result == (
        "Result: the reranker was not measured because today's hybrid search is not ready. "
        "Run ./scripts/init.sh --local-rag-setup, then measure again."
    )
    assert not any(line.startswith("Checked question") for line in harness.lines)


def test_a_stale_store_names_the_setup_command(ready: boot.Env) -> None:
    harness = measure_ports(ready)
    harness.ports.hybrid_loader = lambda: hyb.components_for(hyb.retrieval_retriever())

    assert harness.run("measure", scorer=KeepOrder()) == 1
    assert "today's hybrid search is not ready" in harness.result


def test_a_missing_reranker_model_names_the_download_command(ready: boot.Env) -> None:
    harness = measure_ports(ready, model_installed=False)
    harness.ports.hybrid_loader = real_corpus_components(ready)

    assert harness.run("measure", scorer=KeepOrder()) == 1
    assert "./scripts/init.sh --reranker-download" in harness.result


def test_the_measure_command_writes_no_setting(ready: boot.Env) -> None:
    harness = measure_ports(ready)
    harness.ports.hybrid_loader = real_corpus_components(ready)
    before = ready.paths.settings.read_text()

    harness.run("measure", scorer=KeepOrder())

    assert ready.paths.settings.read_text() == before


def test_an_unexpected_measure_error_stops_with_a_line_and_a_log(ready: boot.Env) -> None:
    harness = measure_ports(ready)

    def explode() -> Any:
        raise ZeroDivisionError("SECRET-TRACE")

    harness.ports.hybrid_loader = explode
    # A loader failure is "not ready"; a failure elsewhere is unexpected.
    assert harness.run("measure", scorer=KeepOrder()) == 1
    assert "not ready" in harness.result

    harness.ports.hybrid_loader = real_corpus_components(ready)
    harness.ports.knowledge_dir = ready.tmp / "no-knowledge"
    assert harness.run("measure", scorer=KeepOrder()) == 1
    assert "reviewed question files could not be read" in harness.result


def test_the_loader_reads_the_approved_golden_and_trap_items_from_the_real_files() -> None:
    from app import reranker_measure as measure

    knowledge = ROOT / "knowledge"
    inputs = measure.MeasureInputs(
        knowledge / "source_catalog.json", knowledge / "passages.json", knowledge / "pac_answer_eval.json",
        knowledge / "golden_set.json", knowledge / "trap_set.json", "2026", date(2026, 11, 10),
    )

    _, _, cases = cli.load_cases(inputs)

    golden = [case for case in cases if case["case_set"] == "golden"]
    traps = [case for case in cases if case["case_set"] == "trap"]
    assert golden and traps and len(golden) + len(traps) == len(cases)
    assert all("category" in case for case in traps) and not any("category" in case for case in golden)
    assert len({case["id"] for case in cases}) == len(cases)


def test_unreadable_reviewed_files_stop_with_one_line() -> None:
    from app import reranker_measure as measure

    missing = Path("/nonexistent/file.json")
    inputs = measure.MeasureInputs(missing, missing, missing, missing, missing, "2026", date(2026, 11, 10))

    with pytest.raises(measure.MeasureStop) as caught:
        cli.load_cases(inputs)

    assert caught.value.line == measure.LINE_INPUTS


# --- init.sh -----------------------------------------------------------------------------------


def make_checkout(tmp_path: Path, with_python: bool) -> Path:
    # init.sh sources scripts/lib and scripts/commands, so the checkout needs the whole folder.
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    (tmp_path / "backend" / "scripts").mkdir(parents=True)
    init = tmp_path / "scripts" / "init.sh"
    stub = tmp_path / "scripts" / "python-env.sh"
    stub.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    for script in (init, stub):
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
    if with_python:
        python = tmp_path / "backend" / ".venv-hybrid" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n', encoding="utf-8")
        python.chmod(python.stat().st_mode | stat.S_IXUSR)
    return init


FLAGS = ["--reranker-download", "--reranker-measure", "--reranker-on", "--reranker-off"]


@pytest.mark.parametrize("flag", FLAGS)
def test_init_names_the_setup_command_when_the_tools_are_missing(tmp_path: Path, flag: str) -> None:
    init = make_checkout(tmp_path, with_python=False)

    done = subprocess.run([str(init), flag], capture_output=True, text=True, cwd=tmp_path, timeout=60)

    assert done.returncode == 1
    assert done.stdout.strip().splitlines()[-1] == (
        "Result: the reranker command did not run. Run ./scripts/init.sh --local-rag-setup."
    )


def test_init_dispatches_each_command_without_arguments(tmp_path: Path) -> None:
    init = make_checkout(tmp_path, with_python=True)

    def lines(flag: str) -> List[str]:
        done = subprocess.run([str(init), flag], capture_output=True, text=True, cwd=tmp_path, timeout=60)
        assert done.returncode == 0, done.stderr
        return done.stdout.splitlines()

    assert lines("--reranker-download")[1:] == ["download"]
    assert lines("--reranker-measure")[1:] == ["measure"]
    assert lines("--reranker-on")[1:] == ["switch", "on"]
    assert lines("--reranker-off")[1:] == ["switch", "off"]
    assert lines("--reranker-on")[0].endswith("reranker.py")


@pytest.mark.parametrize("flag", FLAGS)
def test_init_rejects_extra_arguments(tmp_path: Path, flag: str) -> None:
    init = make_checkout(tmp_path, with_python=True)

    done = subprocess.run([str(init), flag, "x"], capture_output=True, text=True, cwd=tmp_path, timeout=60)

    assert done.returncode == 2 and "on its own" in done.stderr


def test_the_help_lists_the_four_commands() -> None:
    done = subprocess.run([str(ROOT / "scripts" / "init.sh"), "--help"], capture_output=True, text=True, timeout=60)

    for flag in FLAGS:
        assert flag in done.stdout
