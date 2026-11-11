"""Send approved knowledge to QA with one confirmed command, with automatic and one-command rollback.

Operator-only and stdlib-only at import time; the answer service never imports this module.
``deploy`` takes the knowledge merged to ``origin/main`` (fetched read-only, built in a temporary
worktree), runs the quality gate, the embedding build, and the release builder's gates into QA's
own release root, asks for ``yes``, publishes, restarts the QA container on the new release, and
re-checks QA. When those checks fail it goes back to the earlier release by itself; when that
also fails it takes QA off the internet and stops it. ``rollback`` switches to the previous
release the same way. Nothing here deploys on its own, calls ``gh``, pushes, or edits the owner's
checkout or ``knowledge/``. See ``docs/specs/qa_knowledge_deployment.md``.

Messages are fixed English sentences with no token, question, answer, passage, or land value.
External effects go through injected ports (:class:`KnowledgePorts`).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Protocol, Sequence, Tuple
from zoneinfo import ZoneInfo

from app import knowledge_release as kr
from app import local_container as lc
from app import local_rag_bootstrap as bootstrap
from app import local_rag_service as service
from app import qa_deployment as qa

DEPLOY_COMMAND = "./scripts/init.sh --qa-knowledge-deploy"
ROLLBACK_COMMAND = "./scripts/init.sh --qa-knowledge-rollback"
OPERATIONS = ("deploy", "rollback")
SETUP_COMMAND = bootstrap.SETUP_COMMAND

BRANCH = "main"
REMOTE_REF = "origin/main"
IMAGE_RELEASES = "/opt/manijero/knowledge-releases/releases"
SCRATCH_DIR = "work"
DATE_ZONE = "Europe/Madrid"

NOT_SENT = "Result: the approved knowledge was not sent to QA."
NOT_ROLLED_BACK = "Result: QA's knowledge was not rolled back."
NOTHING_NEW = "Result: QA already has the approved knowledge from main; nothing was changed."
NO_EARLIER = "Result: there is no earlier QA knowledge to go back to; nothing was changed."
FIX_AGAIN = "Run this command again."
FIX_DEVELOPER = "A developer must check the new knowledge; send them the log file shown above."
MSG_NOT_RUNNING = "QA is not running."
FIX_START = "Start it with {}".format(qa.DEPLOY_COMMAND)
MSG_NO_FUNNEL = "QA is not shared over the internet (Funnel is not on for QA)."
MSG_NO_HYBRID = "The search software for building knowledge is not installed."
MSG_NO_ORIGIN = "This checkout has no GitHub address (origin) to read the approved knowledge from."
FIX_NO_ORIGIN = "A developer must add the GitHub address (origin) to this checkout."
MSG_FETCH = "The approved knowledge on GitHub could not be fetched."
FIX_FETCH = "Check the internet connection, then run this command again."
MSG_RELEASE_BUSY = "Another command is publishing a knowledge release right now."


# --- Ports --------------------------------------------------------------------------------


class Commands(Protocol):
    def run(self, argv: Sequence[str], cwd: Optional[Path] = None) -> bootstrap.CommandResult: ...


@dataclass
class KnowledgePorts:
    """Every external effect; tests pass fakes."""

    qa: qa.QaPorts
    repo: Path  # the checkout whose ``origin`` is read (never changed)
    git: Commands
    builder: bootstrap.CommandRunner  # runs the worktree's scripts with the two interpreters
    dev_python: str
    hybrid_python: str
    hybrid_ready: Callable[[], bool]
    model_problem: Callable[[], Optional[str]]  # why the pin-verified bge-m3 is not usable, or None
    artifact: Path  # the pin-verified bge-m3 folder

    @property
    def out(self) -> Callable[[str], None]:
        return self.qa.out

    def today(self) -> date:
        return self.qa.clock.now().astimezone(ZoneInfo(DATE_ZONE)).date()


# --- Facts and prerequisites --------------------------------------------------------------


@dataclass
class _Facts:
    tailscale: qa.TailscaleFacts
    docker: str
    settings: Optional[qa.profiles.ProfileSettings] = None
    token: Optional[str] = None
    container: Optional[lc.ContainerInfo] = None
    sha: str = ""


def _root(ports: KnowledgePorts) -> Path:
    return qa.knowledge_root(ports.qa.home)


def _git_ok(ports: KnowledgePorts, *args: str) -> Optional[str]:
    result = ports.git.run(["git", *args], ports.repo)
    return result.stdout.strip() if result.returncode == 0 else None


def _gather(op: str, ports: KnowledgePorts) -> Tuple[_Facts, "qa.Problems"]:
    home = ports.qa.home
    facts = _Facts(tailscale=qa.read_tailscale(ports.qa.tailscale, ports.qa.port), docker=lc.docker_state(ports.qa.docker))
    problems = qa.Problems()
    if facts.docker == lc.DOCKER_MISSING:
        problems.add(lc.MSG_DOCKER_MISSING, lc.FIX_INSTALL_DOCKER)
    elif facts.docker == lc.DOCKER_CLOSED:
        problems.add(lc.MSG_DOCKER_CLOSED, lc.FIX_OPEN_DOCKER)
    else:
        facts.container = qa.qa_container(ports.qa)
        if facts.container is not None and not qa.is_qa_container(facts.container):
            problems.add(qa.MSG_FOREIGN, qa.FIX_FOREIGN)
        elif facts.container is None or not facts.container.running:
            problems.add(MSG_NOT_RUNNING, FIX_START)
    ts = facts.tailscale
    if ts.state == "missing":
        problems.add(qa.MSG_TS_MISSING, qa.FIX_TAILSCALE)
    elif ts.state != "running":
        problems.add(qa.MSG_TS_STOPPED, qa.FIX_TAILSCALE)
    elif ts.funnel != "ours":
        problems.add(MSG_NO_FUNNEL, FIX_START)
    try:
        facts.settings = qa.profiles.read_profile_settings(qa.profiles.QA, home)
    except qa.profiles.ProfileSettingsError as error:
        if error.code == "settings_missing":
            problems.add("QA is not prepared on this computer: the QA settings file does not exist.", qa.FIX_QA_SETUP)
        else:
            problems.add(error.sentence, "Fix the QA settings file as described above, then run this command again.")
    paths = qa.profiles.credential_paths(home, qa.profiles.QA_CLIENT_ID)
    if qa.profiles.check_credentials(paths, qa.profiles.QA_CLIENT_ID) is not None:
        problems.add("The QA access keys are missing or incomplete.", qa.FIX_QA_SETUP)
    else:
        facts.token = qa.profiles.read_token(paths.token)
    if op == "deploy":
        _build_prerequisites(ports, facts, problems)
    if bootstrap.lock_is_held(qa.lock_path(ports.qa)):
        problems.add(qa.MSG_BUSY, service.FIX_WAIT)
    if (_root(ports) / kr.LOCK_NAME).exists():
        problems.add(MSG_RELEASE_BUSY, service.FIX_WAIT)
    if not ports.qa.tty:
        problems.add(qa.MSG_NO_TTY, qa.FIX_NO_TTY)
    return facts, problems


def _build_prerequisites(ports: KnowledgePorts, facts: _Facts, problems: "qa.Problems") -> None:
    if not ports.hybrid_ready():
        problems.add(MSG_NO_HYBRID, "Run {}".format(SETUP_COMMAND))
    reason = ports.model_problem()
    if reason is not None:
        problems.add(reason, "Run {}".format(SETUP_COMMAND))
    if _git_ok(ports, "remote", "get-url", "origin") is None:
        problems.add(MSG_NO_ORIGIN, FIX_NO_ORIGIN)
    elif _git_ok(ports, "fetch", "origin", BRANCH) is None:
        problems.add(MSG_FETCH, FIX_FETCH)
    else:
        facts.sha = _git_ok(ports, "rev-parse", REMOTE_REF) or ""
        if not kr.REVISION_PATTERN.fullmatch(facts.sha):
            problems.add(MSG_FETCH, FIX_FETCH)


# --- Releases -----------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _previous_target(root: Path) -> Optional[str]:
    """The release ``rollback`` goes to: what the latest switch to ``current`` replaced.

    After a rollback this is the release that was rolled back from, so running it again rolls forward.
    """

    try:
        current = kr.current_release_id(root) if (root / kr.RELEASES_DIR).is_dir() else None
        if current is None:
            return None
        events = [event for event in kr.read_log(root) if event.get("release_id") == current]
    except kr.ReleaseError:
        return None
    target = events[-1].get("previous_release_id") if events else None
    return target if isinstance(target, str) else None


def _release_error(error: kr.ReleaseError) -> str:
    code = error.code
    if code == "gate_failed":
        return "the release did not pass its checks"
    if code.startswith("corpus_not_ready"):
        return "the knowledge is not valid for today's date or for the campaign in the QA settings"
    if code == "release_locked":
        return "another command is publishing a knowledge release"
    if code in ("integrity_mismatch", "manifest_invalid", "release_not_found"):
        return "the knowledge release is damaged or missing"
    return "the knowledge release could not be switched"


def _ready_problem(ports: KnowledgePorts, root: Path, release_id: str, as_of: date, campaign: str) -> Optional[str]:
    """Why the prepared release could not be published (the checks ``publish`` makes), without switching."""

    try:
        manifest = kr.verify_release(kr.release_dir(root, release_id))
        if not manifest["gate"]["passed"]:
            return "the release did not pass its checks"
        from app.ask_api import CorpusDocuments
        from app.readiness import evaluate_readiness

        target = kr.release_dir(root, release_id)
        catalog = json.loads((target / kr.CATALOG_FILE).read_text(encoding="utf-8"))
        passages = json.loads((target / kr.PASSAGES_FILE).read_text(encoding="utf-8"))
        verdict = evaluate_readiness(CorpusDocuments(catalog=catalog, passages=passages), as_of, campaign)
    except (kr.ReleaseError, OSError, ValueError):
        return "the knowledge release is damaged or missing"
    if not verdict.ready:
        return "the knowledge is not valid for today's date or for the campaign in the QA settings"
    return None


def _adopt_image_release(ports: KnowledgePorts, facts: _Facts, scratch: Path, campaign: str) -> Optional[str]:
    """Publish the release built into the running image as QA's first release; ``None`` when done."""

    container = facts.container
    release_id = container.labels.get(qa.LABEL_KNOWLEDGE, "") if container is not None else ""
    if not kr.RELEASE_ID_PATTERN.fullmatch(release_id):
        return "the knowledge built into QA's image could not be identified"
    target = scratch / "adopt" / release_id
    target.parent.mkdir(parents=True, exist_ok=True)
    copied = ports.qa.docker.run(
        ["cp", "{}:{}/{}".format(qa.CONTAINER_NAME, IMAGE_RELEASES, release_id), str(target)], lc.DOCKER_TIMEOUT_SECONDS
    )
    if copied.returncode != 0:
        return "the knowledge built into QA's image could not be copied"
    try:
        manifest = kr.verify_release(target)
        built_on = date.fromisoformat(manifest["inputs"]["as_of"])
        root = kr.prepare_root(_root(ports))
        final = root / kr.RELEASES_DIR / release_id
        if not final.exists():
            os.replace(target, final)
        kr.publish(root, release_id, built_on, campaign, ports.qa.clock.now)
    except (kr.ReleaseError, OSError, ValueError, KeyError):
        return "the knowledge built into QA's image could not be verified"
    return None


