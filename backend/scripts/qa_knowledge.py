#!/usr/bin/env python3
"""Send approved knowledge to QA, or take QA back to its earlier knowledge. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --qa-knowledge-deploy     # build, check, publish, and re-check the knowledge merged to main
    ./scripts/init.sh --qa-knowledge-rollback   # go back to the earlier QA knowledge (running it again goes forward)

Nothing is sent without typing ``yes``. If QA's checks fail after a switch, QA goes back to the earlier
knowledge by itself. Every run prints plain sentences and ends with one ``Result:`` line. Exit codes:
``0`` done, ``1`` stopped or failed, ``2`` misuse. ``--qa-status`` shows which knowledge QA serves.
Test-only variables (besides those of ``qa_service.py``): ``MANIJERO_QA_KNOWLEDGE_REPO`` (the checkout whose
``origin`` is read), ``MANIJERO_QA_KNOWLEDGE_DEV_PYTHON`` and ``MANIJERO_QA_KNOWLEDGE_HYBRID_PYTHON`` (the
builder interpreters), ``MANIJERO_QA_KNOWLEDGE_EMBEDDING_CONFIG`` (the pin the search model is checked
against), ``MANIJERO_QA_KNOWLEDGE_TODAY`` (``YYYY-MM-DD``), and ``MANIJERO_QA_PUBLIC_PROBE_URL`` (a loopback
``http://127.0.0.1:<port>`` that stands in for the HTTPS address).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import warnings
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import environment_profiles as profiles  # noqa: E402  (path setup must run first)
from app import local_container as container  # noqa: E402
from app import local_rag_bootstrap as bootstrap  # noqa: E402
from app import local_rag_service as service  # noqa: E402
from app import qa_deployment as qa  # noqa: E402
from app import qa_knowledge as knowledge  # noqa: E402

REPO_ENV = "MANIJERO_QA_KNOWLEDGE_REPO"
DEV_PYTHON_ENV = "MANIJERO_QA_KNOWLEDGE_DEV_PYTHON"
HYBRID_PYTHON_ENV = "MANIJERO_QA_KNOWLEDGE_HYBRID_PYTHON"
EMBEDDING_CONFIG_ENV = "MANIJERO_QA_KNOWLEDGE_EMBEDDING_CONFIG"
TODAY_ENV = "MANIJERO_QA_KNOWLEDGE_TODAY"
PUBLIC_PROBE_ENV = "MANIJERO_QA_PUBLIC_PROBE_URL"
LOOPBACK_PREFIX = "http://127.0.0.1:"
GIT_TIMEOUT_SECONDS = 120

# operation -> (the Ctrl+C sentence, its result line, the failure result line)
WORDING = {
    "deploy": (
        "The deploy was stopped before QA was changed.",
        knowledge.NOT_SENT,
        knowledge.NOT_SENT,
    ),
    "rollback": (
        "The rollback was stopped before QA was changed.",
        knowledge.NOT_ROLLED_BACK,
        knowledge.NOT_ROLLED_BACK,
    ),
}


class FixedDayClock(service.SystemServiceClock):
    """Tests only: today's date is fixed, so the corpus does not age under the test."""

    def __init__(self, day: date) -> None:
        self._day = day

    def now(self) -> datetime:
        return datetime.combine(self._day, time(12, 0), tzinfo=timezone.utc)


