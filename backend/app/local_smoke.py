"""Smoke-test the Desktop and Android emulator apps against the running local answer service.

Operator-only and stdlib-only; the answer service never imports this module. The owner runs it
as ``./scripts/init.sh --local-smoke`` once ``--local-rag-start`` has started the service.
:func:`run_smoke` works in this order and stops at the first gap:

1. take the lock ``<repo>/build/local-smoke/.lock`` (one smoke test at a time);
2. check the service: setup done, a running service started by ``--local-rag-start`` (a stale
   record is cleared), and its three status checks ``OK`` (:func:`local_rag_service.service_checks`);
3. check Java and the Gradle wrapper;
4. Desktop: ``:shared:runDesktopLocalSmoke`` renders the shared app offscreen, asks the fixed
   question, and writes one result line;
5. Android emulator: the first booted ``emulator-*`` serial gets ``installDebug`` and
   ``installDebugAndroidTest`` (both keep the app's data), then ``am instrument`` runs
   ``AndroidLocalSmokeTest``, which reports one result line as an instrumentation status.
   ``connectedAndroidTest`` is never used: it uninstalls the app and wipes its data. Physical
   devices are never used: they cannot reach a loopback service.

Each platform ends in one ``PASS`` or ``FAIL`` line and the run in one ``Result:`` line. Output,
result files, and the logs this module writes carry only outcome codes, source counts, and the
address in use, never question, answer, or passage text. Every external effect goes through the
injected :class:`SmokePorts`, so tests use fakes.
"""

from __future__ import annotations

import fcntl
import os
import re
import signal
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Mapping, Optional, Protocol, Sequence

from app import local_rag_bootstrap as bootstrap
from app import local_rag_service as svc

SMOKE_COMMAND = "./scripts/init.sh --local-smoke"
SMOKE_DIR = Path("build") / "local-smoke"
LOCK_NAME = ".lock"
DESKTOP_RESULT_NAME = "desktop-result.txt"
DESKTOP_LOG_NAME = "desktop.log"
ANDROID_LOG_NAME = "android.log"

DESKTOP = "Desktop"
ANDROID = "Android emulator"

BUILD_TIMEOUT_SECONDS = 15 * 60
INSTRUMENT_TIMEOUT_SECONDS = 5 * 60
ADB_TIMEOUT_SECONDS = 30

DESKTOP_DEFAULT_URL = "http://127.0.0.1:8000"
ANDROID_DEFAULT_URL = "http://10.0.2.2:8000"
DESKTOP_URL_ENV = "MANIJERO_ASK_BASE_URL"
ANDROID_URL_ENV = "ORG_GRADLE_PROJECT_manijeroAskBaseUrl"

TEST_CLASS = "com.jamarglex.manijero.smoke.AndroidLocalSmokeTest"
TEST_RUNNER = "com.jamarglex.manijero.test/androidx.test.runner.AndroidJUnitRunner"
STATUS_KEY = "manijero_smoke_result"

RESULT_PREFIX = "MANIJERO_SMOKE_RESULT"
PASSING = ("answered", "abstained")
CODES = (
    "answered", "abstained", "answered_without_sources", "land_clarification", "unreachable",
    "service_error", "not_ready", "ready_unknown", "not_manijero", "other_address", "no_answer", "error",
)
_RESULT = re.compile(
    r"{} outcome=({}) sources=([0-9]{{1,4}}) address=(default|saved) url=(invalid|https?://[!-~]{{1,512}})".format(
        RESULT_PREFIX, "|".join(CODES)
    )
)
# A crash before the test reports anything, because a method or class the test tools need is
# missing on the device (for example Espresso before 3.6 on API 34+).
_TOOLS_MISMATCH = re.compile(r"\b(NoSuchMethodException|NoSuchMethodError|NoSuchFieldError|NoClassDefFoundError|ClassNotFoundException)\b")
_STATUS_LINE = re.compile(r"INSTRUMENTATION_STATUS: {}=(.*)".format(STATUS_KEY))