# --- Worktree and build -------------------------------------------------------------------


@contextmanager
def _scratch(ports: KnowledgePorts) -> Iterator[Path]:
    base = ports.qa.home / SCRATCH_DIR
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="knowledge-", dir=base))
    try:
        yield scratch
    finally:
        ports.git.run(["git", "worktree", "remove", "--force", str(scratch / "tree")], ports.repo)
        ports.git.run(["git", "worktree", "prune"], ports.repo)
        shutil.rmtree(scratch, ignore_errors=True)


@dataclass(frozen=True)
class _Stop:
    """One plain line to show and the short reason for the ``Result:`` line."""

    line: str
    reason: str


def _quality_gate(ports: KnowledgePorts, tree: Path, log: bootstrap.RunLog) -> Optional[_Stop]:
    argv = [ports.dev_python, str(tree / "backend" / "scripts" / "check_quality_gate.py"), "check"]
    code = ports.builder.run(argv, log).returncode
    if code == 0:
        return None
    if code == 1:
        return _Stop(
            "An answer check got worse than the reviewed quality baseline.", "an answer check got worse than the reviewed baseline"
        )
    if code == 2:
        return _Stop(
            "The quality baseline could not be compared with the new knowledge (it is not reviewed, is out of date, or "
            "could not run).",
            "the quality check could not compare the new knowledge",
        )
    return _Stop("The quality check did not finish.", "the quality check did not finish")


