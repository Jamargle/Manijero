"""The hosted knowledge review owner commands through ``./scripts/init.sh``.

The owner guide (``docs/owner-guide/knowledge-review-pull-requests.md``) replaces a manual
walkthrough with this test: every documented command is run through ``scripts/init.sh``
exactly as the guide writes it, with one missing-prerequisite case and one recovery.

Each run uses a temporary repository clone whose ``origin`` is a local bare repository, a
fake ``gh`` (a Python script that records its arguments and returns canned JSON), and a
temporary review home. The real offline evaluator runs as a child over fixture knowledge
files. No test calls GitHub or the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.review_package import prepare

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
INIT = REPO_ROOT / "scripts" / "init.sh"
GUIDE = REPO_ROOT / "docs" / "owner-guide" / "knowledge-review-pull-requests.md"
RULESET_FILE = REPO_ROOT / "backend" / "deploy" / "github" / "protected-main-ruleset.json"
FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "change_impact"
VENV_PYTHON = BACKEND_ROOT / ".venv" / "bin" / "python"
COMMANDS = ["--knowledge-review-open", "--knowledge-review-protect"]
REVIEWER = "Ana Revisora"
AUTHOR = "fixture-prep-author"
AS_OF = date(2099, 10, 27)
SUCCESS_ID = "7825dfd2af88508fc05c2e393052def95604929145ccd2f2771f71bb30936814"
NEW_SOURCE = "fixture-rd-2200-2099"
NEW_PASSAGE = "fixture-pasaje-rd-2200-art-1"
PR_URL = "https://github.com/owner/repo/pull/7"

pytestmark = pytest.mark.skipif(
    not os.access(VENV_PYTHON, os.X_OK),
    reason="needs the linked shared backend/.venv (./scripts/init.sh --setup-python)",
)

FAKE_GH = """#!{python}
import json, os, sys
from pathlib import Path

argv = sys.argv[1:]
log = Path(os.environ["FAKE_GH_LOG"])
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(argv) + "\\n")
state = json.loads(Path(os.environ["FAKE_GH_STATE"]).read_text(encoding="utf-8"))
if argv[:2] == ["auth", "status"]:
    raise SystemExit(0 if state.get("auth", True) else 1)
if argv[:2] == ["pr", "create"]:
    body = Path(argv[argv.index("--body-file") + 1]).read_text(encoding="utf-8")
    Path(os.environ["FAKE_GH_BODY"]).write_text(body, encoding="utf-8")
    print(state["url"])
    raise SystemExit(0)
if argv[:2] == ["pr", "view"]:
    print(json.dumps(state["pr"]))
    raise SystemExit(0)
if argv[0] == "api":
    if argv[1] == "--method":
        payload = Path(argv[argv.index("--input") + 1]).read_text(encoding="utf-8")
        Path(os.environ["FAKE_GH_PUT"]).write_text(payload, encoding="utf-8")
        print("{{}}")
        raise SystemExit(0)
    if argv[1].endswith("/rulesets"):
        print(json.dumps(state["rulesets"]))
        raise SystemExit(0)
    print(json.dumps(state["ruleset"]))
    raise SystemExit(0)
