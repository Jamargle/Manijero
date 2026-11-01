"""A fixed TCP relay from the container's loopback Ollama port to Ollama on the host Mac.

The answer service drafts only through the constant ``http://127.0.0.1:11434``
(``app.local_generation.OLLAMA_BASE_URL``), which inside a container is the container
itself. This relay listens on exactly that address inside the container and forwards each
connection byte for byte to the constant ``host.docker.internal:11434`` (Docker Desktop's
name for the host Mac). Both addresses are constants: nothing here reads the environment,
a file, or an argument that could point it anywhere else (owner decision 2026-11-01,
``docs/specs/backend_container_image.md``).

``python ollama_relay.py --check`` asks ``/api/tags`` through the relay and exits ``0``
when Ollama answers, ``1`` otherwise. It prints nothing a user typed.

Stdlib only; the test-only ``listen``/``target`` parameters exist so tests can use two
ephemeral loopback sockets.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import urllib.request
from typing import Optional, Sequence, Tuple

Address = Tuple[str, int]

LISTEN: Address = ("127.0.0.1", 11434)
TARGET: Address = ("host.docker.internal", 11434)

MAX_CONNECTIONS = 32
CONNECT_TIMEOUT_SECONDS = 5.0
CHECK_TIMEOUT_SECONDS = 5.0
CHUNK_BYTES = 65_536
MAX_TAGS_BYTES = 1_048_576


def _pipe(source: socket.socket, sink: socket.socket) -> None:
    """Copy bytes until either side closes, then close both."""

    try:
        while True:
            chunk = source.recv(CHUNK_BYTES)
            if not chunk:
                break
            sink.sendall(chunk)
    except OSError:
        pass
    finally:
        for end in (source, sink):
            try:
                end.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            end.close()


def _relay(client: socket.socket, target: Address, slots: threading.BoundedSemaphore) -> None:
    try:
        try:
            upstream = socket.create_connection(target, timeout=CONNECT_TIMEOUT_SECONDS)
        except OSError:
            client.close()
            return
        upstream.settimeout(None)
        back = threading.Thread(target=_pipe, args=(upstream, client), daemon=True)
        back.start()
        _pipe(client, upstream)
        back.join()
    finally:
        slots.release()


def bind(listen: Address = LISTEN) -> socket.socket:
    """Open the listening socket; raises ``OSError`` when the address cannot be bound."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(listen)
        server.listen(MAX_CONNECTIONS)
    except OSError:
        server.close()
        raise
    return server


def serve(server: socket.socket, target: Address = TARGET, stop: Optional[threading.Event] = None) -> None:
    """Accept connections on ``server`` and forward each to ``target`` (bounded threads)."""

    slots = threading.BoundedSemaphore(MAX_CONNECTIONS)
    server.settimeout(0.5)
    while stop is None or not stop.is_set():
        try:
            client, _ = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        client.settimeout(None)
        if not slots.acquire(blocking=False):
            client.close()
            continue
        threading.Thread(target=_relay, args=(client, target, slots), daemon=True).start()


def check(listen: Address = LISTEN) -> int:
    """``0`` when ``/api/tags`` answers with a model list through the relay, else ``1``."""

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = "http://{}:{}/api/tags".format(*listen)
    try:
        with opener.open(urllib.request.Request(url, method="GET"), timeout=CHECK_TIMEOUT_SECONDS) as response:
            status, raw = response.getcode(), response.read(MAX_TAGS_BYTES + 1)
    except Exception:  # noqa: BLE001 - refused, timeout, HTTP error: Ollama is not reachable
        return 1
    try:
        document = json.loads(raw.decode("utf-8")) if len(raw) <= MAX_TAGS_BYTES else None
    except ValueError:
        return 1
    return 0 if status == 200 and isinstance(document, dict) and isinstance(document.get("models"), list) else 1


def main(argv: Optional[Sequence[str]] = None, listen: Address = LISTEN) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--check"]:
        return check(listen)
    if args:
        print("Usage: ollama_relay.py [--check]", file=sys.stderr)
        return 2
    serve(bind(listen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