def _embeddings(ports: KnowledgePorts, tree: Path, index: Path, as_of: date, campaign: str, log: bootstrap.RunLog) -> Optional[_Stop]:
    knowledge = tree / "knowledge"
    argv = [
        ports.hybrid_python, str(tree / "backend" / "scripts" / "manage_embeddings.py"), "build",
        "--config", str(tree / "backend" / "config" / "bge_m3_embedding.json"),
        "--artifact", str(ports.artifact),
        "--catalog", str(knowledge / kr.CATALOG_FILE),
        "--passages", str(knowledge / kr.PASSAGES_FILE),
        "--as-of", as_of.isoformat(),
        "--active-campaign", campaign,
        "--index", str(index),
    ]
    if ports.builder.run(argv, log).returncode == 0:
        return None
    return _Stop("The search index for the new knowledge could not be built.", "the search index could not be built")


def _prepare(
    ports: KnowledgePorts, tree: Path, index: Path, sha: str, as_of: date, campaign: str, log: bootstrap.RunLog
) -> Tuple[Optional[str], Optional[_Stop]]:
    knowledge = tree / "knowledge"
    argv = [
        ports.hybrid_python, str(tree / "backend" / "scripts" / "knowledge_release.py"), "prepare",
        "--root", str(_root(ports)),
        "--catalog", str(knowledge / kr.CATALOG_FILE),
        "--passages", str(knowledge / kr.PASSAGES_FILE),
        "--cases", str(knowledge / kr.CASES_FILE),
        "--as-of", as_of.isoformat(),
        "--active-campaign", campaign,
        "--code-revision", sha,
        "--reviewed-baseline-revision", sha,
        "--embedding-index", str(index),
        "--with-vector-store",
        "--embedding-config", str(tree / "backend" / "config" / "bge_m3_embedding.json"),
        "--json",
    ]
    result = ports.builder.run(argv, log)
    document = bootstrap.last_json_object(result.stdout)
    release_id = str(document.get("release_id") or "")
    if result.returncode == 0 and document.get("gate") == "passed" and kr.RELEASE_ID_PATTERN.fullmatch(release_id):
        return release_id, None
    if result.returncode == 1 and document.get("gate") == "failed":
        return None, _Stop(
            bootstrap.gate_failure_message(str(document.get("failures", ""))), "the new knowledge did not pass its release checks"
        )
    if result.returncode == 2:
        return None, _Stop("The release builder refused the new knowledge or its approval record.", "the release builder refused the new knowledge")
    return None, _Stop("The release could not be prepared.", "the release could not be prepared")