raise SystemExit(64)
"""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def proposal_of(fixtures, candidate_id=SUCCESS_ID):
    record = json.loads((fixtures / "ingestion-state.json").read_text(encoding="utf-8"))[
        "candidates"
    ][candidate_id]
    return {
        "schema_version": "knowledge-update-proposal-v1",
        "summary": "Añade el Real Decreto sintético 2200/2099.",
        "author": {"identity": AUTHOR, "kind": "human"},
        "candidates": [{"candidate_id": candidate_id}],
        "catalog": {
            "add": [
                {
                    "id": NEW_SOURCE,
                    "title": record["title"],
                    "issuing_body": record["issuer"],
                    "original_url": record["publication_url"],
                    "published_on": "2099-09-30",
                    "downloaded_on": "2099-10-01",
                    "verified_on": "2099-10-27",
                    "content_sha256": record["original_sha256"],
                    "review_status": "approved",
                    "reviewed_by": "fixture-reviewer",
                    "reviewed_on": "2099-10-27",
                    "lifecycle_status": "current",
                    "critical": False,
                }
            ],
            "update": [],
            "remove": [],
        },
        "passages": {
            "add": [
                {
                    "id": NEW_PASSAGE,
                    "source_id": NEW_SOURCE,
                    "location": "Artículo 1",
                    "text": "Texto sintético de revisión; no afirma ningún plazo real.",
                }
            ],
            "update": [],
            "remove": [],
        },
        "links": [{"source_id": NEW_SOURCE, "candidate_id": candidate_id}],
        "unresolved_questions": ["¿Se mantiene la fecha del procedimiento anterior?"],
    }


class Owner:
    """One temporary owner machine: a clone, a local bare origin, a fake gh."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.repo = tmp_path / "repo"
        self.origin = tmp_path / "origin.git"
        self.review_home = tmp_path / "knowledge-reviews"
        self.state = tmp_path / "gh-state.json"
        self.log = tmp_path / "gh-calls.jsonl"
        self.body = tmp_path / "gh-body.md"
        self.put = tmp_path / "gh-put.json"
        self.fake_gh = self._fake_gh()
        self.git_env = {
            **os.environ,
            "HOME": str(self.home),
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Fixture Owner",
            "GIT_AUTHOR_EMAIL": "owner@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture Owner",
            "GIT_COMMITTER_EMAIL": "owner@example.invalid",
        }
        self._seed_repository()
        self.package_dir, self.package = self._prepare_package()
        self.write_state()

    def _fake_gh(self) -> Path:
        script = self.tmp / "gh"
        script.write_text(FAKE_GH.format(python=sys.executable), encoding="utf-8")
        script.chmod(0o755)
        return script

    def _git(self, *argv: str, cwd: Path | None = None):
        return subprocess.run(
            ["git", *argv],
            cwd=str(cwd or self.repo),
            env=self.git_env,
            capture_output=True,
            text=True,
            check=True,
        )

    def _seed_repository(self) -> None:
        self._git("init", "--bare", "--initial-branch=main", str(self.origin), cwd=self.tmp)
        self.repo.mkdir()
        self._git("init", "--initial-branch=main", cwd=self.repo)
        knowledge = self.repo / "knowledge"
        knowledge.mkdir()
        (knowledge / "source_catalog.json").write_bytes((FIXTURES / "catalog.json").read_bytes())
        (knowledge / "passages.json").write_bytes((FIXTURES / "passages.json").read_bytes())
        (knowledge / "pac_answer_eval.json").write_bytes((FIXTURES / "cases.json").read_bytes())
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self._git("add", "--", ".")
        self._git("commit", "-m", "fixture baseline")
        self._git("remote", "add", "origin", str(self.origin))
        self._git("push", "-u", "origin", "main")

    def _prepare_package(self):
        fixtures = self.tmp / "change_impact"
        shutil.copytree(FIXTURES, fixtures)
        proposal = fixtures / "proposal.json"
        proposal.write_text(canonical(proposal_of(fixtures)), encoding="utf-8")
        result = prepare(
            fixtures / "ingestion-state.json",
            fixtures / "quarantine",
            self.repo / "knowledge" / "source_catalog.json",
            self.repo / "knowledge" / "passages.json",
            proposal,
            [REVIEWER],
            AS_OF,
            self.review_home,
            cases_path=self.repo / "knowledge" / "pac_answer_eval.json",
        )
        assert result["package"]["merge_readiness"] == "ready_for_review"
        return result["package_dir"], result["package"]

    def write_state(self, **overrides) -> None:
        state = {
            "auth": True,
            "url": PR_URL,
            "pr": {"state": "OPEN", "url": PR_URL, "mergedAt": None},
            "rulesets": [{"id": 42, "name": "protected-main"}],
            "ruleset": self.weak_ruleset(),
        }
        state.update(overrides)
        self.state.write_text(json.dumps(state), encoding="utf-8")

    @staticmethod
    def weak_ruleset():
        committed = json.loads(RULESET_FILE.read_text(encoding="utf-8"))
        return {
            "id": 42,
            "name": committed["name"],
            "target": committed["target"],
            "enforcement": "disabled",
            "conditions": {"ref_name": {"include": ["refs/heads/main"]}},
            "rules": [{"type": "non_fast_forward"}],
            "bypass_actors": [
                {"actor_id": 5, "actor_type": "Team", "bypass_mode": "always"}
            ],
        }

    def env(self, gh: Path | None = None) -> dict:
        environment = {
            **self.git_env,
            "MANIJERO_KNOWLEDGE_REVIEW_HOME": str(self.review_home),
            "MANIJERO_GH_CLI": str(gh or self.fake_gh),
            "MANIJERO_HOSTED_REVIEW_REPO": str(self.repo),
            "FAKE_GH_STATE": str(self.state),
            "FAKE_GH_LOG": str(self.log),
            "FAKE_GH_BODY": str(self.body),
            "FAKE_GH_PUT": str(self.put),
        }
        return environment

    def init(
        self,
        mode: str,
        *args: str,
        gh: Path | None = None,
        answer: str | None = None,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(INIT), mode, *args],
            cwd=REPO_ROOT,
            env=self.env(gh),
            input=answer,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

    def gh_calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def bare(self, *argv: str):
        return subprocess.run(
            ["git", "--git-dir=" + str(self.origin), *argv],
            env=self.git_env,
            capture_output=True,
            text=True,
            check=True,
        )


