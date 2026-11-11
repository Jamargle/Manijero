"""Open one ready knowledge review package as a GitHub pull request, and protect main.

Boundaries:

- the tool never merges, never enables auto-merge, never approves, labels, force-pushes,
  deletes a branch, or rewrites history: the owner merges on GitHub;
- every package is published from a temporary detached worktree of ``origin/main``. The
  owner's checkout, branch, and working tree are never written;
- only a ``ready_for_review`` package with no failed check, an intact manifest, a
  baseline equal to ``origin/main``, a matching reviewed case digest, a valid after-state,
  and a working offline evaluation may be sent;
- ``gh`` is used only for ``auth status``, ``pr create``, ``pr view``, and the
  ``protected-main`` ruleset read/update. Tests and checks use a fake ``gh`` and a local
  bare remote; no test reaches GitHub or the network;
- the pull-request body carries counts only (report-only) plus the package's own evidence.
  No local path, token, or exception text reaches the owner output or the body;
- tracebacks go only to ``<review home>/logs/hosted-review.log`` (``0600``).

Standard-library only: the git runner, the ``gh`` runner, the evaluator child, the clock,
the input, and the output are injected ports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from app import review_package
from app.knowledge_ops import _json_text, _private_dir, _write_private

HOME_ENV = "MANIJERO_KNOWLEDGE_REVIEW_HOME"  # tests only
GH_ENV = "MANIJERO_GH_CLI"  # tests only: replaces the gh program
REPO_ENV = "MANIJERO_HOSTED_REVIEW_REPO"  # tests only: the repository the commands act on

BRANCH_PREFIX = "knowledge-review/"
PULL_REQUEST_RECORD = "pull-request.json"
PULL_REQUEST_VERSION = "knowledge-review-pull-request-v1"
RULESET_NAME = "protected-main"
# The ruleset ships with the code, so it is read next to this module rather than from the
# repository the commands act on (the owner may run them from a separate checkout).
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
RULESET_FILE = Path("backend") / "deploy" / "github" / "protected-main-ruleset.json"
CASES_FILE = Path("knowledge") / "pac_answer_eval.json"
CATALOG_FILE = Path("knowledge") / "source_catalog.json"
PASSAGES_FILE = Path("knowledge") / "passages.json"
REVIEWS_DIR = Path("knowledge") / "reviews"
CAMPAIGN = "2026"
MAX_BODY_CHARS = 60000
MAX_CHANGED_CASE_IDS = 20
LOG_NAME = "hosted-review.log"
GIT_NAME = "Manijero knowledge review"
GIT_EMAIL = "knowledge-review@manijero.invalid"
URL_PATTERN = re.compile(r"^https?://\S+$")

FIXED_BODY_LINES = (
    "The owner merges this on GitHub. Nothing goes live on merge: publishing is a separate release step.",
    "Evaluation counts are report-only, not a quality or legal-coverage claim.",
)
READY_COMMAND = "./scripts/init.sh --knowledge-review-open"
PROTECT_COMMAND = "./scripts/init.sh --knowledge-review-protect"


# --- Ports ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Commands(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Optional[Path] = None,
        input_text: Optional[str] = None,
    ) -> CommandResult: ...


class Evaluator(Protocol):
    def evaluate(
        self, *, catalog: Path, passages: Path, cases: Path, as_of: date
    ) -> Mapping[str, Any]: ...


@dataclass
class Ports:
    """Every external effect; tests pass fakes."""

    home: Path
    repo: Path
    git: Commands
    gh: Commands
    evaluator: Evaluator
    clock: Callable[[], datetime]
    input: Callable[[], str]
    out: Callable[[str], None]


def knowledge_review_home(environ: Mapping[str, str]) -> Path:
    raw = (environ.get(HOME_ENV) or "").strip()
    if raw:
        return Path(raw).expanduser()
    home = (environ.get("HOME") or "").strip()
    return (Path(home) if home else Path.home()) / "manijero" / "knowledge-reviews"


def hosted_review_log(home: Path) -> Path:
    return Path(home) / "logs" / LOG_NAME


def append_review_log(home: Path, message: str) -> None:
    """Append one fixed-code diagnostic to the private hosted-review log."""

    path = hosted_review_log(home)
    try:
        _private_dir(path.parent)
        descriptor = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, (message.rstrip() + "\n").encode("utf-8", "replace"))
        finally:
            os.close(descriptor)
    except OSError:
        pass


# --- Public commands --------------------------------------------------------------------------


def open_reviews(ports: Ports) -> int:
    """Open one pull request per ready package; report the rest without changing them."""

    if not ports.home.is_dir():
        return _open_stop(
            ports,
            "The knowledge review folder is missing. Prepare a review package first "
            "with backend/scripts/knowledge_review.py prepare.",
        )
    slug, problem = _repository(ports)
    if problem:
        return _open_stop(ports, problem)
    problem = _github_ready(ports)
    if problem:
        return _open_stop(ports, problem)
    fetched = ports.git.run(["fetch", "origin", "main"], cwd=ports.repo)
    if fetched.returncode != 0:
        return _open_stop(
            ports,
            "The latest knowledge on GitHub could not be fetched. First thing to do: check "
            "the internet connection, then try again.",
        )

    package_dirs = _review_packages(ports.home)
    if not package_dirs:
        ports.out("There are no review packages waiting.")
        ports.out("Result: nothing to open.")
        return 0

    as_of = ports.clock().astimezone(review_package_date_zone()).date()
    failures = 0
    outcomes: List[str] = []
    for package_dir in package_dirs:
        outcome = _open_one(ports, package_dir, slug, as_of)
        if outcome == "failed":
            failures += 1
        outcomes.append(outcome)

    total = len(package_dirs)
    if failures:
        ports.out(
            "Result: {} of {} review packages need attention; nothing was sent for them.".format(
                failures, total
            )
        )
        return 1
    opened = outcomes.count("opened")
    if opened:
        ports.out(
            "Result: {} review pull request{} opened. Merge the one you approve on GitHub.".format(
                opened, "" if opened == 1 else "s"
            )
        )
    else:
        ports.out("Result: nothing new was opened; every package already has a pull request.")
    return 0


def protect(ports: Ports) -> int:
    """Enable the existing ``protected-main`` ruleset from the committed file."""

    slug, problem = _repository(ports)
    if problem:
        return _protect_stop(ports, problem)
    problem = _github_ready(ports)
    if problem:
        return _protect_stop(ports, problem)
    committed, problem = _committed_ruleset()
    if problem:
        return _protect_stop(ports, problem)

    listed = ports.gh.run(["api", "repos/{}/rulesets".format(slug)])
    rulesets = _json_from(listed.stdout)
    if listed.returncode != 0 or not isinstance(rulesets, list):
        return _protect_failed(
            ports, "The GitHub ruleset list could not be read. Check the internet and the "
            "GitHub login, then run {} again.".format(PROTECT_COMMAND)
        )
    found = next(
        (
            item
            for item in rulesets
            if isinstance(item, dict) and item.get("name") == RULESET_NAME
        ),
        None,
    )
    if found is None or not isinstance(found.get("id"), int):
        ports.out(
            "GitHub has no ruleset named {}. Nothing was changed. First thing to do: create "
            "that ruleset on GitHub, then run {} again.".format(RULESET_NAME, PROTECT_COMMAND)
        )
        ports.out("Result: nothing was changed because the ruleset is missing.")
        return 2

    read = ports.gh.run(["api", "repos/{}/rulesets/{}".format(slug, found["id"])])
    existing = _json_from(read.stdout)
    if read.returncode != 0 or not isinstance(existing, dict):
        return _protect_failed(
            ports, "The {!r} ruleset could not be read. Check the internet and the GitHub "
            "login, then run {} again.".format(RULESET_NAME, PROTECT_COMMAND)
        )
    if ruleset_matches(existing, committed):
        ports.out("already protected")
        ports.out("Result: main is already protected by {}.".format(RULESET_NAME))
        return 0

    _describe_protection(ports)
    answer = ports.input()
    if answer.strip().lower() != "yes":
        ports.out("Nothing was sent. Nothing changed.")
        ports.out("Result: the protection was not changed.")
        return 1

    payload = ruleset_payload(existing, committed)
    scratch = Path(tempfile.mkdtemp(prefix="manijero-protect-"))
    try:
        payload_file = scratch / "ruleset.json"
        _write_private(payload_file, _json_text(payload))
        updated = ports.gh.run(
            [
                "api",
                "--method",
                "PUT",
                "repos/{}/rulesets/{}".format(slug, found["id"]),
                "--input",
                str(payload_file),
            ]
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if updated.returncode != 0:
        return _protect_failed(
            ports, "GitHub did not accept the ruleset update. First thing to do: check the "
            "GitHub login and try again."
        )
    ports.out(
        "{} is on: main only changes through pull requests, the checks fast and full must "
        "pass, and force pushes are blocked.".format(RULESET_NAME)
    )
    ports.out("Result: main is now protected by {}.".format(RULESET_NAME))
    return 0


# --- One package ------------------------------------------------------------------------------


def _open_one(ports: Ports, package_dir: Path, slug: str, as_of: date) -> str:
    record_path = Path(package_dir) / PULL_REQUEST_RECORD
    if record_path.exists():
        return _report_existing(ports, slug, record_path)

    try:
        package = review_package.load_package(package_dir)
    except review_package.ReviewPackageError:
        return _package_problem(
            ports,
            package_dir,
            "This review package is damaged. First thing to do: prepare the package again.",
        )
    package_id = package["package_id"]
    if package.get("merge_readiness") != "ready_for_review":
        return _package_problem(
            ports,
            package_dir,
            "This package is not ready for review. First thing to do: finish its open "
            "questions, or prepare a new package.",
        )
    if package.get("check_summary", {}).get("failed"):
        return _package_problem(
            ports,
            package_dir,
            "This package has a failed check. First thing to do: fix the finding, then "
            "prepare a new package.",
        )

    branch = BRANCH_PREFIX + package_id
    remote = ports.git.run(
        ["ls-remote", "--heads", "origin", "refs/heads/" + branch], cwd=ports.repo
    )
    if remote.returncode != 0:
        return _package_problem(
            ports,
            package_dir,
            "GitHub could not be read. First thing to do: check the internet, then run {} "
            "again.".format(READY_COMMAND),
        )
    if remote.stdout.strip():
        return _package_problem(
            ports,
            package_dir,
            "A branch for this package already exists on GitHub (branch exists). First thing "
            "to do: delete or merge that branch, then prepare a new package.",
        )

    work_root = _work_root(ports.home)
    scratch = Path(tempfile.mkdtemp(prefix="package-", dir=work_root))
    worktree = scratch / "tree"
    try:
        outcome = _publish(ports, package_dir, package, slug, branch, as_of, scratch, worktree)
    finally:
        ports.git.run(["worktree", "remove", str(worktree)], cwd=ports.repo)
        shutil.rmtree(scratch, ignore_errors=True)
    return outcome


def _publish(
    ports: Ports,
    package_dir: Path,
    package: Mapping[str, Any],
    slug: str,
    branch: str,
    as_of: date,
    scratch: Path,
    worktree: Path,
) -> str:
    package_id = package["package_id"]
    added = ports.git.run(
        ["worktree", "add", "--detach", str(worktree), "origin/main"], cwd=ports.repo
    )
    if added.returncode != 0:
        return _package_problem(
            ports,
            package_dir,
            "The latest main could not be read. First thing to do: check the internet, then "
            "run {} again.".format(READY_COMMAND),
        )

    baseline_catalog = _read((worktree / CATALOG_FILE))
    baseline_passages = _read((worktree / PASSAGES_FILE))
    if baseline_catalog is None or baseline_passages is None:
        return _package_problem(
            ports,
            package_dir,
            "The approved knowledge could not be read. First thing to do: tell a developer; "
            "the details are in the review log.",
        )
    before = package["proposal"]["before"]
    if (
        _sha256(baseline_catalog) != before["catalog_sha256"]
        or _sha256(baseline_passages) != before["passages_sha256"]
    ):
        return _package_problem(
            ports,
            package_dir,
            "The approved knowledge changed since this package was prepared. First thing to "
            "do: prepare the package again from the current knowledge.",
        )

    cases_path = worktree / CASES_FILE
    review_bytes = _read(package_dir / "REVIEW.md")
    package_bytes = _read(Path(package_dir) / "package.json")
    if review_bytes is None or package_bytes is None:
        return _package_problem(
            ports,
            package_dir,
            "This review package is damaged. First thing to do: prepare the package again.",
        )
    try:
        review_md = review_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return _package_problem(
            ports,
            package_dir,
            "This review package is damaged. First thing to do: prepare the package again.",
        )
    try:
        after_catalog_text, after_passages_text = review_package.build_after_state(
            package, baseline_catalog, baseline_passages, cases_path, as_of
        )
    except review_package.ReviewPackageError as error:
        return _package_problem(
            ports, package_dir, _after_state_sentence(error.failure)
        )

    after_dir = scratch / "after"
    _private_dir(after_dir)
    after_catalog = after_dir / "source_catalog.json"
    after_passages = after_dir / "passages.json"
    after_catalog.write_text(after_catalog_text, encoding="utf-8")
    after_passages.write_text(after_passages_text, encoding="utf-8")

    try:
        before_eval = ports.evaluator.evaluate(
            catalog=worktree / CATALOG_FILE,
            passages=worktree / PASSAGES_FILE,
            cases=cases_path,
            as_of=as_of,
        )
        after_eval = ports.evaluator.evaluate(
            catalog=after_catalog,
            passages=after_passages,
            cases=cases_path,
            as_of=as_of,
        )
        body = render_pr_body(package, review_md, before_eval, after_eval)
    except Exception as error:  # noqa: BLE001 - one sentence; the type goes to the log
        append_review_log(ports.home, "evaluation failed: {}".format(type(error).__name__))
        return _package_problem(
            ports,
            package_dir,
            "The answer evaluation could not run. First thing to do: check the backend "
            "tools with ./scripts/init.sh --setup-python, then run {} again.".format(
                READY_COMMAND
            ),
        )

    _write_worktree_files(
        worktree, package_id, after_catalog_text, after_passages_text, package_bytes, review_md
    )
    added_paths = [str(CATALOG_FILE), str(PASSAGES_FILE), str(REVIEWS_DIR / package_id)]
    added_result = ports.git.run(["add", "--", *added_paths], cwd=worktree)
    committed = ports.git.run(
        ["commit", "-m", "knowledge: review package {}".format(package_id[:12])], cwd=worktree
    )
    if added_result.returncode != 0 or committed.returncode != 0:
        append_review_log(ports.home, "the review commit could not be created")
        return _package_problem(
            ports,
            package_dir,
            "The review branch could not be prepared. First thing to do: tell a developer; "
            "the details are in the review log.",
        )

    pushed = ports.git.run(
        ["push", "origin", "HEAD:refs/heads/{}".format(branch)], cwd=worktree
    )
    if pushed.returncode != 0:
        append_review_log(ports.home, "push failed (exit {})".format(pushed.returncode))
        return _package_problem(
            ports,
            package_dir,
            "The review branch could not be sent to GitHub. First thing to do: check the "
            "internet and the GitHub login, then run {} again.".format(READY_COMMAND),
        )

    body_file = scratch / "body.md"
    _write_private(body_file, body)
    created = ports.gh.run(
        [
            "pr",
            "create",
            "--repo",
            slug,
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            "Knowledge update review package {}".format(package_id[:16]),
            "--body-file",
            str(body_file),
        ]
    )
    url = _created_url(created)
    if created.returncode != 0 or url is None:
        if created.returncode != 0:
            append_review_log(ports.home, "pull request create failed (exit {})".format(created.returncode))
        else:
            append_review_log(ports.home, "pull request create returned no url")
        return _package_problem(
            ports,
            package_dir,
            "The pull request could not be created on GitHub. First thing to do: check the "
            "GitHub login, then run {} again.".format(READY_COMMAND),
        )
    record = {
        "schema_version": PULL_REQUEST_VERSION,
        "package_id": package_id,
        "branch": branch,
        "url": url,
        "opened_on": as_of.isoformat(),
    }
    _write_private(Path(package_dir) / PULL_REQUEST_RECORD, _json_text(record))
    ports.out("opened: {}".format(url))
    return "opened"


def _report_existing(ports: Ports, slug: str, record_path: Path) -> str:
    try:
        record = _json_from(record_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        record = None
    if not isinstance(record, dict) or not isinstance(record.get("branch"), str):
        return _package_problem(
            ports,
            record_path.parent,
            "The saved pull-request record is damaged. First thing to ask: delete the file "
            "and run the command again.",
        )
    viewed = ports.gh.run(
        [
            "pr",
            "view",
            record["branch"],
            "--repo",
            slug,
            "--json",
            "state,url,mergedAt",
        ]
    )
    state = _json_from(viewed.stdout)
    if viewed.returncode != 0 or not isinstance(state, dict):
        return _package_problem(
            ports,
            record_path.parent,
            "The pull request could not be checked. First thing to do: check the internet "
            "and the GitHub login, then run {} again.".format(READY_COMMAND),
        )
    url = state.get("url") or record.get("url") or ""
    name = str(state.get("state") or "").upper()
    if state.get("mergedAt"):
        ports.out("merged on GitHub. Next: reindex and release the change (see backend/README.md).")
    elif name == "MERGED":
        ports.out("merged on GitHub. Next: reindex and release the change (see backend/README.md).")
    elif name == "OPEN":
        ports.out("already open: {}".format(url))
    elif name == "CLOSED":
        ports.out("closed without merging. First thing to do: prepare a new review package.")
    else:
        return _package_problem(
            ports,
            record_path.parent,
            "The pull request state could not be read. First thing to do: open it on GitHub "
            "and check it yourself.",
        )
    return "reported"


def _after_state_sentence(failure: str) -> str:
    if failure in ("canonical_drift", "evaluation_cases_drift"):
        return (
            "The saved baseline no longer matches this package. First thing to do: prepare "
            "the package again from the current knowledge."
        )
    if failure == "cases_required":
        return (
            "The package has no reviewed answer cases. First thing to do: prepare the "
            "package again with knowledge/pac_answer_eval.json."
        )
    return (
        "The proposed knowledge does not pass its own checks. First thing to do: prepare "
        "the package again."
    )


# --- Pull-request body ------------------------------------------------------------------------


def render_pr_body(
    package: Mapping[str, Any],
    review_md: str,
    before_eval: Mapping[str, Any],
    after_eval: Mapping[str, Any],
) -> str:
    """Render the reviewed evidence and report-only before/after counts."""

    before = _evaluation_counts(before_eval)
    after = _evaluation_counts(after_eval)
    changed = _changed_case_ids(before_eval, after_eval)
    summary = package["check_summary"]
    lines: List[str] = list(FIXED_BODY_LINES)
    lines += [
        "",
        "# Knowledge update review package `{}`".format(package["package_id"][:16]),
        "",
        "## Evaluation results",
        "",
        "| Measure | Before | After |",
        "|---|---|---|",
        "| Cases | {} | {} |".format(before["cases"], after["cases"]),
        "| Expected-state agreement | {} | {} |".format(
            before["expected_state_agreement"], after["expected_state_agreement"]
        ),
        "| Unexpected answers | {} | {} |".format(
            before["unexpected_answers"], after["unexpected_answers"]
        ),
        "| Source matches (answered cases) | {} | {} |".format(
            before["source_matches"], after["source_matches"]
        ),
        "| Passage matches (answered cases) | {} | {} |".format(
            before["passage_matches"], after["passage_matches"]
        ),
        "",
    ]
    if changed:
        lines.append(
            "Changed cases: {}.".format(", ".join("`{}`".format(item) for item in changed))
        )
    else:
        lines.append("No case row changed.")
    lines += [
        "",
        "## Automated checks",
        "",
        "{} passed, {} failed, {} report-only. Merge readiness: {}.".format(
            summary["passed"],
            summary["failed"],
            summary["report_only"],
            package["merge_readiness"],
        ),
        "",
        "## Review evidence",
        "",
        review_md.rstrip("\n"),
        "",
    ]
    return _cap_body("\n".join(lines), package["package_id"])


def _evaluation_counts(report: Mapping[str, Any]) -> Dict[str, int]:
    def count(name: str) -> int:
        value = report.get(name)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("evaluation report is missing {}".format(name))
        return value

    rows = report.get("case_rows")
    if not isinstance(rows, list):
        raise ValueError("evaluation report is missing case rows")
    answered = [
        row
        for row in rows
        if isinstance(row, dict) and row.get("expected_status") == "answered"
    ]
    return {
        "cases": count("cases"),
        "expected_state_agreement": count("expected_state_agreement"),
        "unexpected_answers": count("unexpected_answers"),
        "source_matches": sum(1 for row in answered if row.get("source_match")),
        "passage_matches": sum(1 for row in answered if row.get("passage_match")),
    }


def _changed_case_ids(
    before_eval: Mapping[str, Any], after_eval: Mapping[str, Any]
) -> List[str]:
    before = {
        row.get("id"): _row_key(row)
        for row in before_eval.get("case_rows", [])
        if isinstance(row, dict)
    }
    changed: List[str] = []
    for row in after_eval.get("case_rows", []):
        if not isinstance(row, dict):
            continue
        case_id = row.get("id")
        if not isinstance(case_id, str):
            continue
        if before.get(case_id) != _row_key(row):
            changed.append(case_id)
    return sorted(changed)[:MAX_CHANGED_CASE_IDS]


def _row_key(row: Mapping[str, Any]) -> Tuple[Any, ...]:
    return (
        row.get("expected_state_match"),
        row.get("actual_status"),
        row.get("source_match"),
        row.get("passage_match"),
    )


def _cap_body(body: str, package_id: str) -> str:
    if len(body) <= MAX_BODY_CHARS:
        return body
    pointer = (
        "\n\n[Body cut at 60,000 characters. Read the full committed review evidence at "
        "`knowledge/reviews/{}/REVIEW.md`.]\n".format(package_id)
    )
    budget = MAX_BODY_CHARS - len(pointer)
    cut = body[:budget].rsplit("\n", 1)[0]
    return cut.rstrip("\n") + pointer


# --- Protection -------------------------------------------------------------------------------


def _describe_protection(ports: Ports) -> None:
    ports.out("GitHub will protect main with the ruleset {}:".format(RULESET_NAME))
    ports.out("- only pull requests can change main, and no approval is required;")
    ports.out("- commits GitHub cannot link to an account need no extra approval;")
    ports.out("- the checks fast and full must pass;")
    ports.out("- force pushes are blocked;")
    ports.out("- the people and apps already allowed to bypass it stay allowed;")
    ports.out("- any other rule already on it stays in place.")
    ports.out(
        "To undo later: on GitHub, open Settings > Rules > {} and set enforcement to "
        "Disabled.".format(RULESET_NAME)
    )
    ports.out("Type yes to apply it, or anything else to stop.")


def ruleset_payload(existing: Mapping[str, Any], committed: Mapping[str, Any]) -> Dict[str, Any]:
    """The update for one ruleset; unrelated live rules and bypass actors are kept."""

    payload = {
        key: committed[key]
        for key in ("name", "target", "enforcement", "conditions")
    }
    payload["rules"] = _merged_rules(existing.get("rules"), committed["rules"])
    payload["bypass_actors"] = existing.get("bypass_actors") or []
    return payload


def _merged_rules(live: Any, committed: Sequence[Mapping[str, Any]]) -> List[Any]:
    wanted = {
        rule.get("type")
        for rule in committed
        if isinstance(rule, dict) and isinstance(rule.get("type"), str)
    }
    merged: List[Any] = list(committed)
    if isinstance(live, list):
        merged += [
            rule
            for rule in live
            if isinstance(rule, dict) and rule.get("type") not in wanted
        ]
    return merged


def ruleset_matches(existing: Mapping[str, Any], committed: Mapping[str, Any]) -> bool:
    """Whether the live ruleset already enforces everything the committed file asks.

    Documented extras (for example ``integration_id`` on a required check or an
    unrelated ruleset rule) are ignored; only what the committed file sets counts.
    """

    for key in ("name", "target", "enforcement"):
        if existing.get(key) != committed.get(key):
            return False
    if "conditions" in committed and existing.get("conditions") is None:
        return False
    existing_condition = _condition_ref(existing.get("conditions"))
    committed_condition = _condition_ref(committed.get("conditions"))
    if (
        existing_condition is None
        or committed_condition is None
        or existing_condition != committed_condition
    ):
        return False
    live = _rule_rules(existing.get("rules"))
    wanted = _rule_rules(committed.get("rules"))
    if live is None or wanted is None or not set(wanted) <= set(live):
        return False
    for rule_type, parameters in wanted.items():
        if not _parameters_match(live[rule_type], parameters):
            return False
    return True


def _parameters_match(live: Mapping[str, Any], wanted: Mapping[str, Any]) -> bool:
    for name, value in wanted.items():
        if name == "required_status_checks":
            if not _checks_match(live.get(name), value):
                return False
        elif live.get(name) != value:
            return False
    return True


def _checks_match(live: Any, wanted: Any) -> bool:
    def contexts(items: Any) -> Optional[List[str]]:
        if not isinstance(items, list):
            return None
        found: List[str] = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("context"), str):
                return None
            found.append(item["context"])
        return sorted(found)

    live_contexts = contexts(live)
    wanted_contexts = contexts(wanted)
    return (
        live_contexts is not None
        and wanted_contexts is not None
        and live_contexts == wanted_contexts
    )


def _condition_ref(conditions: Any) -> Optional[Tuple[Any, Any]]:
    if not isinstance(conditions, dict):
        return None
    ref = conditions.get("ref_name")
    if not isinstance(ref, dict):
        return None
    include, exclude = ref.get("include"), ref.get("exclude", [])
    if not isinstance(include, list) or not isinstance(exclude, list):
        return None
    return (tuple(sorted(include)), tuple(sorted(exclude)))


def _rule_rules(rules: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(rules, list):
        return None
    parsed: Dict[str, Any] = {}
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("type"), str):
            return None
        parameters = rule.get("parameters") or {}
        if not isinstance(parameters, dict):
            return None
        item = parsed.setdefault(rule["type"], {})
        item.update(parameters)
    return parsed


def _committed_ruleset() -> Tuple[Dict[str, Any], Optional[str]]:
    path = PACKAGE_ROOT / RULESET_FILE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, (
            "The saved {} ruleset file is missing or damaged. First thing to do: run the "
            "commands from the Manijero folder, or tell a developer.".format(RULESET_NAME)
        )
    if (
        not isinstance(document, dict)
        or document.get("name") != RULESET_NAME
        or not isinstance(document.get("rules"), list)
    ):
        return {}, (
            "The saved {} ruleset file is not valid. First thing to do: tell a developer; "
            "the details are in the review log.".format(RULESET_NAME)
        )
    condition = document.get("conditions")
    ref_name = condition.get("ref_name") if isinstance(condition, dict) else None
    include = ref_name.get("include") if isinstance(ref_name, dict) else None
    if not isinstance(include, list) or "refs/heads/main" not in include:
        return {}, (
            "The saved {} ruleset does not protect main. First thing to do: update the "
            "committed ruleset file, or tell a developer.".format(RULESET_NAME)
        )
    if any(
        not isinstance(rule, dict) or not isinstance(rule.get("type"), str)
        for rule in document["rules"]
    ):
        return {}, (
            "The saved {} ruleset file is not valid. First thing to do: tell a developer; "
            "the details are in the review log.".format(RULESET_NAME)
        )
    return document, None


# --- Prerequisites and helpers ----------------------------------------------------------------


def _repository(ports: Ports) -> Tuple[str, Optional[str]]:
    result = ports.git.run(["remote", "get-url", "origin"], cwd=ports.repo)
    if result.returncode != 0:
        return "", (
            "This folder is not connected to a GitHub repository. First thing to do: run the "
            "commands from the Manijero folder."
        )
    slug = _slug(result.stdout)
    if slug is None:
        return "", (
            "The GitHub address of this folder could not be read. First thing to do: run the "
            "commands from the Manijero folder."
        )
    return slug, None


def _slug(remote: str) -> Optional[str]:
    value = remote.strip()
    if value.endswith(".git"):
        value = value[: -len(".git")]
    if "://" in value:
        path = urlparse(value).path
    elif ":" in value:
        path = value.split(":", 1)[1]
    else:
        path = value
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return None
    return "{}/{}".format(parts[-2], parts[-1])


def _github_ready(ports: Ports) -> Optional[str]:
    status = ports.gh.run(["auth", "status"])
    if status.returncode == 127:
        return (
            "The GitHub tool (gh) is not installed. First thing to do: install it from "
            "https://cli.github.com, then try again."
        )
    if status.returncode != 0:
        return (
            "The GitHub tool is not logged in. First thing to do: run gh auth login in the "
            "Terminal, then try again."
        )
    return None


def _review_packages(home: Path) -> List[Path]:
    packages = [
        child
        for child in sorted(Path(home).iterdir())
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name != "logs"
        and (child / "package.json").is_file()
    ]
    return packages


def _work_root(home: Path) -> Path:
    root = Path(home) / ".work"
    _private_dir(root)
    return root


def _write_worktree_files(
    worktree: Path,
    package_id: str,
    catalog_text: str,
    passages_text: str,
    package_bytes: bytes,
    review_md: str,
) -> None:
    knowledge = Path(worktree) / "knowledge"
    (knowledge / CATALOG_FILE.name).write_text(catalog_text, encoding="utf-8")
    (knowledge / PASSAGES_FILE.name).write_text(passages_text, encoding="utf-8")
    review_dir = Path(worktree) / REVIEWS_DIR / package_id
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "package.json").write_bytes(package_bytes)
    (review_dir / "REVIEW.md").write_text(review_md, encoding="utf-8")


def _read(path: Path) -> Optional[bytes]:
    try:
        return Path(path).read_bytes()
    except OSError:
        return None


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_from(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


def _created_url(result: CommandResult) -> Optional[str]:
    if result.returncode != 0:
        return None
    for line in reversed(result.stdout.splitlines()):
        candidate = line.strip()
        if URL_PATTERN.fullmatch(candidate):
            return candidate
    return None


def _open_stop(ports: Ports, sentence: str) -> int:
    ports.out(sentence)
    ports.out("Result: no review pull request was opened.")
    return 2


def _protect_stop(ports: Ports, sentence: str) -> int:
    ports.out(sentence)
    ports.out("Result: nothing was changed.")
    return 2


def _protect_failed(ports: Ports, sentence: str) -> int:
    ports.out(sentence)
    ports.out("Result: the protection was not changed.")
    return 1


def _package_problem(ports: Ports, package_dir: Path, sentence: str) -> str:
    name = Path(package_dir).name
    label = package_id_from_dir(name)
    ports.out("Package {}: {}".format(label, sentence))
    return "failed"


def package_id_from_dir(name: str) -> str:
    """A short stable label for one package directory, never a local path."""

    return name[:12] if len(name) >= 12 else name


def review_package_date_zone():
    """The date zone the package was prepared with: Europe/Madrid."""

    return ZoneInfo("Europe/Madrid")