def _same_knowledge(root: Path, current: str, tree: Path) -> bool:
    try:
        inputs = kr.read_manifest(kr.release_dir(root, current))["inputs"]
        knowledge = tree / "knowledge"
        return (
            inputs["catalog_sha256"] == _sha256(knowledge / kr.CATALOG_FILE)
            and inputs["passages_sha256"] == _sha256(knowledge / kr.PASSAGES_FILE)
            and inputs["cases_sha256"] == _sha256(knowledge / kr.CASES_FILE)
        )
    except (kr.ReleaseError, OSError, KeyError):
        return False


# --- Switching and checking ---------------------------------------------------------------


def _check_served(ports: KnowledgePorts, facts: _Facts, log: bootstrap.RunLog, expected: str) -> Optional[Tuple[str, str]]:
    """Restart QA on its published release and run the QA checks; ``None`` when all pass."""

    assert facts.settings is not None and facts.token is not None
    failure = qa.start_with(ports.qa, facts.settings, facts.token, log, FIX_DEVELOPER)
    if failure is not None:
        return failure
    served = ports.qa.served_release(service.service_url(ports.qa.port), facts.token)
    if served != expected:
        log.write("metrics reported a different knowledge release id")
        return ("QA does not report the knowledge release that was just switched to.", FIX_DEVELOPER)
    address = facts.tailscale.address
    if not qa.wait_public(ports.qa, address):
        return ("The internet address {} does not answer.".format(address), FIX_DEVELOPER)
    return None


