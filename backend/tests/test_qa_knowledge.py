"""QA knowledge deployment: deploy, automatic way back, and rollback with in-memory fakes.

Offline: no Docker, Tailscale, GitHub, model, or network. The QA home is a temporary folder made
by the real QA settings template and key maker (fake tokens only). Git, the release builder,
Docker, the probes, and the clock are fakes; the release root, release log, and publish/rollback
are the real :mod:`app.knowledge_release` over fixture copies of ``knowledge/``.
"""

from __future__ import annotations

import dataclasses
import fcntl
import json
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Sequence

import pytest

import test_qa_deployment as base
from app import environment_profiles as profiles
from app import knowledge_release as kr
from app import local_container as lc
from app import local_rag_bootstrap as lrb
from app import local_rag_service as svc
from app import qa_deployment as qa
from app import qa_knowledge as qk

REPO_KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"
FILES = ("source_catalog.json", "passages.json", "pac_answer_eval.json")
AS_OF = date(2026, 10, 13)
CAMPAIGN = "2026"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHORT_B = SHA_B[:7]


class DayClock(base.FakeClock):
    def now(self) -> datetime:
        return datetime(2026, 10, 13, 10, 0, 0, tzinfo=timezone.utc)


def _knowledge_copy(target: Path, title_suffix: str = "") -> Path:
    target.mkdir(parents=True)
    for name in FILES:
        shutil.copy(REPO_KNOWLEDGE / name, target / name)
    if title_suffix:
        document = json.loads((target / FILES[0]).read_text(encoding="utf-8"))
        document["sources"][0]["title"] += title_suffix
        (target / FILES[0]).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _prepare(root: Path, source: Path, revision: str) -> kr.PrepareResult:
    return kr.prepare_release(
        root=root,
        catalog=source / FILES[0],
        passages=source / FILES[1],
        cases=source / FILES[2],
        as_of=AS_OF,
        active_campaign=CAMPAIGN,
        code_revision=revision,
        reviewed_baseline_revision=revision,
    )


class FakeGit:
    def __init__(self, knowledge: Path) -> None:
        self.knowledge = knowledge
        self.calls: List[List[str]] = []
        self.has_origin = True
        self.fetch_ok = True
        self.trees: List[Path] = []
        self.on_call: Callable[[str], None] = lambda text: None

    def run(self, argv: Sequence[str], cwd: Optional[Path] = None) -> lrb.CommandResult:
        args = [str(part) for part in argv]
        self.calls.append(args)
        self.on_call("git " + " ".join(args[1:3]))
        words = args[1:]
        if words[:3] == ["remote", "get-url", "origin"]:
            return lrb.CommandResult(0, "git@example.invalid:owner/repo.git\n") if self.has_origin else lrb.CommandResult(2)
        if words[:3] == ["fetch", "origin", "main"]:
            return lrb.CommandResult(0) if self.fetch_ok else lrb.CommandResult(128, "", "no network")
        if words == ["rev-parse", "origin/main"]:
            return lrb.CommandResult(0, SHA_B + "\n")
        if words[:3] == ["worktree", "add", "--detach"]:
            tree = Path(words[3])
            shutil.copytree(self.knowledge, tree / "knowledge")
            self.trees.append(tree)
            return lrb.CommandResult(0)
        if words[:2] == ["worktree", "remove"]:
            shutil.rmtree(words[-1], ignore_errors=True)
            return lrb.CommandResult(0)
        return lrb.CommandResult(0)


def _option(argv: Sequence[str], name: str) -> str:
    return str(argv[list(argv).index(name) + 1])


