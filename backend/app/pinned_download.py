"""Download the files a reviewed embedding pin names, and nothing else. Stdlib only.

Operator-only: the local setup command (:mod:`app.local_rag_bootstrap`) uses this module;
the answer service never imports it. Every URL is built from the pin alone
(``<source_url>/resolve/<model_revision>/<path>``), so no caller can point a download at
another file or revision. Redirects are followed only to ``https`` addresses.

Each file is streamed into ``<file>.part`` while its SHA-256 is computed, then checked
against the pinned size and digest, and only then renamed into place. A ``.part`` file left
by an interrupted run is resumed with an HTTP ``Range`` request (its bytes are hashed
first, so the final check still covers the whole file). A file that differs from the pin
is deleted and the run fails with a fixed code; the pin is never edited. Files that
already match the pin are never fetched again.

Errors carry fixed codes only: ``download_failed``, ``size_mismatch``,
``checksum_mismatch``, ``redirect_refused``, ``unsafe_path``.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from app.embeddings import (
    ArtifactFile,
    EmbeddingModelSpec,
    safe_relative_path,
    verify_artifact,
)

CHUNK_BYTES = 1 << 20
TIMEOUT_SECONDS = 60.0
PART_SUFFIX = ".part"

DOWNLOAD_FAILED = "download_failed"
SIZE_MISMATCH = "size_mismatch"
CHECKSUM_MISMATCH = "checksum_mismatch"
REDIRECT_REFUSED = "redirect_refused"
UNSAFE_PATH = "unsafe_path"

# progress(path, bytes_done, bytes_total)
Progress = Callable[[str, int, int], None]


class DownloadError(Exception):
    """A pinned download failed; ``code`` is fixed and ``path`` is the pinned path."""

    def __init__(self, code: str, path: Optional[str] = None) -> None:
        super().__init__(code if path is None else "{}: {}".format(path, code))
        self.code = code
        self.path = path


@dataclass(frozen=True)
class PendingFile:
    """One pinned file that is missing or differs, with the bytes still to fetch."""

    path: str
    size: int
    sha256: str
    missing_bytes: int


def file_url(spec: EmbeddingModelSpec, path: str) -> str:
    """The upstream URL of one pinned file, derived only from the pin."""

    base = spec.source_url.rstrip("/")
    return "{}/resolve/{}/{}".format(
        base, spec.model_revision, urllib.parse.quote(path, safe="/")
    )


def pending_files(spec: EmbeddingModelSpec, target_dir: Path) -> Tuple[PendingFile, ...]:
    """Return the pinned files that do not yet match, in pin order.

    ``missing_bytes`` counts what is still to download: the pinned size minus the bytes of
    a resumable ``.part`` file.
    """

    report = verify_artifact(Path(target_dir), spec)
    issue_paths = {issue.path for issue in report.issues}
    everything = "artifact_dir" in issue_paths
    pending: List[PendingFile] = []
    for artifact_file in spec.files:
        if not everything and artifact_file.path not in issue_paths:
            continue
        resumable = _resumable_bytes(Path(target_dir), artifact_file)
        pending.append(
            PendingFile(
                path=artifact_file.path,
                size=artifact_file.size,
                sha256=artifact_file.sha256,
                missing_bytes=artifact_file.size - resumable,
            )
        )
    return tuple(pending)


def fetch_pinned_files(
    spec: EmbeddingModelSpec,
    target_dir: Path,
    opener: Any = None,
    progress: Optional[Progress] = None,
    timeout: float = TIMEOUT_SECONDS,
) -> Tuple[PendingFile, ...]:
    """Fetch every pending pinned file into ``target_dir``; return what was fetched.

    Files already matching the pin are kept untouched. On failure the finished files stay
    in place; a bad file is deleted; an interrupted one keeps its ``.part`` for resuming.
    """

    active_opener = opener if opener is not None else https_opener()
    pending = pending_files(spec, target_dir)
    for item in pending:
        _fetch_one(spec, Path(target_dir), item, active_opener, progress, timeout)
    return pending


def https_opener() -> urllib.request.OpenerDirector:
    """An opener with only an HTTPS handler that refuses redirects to non-HTTPS URLs."""

    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        urllib.request.UnknownHandler(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        urllib.request.HTTPDefaultErrorHandler(),
        HttpsOnlyRedirects(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


class HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when the new address is ``https``."""

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise DownloadError(REDIRECT_REFUSED)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# --- One file ---------------------------------------------------------------------------