@pytest.fixture
def owner(tmp_path: Path) -> Owner:
    return Owner(tmp_path)


def results(completed: subprocess.CompletedProcess):
    return [line for line in completed.stdout.splitlines() if line.startswith("Result:")]


def one_clean_result(completed: subprocess.CompletedProcess) -> str:
    assert len(results(completed)) == 1 and completed.stdout.splitlines()[-1] == results(completed)[0], completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr
    return results(completed)[0]


def test_the_guide_documents_exactly_the_two_commands() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    assert set(re.findall(r"\./scripts/init\.sh (--knowledge-review-[a-z]+)", text)) == set(COMMANDS)
    assert len(text.splitlines()) <= 60


@pytest.mark.parametrize("mode", COMMANDS)
def test_an_extra_argument_is_misuse(owner: Owner, mode: str) -> None:
    completed = owner.init(mode, "extra")
    assert completed.returncode == 2
    assert completed.stderr.strip() == "Run {} on its own, with nothing after it.".format(mode)
    assert completed.stdout == "" and owner.gh_calls() == []


def test_help_lists_the_two_commands(owner: Owner) -> None:
    completed = subprocess.run(
        [str(INIT), "--help"],
        cwd=REPO_ROOT,
        env=owner.env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0 and all(command in completed.stdout for command in COMMANDS)


def test_the_owner_walkthrough(owner: Owner) -> None:
    head = owner._git("rev-parse", "HEAD").stdout.strip()
    baseline = {
        name: (owner.repo / "knowledge" / name).read_bytes()
        for name in ("source_catalog.json", "passages.json", "pac_answer_eval.json")
    }

    # Missing prerequisite: no gh program. Nothing is pushed or created.
    missing = owner.init("--knowledge-review-open", gh=owner.tmp / "no-gh-here")
    assert missing.returncode == 2, missing.stdout
    assert missing.stdout.splitlines()[0].startswith("The GitHub tool (gh) is not installed.")
    one_clean_result(missing)
    assert not (owner.package_dir / "pull-request.json").exists()
    assert owner.bare("branch", "--list", "knowledge-review/*").stdout.strip() == ""

    # Recovery: the same command now opens exactly one pull request.
    opened = owner.init("--knowledge-review-open")
    assert opened.returncode == 0, opened.stdout
    assert "opened: {}".format(PR_URL) in opened.stdout
    assert one_clean_result(opened) == (
        "Result: 1 review pull request opened. Merge the one you approve on GitHub."
    )
    assert [call[:2] for call in owner.gh_calls()].count(["pr", "create"]) == 1

    branch = "knowledge-review/{}".format(owner.package["package_id"])
    author = owner.bare("log", "-1", "--format=%an <%ae>", branch).stdout.strip()
    committer = owner.bare("log", "-1", "--format=%cn <%ce>", branch).stdout.strip()
    assert author == "Manijero knowledge review <knowledge-review@manijero.invalid>"
    assert committer == "Fixture Owner <owner@example.invalid>"
    changed = owner.bare("diff", "--name-only", "main..{}".format(branch)).stdout.split()
    assert sorted(changed) == [
        "knowledge/passages.json",
        "knowledge/reviews/{}/REVIEW.md".format(owner.package["package_id"]),
        "knowledge/reviews/{}/package.json".format(owner.package["package_id"]),
        "knowledge/source_catalog.json",
    ]
    catalog = owner.bare("show", "{}:knowledge/source_catalog.json".format(branch)).stdout
    passages = owner.bare("show", "{}:knowledge/passages.json".format(branch)).stdout
    assert hashlib.sha256(catalog.encode()).hexdigest() == owner.package["proposal"]["after"]["catalog_sha256"]
    assert hashlib.sha256(passages.encode()).hexdigest() == owner.package["proposal"]["after"]["passages_sha256"]

    # The owner's checkout is byte-unchanged.
    assert owner._git("rev-parse", "HEAD").stdout.strip() == head
    assert owner._git("status", "--porcelain").stdout == ""
    for name, payload in baseline.items():
        assert (owner.repo / "knowledge" / name).read_bytes() == payload

    # The body carries the fixed lines, the real evaluator's counts, and no local path.
    body = owner.body.read_text(encoding="utf-8")
    assert body.splitlines()[:2] == [
        "The owner merges this on GitHub. Nothing goes live on merge: publishing is a separate release step.",
        "Evaluation counts are report-only, not a quality or legal-coverage claim.",
    ]
    assert "## Evaluation results" in body
    assert "| Cases | 4 | 4 |" in body
    assert "## Automated checks" in body and "## Review evidence" in body
    assert str(owner.tmp) not in body

    # Re-running only reads the recorded pull request and never duplicates it.
    pushed_before = owner.bare("rev-parse", branch).stdout.strip()
    creates_before = [call[:2] for call in owner.gh_calls()].count(["pr", "create"])
    owner.write_state(pr={"state": "OPEN", "url": PR_URL, "mergedAt": None})
    again = owner.init("--knowledge-review-open")
    assert again.returncode == 0 and "already open: {}".format(PR_URL) in again.stdout
    one_clean_result(again)
    assert owner.bare("rev-parse", branch).stdout.strip() == pushed_before
    assert [call[:2] for call in owner.gh_calls()].count(["pr", "create"]) == creates_before

    owner.write_state(pr={"state": "MERGED", "url": PR_URL, "mergedAt": "2026-11-10T10:00:00Z"})
    merged = owner.init("--knowledge-review-open")
    assert merged.returncode == 0 and "merged on GitHub" in merged.stdout
    one_clean_result(merged)

    owner.write_state(pr={"state": "CLOSED", "url": PR_URL, "mergedAt": None})
    closed = owner.init("--knowledge-review-open")
    assert closed.returncode == 0 and "closed without merging" in closed.stdout
    one_clean_result(closed)

    # Protect: describe, ask, and send exactly one update that keeps bypass actors.
    committed = json.loads(RULESET_FILE.read_text(encoding="utf-8"))
    owner.write_state()
    protected = owner.init("--knowledge-review-protect", answer="yes\n")
    assert protected.returncode == 0, protected.stdout
    assert "only pull requests can change main" in protected.stdout
    assert one_clean_result(protected) == "Result: main is now protected by protected-main."
    payload = json.loads(owner.put.read_text(encoding="utf-8"))
    assert payload["name"] == "protected-main" and payload["enforcement"] == "active"
    assert payload["conditions"]["ref_name"]["include"] == ["refs/heads/main"]
    assert "ref" not in payload["conditions"]
    assert {rule["type"] for rule in payload["rules"]} == {
        "pull_request",
        "required_status_checks",
        "non_fast_forward",
    }
    assert payload["bypass_actors"] == [{"actor_id": 5, "actor_type": "Team", "bypass_mode": "always"}]
    puts = [call for call in owner.gh_calls() if call[:2] == ["api", "--method"]]
    assert len(puts) == 1

    # Already matching: a documented GET shape, including an extra rule and check ids,
    # still reports "already protected" and sends no update.
    updated = json.loads(json.dumps({**payload, "id": 42}))
    updated["conditions"] = {"ref_name": {"include": ["refs/heads/main"]}}
    for rule in updated["rules"]:
        if rule["type"] == "required_status_checks":
            for check in rule["parameters"]["required_status_checks"]:
                check["integration_id"] = None
    updated["rules"].append({"type": "deletion"})
    owner.write_state(ruleset=updated)
    already = owner.init("--knowledge-review-protect")
    assert already.returncode == 0 and "already protected" in already.stdout
    assert len([call for call in owner.gh_calls() if call[:2] == ["api", "--method"]]) == 1

    # Not confirmed: nothing is sent.
    owner.write_state(ruleset=owner.weak_ruleset())
    stopped = owner.init("--knowledge-review-protect", answer="no\n")
    assert stopped.returncode == 1
    assert any("Nothing was sent." in line for line in stopped.stdout.splitlines())
    assert len([call for call in owner.gh_calls() if call[:2] == ["api", "--method"]]) == 1

    # No ruleset named protected-main: nothing is created.
    owner.write_state(rulesets=[{"id": 1, "name": "other"}])
    absent = owner.init("--knowledge-review-protect", answer="yes\n")
    assert absent.returncode == 2
    assert "no ruleset named protected-main" in absent.stdout
    assert len([call for call in owner.gh_calls() if call[:2] == ["api", "--method"]]) == 1
    assert committed["name"] == "protected-main"


def test_the_walkthrough_never_asks_for_a_merge_or_a_force_push(owner: Owner) -> None:
    assert owner.init("--knowledge-review-open").returncode == 0
    for argv in owner.gh_calls():
        if argv[0] == "auth":
            assert argv[:2] == ["auth", "status"]
        elif argv[0] == "pr":
            assert argv[1] in ("create", "view")
        else:
            endpoint = argv[1] if not argv[1].startswith("--") else argv[3]
            assert endpoint.startswith("repos/owner/repo/rulesets")
        assert "merge" not in argv
        assert "--auto" not in argv and "review" not in argv and "--admin" not in argv
    # The local bare remote is the only destination; the fake gh is the only API.
    assert str(owner.origin) in owner._git("remote", "get-url", "origin").stdout
