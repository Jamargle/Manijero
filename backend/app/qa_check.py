"""Check the QA Desktop app against the live QA service, end to end, with one command.

Operator-only and stdlib-only; the answer service never imports this module. The owner runs it as
``./scripts/init.sh --qa-check``. :func:`run_qa_check` works in this order and stops at the first gap:

1. take the lock ``<repo>/build/qa-check/.lock`` (one QA check at a time);
2. check the prerequisites without building anything: the QA address (``qa-address.local``), the
   QA access key file (only its existence; this module never opens it), Java, and the Gradle wrapper;
3. probe ``<address>/health`` over https; an unreachable QA fails here, in seconds;
4. run ``:shared:runDesktopQaCheck``, which renders the QA Desktop app offscreen, asks the fixed
   synthetic question, and presses ``Útil`` once; it writes one result line.

Each step ends in one ``PASS`` or ``FAIL`` line and the run in one ``Result:`` line. Output, the
result file, and the log carry only outcome codes, a source count, and the address, never question,
answer, passage, or key text. Every external effect goes through the injected :class:`QaCheckPorts`,
so tests use fakes.
"""

from __future__ import annotations

import fcntl
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping, Optional, Sequence

from app import environment_profiles as profiles
from app import local_smoke as smoke
from app import qa_deployment as qa

CHECK_COMMAND = "./scripts/init.sh --qa-check"
CHECK_DIR = Path("build") / "qa-check"
LOCK_NAME = ".lock"
RESULT_NAME = "desktop-result.txt"
LOG_NAME = "desktop.log"
PLACEHOLDER_ADDRESS = "https://qa.manijero.invalid"
GRADLE_TASK = ":shared:runDesktopQaCheck"
BUILD_TIMEOUT_SECONDS = smoke.BUILD_TIMEOUT_SECONDS

RESULT_PREFIX = "MANIJERO_QA_CHECK_RESULT"
OUTCOMES = smoke.CODES + ("not_qa_build", "no_access_key")
FEEDBACK_CODES = ("sent", "failed", "no_reply", "not_shown", "not_tried")
_RESULT = re.compile(
    r"{} outcome=({}) sources=([0-9]{{1,4}}) feedback=({}) address=(default|saved) url=(invalid|https?://[!-~]{{1,512}})".format(
        RESULT_PREFIX, "|".join(OUTCOMES), "|".join(FEEDBACK_CODES)
    )
)

FIX_DEPLOY = "Deploy QA with {}, then run this command again.".format("./scripts/init.sh --qa-deploy")
FIX_QA_SETUP = "Run {}, then run this command again.".format("./scripts/init.sh --qa-settings-setup")
STEP_STATUS = "Run {} and do its first step, then run this command again.".format(qa.STATUS_COMMAND)
MSG_BUSY = "Another QA check is running in another Terminal window."
MSG_NO_ADDRESS = "No QA address is saved on this computer."
MSG_PLACEHOLDER = "The saved QA address is still a placeholder, so QA is not deployed yet."
MSG_NOT_HTTPS = "The saved QA address is not an https:// address."
MSG_NO_KEY = "The QA access key was not found on this computer."

STOPPED_LINE = "The QA check was stopped."
STOPPED_RESULT = "Result: the QA check was stopped before it finished."
NOT_RUN_RESULT = "Result: the QA check did not run."
PASSED_RESULT = (
    "Result: the QA check passed: QA is reachable, answers with sources, and accepts feedback from the Desktop app."
)

SERVICE = "Service"
ANSWER = "Answer"
FEEDBACK = "Feedback"


# --- Ports --------------------------------------------------------------------------------


@dataclass
class QaCheckPorts:
    runner: smoke.Runner
    tools: smoke.Tools
    probe: Callable[[str], bool]
    out: Callable[[str], None]
    address_file: Path
    qa_home: Path


# --- Result protocol ----------------------------------------------------------------------


@dataclass(frozen=True)
class QaCheckResult:
    outcome: str
    sources: int
    feedback: str
    address: str  # "default" or "saved"
    url: str