def _part_path(target: Path) -> Path:
    return target.with_name(target.name + PART_SUFFIX)


def _target_path(target_dir: Path, path: str) -> Optional[Path]:
    relative = safe_relative_path(path)
    if relative is None:
        return None
    return target_dir / relative


def _resumable_bytes(target_dir: Path, artifact_file: ArtifactFile) -> int:
    target = _target_path(target_dir, artifact_file.path)
    if target is None:
        return 0
    part = _part_path(target)
    try:
        size = part.stat().st_size if part.is_file() and not part.is_symlink() else 0
    except OSError:
        return 0
    return size if size <= artifact_file.size else 0


def _fetch_one(
    spec: EmbeddingModelSpec,
    target_dir: Path,
    item: PendingFile,
    opener: Any,
    progress: Optional[Progress],
    timeout: float,
) -> None:
    target = _target_path(target_dir, item.path)
    if target is None:
        raise DownloadError(UNSAFE_PATH, item.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = _part_path(target)
    if part.is_symlink():
        part.unlink()
    offset = part.stat().st_size if part.is_file() else 0
    if offset > item.size:
        part.unlink()
        offset = 0

    digest = hashlib.sha256()
    if offset:
        _hash_existing(part, digest)
    if offset < item.size:
        offset, digest = _stream(file_url(spec, item.path), part, offset, digest, item, opener, progress, timeout)

    if offset != item.size:
        if offset > item.size:
            _discard(part)
            raise DownloadError(SIZE_MISMATCH, item.path)
        # The connection ended early: keep the part so the next run resumes it.
        raise DownloadError(DOWNLOAD_FAILED, item.path)
    if digest.hexdigest() != item.sha256:
        _discard(part)
        raise DownloadError(CHECKSUM_MISMATCH, item.path)
    os.replace(part, target)


def _stream(
    url: str,
    part: Path,
    offset: int,
    digest: "hashlib._Hash",
    item: PendingFile,
    opener: Any,
    progress: Optional[Progress],
    timeout: float,
) -> Tuple[int, "hashlib._Hash"]:
    headers = {"Range": "bytes={}-".format(offset)} if offset else {}
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        response = opener.open(request, timeout=timeout)
    except DownloadError as error:
        raise DownloadError(error.code, item.path) from None
    except urllib.error.HTTPError as error:
        error.close()
        if error.code == 416 and offset:
            # The server cannot resume this part: start the file again next time.
            _discard(part)
        raise DownloadError(DOWNLOAD_FAILED, item.path) from None
    except (urllib.error.URLError, http.client.HTTPException, OSError, socket.timeout):
        raise DownloadError(DOWNLOAD_FAILED, item.path) from None

    with response:
        status = getattr(response, "status", None) or response.getcode()
        mode = "ab"
        if offset and status != 206:
            # The server ignored the range and sent the whole file: start over.
            offset, digest, mode = 0, hashlib.sha256(), "wb"
        elif offset and not _content_range_starts_at(response, offset):
            _discard(part)
            raise DownloadError(DOWNLOAD_FAILED, item.path)
        elif not offset:
            mode = "wb"
        written = offset
        with part.open(mode) as handle:
            while True:
                try:
                    chunk = response.read(CHUNK_BYTES)
                except (http.client.HTTPException, OSError, socket.timeout):
                    raise DownloadError(DOWNLOAD_FAILED, item.path) from None
                if not chunk:
                    break
                written += len(chunk)
                if written > item.size:
                    break
                handle.write(chunk)
                digest.update(chunk)
                if progress is not None:
                    progress(item.path, written, item.size)
    return written, digest


def _content_range_starts_at(response: Any, offset: int) -> bool:
    headers = getattr(response, "headers", None)
    value = headers.get("Content-Range") if headers is not None else None
    return isinstance(value, str) and value.strip().startswith("bytes {}-".format(offset))


def _hash_existing(part: Path, digest: "hashlib._Hash") -> None:
    with part.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)


def _discard(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
