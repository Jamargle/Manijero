"""QA Telegram alerts: classification, the alert state machine, Telegram handling, and privacy.

Everything is in-process and offline: fake Docker, fake loopback probes, fake Tailscale, a fake
clock, a fake Telegram transport, and a fake Telegram server on a loopback test socket. Only fake
tokens appear; no real launchctl, Docker, Telegram, or network is touched.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app import environment_profiles as profiles
from app import local_container as lc
from app import local_rag_bootstrap as bootstrap
from app import local_rag_service as service
from app import qa_alerts as alerts
from app import qa_deployment as qa

FAKE_TOKEN = "123456789:" + "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"[:30]
CHAT_ID = 4242424242
ADDRESS = "https://secretname-mac.tail1234.ts.net"
START = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)


# --- Fakes ----------------------------------------------------------------------------------


class FakeDocker:
    def __init__(self) -> None:
        self.installed = True
        self.open = True
        self.container: Optional[Dict[str, Any]] = None
        self.calls: List[List[str]] = []

    def run_container(self, running: bool = True) -> None:
        self.container = {
            "running": running,
            "labels": {lc.MANAGED_LABEL: "1", qa.LABEL_ENVIRONMENT: profiles.QA},
        }

    def present(self) -> bool:
        return self.installed

    def run(self, args: Any, timeout: float) -> bootstrap.CommandResult:
        argv = [str(part) for part in args]
        self.calls.append(argv)
        if argv[0] == "info":
            return bootstrap.CommandResult(0, "27.3.1\n") if self.open else bootstrap.CommandResult(1, "", "no daemon")
        if argv[:2] == ["container", "inspect"] and self.container is not None:
            document = [{
                "Config": {"Labels": self.container["labels"]},
                "State": {"Running": self.container["running"], "StartedAt": "2026-11-07T09:00:00Z"},
                "NetworkSettings": {"Ports": {}},
            }]
            return bootstrap.CommandResult(0, json.dumps(document))
        return bootstrap.CommandResult(1, "", "Error: No such object")

    def start(self, args: Any, log_path: Path) -> Any:
        raise AssertionError("the alerts never start a long command")


class FakeProbe:
    def __init__(self) -> None:
        self.health_value = service.SERVICE_NAME
        self.ready_value = service.READY

    def health(self, port: int) -> str:
        return self.health_value

    def ready(self, port: int) -> str:
        return self.ready_value


class FakeTailscale:
    def __init__(self) -> None:
        self.funnel_ours = False

    def present(self) -> bool:
        return True

    def run(self, args: Any, timeout: float) -> bootstrap.CommandResult:
        name = "mac.tail1234.ts.net"
        if list(args)[:1] == ["status"]:
            document = {"BackendState": "Running", "Self": {"DNSName": name + ".", "CapMap": {"https": [], "funnel": []}}}
            return bootstrap.CommandResult(0, json.dumps(document))
        key = name + ":443"
        document = {
            "TCP": {"443": {"HTTPS": True}},
            "Web": {key: {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8100"}}}},
            "AllowFunnel": {key: True},
        } if self.funnel_ours else {}
        return bootstrap.CommandResult(0, json.dumps(document))


class FakeTelegram:
    def __init__(self) -> None:
        self.sent: List[str] = []
        self.tokens: List[str] = []
        self.send_status = 200
        self.updates: List[Dict[str, Any]] = []
        self.token_ok = True

    def call(self, token: str, method: str, payload: Any) -> alerts.TelegramReply:
        self.tokens.append(token)
        if method == "getMe":
            return alerts.TelegramReply(200 if self.token_ok else 401, {"ok": self.token_ok})
        if method == "getUpdates":
            return alerts.TelegramReply(200, {"ok": True, "result": self.updates})
        assert method == "sendMessage"
        assert payload["chat_id"] == CHAT_ID
        if self.send_status != 200:
            return alerts.TelegramReply(self.send_status, None)
        self.sent.append(payload["text"])
        return alerts.TelegramReply(200, {"ok": True})


class FakeClock:
    def __init__(self) -> None:
        self.moment = START

    def now(self) -> datetime:
        return self.moment

    def advance(self, **delta: float) -> None:
        self.moment += timedelta(**delta)


class FakeLaunchctl:
    def __init__(self) -> None:
        self.loaded = False
        self.calls: List[str] = []
        self.installed = True
        self.fail_bootstrap = False

    def present(self) -> bool:
        return self.installed

    def is_loaded(self) -> bool:
        return self.loaded

    def bootstrap(self, plist: Path) -> bool:
        self.calls.append("bootstrap")
        if self.fail_bootstrap:
            return False
        self.loaded = True
        return True

    def bootout(self) -> bool:
        self.calls.append("bootout")
        self.loaded = False
        return True


class FakePrompter:
    def __init__(self, secret: Optional[str] = FAKE_TOKEN, answers: Optional[List[Optional[str]]] = None) -> None:
        self.secret = secret
        self.answers = list(answers if answers is not None else ["", "", ""])
        self.asked: List[str] = []

    def ask(self, question: str) -> Optional[str]:
        self.asked.append(question)
        return self.answers.pop(0) if self.answers else None

    def ask_secret(self, question: str) -> Optional[str]:
        self.asked.append(question)
        return self.secret


class Harness:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MANIJERO_LOCAL_HOME", str(tmp_path / "local"))
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.root = tmp_path
        self.docker = FakeDocker()
        self.docker.run_container()
        self.probe = FakeProbe()
        self.tailscale = FakeTailscale()
        self.telegram = FakeTelegram()
        self.clock = FakeClock()
        self.launchctl = FakeLaunchctl()
        self.prompter = FakePrompter()
        self.counters: Optional[Tuple[int, int]] = (0, 0)
        self.public_ok = True
        self.metric_tokens: List[str] = []
        self.public_calls: List[str] = []
        self.output: List[str] = []
        self.qa_home = tmp_path / "qa"
        self.qa_home.mkdir()
        (self.qa_home / "settings.env").write_text(profiles.render_template(self.qa_home), encoding="utf-8")
        profiles.make_new_credentials(self.qa_home, profiles.QA_CLIENT_ID)
        profiles.write_public_url(self.qa_home, ADDRESS)
        self.repo = tmp_path / "repo"
        python = self.repo / "backend" / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text("#!/bin/sh\n", encoding="utf-8")
        python.chmod(0o755)
        self.home = tmp_path / "alerts"
        self.ports = alerts.AlertPorts(
            home=self.home, qa_home=self.qa_home, repo_root=self.repo, agents_dir=tmp_path / "LaunchAgents",
            port=8100, docker=self.docker, tailscale=self.tailscale, probe=self.probe, metrics=self._metrics,
            public=self._public, telegram=self.telegram, launchctl=self.launchctl, clock=self.clock,
            prompter=self.prompter, tty=True, out=self.output.append,
        )

    def _metrics(self, port: int, token: str) -> Optional[Tuple[int, int]]:
        self.metric_tokens.append(token)
        return self.counters

    def _public(self, address: str) -> bool:
        self.public_calls.append(address)
        return self.public_ok

    def store_credentials(self) -> None:
        alerts.write_credentials(self.home, alerts.Credentials(FAKE_TOKEN, CHAT_ID))

    def check(self, minutes: float = 5) -> None:
        self.clock.advance(minutes=minutes)
        assert alerts.run_check(self.ports) == 0

    def state(self) -> alerts.State:
        return alerts.load_state(self.home)


@pytest.fixture()
def h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    harness = Harness(tmp_path, monkeypatch)
    harness.store_credentials()
    return harness


def hhmm(moment: datetime) -> str:
    return alerts.local_time(alerts.stamp(moment))


# --- Classification -------------------------------------------------------------------------


def classify(facts: alerts.Facts, percent: Optional[float] = None) -> Tuple[Optional[str], bool]:
    return alerts.classify(facts, percent, alerts.ErrorThreshold(900.0, 10.0))


@pytest.mark.parametrize(
    "facts, expected",
    [
        (alerts.Facts(docker_ready=False), ("down_docker", False)),
        (alerts.Facts(container="stopped"), ("down", False)),
        (alerts.Facts(container="running", health_ok=False), ("down", False)),
        (alerts.Facts(container="none", health_ok=False, funnel_ours=True), ("down", False)),
        (alerts.Facts(container="none", health_ok=False, funnel_ours=False), (None, True)),
        (alerts.Facts(container="running", health_ok=True, ready_ok=False), ("not_ready", False)),
        (alerts.Facts(container="running", health_ok=True, ready_ok=True, public_ok=False), ("unreachable", False)),
        (alerts.Facts(container="running", health_ok=True, ready_ok=True, public_ok=True), (None, False)),
        (alerts.Facts(container="running", health_ok=True, ready_ok=True, public_ok=None), (None, False)),
    ],
)
def test_each_kind_is_classified_from_the_facts(facts: alerts.Facts, expected: Tuple[Optional[str], bool]) -> None:
    assert classify(facts) == expected


def test_down_beats_not_ready_beats_erroring_beats_unreachable() -> None:
    facts = alerts.Facts(container="running", health_ok=True, ready_ok=True, public_ok=False)
    assert classify(facts, 50.0) == ("erroring", False)
    assert classify(alerts.Facts(container="running", health_ok=True, ready_ok=False, public_ok=False), 50.0)[0] == "not_ready"
    assert classify(alerts.Facts(container="stopped", health_ok=True, ready_ok=False), 50.0)[0] == "down"


def test_erroring_needs_the_problem_level_and_is_not_judged_without_a_share() -> None:
    facts = alerts.Facts(container="running", health_ok=True, ready_ok=True, public_ok=True)
    assert classify(facts, 9.9) == (None, False)
    assert classify(facts, 10.0) == ("erroring", False)
    assert classify(facts, None) == (None, False)
    assert alerts.classify(facts, 99.0, None) == (None, False)


def test_the_error_share_needs_a_full_window_ignores_zero_questions_and_resets_on_a_restart() -> None:
    window = 900.0
    samples: List[alerts.Sample] = []
    for minute, counters in [(0, (100, 0)), (5, (120, 5)), (10, (140, 10))]:
        samples = alerts.update_samples(samples, counters, minute * 60.0, window)
        assert alerts.error_percent(samples, window) is None  # less than a full window
    samples = alerts.update_samples(samples, (160, 20), 900.0, window)
    assert alerts.error_percent(samples, window) == pytest.approx(20.0 * 100 / 60)
    quiet: List[alerts.Sample] = []
    for minute in (0, 5, 10, 15):
        quiet = alerts.update_samples(quiet, (160, 20), minute * 60.0, window)
    assert alerts.error_percent(quiet, window) is None  # no /ask in the window
    restarted = alerts.update_samples(samples, (3, 0), 1200.0, window)
    assert restarted == [[1200.0, 3.0, 0.0]] and alerts.error_percent(restarted, window) is None


def test_the_threshold_is_read_from_the_dashboard_file(tmp_path: Path) -> None:
    real = alerts.load_threshold()
    document = json.loads(alerts.THRESHOLDS_FILE.read_text(encoding="utf-8"))["errors"]
    assert real is not None
    assert real.problem_percent == float(document["problem_percent"]) and real.window_seconds == 900.0
    patched = tmp_path / "thresholds.json"
    patched.write_text(json.dumps({"errors": {"window": "1h", "problem_percent": 25}}), encoding="utf-8")
    changed = alerts.load_threshold(patched)
    assert changed is not None and changed.window_seconds == 3600.0 and changed.problem_percent == 25.0 and changed.minutes == 60
    patched.write_text("{", encoding="utf-8")
    assert alerts.load_threshold(patched) is None


def test_metrics_text_is_reduced_to_ask_counters() -> None:
    text = "\n".join([
        "# TYPE manijero_http_requests_total counter",
        'manijero_http_requests_total{code="200",route="/ask"} 7',
        'manijero_http_requests_total{code="500",route="/ask"} 2',
        'manijero_http_requests_total{code="503",route="/ask"} 1',
        'manijero_http_requests_total{code="500",route="/health"} 9',
        "manijero_ready 1",
    ])
    assert alerts.parse_ask_counters(text) == (10, 3)
    assert alerts.parse_ask_counters("manijero_ready 1\n") == (0, 0)
    assert alerts.parse_ask_counters("<html>nope</html>") is None


# --- The alert state machine ----------------------------------------------------------------


class Driver:
    def __init__(self) -> None:
        self.state = alerts.State()
        self.now = START
        self.sent: List[str] = []
        self.accept = True

    def send(self, text: str) -> bool:
        if self.accept:
            self.sent.append(text)
        return self.accept

    def step(self, kind: Optional[str], minutes: float = 5, percent: int = 40) -> None:
        self.now += timedelta(minutes=minutes)
        alerts.advance(self.state, kind, percent, 15, self.now, self.send)


def test_one_bad_check_is_quiet_two_send_one_alert_and_a_third_adds_nothing() -> None:
    d = Driver()
    d.step("down")
    assert d.sent == []
    d.step("down")
    assert d.sent == ["Manijero QA: QA is down: the QA service is not running or does not answer. Run ./scripts/init.sh --qa-status on your Mac."]
    d.step("down")
    d.step("down")
    assert len(d.sent) == 1


def test_a_single_blip_never_alerts() -> None:
    d = Driver()
    for kind in ("down", None, "down", None, "down"):
        d.step(kind)
    assert d.sent == []


def test_reminder_comes_at_four_hours_and_never_sooner() -> None:
    d = Driver()
    d.step("not_ready")
    d.step("not_ready")
    first = d.now
    assert len(d.sent) == 1
    d.now = first + timedelta(hours=3, minutes=59) - timedelta(minutes=5)
    d.step("not_ready")
    assert len(d.sent) == 1
    d.step("not_ready", minutes=1)
    d.now = first + timedelta(hours=4) - timedelta(minutes=5)
    d.step("not_ready", minutes=5)
    assert len(d.sent) == 2
    assert d.sent[1] == "Manijero QA: still a problem since {}: QA is running but not ready to answer questions. Run ./scripts/init.sh --qa-status on your Mac.".format(
        hhmm(first - timedelta(minutes=5))
    )
    d.step("not_ready", minutes=30)
    assert len(d.sent) == 2


def test_recovery_needs_two_ok_checks_and_is_sent_once() -> None:
    d = Driver()
    d.step("down")
    d.step("down")
    began = d.now - timedelta(minutes=5)
    d.step(None)
    assert len(d.sent) == 1 and d.state.incident is not None
    d.step(None)
    ok_since = d.now - timedelta(minutes=5)
    assert d.sent[1] == "Manijero QA is back to normal (problem from {} to {}).".format(hhmm(began), hhmm(ok_since))
    d.step(None)
    d.step(None)
    assert len(d.sent) == 2 and d.state.incident is None


def test_no_recovery_message_when_no_alert_was_sent() -> None:
    d = Driver()
    d.accept = False
    d.step("down")
    d.step("down")
    d.step(None)
    d.step(None)
    assert d.sent == [] and d.state.incident is None


def test_a_failed_send_is_retried_on_the_next_check() -> None:
    d = Driver()
    d.accept = False
    d.step("down")
    d.step("down")
    assert d.sent == [] and d.state.incident is not None and d.state.incident["alerted_kind"] is None
    d.accept = True
    d.step("down")
    assert len(d.sent) == 1


def test_a_failed_recovery_send_is_retried() -> None:
    d = Driver()
    d.step("down")
    d.step("down")
    d.accept = False
    d.step(None)
    d.step(None)
    assert d.state.incident is not None
    d.accept = True
    d.step(None)
    assert d.sent[-1].startswith("Manijero QA is back to normal") and d.state.incident is None


def test_a_change_to_another_problem_sends_one_message_for_the_new_one() -> None:
    d = Driver()
    d.step("down")
    d.step("down")
    d.step("not_ready")
    assert len(d.sent) == 1  # a single check of the new kind is still a blip
    d.step("not_ready")
    assert len(d.sent) == 2 and "not ready" in d.sent[1]
    d.step("not_ready")
    assert len(d.sent) == 2


def test_the_same_kind_gets_no_second_problem_message_within_sixty_minutes() -> None:
    d = Driver()
    d.step("down")
    d.step("down")
    d.step(None)
    d.step(None)
    assert len(d.sent) == 2
    d.step("down")
    d.step("down")  # about 20 minutes after the first alert
    assert len(d.sent) == 2
    d.step(None)
    d.step(None)
    assert len(d.sent) == 2  # the suppressed incident also ends without a second recovery message
    d.step("down", minutes=70)
    d.step("down")
    assert len(d.sent) == 3 and d.sent[2].startswith("Manijero QA: QA is down")


def test_stopped_on_purpose_counts_as_ok_and_the_erroring_text_names_the_share() -> None:
    d = Driver()
    d.step("erroring", percent=37)
    d.step("erroring", percent=37)
    assert "QA failed on 37% of questions in the last 15 minutes." in d.sent[0]
    d.step(None)
    d.step(None)
    assert d.state.incident is None


def test_a_damaged_state_file_starts_fresh(tmp_path: Path) -> None:
    alerts.save_state(tmp_path, alerts.State(cand_kind="down", cand_count=1))
    assert alerts.load_state(tmp_path).cand_kind == "down"
    alerts.state_path(tmp_path).write_text("{not json", encoding="utf-8")
    assert alerts.load_state(tmp_path) == alerts.State()
    alerts.state_path(tmp_path).write_text(json.dumps({"version": 1, "cand_kind": "nonsense"}), encoding="utf-8")
    assert alerts.load_state(tmp_path) == alerts.State()


# --- Whole checks with fake probes ----------------------------------------------------------


def test_a_down_service_alerts_after_two_checks_and_recovery_follows(h: Harness) -> None:
    h.probe.health_value = service.PORT_FREE
    h.check()
    assert h.telegram.sent == []
    h.check()
    assert len(h.telegram.sent) == 1 and "QA is down: the QA service is not running" in h.telegram.sent[0]
    h.probe.health_value = service.SERVICE_NAME
    h.check()
    h.check()
    assert len(h.telegram.sent) == 2 and h.telegram.sent[1].startswith("Manijero QA is back to normal")
    assert h.state().incident is None


def test_docker_closed_says_so(h: Harness) -> None:
    h.docker.open = False
    h.check()
    h.check()
    assert h.telegram.sent == ["Manijero QA: QA is down: Docker Desktop is not open. Open Docker Desktop, then run ./scripts/init.sh --qa-deploy."]


def test_an_exited_qa_container_is_down(h: Harness) -> None:
    h.docker.run_container(running=False)
    h.check()
    h.check()
    assert "QA is down" in h.telegram.sent[0]


def test_stopped_on_purpose_is_not_a_problem(h: Harness) -> None:
    h.docker.container = None
    h.probe.health_value = service.PORT_FREE
    for _ in range(4):
        h.check()
    assert h.telegram.sent == [] and h.state().last_check["outcome"] == "stopped"
    h.tailscale.funnel_ours = True  # Funnel still points at QA but the container is gone
    h.check()
    h.check()
    assert "QA is down" in h.telegram.sent[0]


def test_not_ready_and_unreachable_are_reported_and_the_public_probe_waits_for_a_ready_service(h: Harness) -> None:
    h.probe.ready_value = service.UNAVAILABLE
    h.check()
    h.check()
    assert "not ready to answer questions" in h.telegram.sent[0] and h.public_calls == []
    h.probe.ready_value = service.READY
    h.public_ok = False
    h.check()
    h.check()
    assert h.telegram.sent[-1].startswith("Manijero QA: QA works on your Mac but phones cannot reach it.")
    assert h.public_calls and h.public_calls[0] == ADDRESS


def test_erroring_waits_for_a_full_window_then_alerts_at_the_problem_level(h: Harness) -> None:
    for step in range(3):
        h.counters = (100 + 20 * step, 10 * step)
        h.check()
    assert h.telegram.sent == []
    for step in (3, 4):
        h.counters = (100 + 20 * step, 10 * step)
        h.check()
    assert len(h.telegram.sent) == 1
    assert "QA failed on 50% of questions in the last 15 minutes." in h.telegram.sent[0]
    token = profiles.read_token(profiles.credential_paths(h.qa_home, profiles.QA_CLIENT_ID).token)
    assert set(h.metric_tokens) == {token}


def test_a_counter_drop_restarts_the_error_window(h: Harness) -> None:
    for step in range(3):
        h.counters = (100 + 20 * step, 10 * step)
        h.check()
    h.counters = (5, 5)
    for _ in range(3):
        h.check()
    assert h.telegram.sent == []


def test_a_quiet_service_with_few_errors_is_fine(h: Harness) -> None:
    for step in range(6):
        h.counters = (100 + 100 * step, step)
        h.check()
    assert h.telegram.sent == []


def test_a_running_qa_command_skips_the_check_and_changes_nothing(h: Harness) -> None:
    import fcntl

    h.probe.health_value = service.PORT_FREE
    lock = h.qa_home / qa.LOCK_NAME
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        for _ in range(3):
            h.check()
        assert h.telegram.sent == [] and not alerts.state_path(h.home).exists()
        assert "outcome=skipped" in alerts.log_path(h.home).read_text(encoding="utf-8")
    finally:
        os.close(descriptor)


def test_without_telegram_details_nothing_is_sent_and_the_outcome_is_still_recorded(h: Harness) -> None:
    alerts.credentials_path(h.home).unlink()
    h.probe.health_value = service.PORT_FREE
    h.check()
    h.check()
    assert h.telegram.sent == [] and h.state().last_check["send_failed"] is True


def test_alerts_never_hold_secrets_addresses_or_ids(h: Harness) -> None:
    h.docker.container = None
    h.tailscale.funnel_ours = True
    h.probe.health_value = service.PORT_FREE
    h.check()
    h.check()
    h.probe.health_value = service.SERVICE_NAME
    h.public_ok = False
    h.check(minutes=1)
    h.check()
    h.check()
    h.probe.health_value = service.PORT_FREE
    h.check(minutes=250)
    h.check()
    assert len(h.telegram.sent) >= 3
    client_token = profiles.read_token(profiles.credential_paths(h.qa_home, profiles.QA_CLIENT_ID).token)
    forbidden = [FAKE_TOKEN, str(CHAT_ID), "ts.net", "secretname", profiles.QA_CLIENT_ID, client_token or "x", "mac.tail"]
    bodies = list(h.telegram.sent) + h.output
    for path in h.home.rglob("*"):
        if path.is_file() and path != alerts.credentials_path(h.home):
            bodies.append(path.read_text(encoding="utf-8"))
            assert path.stat().st_mode & 0o777 == 0o600, path
    for text in bodies:
        for secret in forbidden:
            assert secret not in text, secret
    assert alerts.credentials_path(h.home).stat().st_mode & 0o777 == 0o600
    assert alerts.credentials_path(h.home).parent.stat().st_mode & 0o777 == 0o700


def test_the_log_rolls_at_one_megabyte(h: Harness) -> None:
    path = alerts.log_path(h.home)
    path.parent.mkdir(parents=True)
    path.write_text("x" * (alerts.LOG_LIMIT_BYTES + 5), encoding="utf-8")
    h.check()
    assert path.with_name(alerts.LOG_NAME + ".1").exists() and path.stat().st_size < 1000


# --- Telegram -------------------------------------------------------------------------------


def update(number: int, chat_id: int, kind: str) -> Dict[str, Any]:
    return {"update_id": number, "message": {"chat": {"id": chat_id, "type": kind, "first_name": "Someone"}, "text": "hi"}}


def test_the_newest_private_chat_is_taken_and_nothing_else_is_read() -> None:
    telegram = FakeTelegram()
    telegram.updates = [update(1, 11, "private"), update(3, -500, "group"), update(2, 22, "private")]
    assert alerts.latest_private_chat(telegram, FAKE_TOKEN) == (22, None)
    telegram.updates = [update(1, -5, "group")]
    assert alerts.latest_private_chat(telegram, FAKE_TOKEN) == (None, "no_message")
    telegram.updates = [{"update_id": 1}, "junk", {"update_id": True, "message": {"chat": {"id": 1, "type": "private"}}}]
    assert alerts.latest_private_chat(telegram, FAKE_TOKEN) == (None, "no_message")


def test_stored_details_must_be_private_and_valid(tmp_path: Path) -> None:
    assert alerts.load_credentials(tmp_path) == (None, "missing")
    alerts.write_credentials(tmp_path, alerts.Credentials(FAKE_TOKEN, CHAT_ID))
    loaded, problem = alerts.load_credentials(tmp_path)
    assert problem is None and loaded == alerts.Credentials(FAKE_TOKEN, CHAT_ID)
    assert FAKE_TOKEN not in repr(loaded) and str(CHAT_ID) not in repr(loaded)
    path = alerts.credentials_path(tmp_path)
    os.chmod(path, 0o644)
    assert alerts.load_credentials(tmp_path) == (None, "unsafe")
    os.chmod(path, 0o600)
    path.write_text(json.dumps({"bot_token": "short", "chat_id": 1}), encoding="utf-8")
    assert alerts.load_credentials(tmp_path) == (None, "unsafe")
    path.write_text(json.dumps({"bot_token": FAKE_TOKEN, "chat_id": True}), encoding="utf-8")
    assert alerts.load_credentials(tmp_path) == (None, "unsafe")


class FakeServer:
    """A Telegram stand-in on a loopback test socket; records paths and bodies."""

    def __init__(self, reply_status: int = 200, reply: Optional[Dict[str, Any]] = None) -> None:
        self.requests: List[Tuple[str, Dict[str, Any]]] = []
        outer = self
        self.reply_status = reply_status
        self.reply = reply if reply is not None else {"ok": True, "result": []}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                outer.requests.append((self.path, body))
                data = json.dumps(outer.reply).encode("utf-8")
                self.send_response(outer.reply_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def api(self) -> str:
        return "http://127.0.0.1:{}".format(self.httpd.server_address[1])

    def __enter__(self) -> "FakeServer":
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def test_the_http_transport_talks_to_the_loopback_fake_and_maps_failures_to_codes() -> None:
    credentials = alerts.Credentials(FAKE_TOKEN, CHAT_ID)
    with FakeServer() as server:
        transport = alerts.HttpTelegram(server.api)
        assert alerts.check_token(transport, FAKE_TOKEN) is None
        assert alerts.send_text(transport, credentials, "hello") is None
        assert [path for path, _ in server.requests] == ["/bot{}/getMe".format(FAKE_TOKEN), "/bot{}/sendMessage".format(FAKE_TOKEN)]
        assert server.requests[1][1] == {"chat_id": CHAT_ID, "text": "hello", "disable_web_page_preview": True}
        for status, token_code, send_code in [(401, "token_rejected", "token_rejected"), (403, "token_rejected", "chat_unavailable"),
                                             (400, "token_rejected", "chat_unavailable"), (500, "unreachable", "unreachable"),
                                             (429, "unreachable", "unreachable")]:
            server.reply_status, server.reply = status, {"ok": False}
            assert alerts.check_token(transport, FAKE_TOKEN) == token_code
            assert alerts.send_text(transport, credentials, "x") == send_code
        server.reply_status, server.reply = 200, {"ok": False}
        assert alerts.send_text(transport, credentials, "x") == "unreachable"  # a 200 that is not ok is not a delivery
    assert alerts.check_token(alerts.HttpTelegram(server.api), FAKE_TOKEN) == "unreachable"  # nothing listens now


def test_the_telegram_address_override_is_loopback_only() -> None:
    assert alerts.api_from_environment({}) is None
    assert alerts.api_from_environment({"MANIJERO_TELEGRAM_API": "http://127.0.0.1:8123"}) == "http://127.0.0.1:8123"
    for bad in ("https://api.telegram.org", "http://example.com:80", "http://127.0.0.1", "http://127.0.0.1:80/x", "http://localhost:80"):
        with pytest.raises(alerts.AlertsUsageError):
            alerts.api_from_environment({"MANIJERO_TELEGRAM_API": bad})


# --- Owner commands, in process --------------------------------------------------------------


def results(h: Harness) -> List[str]:
    return [line for line in h.output if line.startswith("Result:")]


def test_setup_stores_the_details_privately_and_prints_nothing_about_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(tmp_path, monkeypatch)
    h.telegram.updates = [update(1, CHAT_ID, "private")]
    assert alerts.run_setup(h.ports) == 0
    assert results(h) == ["Result: Telegram alerts are set up. Send a test with ./scripts/init.sh --qa-alerts-test."]
    assert alerts.load_credentials(h.home) == (alerts.Credentials(FAKE_TOKEN, CHAT_ID), None)
    assert alerts.credentials_path(h.home).stat().st_mode & 0o777 == 0o600
    assert alerts.credentials_path(h.home).parent.stat().st_mode & 0o777 == 0o700
    for text in h.output + h.prompter.asked:
        assert FAKE_TOKEN not in text and str(CHAT_ID) not in text


def test_setup_through_the_real_transport_against_the_loopback_fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    h = Harness(tmp_path, monkeypatch)
    with FakeServer(reply={"ok": True, "result": [update(9, CHAT_ID, "private")]}) as server:
        h.ports.telegram = alerts.HttpTelegram(server.api)
        assert alerts.run_setup(h.ports) == 0
    assert alerts.load_credentials(h.home)[0] == alerts.Credentials(FAKE_TOKEN, CHAT_ID)


@pytest.mark.parametrize("secret", [None, "", "not-a-token", "12:short", FAKE_TOKEN + " extra words"])
def test_setup_refuses_a_malformed_token_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, secret: Optional[str]) -> None:
    h = Harness(tmp_path, monkeypatch)
    h.prompter.secret = secret
    assert alerts.run_setup(h.ports) == 1
    (result,) = results(h)
    assert result.startswith("Result: Telegram alerts were not set up.")
    assert not h.home.exists() or not alerts.credentials_path(h.home).exists()
    assert all("not-a-token" not in line and "extra words" not in line for line in h.output)


def test_setup_stops_for_a_rejected_token_no_message_no_terminal_and_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rejected = Harness(tmp_path / "first", monkeypatch)
    rejected.telegram.token_ok = False
    assert alerts.run_setup(rejected.ports) == 1 and "did not accept the bot token" in rejected.output[-2]
    assert not alerts.credentials_path(rejected.home).exists()
    h = Harness(tmp_path / "second", monkeypatch)
    assert alerts.run_setup(h.ports) == 1  # three tries with no private message
    assert h.prompter.asked.count("Now open your bot in Telegram, send it any message, then press Enter here: ") == 3
    assert "No private message to your bot was found." in h.output
    assert not alerts.credentials_path(h.home).exists()
    h.ports.tty = False
    h.output.clear()
    assert alerts.run_setup(h.ports) == 1 and "There is no Terminal window" in h.output[0]
    h.ports.tty = True
    h.output.clear()
    h.telegram.send_status = 200
    h.ports.telegram = alerts.HttpTelegram("http://127.0.0.1:9")  # nothing listens: unreachable
    h.prompter.answers = ["", "", ""]
    assert alerts.run_setup(h.ports) == 1 and "Telegram could not be reached." in h.output


def test_setup_asks_before_replacing_and_any_answer_but_yes_keeps_the_details(h: Harness) -> None:
    before = alerts.credentials_path(h.home).read_text(encoding="utf-8")
    for answer in (None, "", "no", "y"):
        h.output.clear()
        h.prompter.answers = [answer]
        assert alerts.run_setup(h.ports) == 0
        assert results(h) == ["Result: the stored Telegram details were kept."]
    assert alerts.credentials_path(h.home).read_text(encoding="utf-8") == before
    h.telegram.updates = [update(1, 77, "private")]
    h.prompter.answers = ["YES", ""]
    assert alerts.run_setup(h.ports) == 0
    assert alerts.load_credentials(h.home)[0] == alerts.Credentials(FAKE_TOKEN, 77)


def test_the_test_alert_is_sent_or_explains_each_failure(h: Harness) -> None:
    assert alerts.run_test(h.ports) == 0
    assert h.telegram.sent == ["Manijero QA: this is a test alert. If you can read it, alerts reach you."]
    assert results(h) == ["Result: a test alert was sent. Check Telegram on your phone."]
    expectations = [(401, "did not accept the bot token"), (403, "would not deliver to your chat"), (500, "could not be reached")]
    for status, words in expectations:
        h.output.clear()
        h.telegram.send_status = status
        assert alerts.run_test(h.ports) == 1
        assert words in h.output[0] and results(h)[0].startswith("Result: the test alert was not sent. ")
    h.output.clear()
    os.chmod(alerts.credentials_path(h.home), 0o644)
    assert alerts.run_test(h.ports) == 1 and "cannot be used" in h.output[0]
    alerts.credentials_path(h.home).unlink()
    h.output.clear()
    assert alerts.run_test(h.ports) == 1 and "not set up yet" in h.output[0]
    assert all(FAKE_TOKEN not in line for line in h.output)


BREAKERS = {
    "telegram": (lambda c: alerts.credentials_path(c.home).unlink(), "Telegram alerts are not set up yet."),
    "settings": (lambda c: (c.qa_home / "settings.env").unlink(), "QA settings file does not exist"),
    "keys": (lambda c: profiles.credential_paths(c.qa_home, profiles.QA_CLIENT_ID).token.unlink(), "QA access keys are missing"),
    "venv": (lambda c: (c.repo / "backend" / ".venv" / "bin" / "python").unlink(), "backend tools are not set up"),
    "launchctl": (lambda c: setattr(c.launchctl, "installed", False), "launchctl"),
}


@pytest.mark.parametrize("name", sorted(BREAKERS))
def test_start_refuses_each_missing_prerequisite_before_writing(name: str, h: Harness) -> None:
    break_it, sentence = BREAKERS[name]
    break_it(h)
    assert alerts.run_start(h.ports) == 1
    assert any(sentence in line for line in h.output), h.output
    assert results(h)[0].startswith("Result: QA alerts were not turned on. ")
    assert h.launchctl.calls == [] and not h.ports.agents_dir.exists()


def test_start_needs_a_real_public_address(h: Harness) -> None:
    (h.qa_home / "settings.env").write_text(profiles.render_template(h.qa_home), encoding="utf-8")
    assert alerts.run_start(h.ports) == 1
    assert "QA has no real internet address yet." in h.output
    assert "--qa-deploy" in results(h)[0]


def test_start_writes_a_secret_free_plist_loads_it_and_is_idempotent(h: Harness) -> None:
    import plistlib

    assert alerts.run_start(h.ports) == 0
    assert results(h) == ["Result: QA alerts are on. The check runs every 5 minutes while this Mac is awake."]
    raw = h.ports.plist.read_bytes()
    document = plistlib.loads(raw)
    assert h.ports.plist.name == "org.manijero.qa-alerts.plist"
    assert document["Label"] == "org.manijero.qa-alerts" and document["StartInterval"] == 300 and document["RunAtLoad"] is True
    assert document["ProgramArguments"] == [
        str(h.repo / "backend" / ".venv" / "bin" / "python"), str(h.repo / "backend" / "scripts" / "qa_alerts.py"), "check",
    ]
    assert all(Path(part).is_absolute() for part in document["ProgramArguments"][:2])
    assert document["EnvironmentVariables"] == {"PATH": alerts.LAUNCHD_PATH}
    text = raw.decode("utf-8")
    for secret in (FAKE_TOKEN, str(CHAT_ID), "MANIJERO_", "ts.net", "secretname"):
        assert secret not in text
    assert h.launchctl.calls == ["bootstrap"]
    h.output.clear()
    assert alerts.run_start(h.ports) == 0
    assert results(h) == ["Result: QA alerts are already on; nothing was changed."]
    assert h.launchctl.calls == ["bootstrap"] and h.ports.plist.read_bytes() == raw


def test_start_reloads_when_the_file_differs_and_reports_a_failed_load(h: Harness) -> None:
    assert alerts.run_start(h.ports) == 0
    h.ports.plist.write_bytes(b"old")
    h.output.clear()
    assert alerts.run_start(h.ports) == 0
    assert h.launchctl.calls == ["bootstrap", "bootout", "bootstrap"]
    h.launchctl.loaded = False
    h.launchctl.fail_bootstrap = True
    h.output.clear()
    assert alerts.run_start(h.ports) == 1
    assert results(h)[0].startswith("Result: QA alerts could not be turned on.")


def test_stop_removes_only_the_job_and_keeps_secrets_and_state(h: Harness) -> None:
    assert alerts.run_stop(h.ports) == 0
    assert results(h) == ["Result: QA alerts were not on, so there was nothing to stop."] and h.launchctl.calls == []
    alerts.run_start(h.ports)
    h.check()
    h.output.clear()
    assert alerts.run_stop(h.ports) == 0
    assert results(h) == ["Result: QA alerts are off."]
    assert not h.ports.plist.exists() and not h.launchctl.loaded
    assert alerts.credentials_path(h.home).exists() and alerts.state_path(h.home).exists()
    assert set(h.launchctl.calls) <= {"bootstrap", "bootout"}


def test_status_lines_and_results(h: Harness) -> None:
    assert alerts.run_status(h.ports) == 1
    assert results(h) == ["Result: QA alerts are off. Turn them on with ./scripts/init.sh --qa-alerts-start."]
    alerts.run_start(h.ports)
    h.output.clear()
    assert alerts.run_status(h.ports) == 1
    assert any(line.startswith("PROBLEM") and "Last check: none yet" in line for line in h.output)
    h.check()
    h.output.clear()
    assert alerts.run_status(h.ports) == 0
    assert [line.split(":")[0].split(None, 1)[1] for line in h.output[:-1]] == ["Alert job", "Telegram", "Last check", "Open problems"]
    assert all(line.startswith("OK") for line in h.output[:-1])
    assert results(h) == ["Result: QA alerts are on and the last check found no problem."]
    for line in h.output:
        assert FAKE_TOKEN not in line and str(CHAT_ID) not in line and "ts.net" not in line


def test_status_reports_an_open_problem_a_stale_check_and_a_moved_checkout(h: Harness) -> None:
    alerts.run_start(h.ports)
    h.probe.health_value = service.PORT_FREE
    h.check()
    h.check()
    h.output.clear()
    assert alerts.run_status(h.ports) == 1
    assert any("Open problems" in line and "QA is down since" in line and "alert sent" in line for line in h.output)
    assert results(h) == ["Result: QA alerts need attention: Run ./scripts/init.sh --qa-status on your Mac."]
    h.probe.health_value = service.SERVICE_NAME
    h.check()
    h.check()
    h.clock.advance(minutes=16)
    h.output.clear()
    assert alerts.run_status(h.ports) == 1
    assert any("more than 15 minutes ago; the Mac may have been asleep" in line for line in h.output)
    h.check()
    h.ports.plist.write_bytes(b"changed")
    h.output.clear()
    assert alerts.run_status(h.ports) == 1 and "different folder or older settings" in "\n".join(h.output)


def test_status_never_changes_anything(h: Harness) -> None:
    alerts.run_start(h.ports)
    h.check()
    snapshot = {p: p.read_bytes() for p in list(h.home.rglob("*")) + [h.ports.plist] if p.is_file()}
    calls = list(h.launchctl.calls)
    alerts.run_status(h.ports)
    assert {p: p.read_bytes() for p in snapshot} == snapshot and h.launchctl.calls == calls