class GitProgram:
    """Runs git with no prompts and a time limit."""

    def run(self, argv: Sequence[str], cwd: Optional[Path] = None) -> bootstrap.CommandResult:
        environment = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        try:
            completed = subprocess.run(  # noqa: S603 - fixed arguments built in app.qa_knowledge
                [str(part) for part in argv],
                cwd=str(cwd) if cwd else None,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return bootstrap.CommandResult(124, "", "timed out")
        except OSError:
            return bootstrap.CommandResult(127, "", "could not run")
        return bootstrap.CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _say(text: str) -> None:
    print(text, flush=True)


def _public_probe(probe_url: str) -> Callable[[str], bool]:
    if probe_url.startswith(LOOPBACK_PREFIX):  # tests only: loopback stands in for the HTTPS address
        return lambda address: qa.system_public_probe(probe_url)
    return qa.system_public_probe


def _qa_ports(ctx: bootstrap.Context, port: int, tools: bootstrap.Ports) -> qa.QaPorts:
    configured = os.environ.get(qa.ADDRESS_FILE_ENV, "").strip()
    day = os.environ.get(TODAY_ENV, "").strip()
    return qa.QaPorts(
        tools=tools,
        probe=service.LoopbackProbe(),
        clock=FixedDayClock(date.fromisoformat(day)) if day else service.SystemServiceClock(),
        docker=container.SystemDockerCli(ctx.repo_root),
        tailscale=qa.SystemTailscaleCli(ctx.repo_root),
        smoke=qa.system_smoke,
        public=_public_probe(os.environ.get(PUBLIC_PROBE_ENV, "").strip()),
        tty=sys.stdin.isatty(),
        home=profiles.qa_home(),
        port=port,
        address_file=Path(configured).expanduser() if configured else ctx.repo_root / "qa-address.local",
    )


def build_ports(ctx: bootstrap.Context, port: int) -> knowledge.KnowledgePorts:
    checkout = bootstrap.GitCheckout(ctx.repo_root, ctx.knowledge_dir)
    tools = bootstrap.Ports(
        ollama=bootstrap.OllamaClient(),
        checkout=checkout,
        runner=bootstrap.LoggedRunner(ctx.repo_root),
        prompter=bootstrap.TerminalPrompter(),
        disk=bootstrap.LocalDisk(),
        clock=bootstrap.SystemClock(),
        opener=None,
        out=_say,
    )
    repo = os.environ.get(REPO_ENV, "").strip()
    dev_python = os.environ.get(DEV_PYTHON_ENV, "").strip() or ctx.dev_python
    hybrid_python = os.environ.get(HYBRID_PYTHON_ENV, "").strip()
    pin = Path(os.environ.get(EMBEDDING_CONFIG_ENV, "").strip() or ctx.embedding_config).expanduser()
    if hybrid_python:
        hybrid_ready: Callable[[], bool] = lambda: os.access(hybrid_python, os.X_OK)  # noqa: E731 - tests only
    else:
        hybrid_python = ctx.hybrid_python
        hybrid_ready = checkout.hybrid_ready
    return knowledge.KnowledgePorts(
        qa=_qa_ports(ctx, port, tools),
        repo=Path(repo).expanduser() if repo else ctx.repo_root,
        git=GitProgram(),
        builder=bootstrap.LoggedRunner(ctx.repo_root),
        dev_python=dev_python,
        hybrid_python=hybrid_python,
        hybrid_ready=hybrid_ready,
        model_problem=lambda: knowledge.model_problem(pin, ctx.paths.bge_m3),
        artifact=ctx.paths.bge_m3,
    )


def main(
    argv: Optional[Sequence[str]] = None,
    ctx: Optional[bootstrap.Context] = None,
    ports: Optional[knowledge.KnowledgePorts] = None,
) -> int:
    parser = argparse.ArgumentParser(description="Send approved knowledge to QA, or take QA back to its earlier knowledge.")
    parser.add_argument("operation", choices=knowledge.OPERATIONS)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    try:
        port = qa.port_from_environment(os.environ)
        date.fromisoformat(os.environ.get(TODAY_ENV, "").strip() or date.today().isoformat())
    except service.UsageError as misuse:
        print(misuse.message, file=sys.stderr, flush=True)
        return 2
    except ValueError:
        print("{} must be a date like 2026-11-11.".format(TODAY_ENV), file=sys.stderr, flush=True)
        return 2
    context = ctx or bootstrap.default_context(sys.executable)
    active = ports or build_ports(context, port)
    out = active.out
    interrupted, interrupted_result, failed_result = WORDING[args.operation]
    log = bootstrap.RunLog(active.qa.home / "logs", "qa-knowledge-{}-error".format(args.operation), active.qa.clock.now)
    runners = {"deploy": knowledge.run_deploy, "rollback": knowledge.run_rollback}
    try:
        return runners[args.operation](active)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} Do the step shown above.".format(failed_result))
        return 1
    except KeyboardInterrupt:
        out("")
        out(interrupted)
        out(interrupted_result)
        return 1
    except Exception:  # noqa: BLE001 - every unexpected failure becomes one sentence plus a log
        path = log.write_traceback()
        out(
            "Something unexpected went wrong. Run the same command again; if it happens again, send "
            "this log file to a developer: {}".format(path)
        )
        out(failed_result)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
