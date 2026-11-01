"""Container entry point: start the fixed Ollama relay, then the unchanged answer service.

Runs as the image's non-root user. The service is ``app.main:app`` in the default profile,
on the container's ``0.0.0.0:8000`` (the host publishes it on ``127.0.0.1`` only), without
reload and without the access log. Every setting comes from the image environment plus
``MANIJERO_ACTIVE_CAMPAIGN`` from ``docker run``; nothing here reads a settings file.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Dict

CONTAINER_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CONTAINER_DIR.parent

APP = "app.main:app"
HOST = "0.0.0.0"  # inside the container only; the host publish is 127.0.0.1
PORT = 8000


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

    import uvicorn

    uvicorn.run(**uvicorn_config())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
