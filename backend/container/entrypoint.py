"""Container entry point: start the fixed Ollama relay, then the unchanged answer service.

Runs as the image's non-root user. With ``MANIJERO_DEPLOYMENT_PROFILE=pilot`` (the QA deployment,
``./scripts/init.sh --qa-deploy``) the service starts only through the pilot launcher
(``serve_pilot.main``), which validates the configuration and the privacy gate first; the
launcher's public-bind acknowledgement is set for this process only, because the host publish
is ``127.0.0.1``. The service is ``app.main:app`` in the default profile,
on the container's ``0.0.0.0:8000`` (the host publishes it on ``127.0.0.1`` only), without
reload and without the access log. Every setting comes from the image environment plus
``MANIJERO_ACTIVE_CAMPAIGN`` from ``docker run``; nothing here reads a settings file.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict

CONTAINER_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CONTAINER_DIR.parent

APP = "app.main:app"
HOST = "0.0.0.0"  # inside the container only; the host publish is 127.0.0.1
PORT = 8000
PILOT_PROFILE = "pilot"
PILOT_ARGV = ("--host", HOST, "--port", str(PORT), "--workers", "1")


def uvicorn_config() -> Dict[str, Any]:
    """The fixed server settings (no reload, no access log)."""

    return {
        "app": APP,
        "host": HOST,
        "port": PORT,
        "reload": False,
        "access_log": False,
        "proxy_headers": False,
        "server_header": False,
    }


def main() -> int:
    for path in (str(BACKEND_DIR), str(CONTAINER_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)
    import ollama_relay

    try:
        server = ollama_relay.bind()
    except OSError:
        print("The Ollama relay could not listen on 127.0.0.1:11434; the service was not started.", file=sys.stderr)
        return 1
    threading.Thread(target=ollama_relay.serve, args=(server,), name="ollama-relay", daemon=True).start()

    if os.environ.get("MANIJERO_DEPLOYMENT_PROFILE") == PILOT_PROFILE:
        return _serve_pilot()

    import uvicorn

    uvicorn.run(**uvicorn_config())
    return 0


def _serve_pilot() -> int:
    """Start the pilot launcher on the container address; it returns 2 when it refuses."""

    os.environ["MANIJERO_PILOT_ALLOW_PUBLIC_BIND"] = "1"  # this process only; the host publish is loopback
    sys.path.insert(0, str(BACKEND_DIR / "scripts"))
    import serve_pilot

    return serve_pilot.main(list(PILOT_ARGV))


if __name__ == "__main__":
    raise SystemExit(main())