def _sentence(text: str) -> str:
    return text.strip().rstrip(".")


def _stop_qa(ports: KnowledgePorts, log: bootstrap.RunLog) -> None:
    """Funnel off first, then remove the QA container: unknown knowledge must not stay reachable."""

    qa.funnel_off(ports.qa)
    qa.remove_ours(ports.qa, log)


def _go_back(ports: KnowledgePorts, facts: _Facts, log: bootstrap.RunLog, target: str, as_of: date, campaign: str) -> bool:
    """Point ``current`` at ``target`` again, restart on it, and check; ``True`` when QA is healthy."""

    try:
        kr.rollback(_root(ports), as_of, campaign, to=target, clock=ports.qa.clock.now)
    except kr.ReleaseError:
        return False
    return _check_served(ports, facts, log, target) is None


def _apply(
    ports: KnowledgePorts, facts: _Facts, log: bootstrap.RunLog, op: str, target: str, running: str, campaign: str
) -> Tuple[str, str]:
    """Switch to ``target``, restart, check. Returns (state, reason): ``ok``, ``refused``, ``restored``,
    ``stopped``, or ``interrupted`` (restored after Ctrl+C)."""

    as_of = ports.today()
    root = _root(ports)
    try:
        if op == "deploy":
            kr.publish(root, target, as_of, campaign, ports.qa.clock.now)
        else:
            kr.rollback(root, as_of, campaign, to=target, clock=ports.qa.clock.now)
    except kr.ReleaseError as error:
        return "refused", _release_error(error)
    try:
        failure = _check_served(ports, facts, log, target)
    except KeyboardInterrupt:
        if not _go_back(ports, facts, log, running, as_of, campaign):
            _stop_qa(ports, log)
        return "interrupted", "the command was stopped with Ctrl+C"
    if failure is None:
        return "ok", ""
    reason = _sentence(failure[0])
    qa.save_logs(ports.qa, log)
    if _go_back(ports, facts, log, running, as_of, campaign):
        return "restored", reason
    _stop_qa(ports, log)
    return "stopped", reason


# --- Deploy -------------------------------------------------------------------------------


def run_deploy(ports: KnowledgePorts) -> int:
    out = ports.out
    out("Checking what QA needs...")
    facts, problems = _gather("deploy", ports)
    if problems:
        return problems.report(out, NOT_SENT)
    try:
        with lc.container_lock(qa.lock_path(ports.qa), qa.MSG_BUSY):
            return _deploy_locked(ports, facts)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(NOT_SENT, service.FIX_WAIT))
        return 1


