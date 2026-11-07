"""Optional Docker-backed smoke of the health dashboard; skipped unless opted in.

Set ``MANIJERO_MONITORING_DOCKER_SMOKE=1`` with Docker Desktop open (and internet for the first
image pull). It checks the generated Prometheus settings and the committed rules with ``promtool``
inside the pinned image, starts the dashboard on a free port with a temporary local home, checks
that Grafana answers anonymously and serves the health dashboard, then stops it.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import urllib.request
from pathlib import Path
from typing import List

import pytest

from app import local_monitoring as monitoring

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"

pytestmark = [
    pytest.mark.skipif(os.environ.get("MANIJERO_MONITORING_DOCKER_SMOKE") != "1", reason="set MANIJERO_MONITORING_DOCKER_SMOKE=1 with Docker Desktop open"),
    pytest.mark.skipif(shutil.which("docker") is None, reason="needs the docker command"),
]


def free_port() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return str(probe.getsockname()[1])


def docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=600, check=False)


def init(tmp_path: Path, port: str, mode: str) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment.update(
        {
            "MANIJERO_LOCAL_HOME": str(tmp_path / "home"),
            "MANIJERO_QA_HOME": str(tmp_path / "qa"),
            "MANIJERO_MONITORING_PORT": port,
        }
    )
    return subprocess.run([str(INIT), mode], cwd=REPO_ROOT, env=environment, capture_output=True, text=True, timeout=900, check=False)


def promtool(tmp_path: Path, pin: str, *args: str) -> subprocess.CompletedProcess:
    return docker(
        "run", "--rm", "--entrypoint", "promtool",
        "--volume", "{}:/etc/manijero-prometheus:ro".format(tmp_path / "home" / "monitoring"),
        "--volume", "{}:/etc/manijero-rules:ro".format(REPO_ROOT / monitoring.RULES_DIR),
        pin, *args,
    )


def test_prometheus_settings_and_rules_pass_promtool_then_the_dashboard_starts_and_stops(tmp_path: Path) -> None:
    pins = monitoring.load_pins(REPO_ROOT / monitoring.IMAGES_FILE)
    monitoring.write_config(tmp_path / "home" / "monitoring", monitoring.prometheus_config(8000, None))

    config = promtool(tmp_path, pins.prometheus.reference, "check", "config", "{}/{}".format(monitoring.CONFIG_MOUNT, monitoring.CONFIG_NAME))
    rules = promtool(tmp_path, pins.prometheus.reference, "check", "rules", monitoring.RULES_FILE)
    assert config.returncode == 0, config.stdout + config.stderr
    assert rules.returncode == 0, rules.stdout + rules.stderr

    port = free_port()
    started = init(tmp_path, port, "--monitoring-start")
    try:
        assert started.returncode == 0, started.stdout + started.stderr
        assert "Open http://127.0.0.1:{} in your web browser.".format(port) in started.stdout
        with urllib.request.urlopen("http://127.0.0.1:{}/api/health".format(port), timeout=10) as reply:
            assert json.loads(reply.read())["database"] == "ok"
        with urllib.request.urlopen("http://127.0.0.1:{}/api/search?query=Manijero".format(port), timeout=10) as reply:
            titles: List[str] = [entry["title"] for entry in json.loads(reply.read())]
        assert "Manijero health" in titles
        published = docker("port", monitoring.GRAFANA).stdout
        assert "127.0.0.1" in published and "0.0.0.0" not in published
        assert docker("port", monitoring.PROMETHEUS).stdout.strip() == ""
    finally:
        stopped = init(tmp_path, port, "--monitoring-stop")
    assert stopped.returncode == 0, stopped.stdout + stopped.stderr