class FakeBuilder:
    """Stands in for the three builder scripts; ``prepare`` runs the real release builder without vectors."""

    def __init__(self) -> None:
        self.calls: List[List[str]] = []
        self.gate_code = 0
        self.embed_code = 0
        self.prepare_mode = "ok"  # ok | gate_failed | refused | crash
        self.on_call: Callable[[str], None] = lambda text: None

    def run(self, argv: Sequence[str], log: lrb.RunLog) -> lrb.CommandResult:
        args = [str(part) for part in argv]
        self.calls.append(args)
        name = Path(args[1]).name
        self.on_call(name)
        if name == "check_quality_gate.py":
            return lrb.CommandResult(self.gate_code)
        if name == "manage_embeddings.py":
            if self.embed_code == 0:
                Path(_option(args, "--index")).write_text("{}", encoding="utf-8")
            return lrb.CommandResult(self.embed_code)
        assert name == "knowledge_release.py" and args[2] == "prepare"
        if self.prepare_mode == "gate_failed":
            return lrb.CommandResult(1, json.dumps({"gate": "failed", "failures": "evaluation_regression:x", "release_id": "0" * 16}))
        if self.prepare_mode == "refused":
            return lrb.CommandResult(2, "", "approval_evidence_invalid")
        if self.prepare_mode == "crash":
            return lrb.CommandResult(70, "", "boom")
        result = kr.prepare_release(
            root=Path(_option(args, "--root")),
            catalog=Path(_option(args, "--catalog")),
            passages=Path(_option(args, "--passages")),
            cases=Path(_option(args, "--cases")),
            as_of=date.fromisoformat(_option(args, "--as-of")),
            active_campaign=_option(args, "--active-campaign"),
            code_revision=_option(args, "--code-revision"),
            reviewed_baseline_revision=_option(args, "--reviewed-baseline-revision"),
        )
        document = {"gate": "passed" if result.passed else "failed", "release_id": result.release_id, "failures": ",".join(result.failures)}
        return lrb.CommandResult(0 if result.passed else 1, json.dumps(document) + "\n")