def parse_result(text: str) -> Optional[QaCheckResult]:
    """The one well-formed result line, or ``None`` (missing, malformed, extra fields, or several)."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        return None
    match = _RESULT.fullmatch(lines[0])
    if match is None:
        return None
    outcome, sources, feedback, address, url = match.groups()
    return QaCheckResult(outcome, int(sources), feedback, address, url)


# --- Lines --------------------------------------------------------------------------------


def could_not_run(log_shown: str) -> str:
    return smoke.could_not_run(ANSWER, log_shown)


def answer_line(result: QaCheckResult, expected: str, log_shown: str) -> str:
    """The one ``PASS`` or ``FAIL`` line of the answer step for a well-formed result."""

    code, url = result.outcome, result.url
    if code == "answered" and result.sources > 0:
        cards = "card" if result.sources == 1 else "cards"
        return "PASS  {}: the QA app asked the test question and showed an answer with {} source {}.".format(
            ANSWER, result.sources, cards
        )
    send_log = "Send {} to a developer.".format(log_shown)
    if code == "other_address" and result.address == "saved":
        return (
            "FAIL  {}: the QA app uses the saved address {}, not {}. In ./scripts/init.sh --desktop-qa open "
            "Ayuda > Herramientas de prueba > Conexión, press Usar la dirección predeterminada, then run "
            "this command again.".format(ANSWER, url, expected)
        )
    texts = {
        "abstained": "the QA app showed an honest abstention (Sin respuesta segura) instead of an answer with sources. "
        + send_log,
        "answered": "the QA app showed an answer without any source card. " + send_log,
        "answered_without_sources": "the QA app showed an answer without any source card. " + send_log,
        "land_clarification": "the QA app asked to choose a land instead of answering the general test question. "
        + send_log,
        "unreachable": "the QA app could not reach the QA service at {}. {}".format(expected, STEP_STATUS),
        "service_error": "the QA service answered the app with an error. " + STEP_STATUS,
        "not_ready": "the QA app reached {}, but it cannot answer questions right now. {}".format(expected, STEP_STATUS),
        "ready_unknown": "the QA app reached {}, but could not tell whether it can answer. {}".format(expected, STEP_STATUS),
        "not_manijero": "the program at {} is not the Manijero answer service. {}".format(expected, STEP_STATUS),
        "no_answer": "the QA app showed no reply within 90 seconds. " + STEP_STATUS,
        "not_qa_build": "the check app was not built as the QA app, so no question was asked. " + send_log,
        "no_access_key": "the QA access key did not reach the check app, so no question was asked. " + FIX_QA_SETUP,
    }
    if code not in texts:  # "error", "other_address" on the default address
        return could_not_run(log_shown)
    return "FAIL  {}: {}".format(ANSWER, texts[code])


def feedback_line(result: QaCheckResult, log_shown: str) -> Optional[str]:
    """The feedback step line; ``None`` when no finished reply was shown, so no rating was tried."""

    code = result.feedback
    if code == "not_tried":
        return None
    if code == "sent":
        return "PASS  {}: QA accepted the app's Útil rating.".format(FEEDBACK)
    texts = {
        "failed": "QA did not accept the app's Útil rating. " + STEP_STATUS,
        "no_reply": "QA did not confirm the app's Útil rating within 30 seconds. " + STEP_STATUS,
        "not_shown": "the QA app showed no rating buttons. Send {} to a developer.".format(log_shown),
    }
    return "FAIL  {}: {}".format(FEEDBACK, texts[code])


def final_result(failed_step: Optional[str]) -> str:
    if failed_step is None:
        return PASSED_RESULT
    return "Result: the QA check failed at the {} step. Do the first step shown above.".format(failed_step)


# --- Command ------------------------------------------------------------------------------


class _NotRun(Exception):
    """A prerequisite gap: nothing was built or started."""

    def __init__(self, line: str, fix: str) -> None:
        super().__init__(fix)
        self.line = line
        self.fix = fix


@contextmanager
def check_lock(path: Path) -> Iterator[None]:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise _NotRun(MSG_BUSY, smoke.FIX_BUSY) from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        os.close(handle)


def default_ports(repo_root: Path, environ: Mapping[str, str], out: Callable[[str], None]) -> QaCheckPorts:
    configured = (environ.get(qa.ADDRESS_FILE_ENV) or "").strip()
    return QaCheckPorts(
        runner=smoke.SubprocessRunner(),
        tools=smoke.SystemTools(environ),
        probe=qa.system_public_probe,
        out=out,
        address_file=Path(configured).expanduser() if configured else repo_root / "qa-address.local",
        qa_home=profiles.qa_home(),
    )


def run_qa_check(repo_root: Path, ports: QaCheckPorts, check_dir: Optional[Path] = None) -> int:
    """Check the prerequisites, the service, then the Desktop app; ``0`` only when every step passes."""

    out = ports.out
    directory = Path(check_dir) if check_dir is not None else Path(repo_root) / CHECK_DIR
    try:
        with check_lock(directory / LOCK_NAME):
            address = _check_prerequisites(repo_root, ports)
            gradlew = Path(repo_root) / "gradlew"
            out("Checking the QA service at {}...".format(address))
            if not ports.probe(address):
                out("FAIL  {}: QA does not answer at {}.".format(SERVICE, address))
                out(
                    "Result: the QA check failed at the service step. Run {} and do its first step, "
                    "then run this command again.".format(qa.STATUS_COMMAND)
                )
                return 1
            out("PASS  {}: QA answers at {}.".format(SERVICE, address))
            failed = _run_desktop(repo_root, ports, directory, gradlew, address)
    except _NotRun as stop:
        out(stop.line)
        out("{} {}".format(NOT_RUN_RESULT, stop.fix))
        return 1
    except KeyboardInterrupt:
        out("")
        out(STOPPED_LINE)
        out(STOPPED_RESULT)
        return 1
    out(final_result(failed))
    return 0 if failed is None else 1


def _read_address(path: Path) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text.rstrip("/") or None


def _check_prerequisites(repo_root: Path, ports: QaCheckPorts) -> str:
    address = _read_address(ports.address_file)
    if address is None:
        raise _NotRun(MSG_NO_ADDRESS, FIX_DEPLOY)
    if address.lower() == PLACEHOLDER_ADDRESS:
        raise _NotRun(MSG_PLACEHOLDER, FIX_DEPLOY)
    if not address.lower().startswith("https://") or len(address) <= len("https://") or " " in address:
        raise _NotRun(MSG_NOT_HTTPS, FIX_DEPLOY)
    key = profiles.credential_paths(ports.qa_home, profiles.QA_CLIENT_ID).token
    if not key.is_file():  # existence only: the key file is never opened here
        raise _NotRun(MSG_NO_KEY, FIX_QA_SETUP)
    if not ports.tools.java_available():
        raise _NotRun(smoke.MSG_NO_JAVA, smoke.FIX_JAVA)
    if not os.access(Path(repo_root) / "gradlew", os.X_OK):
        raise _NotRun(smoke.MSG_NO_WRAPPER, smoke.FIX_WRAPPER)
    return address


def _shown(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _run_desktop(repo_root: Path, ports: QaCheckPorts, directory: Path, gradlew: Path, address: str) -> Optional[str]:
    """Run the Desktop check, print its lines, and return the first failing step name (or ``None``)."""

    out = ports.out
    log = smoke._fresh(directory / LOG_NAME)
    result_file = smoke._fresh(directory / RESULT_NAME)
    shown = _shown(Path(repo_root), log)
    out("Checking the QA Desktop app (the first run can take a few minutes)...")
    run = ports.runner.run(
        [
            str(gradlew), "--console=plain", "--quiet", "-PmanijeroEnvironment=qa", GRADLE_TASK,
            "-PmanijeroSmokeExpected={}".format(address),
            "-PmanijeroSmokeResult={}".format(result_file),
        ],
        cwd=Path(repo_root),
        log_path=log,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    try:
        text = result_file.read_text(encoding="utf-8") if run.ok else ""
    except (OSError, UnicodeDecodeError):
        text = ""
    result = parse_result(text)
    if result is None:
        out(could_not_run(shown))
        return "answer"
    answer = answer_line(result, address, shown)
    out(answer)
    feedback = feedback_line(result, shown)
    if feedback is not None:
        out(feedback)
    if not answer.startswith("PASS"):
        return "answer"
    if feedback is None or not feedback.startswith("PASS"):
        return "feedback"
    return None
