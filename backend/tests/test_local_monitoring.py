"""The health dashboard start, status, and stop logic against an in-memory fake Docker.

No Docker, network, or real clock is used. The fake records every call, keeps containers,
networks, and volumes in memory, and answers ``inspect`` like Docker does.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pytest

from app import local_monitoring as monitoring
from app import local_rag_bootstrap as bootstrap

REPO_ROOT = Path(__file__).resolve().parents[2]
FAKE_TOKEN = "qa-token-" + "x" * 60
FAKE_PASSWORD = "fake-admin-password-for-tests"
MANAGED = monitoring.container.MANAGED_LABEL


class FakeDocker:
    def __init__(self, state: str = "ready") -> None:
        self.state = state  # missing | closed | ready
        self.calls: List[List[str]] = []
        self.containers: Dict[str, Dict[str, Any]] = {}
        self.networks: Dict[str, Dict[str, str]] = {}
        self.volumes: Dict[str, Dict[str, str]] = {}
        self.images: set = set()
        self.password_seen: Optional[str] = None
        self.fail: set = set()

    def present(self) -> bool:
        return self.state != "missing"

    def _result(self, code: int, out: str = "") -> bootstrap.CommandResult:
        return bootstrap.CommandResult(code, out, "" if code == 0 else "error")

    def run(self, args: Sequence[str], timeout: float) -> bootstrap.CommandResult:
        argv = [str(a) for a in args]
        self.calls.append(argv)
        head = argv[0]
        if head == "info":
            return self._result(0, "27.3.1\n") if self.state == "ready" else self._result(1)
        if head in self.fail:
            return self._result(1)
        if head == "container" and argv[1] == "inspect":
            return self._inspect_container(argv[2])
        if head in ("network", "volume") and argv[1] == "inspect":
            table = self.networks if head == "network" else self.volumes
            if argv[2] not in table:
                return self._result(1)
            return self._result(0, json.dumps([{"Labels": table[argv[2]]}]))
        if head in ("network", "volume") and argv[1] == "create":
            labels = {}
            if "--label" in argv:
                key, _, value = argv[argv.index("--label") + 1].partition("=")
                labels[key] = value
            (self.networks if head == "network" else self.volumes)[argv[-1]] = labels
            return self._result(0)
        if head == "network" and argv[1] == "rm":
            self.networks.pop(argv[2], None)
            return self._result(0)
        if head == "image" and argv[1] == "inspect":
            return self._result(0, json.dumps([{"Size": 1234, "Config": {"Labels": {}}}])) if argv[2] in self.images else self._result(1)
        if head == "run":
            return self._run(argv)
        if head == "stop":
            self.containers[argv[-1]]["running"] = False
            return self._result(0)
        if head == "rm":
            self.containers.pop(argv[-1], None)
            return self._result(0)
        return self._result(0)

    def _inspect_container(self, name: str) -> bootstrap.CommandResult:
        entry = self.containers.get(name)
        if entry is None:
            return self._result(1)
        document = {
            "Config": {"Labels": entry["labels"]},
            "State": {"Running": entry["running"]},
            "NetworkSettings": {"Ports": entry["ports"]},
        }
        return self._result(0, json.dumps([document]))

    def _run(self, argv: List[str]) -> bootstrap.CommandResult:
        name = argv[argv.index("--name") + 1]
        labels = {}
        ports: Dict[str, Any] = {}
        for index, part in enumerate(argv):
            if part == "--label":
                key, _, value = argv[index + 1].partition("=")
                labels[key] = value
            if part == "--publish":
                host, _, rest = argv[index + 1].partition(":")
                host_port, _, container_port = rest.partition(":")
                ports["{}/tcp".format(container_port)] = [{"HostIp": host, "HostPort": host_port}]
        if name in self.fail:
            return self._result(1)
        if name == monitoring.GRAFANA:
            self.password_seen = os.environ.get(monitoring.ADMIN_PASSWORD_KEY)
        self.containers[name] = {"labels": labels, "running": True, "ports": ports, "argv": argv}
        return self._result(0)

    def start(self, args: Sequence[str], log_path: Path) -> Any:
        argv = [str(a) for a in args]
        self.calls.append(argv)
        if argv[0] == "pull" and "pull" not in self.fail:
            self.images.add(argv[1])
            code = 0
        else:
            code = 1

        class Done:
            def poll(self) -> int:
                return code

            def stop(self) -> None:
                return None

        return Done()

    def runs(self) -> List[List[str]]:
        return [call for call in self.calls if call[0] == "run"]


class FakeProbe:
    def __init__(self) -> None:
        self.free = True
        self.up = True

    def port_free(self, port: int) -> bool:
        return self.free

    def healthy(self, port: int) -> bool:
        return self.up


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> datetime:
        return datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


class Setup:
    def __init__(self, tmp_path: Path, docker: Optional[FakeDocker] = None) -> None:
        self.docker = docker or FakeDocker()
        self.probe = FakeProbe()
        self.lines: List[str] = []
        self.home = tmp_path / "home"
        self.qa_home = tmp_path / "qa"
        self.ctx = monitoring.MonitoringContext(REPO_ROOT, self.home, self.qa_home, 8123)
        self.ports = monitoring.MonitoringPorts(
            docker=self.docker, probe=self.probe, clock=FakeClock(), out=self.lines.append,
            new_password=lambda: FAKE_PASSWORD,
        )

    def start(self, port: int = 3000) -> int:
        return monitoring.run_start(self.ctx, self.ports, port)

    def text(self) -> str:
        return "\n".join(self.lines)


def real_qa(qa_home: Path, url: str = "https://qa.example.org") -> None:
    from app import environment_profiles as profiles

    qa_home.mkdir(parents=True)
    template = profiles.render_template(qa_home).replace("https://", "https://", 1)
    lines = []
    for line in template.splitlines():
        if line.startswith("MANIJERO_PUBLIC_URL="):
            line = "MANIJERO_PUBLIC_URL={}".format(url)
        lines.append(line)
    (qa_home / "settings.env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (qa_home / "knowledge-releases").mkdir()
    profiles.make_new_credentials(qa_home, profiles.QA_CLIENT_ID)


def token_of(qa_home: Path) -> str:
    return (qa_home / "credentials" / "qa-test-device.token").read_text(encoding="utf-8").strip()


def config_of(setup: Setup) -> Dict[str, Any]:
    return json.loads((setup.home / "monitoring" / "prometheus.yml").read_text(encoding="utf-8"))


def test_start_publishes_only_grafana_on_loopback_with_labels_and_digest_or_version_references(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(monitoring.ADMIN_PASSWORD_KEY, raising=False)
    setup = Setup(tmp_path)

    assert setup.start() == 0, setup.text()

    prometheus_run, grafana_run = setup.docker.runs()
    assert "--publish" not in prometheus_run and "-p" not in prometheus_run
    assert grafana_run[grafana_run.index("--publish") + 1] == "127.0.0.1:3000:3000"
    assert sum(1 for call in setup.docker.runs() for part in call if part in ("--publish", "-p")) == 1
    pins = monitoring.load_pins(REPO_ROOT / monitoring.IMAGES_FILE)
    assert pins.prometheus.reference in prometheus_run and pins.grafana.reference in grafana_run
    for call in setup.docker.runs():
        labels = [call[i + 1] for i, part in enumerate(call) if part == "--label"]
        assert sorted(labels) == ["org.manijero.component=monitoring", "org.manijero.managed=1"]
        assert "--cap-drop" in call and "no-new-privileges" in call
    assert setup.lines[-1] == "Result: the health dashboard started at http://127.0.0.1:3000."
    assert "Open http://127.0.0.1:3000 in your web browser." in setup.lines
    assert [line for line in setup.lines if line.startswith("Result:")] == [setup.lines[-1]]


def test_pulls_run_before_the_containers_and_use_the_pinned_references(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    setup.start()

    pulls = [call for call in setup.docker.calls if call[0] == "pull"]
    pins = monitoring.load_pins(REPO_ROOT / monitoring.IMAGES_FILE)
    assert sorted(call[1] for call in pulls) == sorted([pins.grafana.reference, pins.prometheus.reference])
    order = [call[0] for call in setup.docker.calls]
    assert max(i for i, name in enumerate(order) if name == "pull") < min(i for i, name in enumerate(order) if name == "run")


def test_the_admin_password_reaches_docker_only_through_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(monitoring.ADMIN_PASSWORD_KEY, raising=False)
    setup = Setup(tmp_path)

    setup.start()

    assert setup.docker.password_seen == FAKE_PASSWORD
    assert monitoring.ADMIN_PASSWORD_KEY not in os.environ
    everything = json.dumps(setup.docker.calls) + setup.text()
    log_text = "".join(path.read_text(encoding="utf-8") for path in (setup.home / "logs").glob("*.log"))
    assert FAKE_PASSWORD not in everything + log_text
    grafana_run = setup.docker.runs()[1]
    assert grafana_run[grafana_run.index(monitoring.ADMIN_PASSWORD_KEY) - 1] == "--env"


def test_local_only_config_has_one_job_and_keeps_only_manijero_series(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    setup.start()

    config = config_of(setup)
    (job,) = config["scrape_configs"]
    assert job["static_configs"] == [{"targets": ["host.docker.internal:8123"], "labels": {"env": "local"}}]
    assert job["scrape_interval"] == "15s"
    keep, labelkeep = job["metric_relabel_configs"]
    assert keep == {"source_labels": ["__name__"], "regex": "manijero_.*", "action": "keep"}
    assert labelkeep["action"] == "labelkeep" and "route" in labelkeep["regex"].split("|")
    assert "qa" not in json.dumps(config)
    assert not any("qa.token" in part for call in setup.docker.runs() for part in call)
    assert setup.docker.runs()[0].count("--volume") == 3


def test_placeholder_qa_address_adds_no_qa_job_and_says_so(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    real_qa(setup.qa_home, "https://manijero-qa.invalid")

    setup.start()

    assert [job["job_name"] for job in config_of(setup)["scrape_configs"]] == ["manijero-local"]
    assert 'QA shows "Not set up yet"' in setup.text()


def test_real_qa_adds_a_token_file_job_and_the_token_stays_out_of_every_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANIJERO_QA_HOME", str(tmp_path / "qa"))
    setup = Setup(tmp_path)
    real_qa(setup.qa_home)
    token = token_of(setup.qa_home)

    assert setup.start() == 0, setup.text()

    qa_job = config_of(setup)["scrape_configs"][1]
    assert qa_job["job_name"] == "manijero-qa" and qa_job["scheme"] == "https"
    assert qa_job["static_configs"] == [{"targets": ["qa.example.org:443"], "labels": {"env": "qa"}}]
    assert qa_job["scrape_interval"] == "30s"
    assert qa_job["authorization"]["credentials_file"] == monitoring.QA_TOKEN_MOUNT
    prometheus_run = setup.docker.runs()[0]
    mounted = "{}:{}:ro".format(setup.qa_home / "credentials" / "qa-test-device.token", monitoring.QA_TOKEN_MOUNT)
    assert mounted in prometheus_run
    texts = [json.dumps(setup.docker.calls), setup.text(), (setup.home / "monitoring" / "prometheus.yml").read_text(encoding="utf-8")]
    texts += [path.read_text(encoding="utf-8") for path in (setup.home / "logs").glob("*.log")]
    assert all(token not in text for text in texts)


def test_incomplete_qa_keys_leave_qa_unset(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    real_qa(setup.qa_home)
    (setup.qa_home / "credentials" / "qa-test-device.token").unlink()

    setup.start()

    assert [job["job_name"] for job in config_of(setup)["scrape_configs"]] == ["manijero-local"]


def test_restart_while_running_changes_nothing(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.start()
    setup.docker.calls.clear()
    setup.lines.clear()

    assert setup.start() == 0

    assert not [call for call in setup.docker.calls if call[0] in ("run", "pull", "rm", "stop", "network", "volume")]
    assert "Open http://127.0.0.1:3000 in your web browser." in setup.lines
    assert setup.lines[-1].startswith("Result: nothing new was started")


@pytest.mark.parametrize(
    "state, expected",
    [("missing", "not installed"), ("closed", "not open")],
)
def test_docker_missing_or_closed_creates_nothing(tmp_path: Path, state: str, expected: str) -> None:
    setup = Setup(tmp_path, FakeDocker(state))

    assert setup.start() == 1

    assert expected in setup.text()
    assert setup.lines[-1].startswith("Result: the health dashboard did not start. ")
    assert not [call for call in setup.docker.calls if call[0] not in ("info",)]
    assert not setup.home.exists()


def test_busy_port_stops_early_with_one_fix(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.probe.free = False

    assert setup.start() == 1

    assert "Port 3000 is in use by another program." in setup.lines
    assert setup.lines[-1].endswith("Close the other program that uses port 3000, then run this command again.")
    assert not setup.docker.runs() and not [c for c in setup.docker.calls if c[0] == "pull"]


def test_a_foreign_container_with_a_monitoring_name_is_never_touched(tmp_path: Path) -> None:
    docker = FakeDocker()
    docker.containers[monitoring.GRAFANA] = {"labels": {}, "running": True, "ports": {}}
    setup = Setup(tmp_path, docker)

    assert setup.start() == 1
    stop = monitoring.run_stop(setup.ctx, setup.ports)

    assert "Manijero did not create it" in setup.text()
    assert stop == 0 and setup.lines[-1] == monitoring.NOTHING_TO_STOP
    assert monitoring.GRAFANA in docker.containers
    assert not [call for call in docker.calls if call[0] in ("rm", "stop", "run")]


def test_invalid_pins_stop_before_anything_is_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup = Setup(tmp_path)
    fake_repo = tmp_path / "repo"
    (fake_repo / "backend" / "monitoring").mkdir(parents=True)
    (fake_repo / "backend" / "monitoring" / "images.json").write_text("{}", encoding="utf-8")
    setup.ctx = monitoring.MonitoringContext(fake_repo, setup.home, setup.qa_home, 8123)

    assert setup.start() == 1

    assert monitoring.MSG_BAD_PINS in setup.lines
    assert setup.lines[-1].endswith(monitoring.FIX_BAD_PINS)
    assert not setup.docker.runs()


def test_a_failed_grafana_start_removes_both_containers_and_keeps_the_volume(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.probe.up = False

    assert setup.start() == 1

    assert not setup.docker.containers
    assert monitoring.VOLUME in setup.docker.volumes
    assert "did not answer within 120 seconds" in setup.text()
    assert setup.lines[-1].startswith(monitoring.START_FAILED)


def test_a_failed_pull_creates_no_container(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.docker.fail.add("pull")

    assert setup.start() == 1

    assert not setup.docker.runs()
    assert "could not download" in setup.text()


def test_leftover_stopped_containers_are_cleared_then_started(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.start()
    setup.docker.containers[monitoring.PROMETHEUS]["running"] = False
    setup.lines.clear()

    assert setup.start() == 0

    assert monitoring.MSG_LEFTOVER in setup.lines
    assert all(entry["running"] for entry in setup.docker.containers.values())


def test_stop_removes_only_labelled_containers_and_keeps_the_volume(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.start()
    other = {"labels": {}, "running": True, "ports": {}}
    setup.docker.containers["unrelated"] = other
    setup.lines.clear()

    assert monitoring.run_stop(setup.ctx, setup.ports) == 0

    assert set(setup.docker.containers) == {"unrelated"}
    assert monitoring.VOLUME in setup.docker.volumes
    assert not [call for call in setup.docker.calls if call[:2] == ["volume", "rm"]]
    assert setup.lines[-1] == monitoring.STOPPED


def test_stop_with_nothing_running_says_so_and_is_repeatable(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    assert monitoring.run_stop(setup.ctx, setup.ports) == 0
    assert monitoring.run_stop(setup.ctx, setup.ports) == 0

    assert setup.lines == [monitoring.NOTHING_TO_STOP, monitoring.NOTHING_TO_STOP]


def test_status_reports_running_with_the_address_or_not_running_with_the_start_command(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    assert monitoring.run_status(setup.ctx, setup.ports, 3000) == 1
    assert setup.lines[-1] == monitoring.NOT_RUNNING and "./scripts/init.sh --monitoring-start" in setup.lines[-1]
    setup.start()
    setup.lines.clear()
    before = list(setup.docker.calls)

    assert monitoring.run_status(setup.ctx, setup.ports, 3000) == 0

    assert setup.lines[-1] == "Result: the health dashboard is running at http://127.0.0.1:3000."
    assert "Open http://127.0.0.1:3000 in your web browser." in setup.lines
    new_calls = setup.docker.calls[len(before):]
    assert all(call[0] in ("info", "container", "network", "volume", "image") and call[1:2] != ["create"] for call in new_calls)


def test_status_flags_a_page_that_does_not_answer_and_a_half_running_dashboard(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.start()
    setup.probe.up = False
    assert monitoring.run_status(setup.ctx, setup.ports, 3000) == 1
    assert "does not answer yet" in setup.lines[-1]
    setup.docker.containers[monitoring.PROMETHEUS]["running"] = False
    setup.lines.clear()

    assert monitoring.run_status(setup.ctx, setup.ports, 3000) == 1

    assert "only part of the health dashboard runs" in setup.text()
    assert monitoring.STOP_COMMAND in setup.lines[-1]


def test_status_without_docker_never_creates_anything(tmp_path: Path) -> None:
    for state in ("missing", "closed"):
        setup = Setup(tmp_path / state, FakeDocker(state))

        assert monitoring.run_status(setup.ctx, setup.ports, 3000) == 1
        assert setup.lines[-1] == monitoring.NOT_RUNNING


def test_port_environment_value_is_validated() -> None:
    assert monitoring.port_from_environment({}) == 3000
    assert monitoring.port_from_environment({monitoring.PORT_ENV: "3456"}) == 3456
    for bad in ("0", "65536", "abc", "-1"):
        with pytest.raises(Exception):
            monitoring.port_from_environment({monitoring.PORT_ENV: bad})
