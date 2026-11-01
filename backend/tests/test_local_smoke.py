"""The local smoke test orchestrator with a fake runner, fake tools, and the fake service harness.

Offline: no Gradle, adb, emulator, service, Ollama, or model. The service side reuses the fakes
from ``test_local_rag_service`` (a temporary local home made ready by the fake-backed setup and a
fake running service), so the real ``find_running`` and ``service_checks`` run. Every child step
goes through :class:`FakeRunner`, which records the argv and answers like Gradle or adb would.
"""

from __future__ import annotations

import dataclasses
import fcntl
import os
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

import pytest

import test_local_rag_bootstrap as boot
from test_local_rag_service import Harness, env, harness, ready, running  # noqa: F401 - pytest fixtures
from app import local_rag_service as svc
from app import local_smoke as smoke

QUESTION = "¿Qué es la solicitud única de la PAC?"
DESKTOP_OK = "MANIJERO_SMOKE_RESULT outcome=answered sources=2 address=default url=http://127.0.0.1:8000"
ANDROID_OK = "MANIJERO_SMOKE_RESULT outcome=abstained sources=0 address=default url=http://10.0.2.2:8000"
CHECKING = [
    "Checking the local answer service...",
    "Checking the Desktop app (the first run can take a few minutes)...",
    "Checking the Android emulator app (the first run can take a few minutes)...",
]


def instrumentation_output(line: Optional[str], extra: str = "") -> str:
    status = "INSTRUMENTATION_STATUS: manijero_smoke_result={}\r\nINSTRUMENTATION_STATUS_CODE: 2\r\n".format(line) if line else ""
    return (
        "INSTRUMENTATION_STATUS: class=com.jamarglex.manijero.smoke.AndroidLocalSmokeTest\r\n"
        "INSTRUMENTATION_STATUS_CODE: 1\r\n" + status + extra + "INSTRUMENTATION_STATUS_CODE: 0\r\n"
        "INSTRUMENTATION_RESULT: stream=\r\nOK (1 test)\r\nINSTRUMENTATION_CODE: -1\r\n"
    )


