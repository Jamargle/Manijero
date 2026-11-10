#!/usr/bin/env python3
"""Download, measure, and switch the optional local reranker. Owner entry point behind ``scripts/init.sh``.

The owner never runs this file directly::

    ./scripts/init.sh --reranker-download   # download the reranker model and check it against the reviewed copy
    ./scripts/init.sh --reranker-measure    # compare it with today's search and print the on/off verdict
    ./scripts/init.sh --reranker-on         # switch it on (refused unless the model checks out)
    ./scripts/init.sh --reranker-off        # switch it off

A developer can also run ``check-pin`` (offline: is the reviewed model record complete?).
Every run prints plain sentences and ends with one ``Result:`` line; nothing here prints a
question, an answer, or a passage. An unexpected error prints one sentence and the path of a
log file; the traceback is only in that file. Exit codes: ``0`` done, ``1`` stopped or failed,
``2`` misuse. Plain-language guide: ``docs/owner-guide/reranker.md``.

Agents never run the real download or measurement; tests inject a fake opener, scorer, and
ports.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import knowledge_release as kr  # noqa: E402  (path setup must run first)
from app import local_rag_bootstrap as bootstrap  # noqa: E402
from app import local_rag_service as service  # noqa: E402
from app import golden_set, pinned_download, reranker, trap_set  # noqa: E402
from app.answer_eval import load_case_document  # noqa: E402
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

REPO_ROOT = bootstrap.REPOSITORY_ROOT
RERUN_DOWNLOAD = "./scripts/init.sh --reranker-download"
RERUN_SETUP = bootstrap.SETUP_COMMAND
START_COMMAND = service.START_COMMAND

LINE_UNPINNED = (
    "Result: the reranker model is not pinned yet. A developer must record it first; nothing was "
    "downloaded."
)
LINE_PIN_INVALID = (
    "Result: the reranker model record is not valid. A developer must fix it; nothing was "
    "downloaded."
)
LINE_ALREADY = (
    "Result: the reranker model is already downloaded and matches the reviewed copy; nothing was "
    "downloaded."
)
LINE_DISK = (
    "Result: there is not enough free disk space for the reranker model. It needs {need} free and "
    "only {free} is free. Free up space (for example, empty the Trash), then run "
    + RERUN_DOWNLOAD
    + " again."
)
LINE_DOWNLOAD_FAILED = (
    "Result: the reranker model download did not finish. Check the internet connection, then run "
    + RERUN_DOWNLOAD
    + " again; it continues where it stopped."
)
LINE_MISMATCH = (
    "Result: a downloaded reranker file is not the reviewed one, so it was not accepted. Run "
    + RERUN_DOWNLOAD
    + " again; if it happens again, send this line to the developer."
)
LINE_REDIRECT = (
    "Result: the download was sent to an address that is not secure, so it was refused. Send this "
    "line to the developer."
)
LINE_NOT_SET_UP = (
    "Result: the reranker setting was not changed because the local settings file does not exist "
    "yet. Run " + RERUN_SETUP + " first."
)
LINE_SETTINGS_BAD = (
    "Result: the reranker setting was not changed. Fix the settings file as described above, then "
    "run the same command again."
)
LINE_ON_REFUSED = (
    "Result: the reranker was not switched on because its model is missing or does not match the "
    "reviewed copy. Run " + RERUN_DOWNLOAD + " first."
)
LINE_PIN_BAD_MEASURE = (
    "Result: the reranker was not measured because the reviewed model record is missing or not "
    "valid. Send this line to the developer."
)
LINE_UNEXPECTED = (
    "Result: the {what} stopped on an unexpected problem. The details are in {log}. Send this line "
    "and that file to the developer."
)


@dataclass
class CommandPorts:
    """Every external effect and path; tests pass fakes and temporary copies."""

    paths: bootstrap.LocalPaths
    disk: Any = field(default_factory=bootstrap.LocalDisk)
    clock: Any = field(default_factory=bootstrap.SystemClock)
    out: Callable[[str], None] = print
    pin_path: Path = reranker.DEFAULT_PIN_PATH
    settings_path: Path = reranker.DEFAULT_SETTINGS_PATH
    embedding_config: Path = kr.DEFAULT_EMBEDDING_CONFIG
    hybrid_config: Path = reranker.BACKEND_ROOT / "config" / "hybrid_retrieval.json"
    knowledge_dir: Path = REPO_ROOT / "knowledge"
    hybrid_python: Path = REPO_ROOT / "backend" / ".venv-hybrid" / "bin" / "python"
    # Test seams: None means the real thing.
    hybrid_loader: Optional[Callable[[], Any]] = None
    service_running: Optional[Callable[[], bool]] = None


def default_ports() -> CommandPorts:
    return CommandPorts(paths=bootstrap.local_paths(), out=lambda text: print(text, flush=True))


def _gigabytes(size: int) -> str:
    return "{:.1f} GB".format(size / bootstrap.GIGABYTE)


# --- check-pin ----------------------------------------------------------------------------------


def _check_pin(args: argparse.Namespace, ports: CommandPorts, **_: Any) -> int:
    path = Path(args.pin) if args.pin else ports.pin_path
    try:
        spec = reranker.load_reranker_spec(path)
    except reranker.RerankerError as error:
        ports.out(str(error))
        return 1
    ports.out(
        "Result: the reranker pin is valid ({} files, {}; revision {}).".format(
            len(spec.files), _gigabytes(spec.total_bytes), spec.model_revision[:12]
        )
    )
    return 0


# --- download -----------------------------------------------------------------------------------


def _download(_: argparse.Namespace, ports: CommandPorts, opener: Any = None, **__: Any) -> int:
    out = ports.out
    try:
        spec = reranker.load_reranker_spec(ports.pin_path)
    except reranker.RerankerError as error:
        out(LINE_UNPINNED if str(error) == "reranker_pin_unpinned" else LINE_PIN_INVALID)
        return 1
    target = ports.paths.reranker
    pending = pinned_download.pending_files(spec, target)
    if not pending:
        out(LINE_ALREADY)
        return 0
    needed = sum(item.missing_bytes for item in pending) + bootstrap.FREE_SPACE_MARGIN_BYTES
    anchor = bootstrap.existing_anchor(target)
    free = ports.disk.free_bytes(anchor)
    if free < needed:
        out(LINE_DISK.format(need=bootstrap.format_size(needed), free=bootstrap.format_size(free)))
        return 1
    out(
        "Downloading the reranker model ({}). If it stops, run the same command again; it continues "
        "where it stopped.".format(_gigabytes(sum(item.missing_bytes for item in pending)))
    )
    progress = bootstrap.DownloadProgress(out)
    try:
        pinned_download.fetch_pinned_files(
            spec,
            target,
            opener=opener if opener is not None else pinned_download.https_opener(),
            progress=progress,
        )
    except pinned_download.DownloadError as error:
        if error.code in (pinned_download.CHECKSUM_MISMATCH, pinned_download.SIZE_MISMATCH):
            out(LINE_MISMATCH)
        elif error.code == pinned_download.REDIRECT_REFUSED:
            out(LINE_REDIRECT)
        else:
            out(LINE_DOWNLOAD_FAILED)
        return 1
    report = spec.verify_artifact(target)
    if not report.ok:
        out(LINE_MISMATCH)
        return 1
    out(
        "Result: the reranker model is downloaded and matches the reviewed copy ({}). It stays off "
        "until it is switched on.".format(_gigabytes(spec.total_bytes))
    )
    return 0


# --- measure ------------------------------------------------------------------------------------


def load_cases(inputs: Any) -> Any:
    """``(catalog, passages, cases)``: approved golden items then approved trap items, tagged by set."""

    from app import reranker_measure as measure

    try:
        catalog = load_catalog(inputs.catalog)
        passages = load_passage_set(inputs.passages)
        base_cases, coverage = load_case_document(inputs.cases, catalog, passages)
        golden = golden_set.load_golden(inputs.golden, catalog, passages, base_cases, coverage)
        approved_golden = golden_set.approved_cases(golden)
        coverage = dict(coverage, areas=coverage["areas"] + golden["additional_areas"])
        traps = trap_set.load_traps(inputs.traps, catalog, passages, base_cases, coverage, golden)
        approved_traps = trap_set.approved_cases(traps)
        identifiers = [case["id"] for case in base_cases + approved_golden + approved_traps]
        if len(identifiers) != len(set(identifiers)) or not 1 <= inputs.k <= 100:
            raise ValueError("ids or k")
    except Exception:  # noqa: BLE001 - one fixed line, never a path or message
        raise measure.MeasureStop(measure.LINE_INPUTS) from None
    cases = [dict(case, case_set=measure.CASE_SET_GOLDEN) for case in approved_golden] + [
        dict(case, case_set=measure.CASE_SET_TRAP) for case in approved_traps
    ]
    return catalog, passages, cases


def _measure(
    _: argparse.Namespace, ports: CommandPorts, scorer: Any = None, **__: Any
) -> int:
    from app import embeddings
    from app import reranker_measure as measure

    out = ports.out
    not_ready = measure.LINE_NOT_READY
    try:
        spec = reranker.load_reranker_spec(ports.pin_path)
        settings = reranker.load_reranker_settings(ports.settings_path)
    except reranker.RerankerError:
        out(LINE_PIN_BAD_MEASURE)
        return 1
    # 1. the hybrid environment, 2. the bge-m3 model, 3. a fresh store (checked by the run).
    if not ports.hybrid_python.exists():
        out(not_ready)
        return 1
    try:
        embedding_spec = embeddings.load_model_spec(ports.embedding_config)
        if not embeddings.verify_artifact(ports.paths.bge_m3, embedding_spec).ok:
            out(not_ready)
            return 1
        owner = bootstrap.read_settings(ports.paths.settings)
        campaign = owner.active_campaign if owner is not None else bootstrap.DEFAULT_CAMPAIGN
        release_id = kr.current_release_id(ports.paths.releases)
    except (embeddings.EmbeddingError, bootstrap.BootstrapError, kr.ReleaseError):
        out(not_ready)
        return 1
    if release_id is None:
        out(not_ready)
        return 1
    store_dir = ports.paths.releases / kr.RELEASES_DIR / release_id / kr.VECTOR_STORE_DIR

    from app.hybrid_retrieval import HybridBackend, load_hybrid_components

    loader = ports.hybrid_loader or (
        lambda: load_hybrid_components(
            ports.embedding_config, ports.paths.bge_m3, store_dir, ports.hybrid_config
        )
    )
    knowledge = ports.knowledge_dir
    inputs = measure.MeasureInputs(
        catalog=knowledge / kr.CATALOG_FILE,
        passages=knowledge / kr.PASSAGES_FILE,
        cases=knowledge / kr.CASES_FILE,
        golden=knowledge / "golden_set.json",
        traps=knowledge / "trap_set.json",
        active_campaign=campaign,
        as_of=ports.clock.now().astimezone().date(),
    )
    scorer_loader = (lambda: scorer) if scorer is not None else (
        lambda: reranker.LocalBgeReranker.load(spec, ports.paths.reranker, settings)
    )
    outcome = measure.run_measurement(
        inputs,
        HybridBackend(loader),
        cases_loader=load_cases,
        reranker_ready=lambda: spec.verify_artifact(ports.paths.reranker).ok,
        scorer_loader=scorer_loader,
        settings=settings,
        out=out,
    )
    out(outcome.line)
    return outcome.exit_code


# --- switch -------------------------------------------------------------------------------------


def _service_running(ports: CommandPorts) -> bool:
    if ports.service_running is not None:
        return ports.service_running()
    record, _ = service.find_running(ports.paths, service.SystemProcesses(), clear=False)
    return record is not None


def _switch(args: argparse.Namespace, ports: CommandPorts, **_: Any) -> int:
    out = ports.out
    state = args.state
    try:
        settings = bootstrap.read_settings(ports.paths.settings)
    except bootstrap.SettingsError as error:
        out(error.message)
        out(LINE_SETTINGS_BAD)
        return 1
    if settings is None:
        out(LINE_NOT_SET_UP)
        return 1
    if state == reranker.STATE_ON:
        try:
            spec = reranker.load_reranker_spec(ports.pin_path)
            verified = spec.verify_artifact(ports.paths.reranker).ok
        except reranker.RerankerError:
            verified = False
        if not verified:
            out(LINE_ON_REFUSED)
            return 1
    bootstrap.write_setting(ports.paths.settings, bootstrap.RERANKER_KEY, state)
    note = " Stop and start the service to use it now." if _service_running(ports) else ""
    out(
        "Result: the reranker is switched {}. It is used from the next {}.{}".format(
            state, START_COMMAND, note
        )
    )
    return 0


# --- entry point --------------------------------------------------------------------------------

COMMAND_NAMES = {"download": "download", "measure": "measurement", "switch": "switch"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-pin", help="offline: is the reviewed model record complete?")
    check.add_argument("--pin", default=None, help="a pin file to check instead of the repository one")
    commands.add_parser("download", help="download the model and verify it")
    commands.add_parser("measure", help="compare with today's hybrid search and print the verdict")
    switch = commands.add_parser("switch", help="write the on/off setting")
    switch.add_argument("state", choices=reranker.STATES)
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    opener: Any = None,
    scorer: Any = None,
    ports: Optional[CommandPorts] = None,
) -> int:
    args = _parser().parse_args(argv)
    active = ports if ports is not None else default_ports()
    handlers = {"check-pin": _check_pin, "download": _download, "measure": _measure, "switch": _switch}
    try:
        return handlers[args.command](args, active, opener=opener, scorer=scorer)
    except KeyboardInterrupt:
        active.out("")
        active.out("Result: stopped with Ctrl+C. Run the same command again when you are ready.")
        return 1
    except Exception:  # noqa: BLE001 - the trace goes to a log file, never to the terminal
        log = active.paths.logs / "reranker-last-error.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        active.out(LINE_UNEXPECTED.format(what=COMMAND_NAMES.get(args.command, "command"), log=log))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