def _not_sent(ports: KnowledgePorts, stop: _Stop, old: str, log: bootstrap.RunLog) -> int:
    ports.out(stop.line)
    path = log.ensure()
    ports.out("Details are in the log file: {}".format(path))
    ports.out(
        "Result: the approved knowledge was not sent to QA: {}. QA keeps answering from knowledge release {}.".format(
            stop.reason, old
        )
    )
    return 1


def _deploy_locked(ports: KnowledgePorts, facts: _Facts) -> int:
    out = ports.out
    assert facts.settings is not None
    campaign = facts.settings.campaign
    log = qa.open_log(ports.qa, "knowledge-deploy")
    with _scratch(ports) as scratch:
        old = qa.qa_release_id(ports.qa.home)
        if old is None:
            out("Taking over the knowledge QA runs from its image, so there is an earlier version to go back to...")
            problem = _adopt_image_release(ports, facts, scratch, campaign)
            if problem is not None:
                out("QA's image knowledge could not be set up as the first release: {}.".format(problem))
                out("{} Nothing was changed. {}".format(NOT_SENT, FIX_AGAIN))
                return 1
            old = qa.qa_release_id(ports.qa.home) or ""
        tree = scratch / "tree"
        added = ports.git.run(["git", "worktree", "add", "--detach", str(tree), REMOTE_REF], ports.repo)
        if added.returncode != 0:
            return _not_sent(ports, _Stop("The approved knowledge could not be read.", "the approved knowledge could not be read"), old, log)
        short = facts.sha[:7]
        if _same_knowledge(_root(ports), old, tree):
            out(NOTHING_NEW)
            return 0
        out("Checking the approved knowledge from main at {} (this can take several minutes)...".format(short))
        as_of = ports.today()
        index = scratch / "embedding-index.json"
        stop = _quality_gate(ports, tree, log) or _embeddings(ports, tree, index, as_of, campaign, log)
        release_id: Optional[str] = None
        if stop is None:
            release_id, stop = _prepare(ports, tree, index, facts.sha, as_of, campaign, log)
        if stop is None and release_id is not None:
            problem = _ready_problem(ports, _root(ports), release_id, as_of, campaign)
            if problem is not None:
                stop = _Stop("The new knowledge release is not ready for QA: {}.".format(problem), problem)
        if stop is not None or release_id is None:
            return _not_sent(ports, stop or _Stop("The release could not be prepared.", "the release could not be prepared"), old, log)
        if release_id == old:
            out(NOTHING_NEW)
            return 0
        if not qa.confirm(
            ports.qa,
            [
                "The approved knowledge from main at {} passed every check.".format(short),
                "QA will switch from knowledge release {} to {} and restart for about two minutes.".format(old, release_id),
                "The way back is {} (QA also goes back by itself if its checks fail).".format(ROLLBACK_COMMAND),
            ],
        ):
            out("Nothing was changed.")
            out("{} You did not type yes.".format(NOT_SENT))
            return 1
        out("Switching QA to the new knowledge (this can take up to two minutes)...")
        state, reason = _apply(ports, facts, log, "deploy", release_id, old, campaign)
        return _finish_deploy(ports, log, state, reason, release_id, old, short)