class KH:
    """One QA that runs from its image, plus fakes for everything the knowledge command touches."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp = tmp_path
        self.h = h = base.Harness(tmp_path, monkeypatch)
        h.clock = DayClock()
        image_root = tmp_path / "image-root"
        image_knowledge = _knowledge_copy(tmp_path / "knowledge-image")
        self.new_knowledge = _knowledge_copy(tmp_path / "knowledge-new", " (revisado)")
        self.image_id = _prepare(image_root, image_knowledge, SHA_A).release_id
        self.image_dir = image_root / kr.RELEASES_DIR / self.image_id
        h.docker.add_image(lc.LOCAL_TAG, "sha256:one", release=self.image_id)
        self.git = FakeGit(self.new_knowledge)
        self.builder = FakeBuilder()
        self.cp_code = 0
        self.metrics_calls: List[str] = []
        self.bad: Callable[[Optional[str]], Optional[str]] = lambda current: None  # current -> failure kind
        self.hybrid = True
        self.model: Optional[str] = None
        self.events: List[str] = []
        docker_run = h.docker.run

        def run(args: Sequence[str], timeout: float) -> lrb.CommandResult:
            args = [str(a) for a in args]
            self.events.append("docker " + args[0])
            if args[0] == "cp":
                h.docker.calls.append(args)
                if self.cp_code:
                    return lrb.CommandResult(self.cp_code, "", "no such path")
                assert args[1] == "{}:{}/{}".format(qa.CONTAINER_NAME, qk.IMAGE_RELEASES, self.image_id)
                shutil.copytree(self.image_dir, args[2])
                return lrb.CommandResult(0)
            result = docker_run(args, timeout)
            if args[0] == "run" and h.docker.container is not None:  # Docker inherits the image's labels
                h.docker.container["labels"].setdefault(lc.LABEL_RELEASE, self.image_id)
            return result

        h.docker.run = run  # type: ignore[method-assign]
        tailscale_run = h.tailscale.run
        h.tailscale.run = lambda args, timeout: (self.events.append("tailscale " + " ".join(map(str, args))), tailscale_run(args, timeout))[1]  # type: ignore[method-assign]
        prompter_ask = h.prompter.ask
        h.prompter.ask = lambda question: (self.events.append("prompt"), prompter_ask(question))[1]  # type: ignore[method-assign]
        self.git.on_call = self.events.append
        self.builder.on_call = self.events.append
        probe_ready = h.probe.ready
        h.probe.ready = lambda port: svc.UNAVAILABLE if self.failing("ready") else probe_ready(port)  # type: ignore[method-assign]
        h.deployed()  # QA runs from its image with Funnel on
        self.events.clear()
        h.docker.calls.clear()

    # -- fakes wired into the ports ------------------------------------------------------

    def current(self) -> Optional[str]:
        return qa.qa_release_id(self.h.home)

    def failing(self, kind: str) -> bool:
        return self.bad(self.current()) == kind

    def _smoke(self, url: str, token: str) -> List[str]:
        self.h.smoke_calls.append((url, token))
        return ["ask_status"] if self.failing("smoke") else []

    def _metrics(self, url: str, token: str) -> Optional[str]:
        assert token == self.h.token and url == "http://127.0.0.1:8100"
        self.metrics_calls.append(url)
        if self.failing("metrics"):
            return "f" * 16
        box = self.h.docker.container
        return box["labels"].get(lc.LABEL_RELEASE) if box is not None else None

    def _public(self, address: str) -> bool:
        return not self.failing("public")

    @property
    def ports(self) -> qk.KnowledgePorts:
        qa_ports = dataclasses.replace(
            self.h.ports, smoke=self._smoke, metrics_release=self._metrics, public=self._public, clock=self.h.clock
        )
        return qk.KnowledgePorts(
            qa=qa_ports,
            repo=self.tmp / "checkout",
            git=self.git,
            builder=self.builder,
            dev_python="dev-python",
            hybrid_python="hybrid-python",
            hybrid_ready=lambda: self.hybrid,
            model_problem=lambda: self.model,
            artifact=self.tmp / "bge-m3",
        )

    def deploy(self) -> int:
        return qk.run_deploy(self.ports)

    def rollback(self) -> int:
        return qk.run_rollback(self.ports)

    def reset(self) -> None:
        self.h.lines.clear()
        self.h.docker.calls.clear()
        self.h.tailscale.calls.clear()
        self.h.prompter.answers = ["yes"]
        self.h.prompter.asked.clear()
        self.events.clear()

    # -- views ---------------------------------------------------------------------------

    @property
    def root(self) -> Path:
        return qa.knowledge_root(self.h.home)

    def log_events(self) -> List[Dict[str, Any]]:
        return kr.read_log(self.root)

    def served_label(self) -> Optional[str]:
        box = self.h.docker.container
        return box["labels"].get(lc.LABEL_RELEASE) if box is not None else None

    def new_id(self) -> str:
        return next(event["release_id"] for event in self.log_events() if event["release_id"] != self.image_id)

    def deployed_new(self) -> str:
        """Run a successful deploy and return the new release id."""

        self.bad = lambda current: None
        assert self.deploy() == 0
        new = self.current()
        assert new and new != self.image_id
        self.reset()
        return new


@pytest.fixture
def k(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> KH:
    return KH(tmp_path, monkeypatch)


def _sent(new: str) -> str:
    return "Result: QA now answers from knowledge release {} (main at {}). If something is wrong, run ./scripts/init.sh --qa-knowledge-rollback.".format(new, SHORT_B)


# --- Scenarios 1 and 2: deploy and adoption ------------------------------------------------


def test_deploy_adopts_the_image_release_builds_confirms_publishes_and_checks_in_order(k: KH) -> None:
    assert k.deploy() == 0
    new = k.current()
    assert new and new != k.image_id
    assert k.h.result == _sent(new)
    kinds = [event for event in k.events]
    order = [
        "git fetch origin", "git rev-parse origin/main", "docker cp", "git worktree add",
        "check_quality_gate.py", "manage_embeddings.py", "knowledge_release.py", "prompt", "docker rm", "docker run",
    ]
    positions = [kinds.index(name) for name in order]
    assert positions == sorted(positions), kinds
    assert k.h.docker.calls[[call[0] for call in k.h.docker.calls].index("cp")][2].endswith(k.image_id)
    assert [(e["event"], e["release_id"], e["previous_release_id"]) for e in k.log_events()] == [
        ("publish", k.image_id, None),
        ("publish", new, k.image_id),
    ]
    (argv,) = k.h.docker.runs()
    clients = profiles.credential_paths(k.h.home, profiles.QA_CLIENT_ID).clients
    assert argv == qa.run_argv(base.PORT, CAMPAIGN, clients, new, k.root)
    assert k.served_label() == new and k.metrics_calls and k.h.smoke_calls
    assert k.git.trees and not k.git.trees[0].exists()  # the temporary worktree is always removed
    assert not list((k.h.home / "work").iterdir())
    prompt_text = " ".join(line for line in k.h.lines if "switch from" in line)
    assert "{} to {}".format(k.image_id, new) in prompt_text and SHORT_B in "\n".join(k.h.lines)
    assert "./scripts/init.sh --qa-knowledge-rollback" in "\n".join(k.h.lines)


def test_deploy_passes_the_fetched_main_revision_and_the_qa_release_root_to_the_builders(k: KH) -> None:
    assert k.deploy() == 0
    gate, embed, prepare = k.builder.calls
    tree = k.git.trees[0]
    assert gate == ["dev-python", str(tree / "backend" / "scripts" / "check_quality_gate.py"), "check"]
    assert embed[0] == "hybrid-python" and _option(embed, "--artifact") == str(k.tmp / "bge-m3")
    assert _option(prepare, "--root") == str(k.root)
    assert _option(prepare, "--code-revision") == SHA_B == _option(prepare, "--reviewed-baseline-revision")
    assert _option(prepare, "--as-of") == "2026-10-13" and _option(prepare, "--active-campaign") == CAMPAIGN
    assert "--with-vector-store" in prepare and _option(prepare, "--embedding-index") == _option(embed, "--index")
    assert str(tree) in _option(prepare, "--catalog")
    git_words = [call[1] for call in k.git.calls]
    assert not {"push", "commit", "checkout", "reset", "merge", "pull"} & set(git_words)


def test_a_second_deploy_does_not_adopt_again_and_replaces_the_release(k: KH) -> None:
    first = k.deployed_new()
    k.new_knowledge_changed = _knowledge_copy(k.tmp / "knowledge-third", " (otra vez)")
    k.git.knowledge = k.new_knowledge_changed
    assert k.deploy() == 0
    assert not [call for call in k.h.docker.calls if call[0] == "cp"]
    second = k.current()
    assert second not in (first, k.image_id)
    assert k.log_events()[-1]["previous_release_id"] == first


# --- Scenario 2: adoption failures ---------------------------------------------------------


def test_a_failed_copy_of_the_image_release_changes_nothing(k: KH) -> None:
    k.cp_code = 1
    assert k.deploy() == 1
    assert "could not be copied" in k.h.output
    assert k.h.result.startswith(qk.NOT_SENT + " Nothing was changed.")
    assert k.current() is None and not k.builder.calls and not k.h.docker.runs() and not k.h.prompter.asked


def test_an_image_release_that_does_not_verify_is_not_adopted(k: KH) -> None:
    (k.image_dir / "passages.json").write_text("{}", encoding="utf-8")
    assert k.deploy() == 1
    assert "could not be verified" in k.h.output and k.current() is None
    assert not k.builder.calls and not k.h.docker.runs()
    assert not (k.root / kr.RELEASES_DIR / k.image_id).exists() or k.current() is None


# --- Scenario 3: nothing new ---------------------------------------------------------------


def test_nothing_new_builds_nothing_asks_nothing_and_changes_nothing(k: KH) -> None:
    k.git.knowledge = _knowledge_copy(k.tmp / "same", "")
    assert k.deploy() == 0
    assert k.h.result == "Result: QA already has the approved knowledge from main; nothing was changed."
    assert not k.builder.calls and not k.h.prompter.asked and not k.h.docker.runs()
    assert k.current() == k.image_id and not k.git.trees[0].exists()


# --- Scenario 5: a gate fails ---------------------------------------------------------------


def _quality_regression(k: KH) -> None:
    k.builder.gate_code = 1


def _quality_unenforced(k: KH) -> None:
    k.builder.gate_code = 2


def _embeddings_fail(k: KH) -> None:
    k.builder.embed_code = 1


def _prepare_gate_failed(k: KH) -> None:
    k.builder.prepare_mode = "gate_failed"


def _prepare_refused(k: KH) -> None:
    k.builder.prepare_mode = "refused"


def _prepare_crash(k: KH) -> None:
    k.builder.prepare_mode = "crash"


@pytest.mark.parametrize(
    "setup, line, reason",
    [
        (_quality_regression, "got worse than the reviewed quality baseline", "an answer check got worse"),
        (_quality_unenforced, "could not be compared", "the quality check could not compare"),
        (_embeddings_fail, "search index", "the search index could not be built"),
        (_prepare_gate_failed, "did not pass its checks: an answer check got worse", "the new knowledge did not pass its release checks"),
        (_prepare_refused, "refused the new knowledge", "the release builder refused"),
        (_prepare_crash, "could not be prepared", "the release could not be prepared"),
    ],
)
def test_a_failed_gate_publishes_nothing_and_keeps_the_old_release(k: KH, setup: Any, line: str, reason: str) -> None:
    setup(k)
    assert k.deploy() == 1
    assert line in k.h.output
    assert k.h.result == (
        "Result: the approved knowledge was not sent to QA: {}. QA keeps answering from knowledge release {}.".format(
            k.h.result.split(": ", 2)[2].split(". QA keeps")[0], k.image_id
        )
    )
    assert reason in k.h.result
    assert k.current() == k.image_id and not k.h.docker.runs() and not k.h.prompter.asked
    assert k.served_label() == k.image_id and not k.git.trees[0].exists()
    assert [e["release_id"] for e in k.log_events()] == [k.image_id]
    if setup is _quality_regression:
        assert [Path(c[1]).name for c in k.builder.calls] == ["check_quality_gate.py"]


def test_a_release_that_is_not_ready_for_the_campaign_is_never_asked_about(k: KH, monkeypatch: pytest.MonkeyPatch) -> None:
    old = k.deployed_new()
    k.git.knowledge = _knowledge_copy(k.tmp / "knowledge-third", " (otra vez)")
    monkeypatch.setattr(
        qk, "_ready_problem",
        lambda ports, root, release_id, as_of, campaign: "the knowledge is not valid for today's date or for the campaign in the QA settings",
    )
    assert k.deploy() == 1
    assert "not ready for QA" in k.h.output and "not valid for today's date" in k.h.result
    assert k.current() == old and not k.h.prompter.asked and not k.h.docker.runs()


def test_ready_problem_names_a_release_that_the_campaign_does_not_accept(k: KH, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.readiness as readiness

    release = _prepare(k.tmp / "own-root", k.new_knowledge, SHA_B).release_id
    ports = k.ports
    assert qk._ready_problem(ports, k.tmp / "own-root", release, AS_OF, CAMPAIGN) is None
    monkeypatch.setattr(readiness, "evaluate_readiness", lambda documents, as_of, campaign: SimpleNamespace(ready=False, problems=["x"]))
    assert "not valid for today's date" in str(qk._ready_problem(ports, k.tmp / "own-root", release, AS_OF, CAMPAIGN))


# --- Scenario 4: the QA checks and the automatic way back ----------------------------------

FAILURES = {
    "ready": "did not answer within 120 seconds",
    "smoke": "self-check failed (ask_status)",
    "metrics": "does not report the knowledge release",
    "public": "does not answer",
}


@pytest.mark.parametrize("kind", ["ready", "smoke", "metrics", "public", "exited"])
def test_a_failed_check_after_the_switch_goes_back_to_the_old_knowledge_by_itself(k: KH, kind: str) -> None:
    if kind == "exited":
        k.h.docker.exit_at_once = [True]
        k.h.docker.logs = "profile: pilot\nrefused: campaign_invalid\n"
    else:
        k.bad = lambda current: kind if current != k.image_id else None
    assert k.deploy() == 1
    result = k.h.result
    assert result.startswith("Result: the new knowledge failed the QA checks (")
    assert "so QA went back to knowledge release {} automatically.".format(k.image_id) in result
    detail = "campaign in the QA settings file is not valid" if kind == "exited" else FAILURES[kind]
    assert detail in result
    assert k.current() == k.image_id and k.served_label() == k.image_id
    assert k.h.docker.container and k.h.docker.container["running"]
    assert [(e["event"], e["release_id"]) for e in k.log_events()][-1] == ("rollback", k.image_id)
    assert any(call[0] == "logs" for call in k.h.docker.calls)
    logs = list((k.h.home / "logs").glob("qa-knowledge-deploy-*.log"))
    assert logs and "container output" in logs[0].read_text(encoding="utf-8")
    assert not k.h.tailscale.changes()  # the restored QA stays on the internet


def test_if_the_way_back_also_fails_funnel_goes_off_before_qa_is_stopped(k: KH) -> None:
    k.bad = lambda current: "smoke"
    assert k.deploy() == 1
    assert k.h.result == (
        "Result: the new knowledge failed the QA checks and QA could not go back by itself, so QA was stopped and is off "
        "the internet. Run ./scripts/init.sh --qa-knowledge-rollback, then ./scripts/init.sh --qa-deploy."
    )
    off = k.events.index("tailscale funnel --https=443 off")
    assert off < max(i for i, event in enumerate(k.events) if event == "docker rm")
    assert k.h.docker.container is None and k.h.tailscale.funnel_document == {}


def test_if_the_old_release_cannot_be_restored_qa_is_stopped(k: KH) -> None:
    def break_old(current: Optional[str]) -> Optional[str]:
        if current != k.image_id:
            shutil.rmtree(k.root / kr.RELEASES_DIR / k.image_id, ignore_errors=True)
            return "smoke"
        return None

    k.bad = break_old
    assert k.deploy() == 1
    assert "QA was stopped and is off the internet" in k.h.result and k.h.docker.container is None


def test_ctrl_c_during_the_checks_puts_the_old_knowledge_back(k: KH) -> None:
    calls = {"n": 0}

    def smoke(url: str, token: str) -> List[str]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt
        return []

    ports = k.ports
    ports = dataclasses.replace(ports, qa=dataclasses.replace(ports.qa, smoke=smoke))
    assert qk.run_deploy(ports) == 1
    assert k.h.result == "Result: the command was stopped with Ctrl+C, so QA went back to knowledge release {}.".format(k.image_id)
    assert k.current() == k.image_id and k.h.docker.container and k.h.docker.container["running"]


# --- Scenario 7: rollback ------------------------------------------------------------------


def test_rollback_goes_back_and_running_it_again_goes_forward(k: KH) -> None:
    new = k.deployed_new()
    assert k.rollback() == 0
    assert k.h.result == "Result: QA was rolled back to knowledge release {}.".format(k.image_id)
    assert k.current() == k.image_id and k.served_label() == k.image_id
    assert "Switching QA back" in k.h.output and k.metrics_calls
    k.reset()
    assert k.rollback() == 0
    assert k.h.result == "Result: QA was rolled back to knowledge release {}.".format(new)
    assert k.current() == new and k.served_label() == new


def test_rollback_with_no_earlier_release_changes_nothing(k: KH) -> None:
    assert k.rollback() == 1
    assert k.h.result == "Result: there is no earlier QA knowledge to go back to; nothing was changed."
    assert not k.h.docker.runs() and not k.h.prompter.asked
    assert k.deploy() == 0
    # a first publish adopted the image release (no earlier one), the new one has one
    assert qk._previous_target(k.root) == k.image_id


def test_a_failed_rollback_restores_the_release_that_was_running(k: KH) -> None:
    new = k.deployed_new()
    k.bad = lambda current: "smoke" if current == k.image_id else None
    assert k.rollback() == 1
    assert k.h.result.startswith("Result: QA's knowledge was not rolled back: the earlier knowledge failed the QA checks (")
    assert "went back to knowledge release {} automatically".format(new) in k.h.result
    assert k.current() == new and k.served_label() == new


def test_if_the_rollback_cannot_be_restored_either_qa_is_stopped(k: KH) -> None:
    k.deployed_new()
    k.bad = lambda current: "smoke"
    assert k.rollback() == 1
    assert "QA was stopped and is off the internet" in k.h.result and k.h.docker.container is None


# --- Scenario 6: prerequisites -------------------------------------------------------------


def _qa_not_running(k: KH) -> None:
    k.h.docker.container = None


def _funnel_off(k: KH) -> None:
    k.h.tailscale.funnel_document = {}


def _docker_closed(k: KH) -> None:
    k.h.docker.open = False


def _settings_missing(k: KH) -> None:
    (k.h.home / "settings.env").unlink()


def _key_missing(k: KH) -> None:
    profiles.credential_paths(k.h.home, profiles.QA_CLIENT_ID).token.unlink()


def _no_hybrid(k: KH) -> None:
    k.hybrid = False


def _bad_model(k: KH) -> None:
    k.model = "The search model (bge-m3) on this computer is missing or does not match its reviewed pin."


def _no_origin(k: KH) -> None:
    k.git.has_origin = False


def _no_fetch(k: KH) -> None:
    k.git.fetch_ok = False


def _no_tty(k: KH) -> None:
    k.h.tty = False


def _release_lock(k: KH) -> None:
    k.root.mkdir(parents=True, exist_ok=True)
    (k.root / kr.LOCK_NAME).write_text("", encoding="utf-8")


BUILD_ONLY = {_no_hybrid, _bad_model, _no_origin, _no_fetch}

PREREQUISITES = [
    (_qa_not_running, "QA is not running.", "Start it with ./scripts/init.sh --qa-deploy"),
    (_funnel_off, "Funnel is not on for QA", "Start it with ./scripts/init.sh --qa-deploy"),
    (_docker_closed, "Docker Desktop is not open", "Open the Docker Desktop app"),
    (_settings_missing, "QA is not prepared", "Run ./scripts/init.sh --qa-settings-setup"),
    (_key_missing, "access keys are missing", "Run ./scripts/init.sh --qa-settings-setup"),
    (_no_hybrid, "search software", "Run ./scripts/init.sh --local-rag-setup"),
    (_bad_model, "bge-m3", "Run ./scripts/init.sh --local-rag-setup"),
    (_no_origin, "no GitHub address", "A developer must add"),
    (_no_fetch, "could not be fetched", "Check the internet connection"),
    (_release_lock, "publishing a knowledge release", "Wait for the other command"),
    (_no_tty, "no Terminal window", "Run this command in a Terminal window"),
]


@pytest.mark.parametrize("setup, line, fix", PREREQUISITES)
def test_a_missing_prerequisite_changes_nothing_and_names_its_fix(k: KH, setup: Any, line: str, fix: str) -> None:
    setup(k)
    assert k.deploy() == 1
    assert line in k.h.output
    assert k.h.result.startswith(qk.NOT_SENT + " ") and fix in k.h.result
    assert not k.builder.calls and not k.h.docker.runs() and not k.h.prompter.asked
    assert not [call for call in k.h.docker.calls if call[0] in ("rm", "stop", "cp", "run")]
    assert not k.git.trees and k.current() is None


@pytest.mark.parametrize("setup, line, fix", [row for row in PREREQUISITES if row[0] not in BUILD_ONLY])
def test_rollback_checks_the_same_prerequisites_and_reports_them_as_a_rollback(k: KH, setup: Any, line: str, fix: str) -> None:
    k.deployed_new()
    setup(k)
    assert k.rollback() == 1
    assert line in k.h.output and k.h.result.startswith(qk.NOT_ROLLED_BACK + " ") and fix in k.h.result
    assert not k.h.docker.runs() and not k.h.prompter.asked and k.current() != k.image_id


def test_the_build_prerequisites_are_not_needed_to_roll_back(k: KH) -> None:
    k.deployed_new()
    k.hybrid = False
    k.model = "model"
    k.git.has_origin = False
    assert k.rollback() == 0


def test_a_held_qa_lock_is_reported_before_anything_changes(k: KH) -> None:
    handle = os.open(k.h.home / qa.LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert k.deploy() == 1
    finally:
        os.close(handle)
    assert "Another QA command is running" in k.h.output and not k.builder.calls and not k.h.docker.runs()


def test_several_problems_get_one_line_each_and_the_first_fix_ends_the_result(k: KH) -> None:
    _qa_not_running(k)
    _no_hybrid(k)
    _no_tty(k)
    assert k.deploy() == 1
    lines = [line for line in k.h.lines if not line.startswith(("Checking", "Result"))]
    assert len(lines) == 3
    assert k.h.result == qk.NOT_SENT + " Start it with ./scripts/init.sh --qa-deploy"


@pytest.mark.parametrize("answer", ["no", "", None, "y", "yess"])
def test_any_answer_but_yes_changes_nothing(k: KH, answer: Optional[str]) -> None:
    k.h.prompter.answers = [answer]
    assert k.deploy() == 1
    assert "Nothing was changed." in k.h.lines
    assert k.h.result == qk.NOT_SENT + " You did not type yes."
    assert k.current() == k.image_id and not k.h.docker.runs()
    assert not k.git.trees[0].exists()


def test_a_declined_rollback_changes_nothing(k: KH) -> None:
    new = k.deployed_new()
    k.h.prompter.answers = ["no"]
    assert k.rollback() == 1
    assert "Nothing was changed." in k.h.lines and k.h.result == qk.NOT_ROLLED_BACK + " You did not type yes."
    assert k.current() == new and not k.h.docker.runs()


# --- Scenario 9: safety --------------------------------------------------------------------


def test_no_token_or_passage_text_reaches_output_logs_labels_or_the_release_log(k: KH) -> None:
    k.bad = lambda current: "smoke" if current != k.image_id else None
    k.deploy()
    k.reset()
    k.bad = lambda current: None
    k.deploy()
    passages = json.loads((REPO_KNOWLEDGE / "passages.json").read_text(encoding="utf-8"))
    sample = str(next(iter(passages["passages"]))["text"])[:60] if isinstance(passages, dict) and "passages" in passages else ""
    haystacks = [k.h.output]
    for path in (k.h.home / "logs").glob("*"):
        haystacks.append(path.read_text(encoding="utf-8"))
    haystacks.append((k.root / kr.LOG_NAME).read_text(encoding="utf-8"))
    for call in k.h.docker.calls:
        if call[0] == "run":
            haystacks.append(" ".join(a for a in call if a.startswith("org.manijero") or "=" in a and "--" not in a))
    for text in haystacks:
        assert k.h.token not in text
        assert not sample or sample not in text


def test_only_the_qa_container_and_funnel_entry_are_touched(k: KH) -> None:
    k.deploy()
    removes = [call for call in k.h.docker.calls if call[0] == "rm"]
    assert all(call[-1] == qa.CONTAINER_NAME for call in removes)
    assert all(call[0] in ("info", "image", "container", "run", "rm", "logs", "cp") for call in k.h.docker.calls)
    assert not k.h.tailscale.changes()
    assert {call[0] for call in k.git.calls[:0]} == set()
    assert not any("gh" == call[0] for call in k.git.calls)


def test_the_container_additions_are_exactly_the_mount_two_keys_and_the_label(tmp_path: Path) -> None:
    clients = tmp_path / "clients.json"
    root = tmp_path / "knowledge-releases"
    plain = qa.run_argv(8100, "2026", clients)
    with_release = qa.run_argv(8100, "2026", clients, "1234567890abcdef", root)
    stripped = list(with_release)
    for option, value in (
        ("--label", "org.manijero.knowledge-release=1234567890abcdef"),
        ("--env", "MANIJERO_KNOWLEDGE_RELEASE_ROOT=/opt/manijero/qa-knowledge-releases"),
        ("--env", "MANIJERO_VECTOR_STORE=/opt/manijero/qa-knowledge-releases/releases/1234567890abcdef/vector-store"),
        ("--mount", "type=bind,source={},target=/opt/manijero/qa-knowledge-releases".format(root)),
    ):
        position = stripped.index(value)
        assert stripped[position - 1] == option
        del stripped[position - 1 : position + 1]
    assert stripped == plain
    assert "127.0.0.1:8100:8000" in with_release and "--cap-drop" in with_release
    assert "type=bind,source={},target=/run/manijero/pilot-clients.json,readonly".format(clients) in with_release
