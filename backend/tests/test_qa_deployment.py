"""QA deployment: deploy, update, rollback, status, and stop with in-memory Docker, Tailscale, and probes.

Offline: no Docker, Tailscale, Ollama, model, or network. The QA home is a temporary folder made
by the real QA settings template and key maker (fake tokens only); the address file is temporary.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest

from app import environment_profiles as profiles
from app import local_container as lc
from app import local_rag_bootstrap as lrb
from app import local_rag_service as svc
from app import qa_deployment as qa

NAME = "mac-mini.tail1234.ts.net"
ADDRESS = "https://" + NAME
PORT = 8100
TARGET = "http://127.0.0.1:8100"


def _labels(release: str, revision: str, launchers: str = "default,pilot", campaign: str = "2026") -> Dict[str, str]:
    return {
        lc.MANAGED_LABEL: "1",
        lc.LABEL_RELEASE: release,
        lc.LABEL_REVISION: revision,
        lc.LABEL_CAMPAIGN: campaign,
        qa.LABEL_LAUNCHERS: launchers,
    }


class FakeDocker:
    def __init__(self) -> None:
        self.installed = True
        self.open = True
        self.images: Dict[str, Dict[str, Any]] = {}
        self.container: Optional[Dict[str, Any]] = None
        self.calls: List[List[str]] = []
        self.run_failures: List[int] = []  # one entry consumed per `docker run`; non-zero fails
        self.exit_at_once: List[bool] = []
        self.logs = "service started\n"
        self.stop_code = 0

    def present(self) -> bool:
        return self.installed

    def add_image(self, tag: str, ident: str, release: str = "rel1", revision: str = "a" * 40, **kw: str) -> None:
        self.images[tag] = {"id": ident, "labels": _labels(release, revision, **kw)}

    def run(self, args: Sequence[str], timeout: float) -> lrb.CommandResult:
        args = [str(item) for item in args]
        self.calls.append(args)
        if args[0] == "info":
            return lrb.CommandResult(0, "27.3.1\n") if self.open else lrb.CommandResult(1, "", "no")
        if args[:2] == ["image", "inspect"]:
            image = self.images.get(args[2])
            if image is None:
                return lrb.CommandResult(1, "", "No such image")
            return lrb.CommandResult(
                0, json.dumps([{"Id": image["id"], "Size": 1, "Config": {"Labels": image["labels"]}}])
            )
        if args[:2] == ["container", "inspect"]:
            box = self.container
            if box is None or args[2] != qa.CONTAINER_NAME:
                return lrb.CommandResult(1, "", "No such container")
            ports = {"8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(box["port"])}]} if box["running"] else {}
            document = {
                "Config": {"Labels": box["labels"]},
                "State": {"Running": box["running"], "StartedAt": "2026-11-02T09:30:12.1Z"},
                "NetworkSettings": {"Ports": ports},
            }
            return lrb.CommandResult(0, json.dumps([document]))
        if args[0] == "tag":
            self.images[args[2]] = dict(self.images[args[1]])
            return lrb.CommandResult(0)
        if args[:2] == ["image", "rm"]:
            self.images.pop(args[2], None)
            return lrb.CommandResult(0)
        if args[0] == "run":
            code = self.run_failures.pop(0) if self.run_failures else 0
            if code:
                return lrb.CommandResult(code, "", "docker: error")
            labels = dict(item.split("=", 1) for item in _values(args, "--label"))
            gone = self.exit_at_once.pop(0) if self.exit_at_once else False
            self.container = {
                "labels": labels,
                "running": not gone,
                "image": args[-1],
                "image_id": self.images[args[-1]]["id"],
                "port": int(_values(args, "--publish")[0].split(":")[1]),
                "env": _values(args, "--env"),
            }
            return lrb.CommandResult(0, "c0ffee\n")
        if args[0] == "logs":
            return lrb.CommandResult(0, self.logs)
        if args[0] == "stop":
            if self.stop_code:
                return lrb.CommandResult(self.stop_code, "", "error")
            self.container["running"] = False
            return lrb.CommandResult(0)
        if args[0] == "rm":
            self.container = None
            return lrb.CommandResult(0)
        if args[0] == "exec":
            return lrb.CommandResult(0)
        raise AssertionError("unexpected docker call: {}".format(args))

    def start(self, args: Sequence[str], log_path: Path) -> Any:  # pragma: no cover - never used by QA
        raise AssertionError("QA never builds")

    def runs(self) -> List[List[str]]:
        return [call for call in self.calls if call[0] == "run"]


def _values(args: Sequence[str], option: str) -> List[str]:
    return [args[position + 1] for position, item in enumerate(args) if item == option]


class FakeTailscale:
    def __init__(self) -> None:
        self.installed = True
        self.state = "Running"
        self.capabilities = ["https", "https://tailscale.com/cap/funnel", "funnel-ports?ports=443,8443,10000"]
        self.funnel_document: Dict[str, Any] = {}
        self.calls: List[List[str]] = []
        self.on_code = 0
        self.off_code = 0

    def present(self) -> bool:
        return self.installed

    def set_ours(self) -> None:
        key = NAME + ":443"
        self.funnel_document = {
            "TCP": {"443": {"HTTPS": True}},
            "Web": {key: {"Handlers": {"/": {"Proxy": TARGET}}}},
            "AllowFunnel": {key: True},
        }

    def run(self, args: Sequence[str], timeout: float) -> lrb.CommandResult:
        args = [str(item) for item in args]
        self.calls.append(args)
        if args == list(qa.TAILSCALE_STATUS_ARGV):
            node = {"DNSName": NAME + ".", "CapMap": {name: None for name in self.capabilities}}
            return lrb.CommandResult(0, json.dumps({"BackendState": self.state, "Self": node}))
        if args == list(qa.TAILSCALE_FUNNEL_STATUS_ARGV):
            return lrb.CommandResult(0, json.dumps(self.funnel_document) if self.funnel_document else "{}")
        if args == qa.funnel_on_argv(PORT):
            if self.on_code:
                return lrb.CommandResult(self.on_code)
            self.set_ours()
            return lrb.CommandResult(0)
        if args == qa.funnel_off_argv():
            if self.off_code:
                return lrb.CommandResult(self.off_code)
            self.funnel_document = {}
            return lrb.CommandResult(0)
        raise AssertionError("unexpected tailscale call: {}".format(args))

    def changes(self) -> List[List[str]]:
        return [call for call in self.calls if call[0] == "funnel" and call[1:2] != ["status"]]


class FakeClock:
    def __init__(self) -> None:
        self.time = 0.0

    def now(self) -> datetime:
        return datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.time += seconds


class FakeProbe:
    def __init__(self, docker: FakeDocker) -> None:
        self.docker = docker
        self.other_listener = False
        self.ready_answer = svc.READY

    def health(self, port: int) -> str:
        box = self.docker.container
        if box is not None and box["running"]:
            return svc.SERVICE_NAME
        return svc.PORT_OTHER if self.other_listener else svc.PORT_FREE

    def ready(self, port: int) -> str:
        return self.ready_answer


class Prompter:
    def __init__(self) -> None:
        self.answers: List[Optional[str]] = ["yes"]
        self.asked: List[str] = []

    def ask(self, question: str) -> Optional[str]:
        self.asked.append(question)
        return self.answers.pop(0) if self.answers else None


class Harness:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.lines: List[str] = []
        self.docker = FakeDocker()
        self.tailscale = FakeTailscale()
        self.clock = FakeClock()
        self.probe = FakeProbe(self.docker)
        self.prompter = Prompter()
        self.smoke_failures: List[str] = []
        self.smoke_calls: List[Any] = []
        self.public_ok = True
        self.drafting_ok = True
        self.home = tmp_path / "qa"
        self.address_file = tmp_path / "qa-address.local"
        monkeypatch.setenv("MANIJERO_LOCAL_HOME", str(tmp_path / "local"))
        self.home.mkdir()
        (self.home / "settings.env").write_text(profiles.render_template(self.home), encoding="utf-8")
        profiles.make_new_credentials(self.home, profiles.QA_CLIENT_ID)
        self.token = profiles.read_token(profiles.credential_paths(self.home, profiles.QA_CLIENT_ID).token)
        monkeypatch.setattr(qa.bootstrap, "load_pins", lambda ctx, today: (None, object()))
        monkeypatch.setattr(
            qa.service,
            "drafting_check",
            lambda tools, model: qa.service.Check(self.drafting_ok, "Drafting line" if self.drafting_ok else "PROBLEM  Drafting: Ollama is closed."),
        )
        self.docker.add_image(lc.LOCAL_TAG, "sha256:one")
        self.tailscale.set_ours()
        self.tailscale.funnel_document = {}
        self.tty = True

    @property
    def ports(self) -> qa.QaPorts:
        def smoke(base: str, token: str) -> List[str]:
            self.smoke_calls.append((base, token))
            return self.smoke_failures

        tools = lrb.Ports(
            ollama=None, checkout=None, runner=None, prompter=self.prompter, disk=None, clock=self.clock,
            opener=None, out=self.lines.append,
        )
        return qa.QaPorts(
            tools=tools, probe=self.probe, clock=self.clock, docker=self.docker, tailscale=self.tailscale,
            smoke=smoke, public=lambda address: self.public_ok, tty=self.tty, home=self.home, port=PORT,
            address_file=self.address_file,
        )

    def call(self, op: str) -> int:
        runner = getattr(qa, "run_" + op)
        return runner(None, self.ports)

    @property
    def output(self) -> str:
        return "\n".join(self.lines)

    @property
    def result(self) -> str:
        results = [line for line in self.lines if line.startswith("Result:")]
        assert len(results) == 1, self.lines
        assert self.lines[-1] == results[0]
        return results[0]

    def settings_url(self) -> str:
        return profiles.read_profile_settings(profiles.QA, self.home).public_url or ""

    def deployed(self) -> None:
        """QA already running from qa-current (release rel1) with Funnel on."""

        self.docker.add_image(qa.TAG_CURRENT, "sha256:one")
        assert self.call("deploy") == 0
        self.lines.clear()
        self.docker.calls.clear()
        self.tailscale.calls.clear()
        self.smoke_calls.clear()
        self.prompter.asked.clear()
        self.prompter.answers = ["yes"]


@pytest.fixture
def h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(tmp_path, monkeypatch)


# --- Deploy ----------------------------------------------------------------------------------


def test_first_deploy_tags_runs_checks_turns_funnel_on_and_writes_the_address(h: Harness) -> None:
    assert h.call("deploy") == 0
    assert h.result == "Result: QA is running at {} for test data only.".format(ADDRESS)
    assert h.docker.images[qa.TAG_CURRENT]["id"] == "sha256:one"
    (argv,) = h.docker.runs()
    clients = profiles.credential_paths(h.home, profiles.QA_CLIENT_ID).clients
    assert argv == qa.run_argv(PORT, "2026", clients)
    assert "127.0.0.1:8100:8000" in argv and "--cap-drop" in argv and argv[-1] == qa.TAG_CURRENT
    env = _values(argv, "--env")
    assert sorted(env) == sorted([
        "MANIJERO_ACTIVE_CAMPAIGN=2026", "MANIJERO_DEPLOYMENT_PROFILE=pilot", "MANIJERO_ENVIRONMENT=qa",
        "MANIJERO_QA_TEST_DATA_ONLY=yes", "MANIJERO_PILOT_CLIENTS_FILE=/run/manijero/pilot-clients.json",
    ])
    assert "type=bind,source={},target=/run/manijero/pilot-clients.json,readonly".format(clients) in argv
    kinds = [call[0] for call in h.docker.calls]
    assert kinds.index("tag") < kinds.index("run")
    assert h.tailscale.changes() == [qa.funnel_on_argv(PORT)]
    assert h.smoke_calls == [("http://127.0.0.1:8100", h.token)]
    assert h.settings_url() == ADDRESS
    assert h.address_file.read_text(encoding="utf-8") == ADDRESS + "\n"
    assert "WARNING: QA is for made-up test questions only" in h.output
    assert "yes" not in "".join(h.prompter.asked).split("Type")[0]
    assert "made-up test questions only" in h.output.split("Type yes")[0]
    assert h.token not in h.output


def test_deploy_while_running_changes_nothing_and_needs_no_confirmation(h: Harness) -> None:
    h.deployed()
    h.prompter.answers = []
    assert h.call("deploy") == 0
    assert h.result == (
        "Result: QA is already running at {}; nothing was changed. To ship a newer image use "
        "./scripts/init.sh --qa-update.".format(ADDRESS)
    )
    assert not h.docker.runs() and not h.tailscale.changes() and not h.prompter.asked


def test_deploy_after_the_container_is_gone_starts_qa_current_again(h: Harness) -> None:
    h.deployed()
    h.docker.container = None
    h.tailscale.funnel_document = {}
    assert h.call("deploy") == 0
    assert h.result.startswith("Result: QA is running at")
    assert len(h.docker.runs()) == 1 and h.docker.runs()[0][-1] == qa.TAG_CURRENT
    assert not [call for call in h.docker.calls if call[0] == "tag"]


@pytest.mark.parametrize(
    "setup, line, fix",
    [
        (lambda h: setattr(h.tailscale, "installed", False), "Tailscale is not installed", 'step "Set up Tailscale"'),
        (lambda h: setattr(h.tailscale, "state", "NeedsLogin"), "not logged in", 'step "Set up Tailscale"'),
        (lambda h: setattr(h.tailscale, "capabilities", ["https"]), "HTTPS and Funnel", 'step "Set up Tailscale"'),
        (
            lambda h: h.tailscale.funnel_document.update(
                {"Web": {NAME + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:9999"}}}}, "AllowFunnel": {NAME + ":443": True}}
            ),
            "already sharing something else",
            "tailscale funnel reset",
        ),
        (lambda h: setattr(h.docker, "installed", False), "Docker Desktop is not installed", "Install Docker Desktop"),
        (lambda h: setattr(h.docker, "open", False), "Docker Desktop is not open", "Open the Docker Desktop app"),
        (lambda h: h.docker.images.clear(), "no answer service image", "--container-build"),
        (lambda h: h.docker.add_image(lc.LOCAL_TAG, "x", launchers="default"), "no pilot launcher", "--container-build"),
        (lambda h: h.docker.add_image(lc.LOCAL_TAG, "x", campaign="2025"), "another campaign", "--container-build"),
        (lambda h: (h.home / "settings.env").unlink(), "QA is not prepared", "--qa-settings-setup"),
        (lambda h: profiles.credential_paths(h.home, profiles.QA_CLIENT_ID).token.unlink(), "access keys are missing", "--qa-settings-setup"),
        (lambda h: (h.home / "settings.env").write_text("nonsense\n", encoding="utf-8"), "problem on line 1", "Fix the QA settings"),
        (lambda h: setattr(h, "drafting_ok", False), "Ollama is closed", "Drafting step"),
        (lambda h: setattr(h.probe, "other_listener", True), "Port 8100 is in use by another program", "Close the other program"),
        (
            lambda h: setattr(h.docker, "container", {"labels": {}, "running": True, "port": 8100, "image": "x", "image_id": "x", "env": []}),
            "Manijero did not create it",
            "Rename or delete",
        ),
        (lambda h: setattr(h, "tty", False), "no Terminal window", "Terminal window you can type in"),
    ],
)
def test_a_missing_prerequisite_changes_nothing_and_names_its_fix(h: Harness, setup: Any, line: str, fix: str) -> None:
    setup(h)
    assert h.call("deploy") == 1
    assert line in h.output
    assert h.result.startswith("Result: QA was not deployed. ") and fix in h.result
    assert not h.docker.runs() and not h.tailscale.changes() and not h.prompter.asked
    assert not [call for call in h.docker.calls if call[0] in ("tag", "rm", "stop")]
    assert not h.address_file.exists()


def test_a_busy_lock_is_reported_before_anything_changes(h: Harness) -> None:
    import fcntl

    handle = os.open(h.home / qa.LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert h.call("deploy") == 1
    finally:
        os.close(handle)
    assert "Another QA command is running" in h.output and not h.docker.runs()


@pytest.mark.parametrize("answer", ["no", "", None, "y", "yess"])
def test_any_answer_but_yes_changes_nothing(h: Harness, answer: Optional[str]) -> None:
    h.prompter.answers = [answer]
    assert h.call("deploy") == 1
    assert h.result.startswith("Result: QA was not deployed.")
    assert not h.docker.runs() and not h.tailscale.changes()


def test_a_container_that_exits_is_removed_funnel_stays_off_and_the_refusal_is_translated(h: Harness) -> None:
    h.docker.exit_at_once = [True]
    h.docker.logs = "profile: pilot\nrefused: clients_permissions\n"
    assert h.call("deploy") == 1
    assert "readable by other users" in h.output
    assert h.result.startswith("Result: QA was not deployed. Run ./scripts/init.sh --qa-settings-setup")
    assert h.docker.container is None and not h.tailscale.changes()
    assert qa.TAG_CURRENT not in h.docker.images
    assert list((h.home / "logs").glob("qa-deploy-*.log"))
    assert "refused" not in h.output and "profile: pilot" not in h.output


def test_a_failed_smoke_check_removes_the_container_and_names_only_fixed_codes(h: Harness) -> None:
    h.smoke_failures = ["ask_unauthorized"]
    assert h.call("deploy") == 1
    assert "self-check failed (ask_unauthorized)" in h.output
    assert h.docker.container is None and not h.tailscale.changes()


def test_not_ready_within_120_seconds_fails_and_cleans_up(h: Harness) -> None:
    h.probe.ready_answer = svc.UNAVAILABLE
    assert h.call("deploy") == 1
    assert "did not answer within 120 seconds" in h.output
    assert h.docker.container is None and h.clock.time >= 120


def test_a_public_address_that_never_answers_turns_funnel_off_again(h: Harness) -> None:
    h.public_ok = False
    assert h.call("deploy") == 1
    assert "does not answer yet" in h.output
    assert h.tailscale.changes() == [qa.funnel_on_argv(PORT), qa.funnel_off_argv()]
    assert h.docker.container is None
    assert h.settings_url().endswith(".invalid") and not h.address_file.exists()


def test_ctrl_c_during_the_wait_cleans_up_and_reraises(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupt(seconds: float) -> None:
        raise KeyboardInterrupt

    h.probe.ready_answer = svc.UNAVAILABLE
    monkeypatch.setattr(h.clock, "sleep", interrupt)
    assert h.call("deploy") == 1
    assert "Ctrl+C" in h.output and h.result.startswith("Result: QA was not deployed.")
    assert h.docker.container is None and not h.tailscale.changes()


# --- Update and rollback ---------------------------------------------------------------------


def test_update_promotes_the_new_image_and_keeps_funnel_and_address(h: Harness) -> None:
    h.deployed()
    h.docker.add_image(lc.LOCAL_TAG, "sha256:two", release="rel2", revision="b" * 40)
    assert h.call("update") == 0
    assert h.result == "Result: QA was updated to manijero-backend:rel2-{}. If something is wrong, run ./scripts/init.sh --qa-rollback.".format("b" * 12)
    assert h.docker.images[qa.TAG_CURRENT]["id"] == "sha256:two" and h.docker.images[qa.TAG_PREVIOUS]["id"] == "sha256:one"
    assert h.docker.container["image_id"] == "sha256:two"
    assert not h.tailscale.changes() and h.settings_url() == ADDRESS


def test_update_with_nothing_new_changes_nothing(h: Harness) -> None:
    h.deployed()
    h.prompter.answers = []
    assert h.call("update") == 0
    assert h.result == "Result: nothing new to ship; QA already runs manijero-backend:rel1-{}.".format("a" * 12)
    assert not h.docker.runs()


def test_update_before_any_deploy_says_to_deploy_first(h: Harness) -> None:
    assert h.call("update") == 1
    assert h.result == "Result: QA was not updated. Run ./scripts/init.sh --qa-deploy first."


def test_a_failed_update_restores_the_earlier_version_and_tags(h: Harness) -> None:
    h.deployed()
    h.docker.add_image(lc.LOCAL_TAG, "sha256:two", release="rel2", revision="b" * 40)
    h.docker.exit_at_once = [True]
    assert h.call("update") == 1
    assert h.result.startswith("Result: QA was not updated. The earlier version is running again.")
    assert h.docker.images[qa.TAG_CURRENT]["id"] == "sha256:one"
    assert qa.TAG_PREVIOUS not in h.docker.images
    assert h.docker.container["image_id"] == "sha256:one" and h.docker.container["running"]


def test_rollback_swaps_the_tags_and_running_it_again_rolls_forward(h: Harness) -> None:
    h.deployed()
    h.docker.add_image(lc.LOCAL_TAG, "sha256:two", release="rel2", revision="b" * 40)
    assert h.call("update") == 0
    h.lines.clear()
    h.prompter.answers = ["yes", "yes"]
    assert h.call("rollback") == 0
    assert h.result == "Result: QA was rolled back to manijero-backend:rel1-{}.".format("a" * 12)
    assert h.docker.images[qa.TAG_CURRENT]["id"] == "sha256:one" and h.docker.images[qa.TAG_PREVIOUS]["id"] == "sha256:two"
    assert qa.TAG_SWAP not in h.docker.images
    h.lines.clear()
    assert h.call("rollback") == 0
    assert h.docker.images[qa.TAG_CURRENT]["id"] == "sha256:two"


def test_rollback_without_an_earlier_version_changes_nothing(h: Harness) -> None:
    h.deployed()
    assert h.call("rollback") == 1
    assert h.result == "Result: there is no earlier QA version to go back to; nothing was changed."
    assert not h.docker.runs()


def test_a_failed_rollback_starts_the_version_that_was_running(h: Harness) -> None:
    h.deployed()
    h.docker.add_image(lc.LOCAL_TAG, "sha256:two", release="rel2", revision="b" * 40)
    assert h.call("update") == 0
    h.lines.clear()
    h.prompter.answers = ["yes", "yes"]
    h.docker.exit_at_once = [True]
    assert h.call("rollback") == 1
    assert h.result.startswith("Result: QA was not rolled back. The earlier version is running again.")
    assert h.docker.images[qa.TAG_CURRENT]["id"] == "sha256:two" and h.docker.container["image_id"] == "sha256:two"


def test_update_and_rollback_confirm_first_and_refuse_without_a_terminal(h: Harness) -> None:
    h.deployed()
    h.docker.add_image(lc.LOCAL_TAG, "sha256:two", release="rel2", revision="b" * 40)
    h.tty = False
    assert h.call("update") == 1 and "no Terminal window" in h.output
    h.tty = True
    h.prompter.answers = ["no"]
    h.lines.clear()
    assert h.call("update") == 1 and h.result.startswith("Result: QA was not updated.")
    assert h.docker.images[qa.TAG_CURRENT]["id"] == "sha256:one"


# --- Status and stop -------------------------------------------------------------------------


def test_status_reports_five_checks_and_changes_nothing(h: Harness) -> None:
    h.deployed()
    assert h.call("status") == 0
    for label in ("Container", "Answers", "Drafting", "Internet address", "Address files"):
        assert any(line.startswith("OK") and label + ":" in line for line in h.lines), label
    assert qa.TEST_DATA_LINE in h.lines
    assert h.result == "Result: QA is running at {} for test data only.".format(ADDRESS)
    assert "2026-11-02 09:30 UTC" in h.output
    assert not h.docker.runs() and not h.tailscale.changes()
    assert not [call for call in h.docker.calls if call[0] in ("tag", "rm", "stop")]


def test_status_names_the_first_problem(h: Harness) -> None:
    h.deployed()
    h.tailscale.funnel_document = {}
    assert h.call("status") == 1
    assert any(line.startswith("PROBLEM") and "Internet address" in line for line in h.lines)
    assert h.result.startswith("Result: QA needs attention: ")
    h.lines.clear()
    h.tailscale.set_ours()
    h.address_file.write_text("https://other.ts.net\n", encoding="utf-8")
    assert h.call("status") == 1
    assert any(line.startswith("PROBLEM") and "Address files" in line for line in h.lines)


def test_status_when_nothing_runs(h: Harness) -> None:
    assert h.call("status") == 1
    assert h.result == "Result: QA is not running. Start it with ./scripts/init.sh --qa-deploy."
    h.lines.clear()
    h.docker.open = False
    assert h.call("status") == 1 and h.result.startswith("Result: QA is not running.")


def test_stop_turns_funnel_off_before_stopping_the_container_and_keeps_tags_and_files(h: Harness) -> None:
    h.deployed()
    events: List[str] = []
    docker_run, tailscale_run = h.docker.run, h.tailscale.run
    h.docker.run = lambda args, timeout: (events.append("docker " + str(args[0])), docker_run(args, timeout))[1]  # type: ignore[method-assign]
    h.tailscale.run = lambda args, timeout: (events.append("tailscale " + " ".join(map(str, args))), tailscale_run(args, timeout))[1]  # type: ignore[method-assign]
    assert h.call("stop") == 0
    assert h.result == "Result: QA has stopped and is no longer reachable from the internet."
    assert h.tailscale.changes() == [qa.funnel_off_argv()]
    off = events.index("tailscale funnel --https=443 off")
    assert off < events.index("docker stop") < events.index("docker rm")
    assert h.docker.container is None
    assert qa.TAG_CURRENT in h.docker.images and h.address_file.exists() and h.settings_url() == ADDRESS


def test_stop_leaves_the_container_running_when_funnel_cannot_be_turned_off(h: Harness) -> None:
    h.deployed()
    h.tailscale.off_code = 1
    assert h.call("stop") == 1
    assert h.docker.container is not None and h.docker.container["running"]
    assert h.result.startswith("Result: QA could not be stopped.")


def test_stop_with_nothing_running_and_with_foreign_things(h: Harness) -> None:
    assert h.call("stop") == 0
    assert h.result == "Result: QA was not running, so there was nothing to stop."
    h.lines.clear()
    h.docker.container = {"labels": {}, "running": True, "port": 8100, "image": "x", "image_id": "x", "env": []}
    foreign = {"Web": {NAME + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:9999"}}}}, "AllowFunnel": {NAME + ":443": True}}
    h.tailscale.funnel_document = foreign
    assert h.call("stop") == 0
    assert h.docker.container is not None and h.tailscale.funnel_document == foreign
    assert not h.tailscale.changes() and not [c for c in h.docker.calls if c[0] in ("stop", "rm")]


# --- Tailscale facts, address writing, secrecy ----------------------------------------------


def test_funnel_state_reads_only_its_own_entry_as_ours() -> None:
    key = NAME + ":443"
    ours = {"TCP": {"443": {"HTTPS": True}}, "Web": {key: {"Handlers": {"/": {"Proxy": TARGET + "/"}}}}, "AllowFunnel": {key: True}}
    assert qa._funnel_state(ours, NAME, PORT) == "ours"
    assert qa._funnel_state({}, NAME, PORT) == "off"
    assert qa._funnel_state({**ours, "AllowFunnel": {}}, NAME, PORT) == "off"
    two_paths = {**ours, "Web": {key: {"Handlers": {"/": {"Proxy": TARGET}, "/x": {"Proxy": TARGET}}}}}
    assert qa._funnel_state(two_paths, NAME, PORT) == "foreign"
    assert qa._funnel_state({"TCP": {"443": {"TCPForward": "127.0.0.1:1"}}}, NAME, PORT) == "foreign"
    other_host = {**ours, "Web": {"other.ts.net:443": ours["Web"][key]}}
    assert qa._funnel_state(other_host, NAME, PORT) == "foreign"


def test_write_public_url_keeps_comments_other_lines_and_mode(h: Harness) -> None:
    path = h.home / "settings.env"
    before = path.read_text(encoding="utf-8")
    mode = path.stat().st_mode & 0o777
    profiles.write_public_url(h.home, ADDRESS)
    after = path.read_text(encoding="utf-8").splitlines()
    assert "MANIJERO_PUBLIC_URL=" + ADDRESS in after and "MANIJERO_PUBLIC_URL=https://qa.manijero.invalid" not in after
    assert [line for line in after if line != "MANIJERO_PUBLIC_URL=" + ADDRESS] == [
        line for line in before.splitlines() if not line.startswith("MANIJERO_PUBLIC_URL=")
    ]
    assert path.stat().st_mode & 0o777 == mode
    with pytest.raises(profiles.ProfileSettingsError):
        profiles.write_public_url(h.home, "http://insecure.example")


def test_no_command_prints_or_logs_a_token_a_question_or_an_answer(h: Harness) -> None:
    h.docker.logs = "refused: clients_permissions\n"
    h.deployed()
    for op in ("status", "stop"):
        h.call(op)
    logs = "".join(path.read_text(encoding="utf-8") for path in (h.home / "logs").glob("*.log"))
    assert h.token not in h.output and h.token not in logs
    assert profiles.token_sha256(h.token) not in h.output + logs
    assert all(h.token not in " ".join(call) for call in h.docker.calls + h.tailscale.calls)


def test_port_from_environment() -> None:
    assert qa.port_from_environment({}) == 8100
    assert qa.port_from_environment({"MANIJERO_QA_PORT": "9000"}) == 9000
    for bad in ("0", "70000", "x", "-1"):
        with pytest.raises(svc.UsageError):
            qa.port_from_environment({"MANIJERO_QA_PORT": bad})