class FakeRunner:
    """Answers like Gradle and adb; ``fail`` names an argv marker whose step exits 1."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, object]] = []
        self.desktop: Optional[str] = DESKTOP_OK + "\n"
        self.devices = "List of devices attached\nemulator-5554\tdevice\n\n"
        self.boot: Dict[str, str] = {"emulator-5554": "1"}
        self.instrument = instrumentation_output(ANDROID_OK)
        self.fail: Optional[str] = None
        self.time_out: Optional[str] = None
        self.interrupt: Optional[str] = None

    def run(self, argv: Sequence[str], cwd: Path, log_path: Path, timeout: float, env: Optional[Mapping[str, str]] = None) -> smoke.RunResult:
        argv = [str(part) for part in argv]
        self.calls.append({"argv": argv, "env": dict(env) if env is not None else None, "timeout": timeout, "log": Path(log_path), "cwd": Path(cwd)})
        joined = " ".join(argv)
        if self.interrupt and self.interrupt in joined:
            raise KeyboardInterrupt
        if self.time_out and self.time_out in joined:
            return smoke.RunResult(None, True)
        code = 1 if self.fail and self.fail in joined else 0
        if ":shared:runDesktopLocalSmoke" in argv:
            target = next(part.split("=", 1)[1] for part in argv if part.startswith("-PmanijeroSmokeResult="))
            if self.desktop is not None:
                Path(target).write_text(self.desktop, encoding="utf-8")
            return smoke.RunResult(code)
        if argv[1:] == ["devices"]:
            return smoke.RunResult(code, output=self.devices)
        if "getprop" in argv:
            return smoke.RunResult(code, output=self.boot.get(argv[2], "") + "\r\n")
        if ":androidApp:installDebug" in argv:
            return smoke.RunResult(code)
        if "instrument" in argv:
            return smoke.RunResult(code, output=self.instrument)
        raise AssertionError("unexpected step: {}".format(argv))

    def argvs(self) -> List[List[str]]:
        return [call["argv"] for call in self.calls]  # type: ignore[misc]


class FakeTools:
    def __init__(self) -> None:
        self.java = True
        self.adb: Optional[str] = "/sdk/platform-tools/adb"

    def java_available(self) -> bool:
        return self.java

    def adb_path(self) -> Optional[str]:
        return self.adb


class Smoke:
    def __init__(self, harness: Harness, tmp_path: Path) -> None:
        self.harness = harness
        self.runner = FakeRunner()
        self.tools = FakeTools()
        self.environ: Dict[str, str] = {"PATH": "/bin"}
        self.dir = tmp_path / "local-smoke"

    def run(self) -> int:
        self.harness.env._reset()
        ports = smoke.SmokePorts(service=self.harness.ports, runner=self.runner, tools=self.tools, environ=self.environ)
        return smoke.run_smoke(self.harness.env.ctx, ports, smoke_dir=self.dir)

    @property
    def lines(self) -> List[str]:
        return self.harness.lines


@pytest.fixture
def s(running: Harness, tmp_path: Path) -> Smoke:  # noqa: F811 - the fixture from test_local_rag_service
    return Smoke(running, tmp_path)


def _hold(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


# --- 1. Both platforms pass ----------------------------------------------------------------


def test_both_platforms_pass(s: Smoke) -> None:
    code = s.run()

    assert code == 0, s.lines
    assert s.lines == [
        CHECKING[0],
        CHECKING[1],
        "PASS  Desktop: the app asked the test question and showed an answer with 2 source cards.",
        CHECKING[2],
        "PASS  Android emulator: the app asked the test question and showed an honest abstention (Sin respuesta segura).",
        "Result: the smoke test passed on Desktop and the Android emulator.",
    ]
    repo = s.harness.env.ctx.repo_root
    desktop, devices, boot_prop, install, instrument = s.runner.calls
    assert desktop["argv"] == [
        str(repo / "gradlew"), "--console=plain", "--quiet", ":shared:runDesktopLocalSmoke",
        "-PmanijeroSmokeExpected=http://127.0.0.1:8000",
        "-PmanijeroSmokeResult={}".format(s.dir / "desktop-result.txt"),
    ]
    assert desktop["timeout"] == 15 * 60 and desktop["log"] == s.dir / "desktop.log"
    assert devices["argv"] == ["/sdk/platform-tools/adb", "devices"]
    assert boot_prop["argv"] == ["/sdk/platform-tools/adb", "-s", "emulator-5554", "shell", "getprop", "sys.boot_completed"]
    assert install["argv"] == [str(repo / "gradlew"), "--console=plain", "--quiet", ":androidApp:installDebug", ":androidApp:installDebugAndroidTest"]
    assert install["env"] == {"PATH": "/bin", "ANDROID_SERIAL": "emulator-5554"} and install["timeout"] == 15 * 60
    assert instrument["argv"] == [
        "/sdk/platform-tools/adb", "-s", "emulator-5554", "shell", "am", "instrument", "-w", "-r",
        "-e", "class", "com.jamarglex.manijero.smoke.AndroidLocalSmokeTest",
        "-e", "expectedAddress", "http://10.0.2.2:8000",
        "com.jamarglex.manijero.test/androidx.test.runner.AndroidJUnitRunner",
    ]
    assert instrument["timeout"] == 5 * 60 and instrument["log"] == s.dir / "android.log"
    assert all("connectedAndroidTest" not in " ".join(argv) and "uninstall" not in argv for argv in s.runner.argvs())
    assert sorted(path.name for path in s.dir.iterdir()) == [".lock", "desktop-result.txt"]


def test_a_custom_service_port_sets_both_expected_addresses(s: Smoke) -> None:
    current = s.harness.record()
    assert current is not None
    svc.write_record(s.harness.record_file, dataclasses.replace(current, port=8765))
    s.harness.processes.table[40_000]["cmd"] = s.harness.processes.table[40_000]["cmd"].replace("8000", "8765")
    s.runner.desktop = DESKTOP_OK.replace(":8000", ":8765")
    s.runner.instrument = instrumentation_output(ANDROID_OK.replace(":8000", ":8765"))

    assert s.run() == 0, s.lines
    argvs = s.runner.argvs()
    assert "-PmanijeroSmokeExpected=http://127.0.0.1:8765" in argvs[0]
    assert "http://10.0.2.2:8765" in argvs[-1]


def test_a_single_source_card_reads_as_one_card(s: Smoke) -> None:
    s.runner.desktop = DESKTOP_OK.replace("sources=2", "sources=1")
    assert s.run() == 0
    assert "an answer with 1 source card." in s.lines[2]


# --- 2. A prerequisite is missing: nothing builds, installs, or starts ----------------------


def _stop_service(s: Smoke) -> None:
    s.harness.processes.table[40_000]["alive"] = False


@pytest.mark.parametrize(
    "arrange, expected_lines, fix",
    [
        (lambda s: s.harness.env.paths.settings.unlink(), [svc.MSG_NOT_SET_UP], "Run ./scripts/init.sh --local-rag-setup."),
        (lambda s: svc.remove_record(s.harness.record_file), ["The local answer service is not running."],
         "Start it with ./scripts/init.sh --local-rag-start, then run this command again."),
        (_stop_service, [svc.MSG_STALE, "The local answer service is not running."],
         "Start it with ./scripts/init.sh --local-rag-start, then run this command again."),
        (lambda s: setattr(s.harness.env.ollama, "running", False), ["PROBLEM  Drafting: Ollama is not running."], "Do the step shown above."),
        (lambda s: s.harness.write_record(40_000), ["PROBLEM  Search: a newer knowledge release was published"], "Do the step shown above."),
        (lambda s: setattr(s.harness.probe, "ready_answer", svc.UNAVAILABLE), ["PROBLEM  Answers: the service runs but cannot answer"], "Do the step shown above."),
        (lambda s: setattr(s.tools, "java", False), ["Java was not found on this computer."],
         "Install Temurin 21 from https://adoptium.net, then run this command again."),
        (lambda s: _hold(s.dir / ".lock"), ["Another smoke test is running in another Terminal window."],
         "Wait for it to finish, then run this command again."),
    ],
    ids=["no-settings", "not-running", "stale-record", "ollama-closed", "newer-release", "ready-unavailable", "no-java", "lock-held"],
)
def test_a_missing_prerequisite_stops_before_any_build(s: Smoke, arrange, expected_lines: List[str], fix: str) -> None:
    held = arrange(s)
    try:
        code = s.run()
    finally:
        if isinstance(held, int):
            os.close(held)

    assert code == 1
    assert s.lines[0] == CHECKING[0]
    assert len(s.lines) == len(expected_lines) + 2, s.lines
    for line, expected in zip(s.lines[1:-1], expected_lines):
        assert line.startswith(expected), (line, expected)
    assert s.lines[-1] == "Result: the smoke test did not run. " + fix
    assert s.runner.calls == []
    assert "Traceback" not in "\n".join(s.lines)


def test_a_stale_record_is_cleared(s: Smoke) -> None:
    _stop_service(s)
    s.run()
    assert not s.harness.record_file.exists()
    assert s.harness.processes.signals == []


# --- 3. No emulator -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "arrange, text",
    [
        (lambda s: setattr(s.tools, "adb", None), "adb was not found. Install SDK Platform-Tools in Android Studio"),
        (lambda s: setattr(s.runner, "devices", "List of devices attached\n\n"), "no Android emulator is running. Start one with ./scripts/init.sh --android-run or Android Studio's Device Manager"),
        (lambda s: setattr(s.runner, "devices", "List of devices attached\nR58M123ABC\tdevice\n"), "no Android emulator is running."),
        (lambda s: setattr(s.runner, "devices", "List of devices attached\nemulator-5554\toffline\n"), "the Android emulator is still starting. Wait for its home screen"),
        (lambda s: s.runner.boot.update({"emulator-5554": ""}), "the Android emulator is still starting."),
    ],
    ids=["no-adb", "no-emulator", "only-physical-device", "offline", "still-booting"],
)
def test_no_ready_emulator_keeps_desktop_and_fails_android_with_one_fix(s: Smoke, arrange, text: str) -> None:
    arrange(s)

    assert s.run() == 1
    assert s.lines[2].startswith("PASS  Desktop:")
    assert s.lines[4].startswith("FAIL  Android emulator: " + text), s.lines[4]
    assert s.lines[4].endswith("then run this command again.")
    assert s.lines[-1] == "Result: the smoke test failed on the Android emulator. Do the first step shown above."
    joined = [" ".join(argv) for argv in s.runner.argvs()]
    assert not any("install" in argv or "instrument" in argv for argv in joined)
    assert not any("R58M123ABC" in argv for argv in joined)


def test_the_first_booted_emulator_is_used(s: Smoke) -> None:
    s.runner.devices = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\tdevice\n"
    s.runner.boot = {"emulator-5554": "0", "emulator-5556": "1"}

    assert s.run() == 0, s.lines
    install = next(call for call in s.runner.calls if ":androidApp:installDebug" in call["argv"])  # type: ignore[operator]
    assert install["env"]["ANDROID_SERIAL"] == "emulator-5556"  # type: ignore[index]


# --- 4 and 5. Each outcome maps to its line -------------------------------------------------


def _desktop_result(outcome: str, sources: int = 0, address: str = "default", url: str = "http://127.0.0.1:8000") -> str:
    return "MANIJERO_SMOKE_RESULT outcome={} sources={} address={} url={}\n".format(outcome, sources, address, url)


STATUS_STEP = "Run ./scripts/init.sh --local-rag-service-status and do its first step, then run this command again."
SEND_LOG = "Send build/local-smoke/desktop.log to a developer."


@pytest.mark.parametrize(
    "outcome, line",
    [
        ("answered_without_sources", "the app showed an answer without any source card. " + SEND_LOG),
        ("answered", "the app showed an answer without any source card. " + SEND_LOG),  # zero sources
        ("land_clarification", "the app asked to choose a land instead of answering the general test question. " + SEND_LOG),
        ("unreachable", "the app could not reach the local answer service at http://127.0.0.1:8000. " + STATUS_STEP),
        ("service_error", "the local answer service answered the app with an error. " + STATUS_STEP),
        ("not_ready", "the app reached the service at http://127.0.0.1:8000, but it cannot answer questions right now. " + STATUS_STEP),
        ("ready_unknown", "the app reached the service at http://127.0.0.1:8000, but could not tell whether it can answer. " + STATUS_STEP),
        ("not_manijero", "the program at http://127.0.0.1:8000 is not the Manijero answer service. " + STATUS_STEP),
        ("no_answer", "the app showed no reply within 90 seconds. " + STATUS_STEP),
        ("error", "the check could not run. Details are in build/local-smoke/desktop.log; send that file to a developer."),
    ],
)
def test_each_failing_outcome_has_one_plain_line(s: Smoke, outcome: str, line: str) -> None:
    result = smoke.parse_result(_desktop_result(outcome))
    assert result is not None
    shown = smoke.platform_line(smoke.DESKTOP, result, "http://127.0.0.1:8000", "http://127.0.0.1:8000", "build/local-smoke/desktop.log")
    assert shown == "FAIL  Desktop: " + line


def test_a_failing_desktop_result_still_checks_android(s: Smoke) -> None:
    s.runner.desktop = _desktop_result("no_answer")

    assert s.run() == 1
    assert s.lines[2].startswith("FAIL  Desktop: the app showed no reply")
    assert s.lines[4].startswith("PASS  Android emulator:")
    assert s.lines[-1] == "Result: the smoke test failed on Desktop. Do the first step shown above."


def test_both_failing_are_named(s: Smoke) -> None:
    s.runner.desktop = _desktop_result("service_error")
    s.runner.instrument = instrumentation_output(ANDROID_OK.replace("abstained", "unreachable"))

    assert s.run() == 1
    assert s.lines[-1] == "Result: the smoke test failed on Desktop and the Android emulator. Do the first step shown above."


@pytest.mark.parametrize(
    "result, environ, fix",
    [
        (_desktop_result("other_address", address="saved", url="http://192.168.1.20:8000"), {},
         "press Usar la dirección predeterminada"),
        (_desktop_result("other_address", address="default", url="http://127.0.0.1:9000"), {},
         "enter http://127.0.0.1:8000 and press Comprobar"),
        (_desktop_result("other_address", address="saved", url="http://192.168.1.20:8000"), {"MANIJERO_ASK_BASE_URL": "http://127.0.0.1:9000"},
         "enter http://127.0.0.1:8000 and press Comprobar"),
    ],
    ids=["saved-default-matches", "default-differs", "saved-default-differs"],
)
def test_another_address_names_the_right_conexion_fix(s: Smoke, result: str, environ: Dict[str, str], fix: str) -> None:
    s.runner.desktop = result
    s.environ.update(environ)

    assert s.run() == 1
    url = smoke.parse_result(result).url  # type: ignore[union-attr]
    assert s.lines[2] == (
        "FAIL  Desktop: the app uses {}, not http://127.0.0.1:8000. Open Ayuda > Herramientas de prueba > Conexión, "
        "{}, then run this command again.".format(url, fix)
    )


def test_the_android_default_comes_from_the_gradle_property_environment(s: Smoke) -> None:
    s.runner.instrument = instrumentation_output(
        "MANIJERO_SMOKE_RESULT outcome=other_address sources=0 address=saved url=http://192.168.1.20:8000"
    )
    s.environ["ORG_GRADLE_PROJECT_manijeroAskBaseUrl"] = "http://10.0.2.2:9000"

    assert s.run() == 1
    assert "enter http://10.0.2.2:8000 and press Comprobar, then run this command again." in s.lines[4]


# --- 6. A build, install, or run step fails ------------------------------------------------


COULD_NOT_RUN_DESKTOP = "FAIL  Desktop: the check could not run. Details are in {}; send that file to a developer."


@pytest.mark.parametrize(
    "desktop",
    [
        None,
        "",
        "garbage\n",
        DESKTOP_OK + " extra=1\n",
        DESKTOP_OK + "\n" + DESKTOP_OK + "\n",
        DESKTOP_OK.replace("answered", "excellent"),
        DESKTOP_OK.replace("sources=2", "sources=two"),
        DESKTOP_OK.replace("address=default", "address=other"),
        DESKTOP_OK.replace("url=http://127.0.0.1:8000", "url=ftp://x"),
        DESKTOP_OK.replace("MANIJERO_SMOKE_RESULT ", ""),
    ],
    ids=["missing", "empty", "garbage", "extra-field", "two-lines", "unknown-code", "bad-count", "bad-address", "bad-url", "no-prefix"],
)
def test_a_missing_or_malformed_desktop_result_could_not_run(s: Smoke, desktop: Optional[str]) -> None:
    s.runner.desktop = desktop

    assert s.run() == 1
    assert s.lines[2] == COULD_NOT_RUN_DESKTOP.format(s.dir / "desktop.log")


def test_the_result_file_is_shown_relative_to_the_repository(running: Harness) -> None:  # noqa: F811
    smoke_dir = running.env.ctx.repo_root / "build" / "local-smoke"
    assert smoke._shown(running.env.ctx, smoke_dir / "desktop.log") == "build/local-smoke/desktop.log"


@pytest.mark.parametrize(
    "arrange",
    [
        lambda s: setattr(s.runner, "fail", ":shared:runDesktopLocalSmoke"),
        lambda s: setattr(s.runner, "time_out", ":shared:runDesktopLocalSmoke"),
    ],
    ids=["gradle-exit-1", "gradle-timeout"],
)
def test_a_desktop_build_failure_could_not_run_even_with_a_result(s: Smoke, arrange) -> None:
    arrange(s)

    assert s.run() == 1
    assert s.lines[2] == COULD_NOT_RUN_DESKTOP.format(s.dir / "desktop.log")
    assert s.lines[4].startswith("PASS  Android emulator:")


COULD_NOT_RUN_ANDROID = (
    "FAIL  Android emulator: the check could not run. Details are in {}; send that file to a developer."
)


@pytest.mark.parametrize(
    "arrange",
    [
        lambda s: setattr(s.runner, "fail", ":androidApp:installDebug"),
        lambda s: setattr(s.runner, "time_out", ":androidApp:installDebug"),
        lambda s: setattr(s.runner, "time_out", "instrument"),
        lambda s: setattr(s.runner, "fail", "instrument"),
        lambda s: setattr(s.runner, "fail", "devices"),
        lambda s: setattr(s.runner, "instrument", instrumentation_output(None, "INSTRUMENTATION_FAILED: com.jamarglex.manijero.test\r\n")),
        lambda s: setattr(s.runner, "instrument", instrumentation_output(ANDROID_OK + " extra=1")),
        lambda s: setattr(s.runner, "instrument", instrumentation_output(ANDROID_OK, "INSTRUMENTATION_STATUS: manijero_smoke_result={}\r\n".format(ANDROID_OK))),
    ],
    ids=["install-exit-1", "install-timeout", "instrument-timeout", "instrument-exit-1", "adb-devices-fails", "no-status", "extra-field", "two-statuses"],
)
def test_an_android_install_or_run_failure_could_not_run(s: Smoke, arrange) -> None:
    arrange(s)

    assert s.run() == 1
    assert s.lines[4] == COULD_NOT_RUN_ANDROID.format(s.dir / "android.log")
    assert s.lines[-1] == "Result: the smoke test failed on the Android emulator. Do the first step shown above."


def test_a_failed_assertion_with_a_well_formed_status_reports_the_outcome(s: Smoke) -> None:
    failing = ANDROID_OK.replace("abstained", "land_clarification")
    s.runner.instrument = instrumentation_output(failing).replace("OK (1 test)", "FAILURES!!! Tests run: 1,  Failures: 1")

    assert s.run() == 1
    assert s.lines[4].startswith("FAIL  Android emulator: the app asked to choose a land")


# --- 7. Interruption ----------------------------------------------------------------------


@pytest.mark.parametrize("step", [":shared:runDesktopLocalSmoke", ":androidApp:installDebug", "instrument"])
def test_ctrl_c_ends_the_step_and_says_it_stopped(s: Smoke, step: str) -> None:
    s.runner.interrupt = step

    assert s.run() == 1
    assert s.lines[-3:] == ["", "The smoke test was stopped.", "Result: the smoke test was stopped before it finished."]
    lock = s.dir / ".lock"
    handle = os.open(lock, os.O_RDWR)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)  # released
    finally:
        os.close(handle)


# --- 8. Privacy ---------------------------------------------------------------------------


def test_no_output_or_written_file_carries_the_question(s: Smoke) -> None:
    s.run()
    written = "\n".join(path.read_text(encoding="utf-8") for path in s.dir.iterdir() if path.is_file())
    for text in ("\n".join(s.lines), written, " ".join(" ".join(argv) for argv in s.runner.argvs())):
        assert QUESTION not in text
        assert "solicitud" not in text.lower()


def test_the_result_protocol_parses_only_one_exact_line() -> None:
    assert smoke.parse_result(DESKTOP_OK + "\n") == smoke.SmokeResult("answered", 2, "default", "http://127.0.0.1:8000")
    assert smoke.parse_result("MANIJERO_SMOKE_RESULT outcome=error sources=0 address=saved url=invalid") is not None
    assert smoke.parse_result(DESKTOP_OK.replace("url=http://127.0.0.1:8000", "url=http://a b")) is None
    assert smoke.parse_instrumentation(instrumentation_output(ANDROID_OK)) == smoke.SmokeResult("abstained", 0, "default", "http://10.0.2.2:8000")
    assert set(smoke.CODES) >= set(smoke.PASSING) and len(smoke.CODES) == len(set(smoke.CODES)) == 12


# --- Real runner (local child processes only, no network) ----------------------------------


def test_the_subprocess_runner_logs_output_and_ends_a_step_that_runs_too_long(tmp_path: Path) -> None:
    runner = smoke.SubprocessRunner()
    log = tmp_path / "step.log"

    done = runner.run([sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"], tmp_path, log, 30)
    assert done.ok and done.output == "out\n"

    slow = runner.run([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, log, 0.5)
    assert slow.timed_out and slow.returncode is None and not slow.ok

    failed = runner.run([sys.executable, "-c", "raise SystemExit(3)"], tmp_path, log, 30, env={"PATH": os.environ["PATH"]})
    assert failed.returncode == 3 and not failed.ok

    text = log.read_text(encoding="utf-8")
    assert "out" in text and "err" in text and "exit 0" in text and "timed out after 0 seconds" in text and "exit 3" in text
    assert [path.name for path in tmp_path.iterdir()] == ["step.log"]  # the capture file is gone


def test_the_system_tools_find_java_and_adb_only_where_they_are(tmp_path: Path) -> None:
    sdk = tmp_path / "sdk"
    adb = sdk / "platform-tools" / "adb"
    adb.parent.mkdir(parents=True)
    adb.write_text("#!/bin/sh\n", encoding="utf-8")
    adb.chmod(0o755)
    java_home = tmp_path / "jdk"
    (java_home / "bin").mkdir(parents=True)
    (java_home / "bin" / "java").write_text("#!/bin/sh\n", encoding="utf-8")
    (java_home / "bin" / "java").chmod(0o755)

    assert smoke.SystemTools({"ANDROID_HOME": str(sdk)}).adb_path() == str(adb)
    assert smoke.SystemTools({"ANDROID_SDK_ROOT": str(sdk)}).adb_path() == str(adb)
    assert smoke.SystemTools({"ANDROID_HOME": str(tmp_path / "none")}).adb_path() is None
    assert smoke.SystemTools({"JAVA_HOME": str(java_home), "PATH": ""}).java_available()
    assert not smoke.SystemTools({"PATH": str(tmp_path / "empty")}).java_available()


def test_the_smoke_java_check_rejects_a_placeholder_and_a_java_only_on_path(tmp_path: Path) -> None:
    stub_home = tmp_path / "stub"
    (stub_home / "bin").mkdir(parents=True)
    stub = stub_home / "bin" / "java"
    stub.write_text("#!/bin/sh\necho 'Unable to locate a Java Runtime.' >&2\nexit 1\n", encoding="utf-8")
    stub.chmod(0o755)

    assert not smoke.SystemTools({"JAVA_HOME": str(stub_home)}).java_available()
    # A working java only on PATH: init.sh would have exported its JAVA_HOME, so without one it is absent.
    working = tmp_path / "path-bin" / "java"
    working.parent.mkdir()
    working.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    working.chmod(0o755)
    assert not smoke.SystemTools({"PATH": str(working.parent)}).java_available()
