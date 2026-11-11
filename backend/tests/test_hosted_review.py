"""Hosted knowledge review pull requests: package gate, body, re-runs, ruleset, and ports.

Fake git, fake gh, and a fake evaluator stand in for every external effect. Nothing here
opens a socket, calls GitHub, or reads the owner's checkout.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app import hosted_review
from app.hosted_review import CommandResult, Ports
from app.review_package import ReviewPackageError, build_after_state, prepare

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "change_impact"
ROOT = Path(__file__).resolve().parents[2]
RULESET_FILE = ROOT / "backend" / "deploy" / "github" / "protected-main-ruleset.json"
REVIEWER = "Ana Revisora"
AUTHOR = "fixture-prep-author"
AS_OF = date(2099, 10, 27)
SUCCESS_ID = "7825dfd2af88508fc05c2e393052def95604929145ccd2f2771f71bb30936814"
AMBIGUOUS_ID = "6fe24ce64b69be1726cd3306283e56e369c9f41011fbd01d60df47a78b6d0857"
NEW_SOURCE = "fixture-rd-2200-2099"
NEW_PASSAGE = "fixture-pasaje-rd-2200-art-1"
PR_URL = "https://github.com/owner/repo/pull/7"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class FakeGit:
    def __init__(self, baseline, *, remote_ok=True, branches=(), push_ok=True):
        self.baseline = dict(baseline)
        self.remote_ok = remote_ok
        self.branches = set(branches)
        self.push_ok = push_ok
        self.calls = []
        self.pushes = []
        self.committed = {}
        self._added = []

    def run(self, argv, *, cwd=None, input_text=None):
        argv = [str(item) for item in argv]
        self.calls.append(argv)
        if argv[:3] == ["remote", "get-url", "origin"]:
            if not self.remote_ok:
                return CommandResult(2, "", "no origin")
            return CommandResult(0, "git@github.com:owner/repo.git\n")
        if argv[:3] == ["worktree", "add", "--detach"]:
            tree = Path(argv[3])
            (tree / "knowledge").mkdir(parents=True, exist_ok=True)
            for relative, payload in self.baseline.items():
                target = tree / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            return CommandResult(0)
        if argv[:2] == ["ls-remote", "--heads"]:
            branch = argv[3].split("refs/heads/", 1)[-1]
            if branch in self.branches:
                return CommandResult(0, "abc123\trefs/heads/{}\n".format(branch))
            return CommandResult(0)
        if argv[0] == "add":
            self._added = list(argv[2:])
            return CommandResult(0)
        if argv[0] == "commit":
            for relative in self._added:
                path = Path(cwd) / relative
                files = [path] if path.is_file() else sorted(path.rglob("*"))
                for file in files:
                    if file.is_file():
                        self.committed[str(file.relative_to(cwd))] = file.read_bytes()
            self._added = []
            return CommandResult(0)
        if argv[0] == "push":
            self.pushes.append(argv)
            return CommandResult(0 if self.push_ok else 1)
        if argv[:2] == ["worktree", "remove"]:
            shutil.rmtree(argv[2], ignore_errors=True)
            return CommandResult(0)
        return CommandResult(0)


class FakeGh:
    def __init__(self, *, auth_ok=True, url=PR_URL, view=None, rulesets=None, ruleset=None, create_ok=True):
        self.auth_ok = auth_ok
        self.url = url
        self.view = view or {}
        self.rulesets = rulesets or []
        self.ruleset = ruleset or {}
        self.create_ok = create_ok
        self.calls = []
        self.body = None
        self.put_body = None

    def run(self, argv, *, cwd=None, input_text=None):
        argv = [str(item) for item in argv]
        self.calls.append(argv)
        if argv[:2] == ["auth", "status"]:
            return CommandResult(0 if self.auth_ok else 1)
        if argv[:2] == ["pr", "create"]:
            self.body = Path(argv[argv.index("--body-file") + 1]).read_text(encoding="utf-8")
            return CommandResult(0 if self.create_ok else 1, self.url + "\n" if self.create_ok else "")
        if argv[:2] == ["pr", "view"]:
            return CommandResult(0, json.dumps(self.view))
        if argv[0] == "api":
            if argv[1] == "--method":
                self.put_body = json.loads(
                    Path(argv[argv.index("--input") + 1]).read_text(encoding="utf-8")
                )
                return CommandResult(0, "{}")
            if argv[1].endswith("/rulesets"):
                return CommandResult(0, json.dumps(self.rulesets))
            return CommandResult(0, json.dumps(self.ruleset))
        return CommandResult(64)


class FakeEvaluator:
    def __init__(self, before, after):
        self.reports = [before, after]
        self.calls = []

    def evaluate(self, *, catalog, passages, cases, as_of):
        self.calls.append((catalog, passages, cases, as_of))
        report = self.reports.pop(0)
        if isinstance(report, Exception):
            raise report
        return report


def row(case_id, *, match=True, actual="answered", source=True, passage=True, expected="answered"):
    return {
        "id": case_id,
        "expected_status": expected,
        "actual_status": actual,
        "expected_state_match": match,
        "source_match": source,
        "passage_match": passage,
    }


def report(rows):
    return {
        "cases": len(rows),
        "expected_state_agreement": sum(1 for item in rows if item["expected_state_match"]),
        "unexpected_answers": sum(
            1 for item in rows if item["actual_status"] == "answered" and item["expected_status"] != "answered"
        ),
        "case_rows": rows,
    }


def record_of(fixtures, candidate_id):
    return json.loads((fixtures / "ingestion-state.json").read_text(encoding="utf-8"))["candidates"][
        candidate_id
    ]


def proposal_of(fixtures, candidate_id=SUCCESS_ID):
    record = record_of(fixtures, candidate_id)
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


def make_package(tmp_path, candidate_id=SUCCESS_ID):
    fixtures = tmp_path / "change_impact"
    shutil.copytree(FIXTURES, fixtures)
    proposal = fixtures / "proposal.json"
    proposal.write_text(canonical(proposal_of(fixtures, candidate_id)), encoding="utf-8")
    workspace = tmp_path / "reviews"
    result = prepare(
        fixtures / "ingestion-state.json",
        fixtures / "quarantine",
        fixtures / "catalog.json",
        fixtures / "passages.json",
        proposal,
        [REVIEWER],
        AS_OF,
        workspace,
        cases_path=fixtures / "cases.json",
    )
    return result["package_dir"], result["package"], fixtures


def baseline_of(fixtures):
    return {
        "knowledge/source_catalog.json": (fixtures / "catalog.json").read_bytes(),
        "knowledge/passages.json": (fixtures / "passages.json").read_bytes(),
        "knowledge/pac_answer_eval.json": (fixtures / "cases.json").read_bytes(),
    }


def make_ports(
    tmp_path,
    *,
    git=None,
    gh=None,
    evaluator=None,
    home=None,
    answers=("yes",),
):
    lines = []
    remaining = list(answers)
    ports = Ports(
        home=Path(home) if home is not None else tmp_path / "reviews",
        repo=ROOT,
        git=git or FakeGit({}),
        gh=gh or FakeGh(),
        evaluator=evaluator
        or FakeEvaluator(report([row("a")]), report([row("a")])),
        clock=lambda: datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc),
        input=lambda: remaining.pop(0) if remaining else "",
        out=lines.append,
    )
    return ports, lines


def ready_ports(tmp_path, fixtures, **overrides):
    git = overrides.pop("git", FakeGit(baseline_of(fixtures)))
    gh = overrides.pop("gh", FakeGh())
    evaluator = overrides.pop("evaluator", None)
    ports, lines = make_ports(tmp_path, git=git, gh=gh, evaluator=evaluator, **overrides)
    return ports, lines, git, gh


def result_line(lines):
    results = [line for line in lines if line.startswith("Result:")]
    assert len(lines) <= 15 and len(results) == 1 and lines[-1] == results[0]
    return results[0]


# --- Scenario 1: a ready package becomes one pull request -----------------------------


def test_a_ready_package_opens_one_pull_request(tmp_path):
    package_dir, package, fixtures = make_package(tmp_path)
    ports, lines, git, gh = ready_ports(tmp_path, fixtures, home=package_dir.parent)

    assert hosted_review.open_reviews(ports) == 0

    assert "opened: {}".format(PR_URL) in lines
    assert result_line(lines) == "Result: 1 review pull request opened. Merge the one you approve on GitHub."
    assert len(git.pushes) == 1
    assert git.pushes[0] == [
        "push",
        "origin",
        "HEAD:refs/heads/knowledge-review/{}".format(package["package_id"]),
    ]
    assert sum(1 for call in gh.calls if call[:2] == ["pr", "create"]) == 1
    create = next(call for call in gh.calls if call[:2] == ["pr", "create"])
    assert create[create.index("--base") + 1] == "main"
    assert create[create.index("--head") + 1] == "knowledge-review/{}".format(package["package_id"])
    assert "merge" not in create and "--auto" not in create

    committed = git.committed
    assert sha(committed["knowledge/source_catalog.json"]) == package["proposal"]["after"]["catalog_sha256"]
    assert sha(committed["knowledge/passages.json"]) == package["proposal"]["after"]["passages_sha256"]
    evidence = "knowledge/reviews/{}".format(package["package_id"])
    assert committed[evidence + "/package.json"] == (package_dir / "package.json").read_bytes()
    assert committed[evidence + "/REVIEW.md"] == (package_dir / "REVIEW.md").read_bytes()
    assert set(committed) == {
        "knowledge/source_catalog.json",
        "knowledge/passages.json",
        evidence + "/package.json",
        evidence + "/REVIEW.md",
    }

    record_path = package_dir / "pull-request.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["url"] == PR_URL
    assert record["branch"] == "knowledge-review/{}".format(package["package_id"])
    assert record_path.stat().st_mode & 0o777 == 0o600
    assert list((package_dir.parent / ".work").iterdir()) == []


def test_the_body_starts_with_the_fixed_lines_and_report_only_counts(tmp_path):
    _, package, fixtures = make_package(tmp_path)
    body = hosted_review.render_pr_body(
        package,
        "# Review\n\nEvidence.\n",
        report(
            [
                row("a", match=False, actual="abstained", source=False, passage=False),
                row("b", expected="abstain", actual="abstain"),
            ]
        ),
        report([row("a"), row("b", expected="abstain", actual="abstain")]),
    )
    assert body.splitlines()[:2] == list(hosted_review.FIXED_BODY_LINES)
    assert "## Evaluation results" in body
    assert "| Expected-state agreement | 1 | 2 |" in body
    assert "| Unexpected answers | 0 | 0 |" in body
    assert "| Source matches (answered cases) | 0 | 1 |" in body
    assert "| Passage matches (answered cases) | 0 | 1 |" in body
    assert "Changed cases: `a`." in body
    assert "## Review evidence" in body and "Evidence." in body


def test_the_body_lists_at_most_twenty_changed_ids_and_is_capped(tmp_path):
    _, package, _ = make_package(tmp_path)
    before = report([row("case-{:02d}".format(index), match=False) for index in range(30)])
    after = report([row("case-{:02d}".format(index)) for index in range(30)])
    body = hosted_review.render_pr_body(package, "x\n" * 40000, before, after)
    assert len(body) <= hosted_review.MAX_BODY_CHARS
    assert "case-19" in body and "case-20" not in body
    assert "Read the full committed review evidence" in body


def test_build_after_state_returns_the_package_after_hashes(tmp_path):
    _, package, fixtures = make_package(tmp_path)
    baseline = baseline_of(fixtures)
    catalog_text, passages_text = build_after_state(
        package,
        baseline["knowledge/source_catalog.json"],
        baseline["knowledge/passages.json"],
        fixtures / "cases.json",
        AS_OF,
    )
    assert sha(catalog_text.encode("utf-8")) == package["proposal"]["after"]["catalog_sha256"]
    assert sha(passages_text.encode("utf-8")) == package["proposal"]["after"]["passages_sha256"]


# --- Scenario 3: re-running reports, never duplicates ---------------------------------


@pytest.mark.parametrize(
    ("view", "expected"),
    [
        ({"state": "OPEN", "url": PR_URL, "mergedAt": None}, "already open: " + PR_URL),
        (
            {"state": "MERGED", "url": PR_URL, "mergedAt": "2026-11-10T10:00:00Z"},
            "merged on GitHub",
        ),
        ({"state": "CLOSED", "url": PR_URL, "mergedAt": None}, "closed without merging"),
    ],
)
def test_a_recorded_pull_request_is_reported_never_duplicated(tmp_path, view, expected):
    package_dir, package, fixtures = make_package(tmp_path)
    (package_dir / "pull-request.json").write_text(
        canonical(
            {
                "schema_version": hosted_review.PULL_REQUEST_VERSION,
                "package_id": package["package_id"],
                "branch": "knowledge-review/" + package["package_id"],
                "url": PR_URL,
                "opened_on": "2026-11-10",
            }
        ),
        encoding="utf-8",
    )
    ports, lines, git, gh = ready_ports(
        tmp_path, fixtures, home=package_dir.parent, gh=FakeGh(view=view)
    )

    assert hosted_review.open_reviews(ports) == 0
    assert any(line.startswith(expected) for line in lines)
    assert git.pushes == [] and not [call for call in gh.calls if call[:2] == ["pr", "create"]]
    assert [call[:2] for call in gh.calls if call[:2] == ["pr", "view"]] == [["pr", "view"]]
    result_line(lines)


def test_a_remote_branch_without_a_record_is_refused(tmp_path):
    package_dir, package, fixtures = make_package(tmp_path)
    git = FakeGit(
        baseline_of(fixtures), branches={"knowledge-review/" + package["package_id"]}
    )
    ports, lines, git, gh = ready_ports(
        tmp_path, fixtures, home=package_dir.parent, git=git
    )

    assert hosted_review.open_reviews(ports) == 1
    assert any("branch exists" in line for line in lines)
    assert git.pushes == [] and not [call for call in gh.calls if call[:2] == ["pr", "create"]]
    result_line(lines)


# --- Scenario 4: unsafe or stale packages are not sent --------------------------------


class SequenceGit(FakeGit):
    """Serve one baseline per worktree, in the order the packages are opened."""

    def __init__(self, baselines, **kwargs):
        super().__init__({}, **kwargs)
        self._queue = list(baselines)

    def run(self, argv, *, cwd=None, input_text=None):
        if [str(item) for item in argv[:3]] == ["worktree", "add", "--detach"]:
            self.baseline = self._queue.pop(0)
        return super().run(argv, cwd=cwd, input_text=input_text)


def test_unsafe_and_stale_packages_are_skipped_while_a_good_one_is_opened(tmp_path):
    good_dir, good, fixtures = make_package(tmp_path / "good")
    baseline = baseline_of(fixtures)
    home = tmp_path / "reviews"
    home.mkdir()
    shutil.copytree(good_dir, home / "a-good")
    ambiguous_dir, ambiguous, _ = make_package(tmp_path / "ambiguous", AMBIGUOUS_ID)
    shutil.copytree(ambiguous_dir, home / "b-ambiguous")
    damaged = home / "c-damaged"
    damaged.mkdir()
    (damaged / "package.json").write_text("{not json\n", encoding="utf-8")
    drift_dir, drift, _ = make_package(tmp_path / "drift")
    shutil.copytree(drift_dir, home / "d-drift")
    drifted = dict(baseline)
    drifted["knowledge/source_catalog.json"] = b'{"schema_version": "changed"}'
    cases_dir, cases, _ = make_package(tmp_path / "cases")
    shutil.copytree(cases_dir, home / "e-cases")
    cases_changed = dict(baseline)
    cases_changed["knowledge/pac_answer_eval.json"] = b'{"schema_version": "changed"}'

    git = SequenceGit([baseline, drifted, cases_changed])
    ports, lines = make_ports(
        tmp_path / "run",
        git=git,
        evaluator=FakeEvaluator(report([row("a")]), report([row("a")])),
        home=home,
    )

    assert hosted_review.open_reviews(ports) == 1
    assert sum(1 for line in lines if line.startswith("opened: ")) == 1
    assert len([line for line in lines if line.startswith("Package ")]) == 4
    assert result_line(lines).startswith("Result: 4 of 5 review packages need attention")
    assert len(git.pushes) == 1
    assert ambiguous["merge_readiness"] == "needs_human_attention"
    assert drift["package_id"] and cases["package_id"] and good["package_id"]


def test_a_failed_evaluation_sends_nothing(tmp_path):
    package_dir, _, fixtures = make_package(tmp_path)
    ports, lines, git, gh = ready_ports(
        tmp_path,
        fixtures,
        home=package_dir.parent,
        evaluator=FakeEvaluator(report([row("a")]), RuntimeError("boom")),
    )

    assert hosted_review.open_reviews(ports) == 1
    assert any("answer evaluation could not run" in line for line in lines)
    assert git.pushes == [] and not [call for call in gh.calls if call[:2] == ["pr", "create"]]
    result_line(lines)


def test_a_failed_push_is_logged_without_a_path_or_token(tmp_path):
    package_dir, _, fixtures = make_package(tmp_path)
    git = FakeGit(baseline_of(fixtures), push_ok=False)
    ports, lines, _, _ = ready_ports(tmp_path, fixtures, home=package_dir.parent, git=git)

    assert hosted_review.open_reviews(ports) == 1
    assert any("could not be sent to GitHub" in line for line in lines)
    log = hosted_review.hosted_review_log(ports.home).read_text(encoding="utf-8")
    assert "push failed (exit 1)" in log
    assert str(tmp_path) not in log


def test_a_failed_pull_request_create_is_logged_without_a_path_or_token(tmp_path):
    package_dir, _, fixtures = make_package(tmp_path)
    gh = FakeGh(create_ok=False)
    ports, lines, git, _ = ready_ports(tmp_path, fixtures, home=package_dir.parent, gh=gh)

    assert hosted_review.open_reviews(ports) == 1
    assert any("could not be created on GitHub" in line for line in lines)
    assert len(git.pushes) == 1
    log = hosted_review.hosted_review_log(ports.home).read_text(encoding="utf-8")
    assert "pull request create failed (exit 1)" in log
    assert str(tmp_path) not in log


# --- Scenario 5: missing prerequisites fail closed ------------------------------------


@pytest.mark.parametrize(
    ("case", "sentence"),
    [
        ("missing-home", "knowledge review folder is missing"),
        ("no-origin", "not connected to a GitHub repository"),
        ("no-login", "not logged in"),
    ],
)
def test_missing_prerequisites_change_nothing(tmp_path, case, sentence):
    git_port = FakeGit({}, remote_ok=case != "no-origin")
    gh_port = FakeGh(auth_ok=case != "no-login")
    home = tmp_path / "missing-home"
    if case != "missing-home":
        home.mkdir()
    ports, lines = make_ports(tmp_path, git=git_port, gh=gh_port, home=home)

    code = hosted_review.open_reviews(ports)
    assert code == 2
    assert any(sentence in line for line in lines)
    assert result_line(lines) == "Result: no review pull request was opened."
    assert git_port.pushes == []
    if case == "missing-home":
        assert gh_port.calls == []


def test_an_absent_gh_program_is_a_missing_prerequisite(tmp_path):
    home = tmp_path / "reviews"
    home.mkdir()
    ports, lines = make_ports(tmp_path, git=FakeGit({}), gh=FakeGh(auth_ok=False), home=home)
    assert hosted_review.open_reviews(ports) == 2
    assert any("not logged in" in line for line in lines)
    result_line(lines)


def test_recovery_after_the_missing_prerequisite_is_fixed(tmp_path):
    package_dir, _, fixtures = make_package(tmp_path)
    git = FakeGit(baseline_of(fixtures))
    missing_gh = FakeGh(auth_ok=False)
    ports, lines = make_ports(tmp_path, git=git, gh=missing_gh, home=package_dir.parent)
    assert hosted_review.open_reviews(ports) == 2

    ports.gh = FakeGh()
    assert hosted_review.open_reviews(ports) == 0
    assert len(git.pushes) == 1


# --- Scenario 6: protect main with the existing ruleset -------------------------------


def _committed():
    return json.loads(RULESET_FILE.read_text(encoding="utf-8"))


def _existing_matching():
    document = _committed()
    document = dict(document)
    document.update({"id": 42, "bypass_actors": [{"actor_id": 5, "actor_type": "Team", "bypass_mode": "always"}]})
    return document


def test_protect_reports_an_already_matching_ruleset(tmp_path):
    ruleset = _existing_matching()
    gh = FakeGh(rulesets=[{"id": 42, "name": "protected-main"}], ruleset=ruleset)
    ports, lines = make_ports(tmp_path, gh=gh)

    assert hosted_review.protect(ports) == 0
    assert "already protected" in lines
    assert result_line(lines) == "Result: main is already protected by protected-main."
    assert gh.put_body is None


def _existing_weak():
    document = _committed()
    return {
        "id": 42,
        "name": document["name"],
        "target": document["target"],
        "enforcement": "disabled",
        "conditions": {"ref_name": {"include": ["refs/heads/main"]}},
        "rules": [{"type": "non_fast_forward"}],
        "bypass_actors": [{"actor_id": 5, "actor_type": "Team", "bypass_mode": "always"}],
    }


def test_protect_stops_without_yes_and_sends_nothing(tmp_path):
    existing = _existing_matching()
    existing["rules"] = [{"type": "non_fast_forward"}]
    gh = FakeGh(rulesets=[{"id": 42, "name": "protected-main"}], ruleset=existing)
    ports, lines = make_ports(tmp_path, gh=gh, answers=("no",))

    assert hosted_review.protect(ports) == 1
    assert any("Nothing was sent. Nothing changed." in line for line in lines)
    assert any("only pull requests can change main" in line for line in lines)
    assert gh.put_body is None
    assert result_line(lines) == "Result: the protection was not changed."


def test_protect_updates_one_ruleset_and_keeps_bypass_actors(tmp_path):
    existing = _existing_matching()
    existing["rules"] = [{"type": "non_fast_forward"}]
    gh = FakeGh(rulesets=[{"id": 42, "name": "protected-main"}], ruleset=existing)
    ports, lines = make_ports(tmp_path, gh=gh, answers=("yes",))

    assert hosted_review.protect(ports) == 0
    assert ports.out is not None
    assert gh.put_body is not None
    assert gh.put_body["bypass_actors"] == existing["bypass_actors"]
    assert gh.put_body["enforcement"] == "active"
    assert gh.put_body["name"] == "protected-main"
    assert gh.put_body["conditions"]["ref_name"]["include"] == ["refs/heads/main"]
    assert "ref" not in gh.put_body["conditions"]
    types = {rule["type"] for rule in gh.put_body["rules"]}
    assert types == {"pull_request", "required_status_checks", "non_fast_forward"}
    pull_request = next(rule for rule in gh.put_body["rules"] if rule["type"] == "pull_request")
    assert pull_request["parameters"]["require_extra_approval_for_unattributed_changes"] is False
    assert any("only pull requests can change main" in line for line in lines)
    assert any("commits GitHub cannot link to an account" in line for line in lines)
    assert any("To undo later" in line for line in lines)
    assert result_line(lines) == "Result: main is now protected by protected-main."
    puts = [call for call in gh.calls if call[:2] == ["api", "--method"]]
    assert len(puts) == 1


def test_protect_creates_nothing_when_the_ruleset_is_missing(tmp_path):
    gh = FakeGh(rulesets=[{"id": 1, "name": "other"}])
    ports, lines = make_ports(tmp_path, gh=gh)

    assert hosted_review.protect(ports) == 2
    assert any("no ruleset named protected-main" in line for line in lines)
    assert result_line(lines) == "Result: nothing was changed because the ruleset is missing."
    assert gh.put_body is None


def _documented_live():
    """A ruleset as GitHub returns it: ref_name, check ids, and an extra rule."""

    document = _existing_matching()
    document["conditions"] = {"ref_name": {"include": ["refs/heads/main"]}}
    rules = []
    for rule in document["rules"]:
        if rule["type"] != "required_status_checks":
            rules.append(rule)
            continue
        parameters = dict(rule["parameters"])
        parameters["required_status_checks"] = [
            {"context": check["context"], "integration_id": None}
            for check in parameters["required_status_checks"]
        ]
        parameters["do_not_enforce_on_create"] = False
        rules.append({**rule, "parameters": parameters})
    document["rules"] = rules + [{"type": "deletion"}]
    return document


def test_the_committed_ruleset_uses_the_documented_ref_name_shape():
    committed = _committed()
    assert "ref_name" in committed["conditions"]
    assert "ref" not in committed["conditions"]
    assert "refs/heads/main" in committed["conditions"]["ref_name"]["include"]
    assert hosted_review._committed_ruleset() == (committed, None)


def test_the_committed_ruleset_needs_no_extra_approval_for_unattributed_commits():
    committed = _committed()
    pull_request = next(rule for rule in committed["rules"] if rule["type"] == "pull_request")
    assert pull_request["parameters"]["require_extra_approval_for_unattributed_changes"] is False


def test_a_live_extra_approval_rule_is_replaced_and_reported_as_a_mismatch():
    committed = _committed()
    live = _documented_live()
    pull_request = next(rule for rule in live["rules"] if rule["type"] == "pull_request")
    pull_request["parameters"]["require_extra_approval_for_unattributed_changes"] = True
    assert not hosted_review.ruleset_matches(live, committed)
    payload = hosted_review.ruleset_payload(live, committed)
    updated = next(rule for rule in payload["rules"] if rule["type"] == "pull_request")
    assert updated["parameters"]["require_extra_approval_for_unattributed_changes"] is False


def test_a_committed_ruleset_without_main_is_refused(tmp_path, monkeypatch):
    target = tmp_path / hosted_review.RULESET_FILE
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "name": "protected-main",
                "target": "branch",
                "enforcement": "active",
                "conditions": {"ref_name": {"include": ["refs/heads/other"]}},
                "rules": [{"type": "non_fast_forward"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(hosted_review, "PACKAGE_ROOT", tmp_path)
    document, problem = hosted_review._committed_ruleset()
    assert document == {} and "does not protect main" in problem


def test_ruleset_match_tolerates_documented_extras_and_ignores_old_ref_shape():
    committed = _committed()
    assert hosted_review.ruleset_matches(_documented_live(), committed)
    assert not hosted_review.ruleset_matches(_existing_weak(), committed)
    old = json.loads(json.dumps(committed))
    old["conditions"] = {"ref": old["conditions"]["ref_name"]}
    assert not hosted_review.ruleset_matches(_documented_live(), old)


def test_ruleset_payload_uses_ref_name_and_keeps_unrelated_live_rules():
    committed = _committed()
    live = _documented_live()
    payload = hosted_review.ruleset_payload(live, committed)
    assert payload["conditions"]["ref_name"]["include"] == ["refs/heads/main"]
    assert "ref" not in payload["conditions"]
    assert payload["bypass_actors"] == live["bypass_actors"]
    types = [rule["type"] for rule in payload["rules"]]
    assert "deletion" in types
    assert types.count("deletion") == 1
    checks = next(
        rule["parameters"]["required_status_checks"]
        for rule in payload["rules"]
        if rule["type"] == "required_status_checks"
    )
    assert [check["context"] for check in checks] == ["fast", "full"]


# --- Scenario 7: never merge, never force, never call GitHub in tests -----------------


def test_recorded_argv_stays_inside_the_allowlist(tmp_path):
    package_dir, package, fixtures = make_package(tmp_path)
    ports, _, git, gh = ready_ports(tmp_path, fixtures, home=package_dir.parent)
    assert hosted_review.open_reviews(ports) == 0

    (package_dir / "pull-request.json").write_text(
        canonical(
            {
                "schema_version": hosted_review.PULL_REQUEST_VERSION,
                "package_id": package["package_id"],
                "branch": "knowledge-review/" + package["package_id"],
                "url": PR_URL,
                "opened_on": "2026-11-10",
            }
        ),
        encoding="utf-8",
    )
    ports.gh = FakeGh(view={"state": "OPEN", "url": PR_URL, "mergedAt": None})
    assert hosted_review.open_reviews(ports) == 0

    protect_gh = FakeGh(
        rulesets=[{"id": 42, "name": "protected-main"}], ruleset=_existing_matching()
    )
    protect_ports = make_ports(tmp_path, gh=protect_gh)[0]
    assert hosted_review.protect(protect_ports) == 0

    for argv in gh.calls + protect_gh.calls:
        if argv[0] == "auth":
            assert argv[:2] == ["auth", "status"]
        elif argv[0] == "pr":
            assert argv[1] in ("create", "view")
        else:
            endpoint = argv[1] if not argv[1].startswith("--") else argv[3]
            assert endpoint.startswith("repos/owner/repo/rulesets")
        joined = " ".join(argv)
        assert "merge" not in joined and "--auto" not in joined
        assert "review" not in argv and "--admin" not in argv

    for argv in git.pushes:
        assert argv[:2] == ["push", "origin"]
        assert not {"--force", "-f", "--force-with-lease", "--delete"} & set(argv)
        assert not argv[-1].startswith("+")


def test_a_damaged_record_is_reported_without_a_github_call(tmp_path):
    package_dir, _, fixtures = make_package(tmp_path)
    (package_dir / "pull-request.json").write_text("{broken", encoding="utf-8")
    ports, lines, git, gh = ready_ports(tmp_path, fixtures, home=package_dir.parent)

    assert hosted_review.open_reviews(ports) == 1
    assert any("record is damaged" in line for line in lines)
    assert git.pushes == [] and not [call for call in gh.calls if call[:2] == ["pr", "view"]]