def _finish_deploy(
    ports: KnowledgePorts, log: bootstrap.RunLog, state: str, reason: str, new: str, old: str, short: str
) -> int:
    out = ports.out
    if state == "ok":
        out(
            "Result: QA now answers from knowledge release {} (main at {}). If something is wrong, run {}.".format(
                new, short, ROLLBACK_COMMAND
            )
        )
        return 0
    if state == "refused":
        out("The new knowledge could not be published ({}). QA was not changed.".format(reason))
        out(
            "Result: the approved knowledge was not sent to QA: {}. QA keeps answering from knowledge release {}.".format(
                reason, old
            )
        )
        return 1
    out("Details are in the log file: {}".format(log.ensure()))
    if state == "interrupted":
        out("Result: the command was stopped with Ctrl+C, so QA went back to knowledge release {}.".format(old))
        return 1
    if state == "stopped":
        out(
            "Result: the new knowledge failed the QA checks and QA could not go back by itself, so QA was stopped "
            "and is off the internet. Run {}, then {}.".format(ROLLBACK_COMMAND, qa.DEPLOY_COMMAND)
        )
        return 1
    out(
        "Result: the new knowledge failed the QA checks ({}), so QA went back to knowledge release {} "
        "automatically. {}".format(reason, old, FIX_DEVELOPER)
    )
    return 1


# --- Rollback -----------------------------------------------------------------------------


def run_rollback(ports: KnowledgePorts) -> int:
    out = ports.out
    out("Checking what QA needs...")
    facts, problems = _gather("rollback", ports)
    if problems:
        return problems.report(out, NOT_ROLLED_BACK)
    root = _root(ports)
    target = _previous_target(root)
    if target is None:
        out(NO_EARLIER)
        return 1
    try:
        with lc.container_lock(qa.lock_path(ports.qa), qa.MSG_BUSY):
            return _rollback_locked(ports, facts, target)
    except bootstrap.BootstrapError as stop:
        out(stop.message)
        out("{} {}".format(NOT_ROLLED_BACK, service.FIX_WAIT))
        return 1


def _rollback_locked(ports: KnowledgePorts, facts: _Facts, target: str) -> int:
    out = ports.out
    assert facts.settings is not None
    running = qa.qa_release_id(ports.qa.home)
    if running is None:
        out(NO_EARLIER)
        return 1
    if not qa.confirm(
        ports.qa,
        [
            "QA will go back from knowledge release {} to {} and restart for about two minutes.".format(running, target),
            "Running {} again goes forward again.".format(ROLLBACK_COMMAND),
        ],
    ):
        out("Nothing was changed.")
        out("{} You did not type yes.".format(NOT_ROLLED_BACK))
        return 1
    log = qa.open_log(ports.qa, "knowledge-rollback")
    out("Switching QA back (this can take up to two minutes)...")
    state, reason = _apply(ports, facts, log, "rollback", target, running, facts.settings.campaign)
    if state == "ok":
        out("Result: QA was rolled back to knowledge release {}.".format(target))
        return 0
    if state == "refused":
        out("The earlier knowledge could not be switched to ({}). QA was not changed.".format(reason))
        out("{} QA keeps answering from knowledge release {}.".format(NOT_ROLLED_BACK, running))
        return 1
    out("Details are in the log file: {}".format(log.ensure()))
    if state == "interrupted":
        out("Result: the command was stopped with Ctrl+C, so QA went back to knowledge release {}.".format(running))
        return 1
    if state == "stopped":
        out(
            "Result: the earlier knowledge failed the QA checks and QA could not go back by itself, so QA was "
            "stopped and is off the internet. Run {}, then {}.".format(ROLLBACK_COMMAND, qa.DEPLOY_COMMAND)
        )
        return 1
    out(
        "Result: QA's knowledge was not rolled back: the earlier knowledge failed the QA checks ({}), so QA went back "
        "to knowledge release {} automatically. {}".format(reason, running, FIX_DEVELOPER)
    )
    return 1


# --- Real checks --------------------------------------------------------------------------


def model_problem(config: Path, artifact: Path) -> Optional[str]:
    """Why the pin-verified ``bge-m3`` folder is unusable, or ``None`` when it matches its pin."""

    from app.embeddings import EmbeddingError, load_model_spec, verify_artifact

    try:
        spec = load_model_spec(config)
    except EmbeddingError:
        return "The reviewed search-model pin is not valid. A developer must review it."
    if not verify_artifact(artifact, spec).ok:
        return "The search model (bge-m3) on this computer is missing or does not match its reviewed pin."
    return None