MSG_BUSY = "Another smoke test is running in another Terminal window."
FIX_BUSY = "Wait for it to finish, then run this command again."
MSG_NOT_RUNNING = "The local answer service is not running."
FIX_START = "Start it with {}, then run this command again.".format(svc.START_COMMAND)
FIX_SHOWN = "Do the step shown above."
MSG_NO_JAVA = "Java was not found on this computer."
FIX_JAVA = "Install Temurin 21 from https://adoptium.net, then run this command again."
MSG_NO_WRAPPER = "The project's Gradle wrapper (gradlew) is missing."
FIX_WRAPPER = "Get a fresh copy of the project from a developer, then run this command again."
STEP_STATUS = "Run {} and do its first step, then run this command again.".format(svc.SERVICE_STATUS_COMMAND)
STEP_AGAIN = "then run this command again."

STOPPED_LINE = "The smoke test was stopped."
STOPPED_RESULT = "Result: the smoke test was stopped before it finished."
NOT_RUN_RESULT = "Result: the smoke test did not run."
PASSED_RESULT = "Result: the smoke test passed on Desktop and the Android emulator."


# --- Ports --------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """One finished child step: its exit code (``None`` when it timed out) and its standard output."""

    returncode: Optional[int]
    timed_out: bool = False
    output: str = ""

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        cwd: Path,
        log_path: Path,
        timeout: float,
        env: Optional[Mapping[str, str]] = None,
    ) -> RunResult:
        """Run one child, its output going to ``log_path`` only; on Ctrl+C end it and re-raise."""


class Tools(Protocol):
    def java_available(self) -> bool: ...

    def adb_path(self) -> Optional[str]: ...


@dataclass
class SmokePorts:
    service: svc.ServicePorts
    runner: Runner
    tools: Tools
    environ: Mapping[str, str]

    @property
    def out(self):
        return self.service.out


# --- Result protocol ----------------------------------------------------------------------


@dataclass(frozen=True)
class SmokeResult:
    outcome: str
    sources: int
    address: str  # "default" or "saved"
    url: str

    @property
    def passed(self) -> bool:
        return self.outcome in PASSING


def parse_result(text: str) -> Optional[SmokeResult]:
    """The one well-formed result line, or ``None`` (missing, malformed, extra fields, or several)."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    match = _RESULT.fullmatch(lines[0])
    if match is None:
        return None
    outcome, sources, address, url = match.groups()
    return SmokeResult(outcome, int(sources), address, url)


def parse_instrumentation(output: str) -> Optional[SmokeResult]:
    """The result carried by the ``manijero_smoke_result`` instrumentation status, else ``None``."""

    rows = (row.rstrip("\r") for row in output.splitlines())
    values = [match.group(1) for match in map(_STATUS_LINE.fullmatch, rows) if match]
    return parse_result(values[0]) if len(values) == 1 else None


# --- Lines --------------------------------------------------------------------------------


def _same_address(first: str, second: str) -> bool:
    return first.strip().rstrip("/").lower() == second.strip().rstrip("/").lower()


def build_default(platform: str, environ: Mapping[str, str]) -> str:
    """The platform's build-default address as the smoke run builds it (see ``AskEndpoint.kt``)."""

    if platform == DESKTOP:
        return (environ.get(DESKTOP_URL_ENV) or "").strip() or DESKTOP_DEFAULT_URL
    return (environ.get(ANDROID_URL_ENV) or "").strip() or ANDROID_DEFAULT_URL


def could_not_run(platform: str, log_shown: str) -> str:
    return "FAIL  {}: the check could not run. Details are in {}; send that file to a developer.".format(
        platform, log_shown
    )


