#!/usr/bin/env python3
"""Deploy, update, roll back, check, and stop the QA answer service. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --qa-deploy     # run QA from the built image, reachable over HTTPS (Tailscale Funnel)
    ./scripts/init.sh --qa-update     # ship the newest built image (the earlier one is kept)
    ./scripts/init.sh --qa-rollback   # put the earlier image back (running it again rolls forward)
    ./scripts/init.sh --qa-status     # is QA running, answering, and reachable
    ./scripts/init.sh --qa-stop       # take QA off the internet and stop it

Every run prints plain sentences and ends with one ``Result:`` line. QA is for made-up test
questions only. Exit codes: ``0`` done, ``1`` stopped or failed, ``2`` misuse.
``MANIJERO_QA_HOME``, ``MANIJERO_LOCAL_HOME``, ``MANIJERO_DOCKER_CLI``, ``MANIJERO_TAILSCALE_CLI``,
``MANIJERO_QA_PORT``, and ``MANIJERO_QA_ADDRESS_FILE`` exist for tests only.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path
from typing import Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import environment_profiles as profiles  # noqa: E402  (path setup must run first)
from app import local_container as container  # noqa: E402
from app import local_rag_bootstrap as bootstrap  # noqa: E402
from app import local_rag_service as service  # noqa: E402
from app import qa_deployment as qa  # noqa: E402

# operation -> (the Ctrl+C sentence, its result line, the failure result line)
WORDING = {
    "deploy": ("The deploy was stopped before QA was changed.", qa.NOT_DONE["deploy"], qa.NOT_DONE["deploy"]),
    "update": ("The update was stopped before QA was changed.", qa.NOT_DONE["update"], qa.NOT_DONE["update"]),
    "rollback": ("The rollback was stopped before QA was changed.", qa.NOT_DONE["rollback"], qa.NOT_DONE["rollback"]),
    "status": (
        "The check was stopped. Nothing was changed.",
        "Result: the check was stopped.",
        "Result: QA could not be checked.",
    ),
    "stop": (
        "The stop was interrupted. Run {} again to finish it.".format(qa.STOP_COMMAND),
        "Result: the stop was interrupted.",
        "Result: QA could not be stopped.",
    ),
}


def _say(text: str) -> None:
    print(text, flush=True)


def build_ports(ctx: bootstrap.Context, port: int) -> qa.QaPorts:
    tools = bootstrap.Ports(
        ollama=bootstrap.OllamaClient(),
        checkout=bootstrap.GitCheckout(ctx.repo_root, ctx.knowledge_dir),
        runner=bootstrap.LoggedRunner(ctx.repo_root),
        prompter=bootstrap.TerminalPrompter(),
        disk=bootstrap.LocalDisk(),
        clock=bootstrap.SystemClock(),
        opener=None,
        out=_say,
    )
    configured = os.environ.get(qa.ADDRESS_FILE_ENV, "").strip()
    return qa.QaPorts(
        tools=tools,
        probe=service.LoopbackProbe(),
        clock=service.SystemServiceClock(),
        docker=container.SystemDockerCli(ctx.repo_root),
        tailscale=qa.SystemTailscaleCli(ctx.repo_root),
        smoke=qa.system_smoke,
        public=qa.system_public_probe,
        tty=sys.stdin.isatty(),
        home=profiles.qa_home(),
        port=port,
        address_file=Path(configured).expanduser() if configured else ctx.repo_root / "qa-address.local",
    )


def main(
    argv: Optional[Sequence[str]] = None,
    ctx: Optional[bootstrap.Context] = None,
    ports: Optional[qa.QaPorts] = None,
) -> int:
    parser = argparse.ArgumentParser(description="Deploy, update, roll back, check, or stop the QA answer service.")
    parser.add_argument("operation", choices=qa.OPERATIONS)
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore")
    try:
        port = qa.port_from_environment(os.environ)
    except service.UsageError as misuse:
        print(misuse.message, file=sys.stderr, flush=True)
        return 2
    context = ctx or bootstrap.default_context(sys.executable)
    active = ports or build_ports(context, port)
    out = active.out
    interrupted, interrupted_result, failed_result = WORDING[args.operation]
    log = bootstrap.RunLog(active.home / "logs", "qa-{}-error".format(args.operation), active.clock.now)
    runners = {
        "deploy": qa.run_deploy,
        "update": qa.run_update,
        "rollback": qa.run_rollback,
        "status": qa.run_status,
        "stop": qa.run_stop,
    }
    try:
        return runners[args.operation](context, active)
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