def platform_line(platform: str, result: SmokeResult, expected: str, default_url: str, log_shown: str) -> str:
    """The one ``PASS`` or ``FAIL`` line for a well-formed result."""

    code, url = result.outcome, result.url
    if code == "answered" and result.sources > 0:
        cards = "card" if result.sources == 1 else "cards"
        return "PASS  {}: the app asked the test question and showed an answer with {} source {}.".format(
            platform, result.sources, cards
        )
    if code == "abstained":
        return (
            "PASS  {}: the app asked the test question and showed an honest abstention "
            "(Sin respuesta segura).".format(platform)
        )
    send_log = "Send {} to a developer.".format(log_shown)
    if code == "other_address":
        uses_default = result.address == "saved" and _same_address(default_url, expected)
        step = (
            "press Usar la dirección predeterminada"
            if uses_default
            else "enter {} and press Comprobar".format(expected)
        )
        return "FAIL  {}: the app uses {}, not {}. Open Ayuda > Herramientas de prueba > Conexión, {}, {}".format(
            platform, url, expected, step, STEP_AGAIN
        )
    texts = {
        "answered": "the app showed an answer without any source card. " + send_log,
        "answered_without_sources": "the app showed an answer without any source card. " + send_log,
        "land_clarification": "the app asked to choose a land instead of answering the general test question. " + send_log,
        "unreachable": "the app could not reach the local answer service at {}. {}".format(url, STEP_STATUS),
        "service_error": "the local answer service answered the app with an error. " + STEP_STATUS,
        "not_ready": "the app reached the service at {}, but it cannot answer questions right now. {}".format(url, STEP_STATUS),
        "ready_unknown": "the app reached the service at {}, but could not tell whether it can answer. {}".format(url, STEP_STATUS),
        "not_manijero": "the program at {} is not the Manijero answer service. {}".format(url, STEP_STATUS),
        "no_answer": "the app showed no reply within 90 seconds. " + STEP_STATUS,
    }
    if code not in texts:  # "error": the driver itself could not finish
        return could_not_run(platform, log_shown)
    return "FAIL  {}: {}".format(platform, texts[code])


def tools_mismatch(platform: str, log_shown: str) -> str:
    return (
        "FAIL  {}: the Android test tools do not match this emulator's Android version. Details are in "
        "{}; send that file to a developer.".format(platform, log_shown)
    )


def final_result(failed: Sequence[str]) -> str:
    if not failed:
        return PASSED_RESULT
    names = " and ".join(name if name == DESKTOP else "the " + name for name in failed)
    return "Result: the smoke test failed on {}. Do the first step shown above.".format(names)


# --- Command ------------------------------------------------------------------------------


class _NotRun(Exception):
    """A prerequisite gap: nothing was built, installed, or started."""

    def __init__(self, lines: Sequence[str], fix: str) -> None:
        super().__init__(fix)
        self.lines = list(lines)
        self.fix = fix


@contextmanager
def smoke_lock(path: Path) -> Iterator[None]:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise _NotRun([MSG_BUSY], FIX_BUSY) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


def run_smoke(ctx: bootstrap.Context, ports: SmokePorts, smoke_dir: Optional[Path] = None) -> int:
    """Check the prerequisites, then Desktop, then the Android emulator; ``0`` only when both pass."""

    out = ports.out
    directory = Path(smoke_dir) if smoke_dir is not None else ctx.repo_root / SMOKE_DIR
    out("Checking the local answer service...")
    try:
        with smoke_lock(directory / LOCK_NAME):
            port = _check_service(ctx, ports)
            gradlew = _check_build_tools(ctx, ports)
            lines = [
                _run_desktop(ctx, ports, directory, gradlew, port),
                _run_android(ctx, ports, directory, gradlew, port),
            ]
    except _NotRun as stop:
        for line in stop.lines:
            out(line)
        out("{} {}".format(NOT_RUN_RESULT, stop.fix))
        return 1
    except KeyboardInterrupt:
        out("")
        out(STOPPED_LINE)
        out(STOPPED_RESULT)
        return 1
    failed = [name for name, line in zip((DESKTOP, ANDROID), lines) if not line.startswith("PASS")]
    out(final_result(failed))
    return 0 if not failed else 1


def _check_service(ctx: bootstrap.Context, ports: SmokePorts) -> int:
    paths = ctx.paths
    try:
        settings = bootstrap.read_settings(paths.settings)
    except bootstrap.SettingsError as error:
        raise _NotRun([error.message], svc.FIX_SETTINGS) from None
    if settings is None:
        raise _NotRun([svc.MSG_NOT_SET_UP], svc.FIX_RUN_SETUP)
    record, stale = svc.find_running(paths, ports.service.processes)
    if record is None:
        raise _NotRun(([svc.MSG_STALE] if stale else []) + [MSG_NOT_RUNNING], FIX_START)
    try:
        checks = svc.service_checks(ctx, ports.service, record)
    except bootstrap.BootstrapError as error:
        raise _NotRun([error.message], FIX_SHOWN) from None
    failing = [check for check in checks if not check.ok]
    if failing:
        raise _NotRun([failing[0].line], FIX_SHOWN)
    return record.port


def _check_build_tools(ctx: bootstrap.Context, ports: SmokePorts) -> Path:
    if not ports.tools.java_available():
        raise _NotRun([MSG_NO_JAVA], FIX_JAVA)
    gradlew = ctx.repo_root / "gradlew"
    if not os.access(gradlew, os.X_OK):
        raise _NotRun([MSG_NO_WRAPPER], FIX_WRAPPER)
    return gradlew


def _shown(ctx: bootstrap.Context, path: Path) -> str:
    try:
        return str(path.relative_to(ctx.repo_root))
    except ValueError:
        return str(path)


def _fresh(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return path


def _run_desktop(ctx: bootstrap.Context, ports: SmokePorts, directory: Path, gradlew: Path, port: int) -> str:
    out = ports.out
    expected = svc.service_url(port)
    log = _fresh(directory / DESKTOP_LOG_NAME)
    result_file = _fresh(directory / DESKTOP_RESULT_NAME)
    shown = _shown(ctx, log)
    out("Checking the Desktop app (the first run can take a few minutes)...")
    run = ports.runner.run(
        [
            str(gradlew), "--console=plain", "--quiet", ":shared:runDesktopLocalSmoke",
            "-PmanijeroSmokeExpected={}".format(expected),
            "-PmanijeroSmokeResult={}".format(result_file),
        ],
        cwd=ctx.repo_root,
        log_path=log,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    try:
        text = result_file.read_text(encoding="utf-8") if run.ok else ""
    except (OSError, UnicodeDecodeError):
        text = ""
    line = _line_for(DESKTOP, parse_result(text), expected, build_default(DESKTOP, ports.environ), shown)
    out(line)
    return line


def _line_for(platform: str, result: Optional[SmokeResult], expected: str, default_url: str, shown: str) -> str:
    if result is None:
        return could_not_run(platform, shown)
    return platform_line(platform, result, expected, default_url, shown)


def _emulator_fail(text: str) -> str:
    return "FAIL  {}: {} {}".format(ANDROID, text, STEP_AGAIN)


def _run_android(ctx: bootstrap.Context, ports: SmokePorts, directory: Path, gradlew: Path, port: int) -> str:
    out = ports.out
    expected = "http://{}:{}".format(svc.EMULATOR_HOST, port)
    log = _fresh(directory / ANDROID_LOG_NAME)
    shown = _shown(ctx, log)
    out("Checking the Android emulator app (the first run can take a few minutes)...")
    line = _android_line(ctx, ports, gradlew, expected, log, shown)
    out(line)
    return line


def _android_line(
    ctx: bootstrap.Context, ports: SmokePorts, gradlew: Path, expected: str, log: Path, shown: str
) -> str:
    runner = ports.runner
    adb = ports.tools.adb_path()
    if adb is None:
        return _emulator_fail(
            "adb was not found. Install SDK Platform-Tools in Android Studio (Tools > SDK Manager > SDK Tools),"
        )
    devices = runner.run([adb, "devices"], cwd=ctx.repo_root, log_path=log, timeout=ADB_TIMEOUT_SECONDS)
    if not devices.ok:
        return could_not_run(ANDROID, shown)
    emulators = []
    for row in devices.output.splitlines()[1:]:
        parts = row.split()
        if len(parts) >= 2 and parts[0].startswith("emulator-"):
            emulators.append((parts[0], parts[1]))
    if not emulators:
        return _emulator_fail(
            "no Android emulator is running. Start one with ./scripts/init.sh --android-run or Android "
            "Studio's Device Manager,"
        )
    serial = None
    for candidate, state in emulators:
        if state != "device":
            continue
        boot = runner.run(
            [adb, "-s", candidate, "shell", "getprop", "sys.boot_completed"],
            cwd=ctx.repo_root,
            log_path=log,
            timeout=ADB_TIMEOUT_SECONDS,
        )
        if boot.ok and boot.output.strip() == "1":
            serial = candidate
            break
    if serial is None:
        return _emulator_fail("the Android emulator is still starting. Wait for its home screen,")

    install = runner.run(
        [str(gradlew), "--console=plain", "--quiet", ":androidApp:installDebug", ":androidApp:installDebugAndroidTest"],
        cwd=ctx.repo_root,
        log_path=log,
        timeout=BUILD_TIMEOUT_SECONDS,
        env={**ports.environ, "ANDROID_SERIAL": serial},
    )
    if not install.ok:
        return could_not_run(ANDROID, shown)
    instrument = runner.run(
        [
            adb, "-s", serial, "shell", "am", "instrument", "-w", "-r",
            "-e", "class", TEST_CLASS,
            "-e", "expectedAddress", expected,
            TEST_RUNNER,
        ],
        cwd=ctx.repo_root,
        log_path=log,
        timeout=INSTRUMENT_TIMEOUT_SECONDS,
    )
    result = parse_instrumentation(instrument.output) if instrument.ok else None
    if result is None and not instrument.timed_out and _TOOLS_MISMATCH.search(instrument.output):
        return tools_mismatch(ANDROID, shown)
    return _line_for(ANDROID, result, expected, build_default(ANDROID, ports.environ), shown)


# --- Real ports ---------------------------------------------------------------------------


class SubprocessRunner:
    """Runs each child in its own session with its output in the log only; ends it on timeout or Ctrl+C.

    Standard output goes to an unnamed file next to the log rather than a pipe, so a helper process
    that outlives the child (such as the Gradle daemon) can never keep the step waiting.
    """

    def run(
        self,
        argv: Sequence[str],
        cwd: Path,
        log_path: Path,
        timeout: float,
        env: Optional[Mapping[str, str]] = None,
    ) -> RunResult:
        directory = Path(log_path).parent
        directory.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log, tempfile.TemporaryFile("w+", dir=directory) as captured:
            log.write("$ {}\n".format(" ".join(str(part) for part in argv)))
            log.flush()
            child = subprocess.Popen(  # noqa: S603 - fixed argv built by this module
                [str(part) for part in argv],
                cwd=str(cwd),
                env=dict(env) if env is not None else None,
                stdin=subprocess.DEVNULL,
                stdout=captured,
                stderr=log,
                start_new_session=True,  # Ctrl+C reaches this process only; the child is ended below
            )
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._end(child)
                return self._finish(log, captured, None, "timed out after {} seconds".format(int(timeout)))
            except BaseException:
                self._end(child)
                log.write("stopped\n")
                raise
            return self._finish(log, captured, child.returncode, "exit {}".format(child.returncode))

    @staticmethod
    def _finish(log, captured, returncode: Optional[int], note: str) -> RunResult:
        captured.seek(0)
        output = captured.read()
        log.write(output)
        if output and not output.endswith("\n"):
            log.write("\n")
        log.write(note + "\n")
        return RunResult(returncode, returncode is None, output)

    @staticmethod
    def _end(child: "subprocess.Popen[str]") -> None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            child.wait()


class SystemTools:
    """``java`` from the ``JAVA_HOME`` that ``scripts/java-env.sh`` resolved; ``adb`` from the SDK.

    ``./scripts/init.sh --local-smoke`` runs the shared Java resolution and exports ``JAVA_HOME``
    only when it found a Java that runs, so Java counts as present exactly when ``JAVA_HOME/bin/java
    -version`` succeeds. A ``java`` that is only on ``PATH`` (such as Apple's placeholder) is never
    taken on its own, so this check and the resolution always agree.
    """

    def __init__(self, environ: Mapping[str, str]) -> None:
        self._environ = environ

    def java_available(self) -> bool:
        java_home = (self._environ.get("JAVA_HOME") or "").strip()
        java = Path(java_home) / "bin" / "java"
        if not java_home or not os.access(java, os.X_OK):
            return False
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv
                [str(java), "-version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=ADB_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return completed.returncode == 0

    def adb_path(self) -> Optional[str]:
        sdk = (self._environ.get("ANDROID_HOME") or self._environ.get("ANDROID_SDK_ROOT") or "").strip()
        root = Path(sdk) if sdk else Path.home() / "Library" / "Android" / "sdk"
        adb = root / "platform-tools" / "adb"
        return str(adb) if os.access(adb, os.X_OK) else None
