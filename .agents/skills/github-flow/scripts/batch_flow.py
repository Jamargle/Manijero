#!/usr/bin/env python3
"""The batch loop behind .agents/skills/github-flow/scripts/batch.sh: next, integrate, and status.

A batch is up to BATCH_SIZE features taken one at a time in selector order, each in its own
worktree and headless session from one common main SHA, then merged into one integration branch
and opened as one PR against main. The owner merges that PR; the next `next` starts a new batch.

The script does every step that repeats each batch and stops, with a plain message and its own
exit code, wherever a person must decide: owner decisions a feature with no spec needs, a merge
conflict outside the files it knows how to resolve, a failing check, or a PR awaiting review.
It never force-pushes, merges a PR, or deletes a branch, worktree, issue, or PR.

Standard library only: it runs before any project setup.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

def _repository_root(start: Path) -> Path:
    """The checkout this copy of the script belongs to: the nearest folder with a `.git` entry."""

    for folder in start.parents:
        if (folder / ".git").exists():
            return folder
    raise SystemExit("batch_flow.py must live inside a git checkout")


REPO_ROOT = _repository_root(Path(__file__).resolve())
WORKTREES_ROOT = REPO_ROOT.parent / (REPO_ROOT.name + "-worktrees")
STATE_FILE = REPO_ROOT / "build" / "batches" / "current.json"
BASE_BRANCH = "main"
BATCH_SIZE = 3

EXIT_ERROR = 1
EXIT_DECISIONS = 3  # the next feature needs owner decisions: rerun with --note
EXIT_CONFLICT = 4  # a merge conflict needs a person: resolve, commit nothing, rerun integrate
EXIT_CHECK = 5  # a check failed on the integration branch
EXIT_WAIT = 6  # nothing to do yet: a PR awaits review, or the batch is full or empty
EXIT_NOT_ACCEPTED = 7  # the feature session ended without acceptance

STATUS_RANK = {"not_started": 0, "in_progress": 1, "passing": 2, "accepted": 3}
MAX_REPORT_CHARS = 4000


class Stop(Exception):
    """A plain-language stop with the exit code the caller sees."""

    def __init__(self, message: str, code: int = EXIT_ERROR) -> None:
        super().__init__(message)
        self.code = code


def say(message: str = "") -> None:
    print(message, flush=True)


def run(args: Sequence[str], cwd: Optional[Path] = None, check: bool = True,
        env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    result = subprocess.run(list(args), cwd=str(cwd or REPO_ROOT), text=True, capture_output=True, env=env)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise Stop("This step failed: {}\n{}".format(" ".join(args), detail))
    return result


def git(*args: str, cwd: Optional[Path] = None, check: bool = True) -> str:
    return run(["git", *args], cwd=cwd, check=check).stdout.strip()


# --- pure helpers (unit-tested) --------------------------------------------------------------


def next_batch_number(branch_names: Sequence[str]) -> int:
    numbers = [int(match.group(1)) for name in branch_names
               if (match := re.search(r"integration/\d{4}-\d{2}-\d{2}-batch-(\d+)$", name.strip()))]
    return max(numbers, default=0) + 1


def choose_feature(selector_status: str, taken: Sequence[str]) -> Optional[str]:
    """The first dependency-ready feature in selector order that this batch has not taken."""

    for line in selector_status.splitlines():
        if not line.startswith("FEATURE "):
            continue
        fields = dict(part.split("=", 1) for part in line.split()[1:] if "=" in part)
        if fields.get("ready") == "yes" and fields.get("id") not in taken:
            return fields["id"]
    return None


def feature_counts(feature_list_text: str) -> Dict[str, int]:
    data = json.loads(feature_list_text)
    features = data["features"] if isinstance(data, dict) else data
    counts = {"total": len(features)}
    for feature in features:
        counts[feature["status"]] = counts.get(feature["status"], 0) + 1
    return counts


def recount_progress(progress_text: str, counts: Dict[str, int]) -> str:
    """Fix the two counts in PROGRESS.md that every merged batch makes stale."""

    text = re.sub(r"\b\d+ of \d+ features are accepted",
                  "{} of {} features are accepted".format(counts.get("accepted", 0), counts["total"]),
                  progress_text)
    return re.sub(r"The \d+ `not_started` features",
                  "The {} `not_started` features".format(counts.get("not_started", 0)), text)


_TOKEN = re.compile(r"\s+|\S+")
Edit = Tuple[int, int, List[str]]


def _edits(base: List[str], side: List[str]) -> List[Edit]:
    matcher = SequenceMatcher(None, base, side, autojunk=False)
    return [(i1, i2, side[j1:j2]) for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]


def _overlap(a: Edit, b: Edit) -> bool:
    (a1, a2, _), (b1, b2, _) = a, b
    if a1 == a2 and b1 == b2:
        return False  # two insertions at one point: both are kept, ours first
    if a1 == a2:
        return b1 < a1 < b2
    if b1 == b2:
        return a1 < b1 < a2
    return max(a1, b1) < min(a2, b2)


def _blank(tokens: Sequence[str]) -> bool:
    return all(not token.strip() for token in tokens)


def _number(tokens: Sequence[str]) -> bool:
    return len(tokens) == 1 and tokens[0].isdigit()


def token_merge(base: str, ours: str, theirs: str) -> Optional[str]:
    """Three-way merge of prose by words; None when both sides changed the same words.

    Two insertions at one point keep both (ours first). Clashes that only differ in whitespace
    (one side reflowed a paragraph) or in a bare number (a count that recount_progress fixes)
    keep ours. Any other clash is left for a person.
    """

    base_tokens = _TOKEN.findall(base)
    ours_edits = _edits(base_tokens, _TOKEN.findall(ours))
    theirs_edits = _edits(base_tokens, _TOKEN.findall(theirs))
    kept_theirs: List[Edit] = []
    for theirs_edit in theirs_edits:
        clashes = [edit for edit in ours_edits if _overlap(edit, theirs_edit)]
        if not clashes:
            kept_theirs.append(theirs_edit)
            continue
        for ours_edit in clashes:
            same_range = ours_edit[:2] == theirs_edit[:2]
            if same_range and ours_edit[2] == theirs_edit[2]:
                continue
            if _blank(base_tokens[theirs_edit[0]:theirs_edit[1]]) and _blank(theirs_edit[2]) \
                    and _blank(base_tokens[ours_edit[0]:ours_edit[1]]) and _blank(ours_edit[2]):
                continue
            if same_range and _number(base_tokens[theirs_edit[0]:theirs_edit[1]]) \
                    and _number(ours_edit[2]) and _number(theirs_edit[2]):
                continue
            return None
    ordered = sorted([(edit, 0) for edit in ours_edits] + [(edit, 1) for edit in kept_theirs],
                     key=lambda item: (item[0][0], item[0][0] != item[0][1], item[1]))
    out: List[str] = []
    position = 0
    for (start, end, replacement), _side in ordered:
        out.extend(base_tokens[position:start])
        out.extend(replacement)
        position = max(position, end)
    out.extend(base_tokens[position:])
    return "".join(out)


def union_or_merge(ours: str, base: str, theirs: str) -> Optional[str]:
    """Both sides added lines at the same spot (log rows, limitation bullets): keep both."""

    if not base.strip():
        ours_lines = ours.splitlines(True)
        return ours + "".join(line for line in theirs.splitlines(True) if line not in ours_lines)
    return token_merge(base, ours, theirs)


_STATUS_LINE = re.compile(r'"id": "([^"]+)".*"status": "([^"]+)"')


def newest_status_lines(ours: str, base: str, theirs: str) -> Optional[str]:
    """feature_list.json: per feature line, keep the side with the more advanced status."""

    def parse(block: str) -> Optional[Dict[str, Tuple[str, str]]]:
        found: Dict[str, Tuple[str, str]] = {}
        for line in block.splitlines(True):
            match = _STATUS_LINE.search(line)
            if match is None:
                if line.strip():
                    return None
                continue
            found[match.group(1)] = (match.group(2), line)
        return found

    ours_lines, theirs_lines = parse(ours), parse(theirs)
    if ours_lines is None or theirs_lines is None:
        return None
    out = []
    for feature_id in list(ours_lines) + [key for key in theirs_lines if key not in ours_lines]:
        candidates = [side[feature_id] for side in (ours_lines, theirs_lines) if feature_id in side]
        status, line = max(candidates, key=lambda item: STATUS_RANK.get(item[0], -1))
        out.append(line)
    return "".join(out)


Resolver = Callable[[str, str, str], Optional[str]]
_HUNK = re.compile(r"^<<<<<<< [^\n]*\n(.*?)^\|\|\|\|\|\|\| [^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]*\n",
                   re.S | re.M)


def resolver_for(path: str) -> Optional[Resolver]:
    """Only the files every batch conflicts in; code and anything else go to a person."""

    if path == "feature_list.json":
        return newest_status_lines
    if path == "PROGRESS.md" or (path.startswith(("docs/progress/", "docs/owner-guide/")) and path.endswith(".md")):
        return union_or_merge
    return None


def resolve_conflicts(text: str, resolver: Resolver) -> Optional[str]:
    """Resolve every diff3 conflict hunk in text, or None when any hunk needs a person."""

    failed = False

    def replace(match: "re.Match[str]") -> str:
        nonlocal failed
        resolved = resolver(match.group(1), match.group(2), match.group(3))
        if resolved is None:
            failed = True
            return match.group(0)
        return resolved

    merged = _HUNK.sub(replace, text)
    if failed or re.search(r"^(<<<<<<<|>>>>>>>) ", merged, re.M):
        return None
    return merged


def build_pr_body(state: dict, details: Dict[str, dict]) -> str:
    base = state["base_sha"][:7]
    features = state["features"]
    lines = [
        "Batch {}: {} feature{}, taken one at a time with `.agents/skills/github-flow/scripts/batch.sh next` from `{}` `{}`. Each was "
        "planned, implemented, and validated in its own worktree and session, then merged here with "
        "`.agents/skills/github-flow/scripts/batch.sh integrate`.".format(state["number"], len(features), "" if len(features) == 1 else "s",
                                                  BASE_BRANCH, base),
        "",
        "## Features",
        "",
        "| Feature | Commits | Issue | Acceptance |",
        "|---|---|---|---|",
    ]
    for feature in features:
        info = details[feature["id"]]
        commits = ", ".join("`{}`".format(sha) for sha in info["commits"]) or "none"
        lines.append("| `{}`: {} | {} | #{} | [record](docs/validations/{}.md) |".format(
            feature["id"], info["title"], commits, feature["issue"], feature["id"]))
    notes = [feature for feature in features if feature.get("note")]
    if notes:
        lines += ["", "## Owner decisions", ""]
        lines += ["- **`{}`:** {}".format(feature["id"], feature["note"]) for feature in notes]
    lines += ["", "## Integration", ""]
    resolved = state.get("auto_resolved") or []
    lines.append("- Resolved by the script: {}.".format(", ".join("`{}`".format(item) for item in resolved))
                 if resolved else "- No conflicts needed the script's resolution.")
    manual = state.get("manual") or []
    if manual:
        lines.append("- Resolved by hand: {}. See the merge commits.".format(
            ", ".join("`{}`".format(item) for item in manual)))
    lines += ["", "## Usage (API-equivalent prices)", "", "| Feature | Turns | Minutes | Cost |", "|---|---|---|---|"]
    total = 0.0
    for feature in features:
        usage = details[feature["id"]]["usage"]
        if usage is None:
            lines.append("| `{}` | not reported | | |".format(feature["id"]))
            continue
        total += usage["cost"]
        lines.append("| `{}` | {} | {:.1f} | ${:.2f} |".format(feature["id"], usage["turns"], usage["minutes"],
                                                              usage["cost"]))
    lines.append("| **Batch** | | | **${:.2f}** |".format(total))
    lines += ["", "## Verification", ""]
    lines += ["- `{}`: {}".format(name, summary) for name, summary in state.get("checks") or []]
    lines += ["", "## Session reports", ""]
    for feature in features:
        report = details[feature["id"]]["report"] or "No report was saved."
        lines += ["<details><summary><code>{}</code></summary>".format(feature["id"]), "", report.strip(), "",
                  "</details>", ""]
    lines.append(", ".join("Closes #{}".format(feature["issue"]) for feature in features) + ".")
    lines += ["", "🤖 Generated with [Claude Code](https://claude.com/claude-code)", ""]
    return "\n".join(lines)


# --- repository state ------------------------------------------------------------------------


def load_state() -> Optional[dict]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def features_by_id(root: Path) -> Dict[str, dict]:
    data = json.loads((root / "feature_list.json").read_text(encoding="utf-8"))
    return {feature["id"]: feature for feature in (data["features"] if isinstance(data, dict) else data)}


def require_base_checkout() -> None:
    git_dir = Path(git("rev-parse", "--absolute-git-dir"))
    common = Path(git("rev-parse", "--git-common-dir"))
    common = common if common.is_absolute() else (REPO_ROOT / common)
    if git_dir.resolve() != common.resolve():
        raise Stop("Run .agents/skills/github-flow/scripts/batch.sh from the main checkout ({}), not from a worktree.".format(REPO_ROOT))


def require_clean_main() -> None:
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != BASE_BRANCH:
        raise Stop("The main checkout is on {}; switch it to {} first.".format(branch, BASE_BRANCH))
    if git("status", "--porcelain", "--untracked-files=no"):
        raise Stop("The main checkout has uncommitted changes; commit or discard them first.")


def branch_exists(name: str, cwd: Optional[Path] = None) -> bool:
    return run(["git", "rev-parse", "--verify", "--quiet", "refs/heads/" + name], cwd=cwd, check=False).returncode == 0


def ensure_worktree(path: Path, branch: str, base_sha: str) -> Path:
    if path.exists():
        current = git("rev-parse", "--abbrev-ref", "HEAD", cwd=path)
        if current != branch:
            raise Stop("{} exists but is on {}, not {}.".format(path, current, branch))
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    if branch_exists(branch):
        say("Reusing the existing branch {}.".format(branch))
        git("worktree", "add", str(path), branch)
    else:
        git("worktree", "add", str(path), "-b", branch, base_sha)
    return path


def pr_state(number: int) -> str:
    return run(["gh", "pr", "view", str(number), "--json", "state", "-q", ".state"]).stdout.strip()


def current_or_new_batch() -> dict:
    state = load_state()
    if state is not None and state.get("pr"):
        status = pr_state(state["pr"])
        if status == "OPEN":
            raise Stop("Batch {} is waiting for review in PR #{} ({}). After it is merged, run this "
                       "again to start the next batch.".format(state["number"], state["pr"], state.get("pr_url", "")),
                       EXIT_WAIT)
        if status != "MERGED":
            raise Stop("PR #{} of batch {} is {} without being merged. Decide what to do with it first; the "
                       "batch record is {}.".format(state["pr"], state["number"], status.lower(), STATE_FILE))
        archived = STATE_FILE.with_name("batch-{}.json".format(state["number"]))
        STATE_FILE.rename(archived)
        say("Batch {} was merged in PR #{}.".format(state["number"], state["pr"]))
        state = None
    if state is not None:
        return state
    require_clean_main()
    git("fetch", "origin", BASE_BRANCH)
    git("merge", "--ff-only", "origin/" + BASE_BRANCH)
    base_sha = git("rev-parse", "HEAD")
    branches = git("branch", "-a", "--format=%(refname:short)").splitlines()
    number = next_batch_number(branches)
    today = datetime.date.today().isoformat()
    state = {
        "number": number,
        "branch": "integration/{}-batch-{}".format(today, number),
        "base_sha": base_sha,
        "features": [],
        "auto_resolved": [],
        "manual": [],
        "pending_manual": [],
        "checks": [],
        "checks_sha": None,
        "pr": None,
    }
    save_state(state)
    say("Started batch {} from {} {}.".format(number, BASE_BRANCH, base_sha[:7]))
    return state


# --- next ------------------------------------------------------------------------------------


def ensure_issue(entry: dict, title: str) -> None:
    if entry.get("issue"):
        return
    feature_id = entry["id"]
    listing = run(["gh", "issue", "list", "--state", "all", "--search", feature_id, "--json", "number,title",
                   "--limit", "50"]).stdout
    for item in json.loads(listing or "[]"):
        if item["title"].startswith("[{}]".format(feature_id)):
            entry["issue"] = item["number"]
            say("Reusing issue #{}.".format(item["number"]))
            return
    body = "Feature `{}` from `feature_list.json`.\n\n".format(feature_id)
    body += "Owner decisions: {}\n".format(entry["note"]) if entry.get("note") else "No owner decisions recorded.\n"
    url = run(["gh", "issue", "create", "--title", "[{}] {}".format(feature_id, title), "--body", body]).stdout
    entry["issue"] = int(url.strip().splitlines()[-1].rstrip("/").rsplit("/", 1)[-1])
    say("Created issue #{}.".format(entry["issue"]))


def session_usage(worktree: Path, feature_id: str) -> Optional[dict]:
    try:
        rows = (worktree / "build" / "agent-sessions" / "usage.tsv").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    header = rows[0].split("\t") if rows else []
    usage = {"turns": 0, "minutes": 0.0, "cost": 0.0, "sessions": 0}
    for row in rows[1:]:
        values = dict(zip(header, row.split("\t")))
        if values.get("feature") != feature_id:
            continue
        usage["turns"] += int(values.get("turns") or 0)
        usage["minutes"] += float(values.get("minutes") or 0)
        usage["cost"] += float(values.get("cost_usd") or 0)
        usage["sessions"] += 1
    return usage if usage["sessions"] else None


def session_report(worktree: Path, feature_id: str) -> Optional[str]:
    logs = sorted((worktree / "build" / "agent-sessions").glob("{}-*.log".format(feature_id)))
    if not logs:
        return None
    try:
        report = json.loads(logs[-1].read_text(encoding="utf-8").strip().splitlines()[-1]).get("result")
    except (ValueError, IndexError):
        return None
    if report and len(report) > MAX_REPORT_CHARS:
        report = report[:MAX_REPORT_CHARS] + "\n\n(cut; the full report is in {})".format(logs[-1].name)
    return report


def cmd_next(note: str, no_decisions: bool) -> int:
    require_base_checkout()
    state = current_or_new_batch()
    pending = [entry for entry in state["features"] if entry["status"] != "accepted"]
    accepted = [entry for entry in state["features"] if entry["status"] == "accepted"]
    if pending:
        entry = pending[0]
        say("Continuing {}, which is {}.".format(entry["id"], entry["status"].replace("_", " ")))
        if note:
            entry["note"] = (entry.get("note", "") + " " + note).strip()
    else:
        if len(accepted) >= BATCH_SIZE:
            raise Stop("Batch {} already has {} accepted features. Run .agents/skills/github-flow/scripts/batch.sh integrate.".format(
                state["number"], len(accepted)), EXIT_WAIT)
        selector = run(["./scripts/select-feature.sh", "--status"]).stdout
        feature_id = choose_feature(selector, [entry["id"] for entry in state["features"]])
        if feature_id is None:
            hint = " Run .agents/skills/github-flow/scripts/batch.sh integrate --partial to ship them." if accepted else ""
            raise Stop("No other feature is ready in batch {}: the rest wait on features that are not on main "
                       "yet.{}".format(state["number"], hint), EXIT_WAIT)
        feature = features_by_id(REPO_ROOT)[feature_id]
        spec = REPO_ROOT / (feature.get("spec") or "docs/specs/{}.md".format(feature_id))
        if not spec.exists() and not note and not no_decisions:
            say("Next feature: {}".format(feature_id))
            say("  {}".format(feature["title"]))
            say("It has no spec yet, so the title is its only requirement.")
            say("Result: {} needs the owner's decisions first. Run .agents/skills/github-flow/scripts/batch.sh next --note \"...\" "
                "with them, or .agents/skills/github-flow/scripts/batch.sh next --no-decisions if none are needed.".format(feature_id))
            return EXIT_DECISIONS
        entry = {"id": feature_id, "status": "not_started", "note": note, "issue": None, "commit": None}
        state["features"].append(entry)
    save_state(state)

    feature = features_by_id(REPO_ROOT)[entry["id"]]
    ensure_issue(entry, feature["title"])
    save_state(state)
    worktree = ensure_worktree(WORKTREES_ROOT / entry["id"], "feature/" + entry["id"], state["base_sha"])
    command = ["./scripts/feature-session.sh", "--headless"]
    if entry.get("note"):
        command += ["--note", "Owner decisions (write them into the spec Notes): " + entry["note"]]
    command.append(entry["id"])
    say("Running {} in its own session. This usually takes 10 to 20 minutes.".format(entry["id"]))
    subprocess.run(command, cwd=str(worktree))

    entry["status"] = features_by_id(worktree)[entry["id"]]["status"]
    if git("rev-list", "--count", "{}..HEAD".format(state["base_sha"]), cwd=worktree) != "0":
        entry["commit"] = git("log", "-1", "--format=%h %s", cwd=worktree)
    save_state(state)
    usage = session_usage(worktree, entry["id"])
    cost = "about ${:.2f} so far at API prices".format(usage["cost"]) if usage else "usage not reported"
    run(["gh", "issue", "comment", str(entry["issue"]), "--body",
         "Status: {}. Commit: {}. Batch {}, base `{}`; {}.".format(
             entry["status"], entry["commit"] or "none", state["number"], state["base_sha"][:7], cost)],
        check=False)

    accepted_now = sum(1 for item in state["features"] if item["status"] == "accepted")
    say("")
    if entry["status"] != "accepted":
        say("Result: {} is {}, not accepted. Read the report above; run .agents/skills/github-flow/scripts/batch.sh next to continue "
            "it in a fresh session.".format(entry["id"], entry["status"].replace("_", " ")))
        return EXIT_NOT_ACCEPTED
    say("Result: {} is accepted ({}); {}.".format(entry["id"], entry["commit"], cost))
    if accepted_now >= BATCH_SIZE:
        say("Batch {} is full. Next: .agents/skills/github-flow/scripts/batch.sh integrate".format(state["number"]))
    else:
        say("Batch {}: {} of {} accepted. Next: .agents/skills/github-flow/scripts/batch.sh next".format(state["number"], accepted_now,
                                                                              BATCH_SIZE))
    return 0


# --- integrate -------------------------------------------------------------------------------


def unmerged_files(cwd: Path) -> List[str]:
    return [line for line in git("diff", "--name-only", "--diff-filter=U", cwd=cwd).splitlines() if line]


def merge_in_progress(cwd: Path) -> bool:
    return run(["git", "rev-parse", "--verify", "--quiet", "MERGE_HEAD"], cwd=cwd, check=False).returncode == 0


def resolve_file(cwd: Path, relative: str) -> bool:
    resolver = resolver_for(relative)
    if resolver is None:
        return False
    path = cwd / relative
    merged = resolve_conflicts(path.read_text(encoding="utf-8"), resolver)
    if merged is None:
        return False
    if relative == "feature_list.json":
        try:
            json.loads(merged)
        except ValueError:
            return False
    path.write_text(merged, encoding="utf-8")
    git("add", relative, cwd=cwd)
    return True


def run_checks(cwd: Path, feature_ids: Sequence[str]) -> List[Tuple[str, str]]:
    commands: List[List[str]] = []
    if not (cwd / "backend" / ".venv").exists():
        commands.append(["./scripts/init.sh", "--setup-python"])
    commands += [["./scripts/init.sh", "--feature", feature_id] for feature_id in feature_ids]
    commands.append(["./scripts/init.sh", "--verify"])
    environment = dict(os.environ, CI="true")
    results = []
    for command in commands:
        label = " ".join(command[1:])
        say("Checking {} ...".format(label))
        result = run(command, cwd=cwd, check=False, env=environment)
        output = (result.stdout + result.stderr).strip().splitlines()
        if result.returncode != 0:
            raise Stop("The check {} failed on the integration branch:\n{}".format(
                label, "\n".join(output[-15:])), EXIT_CHECK)
        if command[1] != "--setup-python":
            passed = [line for line in output if line.startswith("[ok]") and "backend-tests" in line]
            summary = output[-1] if output else "passed"
            if passed:
                summary = "{} ({})".format(summary, passed[-1].split(None, 2)[-1])
            results.append((label, summary))
    return results


def cmd_integrate(partial: bool) -> int:
    require_base_checkout()
    state = load_state()
    if state is None:
        raise Stop("There is no batch in progress. Start one with .agents/skills/github-flow/scripts/batch.sh next.", EXIT_WAIT)
    if state.get("pr"):
        say("Batch {} is already in PR #{}: {}".format(state["number"], state["pr"], state.get("pr_url", "")))
        return 0
    unfinished = [entry["id"] for entry in state["features"] if entry["status"] != "accepted"]
    if unfinished:
        raise Stop("Not accepted yet: {}. Run .agents/skills/github-flow/scripts/batch.sh next to finish it.".format(", ".join(unfinished)),
                   EXIT_WAIT)
    if not state["features"]:
        raise Stop("Batch {} has no features yet. Run .agents/skills/github-flow/scripts/batch.sh next.".format(state["number"]), EXIT_WAIT)
    if len(state["features"]) < BATCH_SIZE and not partial:
        raise Stop("Batch {} has {} of {} features. Run .agents/skills/github-flow/scripts/batch.sh next, or integrate --partial to ship "
                   "it now.".format(state["number"], len(state["features"]), BATCH_SIZE), EXIT_WAIT)

    worktree = ensure_worktree(WORKTREES_ROOT / "integration-batch-{}".format(state["number"]), state["branch"],
                               state["base_sha"])
    if merge_in_progress(worktree):
        left = unmerged_files(worktree)
        if left:
            raise Stop("These files still have conflicts in {}: {}. Resolve them, `git add` them, and run "
                       ".agents/skills/github-flow/scripts/batch.sh integrate again.".format(worktree, ", ".join(left)), EXIT_CONFLICT)
        git("commit", "--no-edit", cwd=worktree)
        state["manual"] += state.get("pending_manual") or []
        state["pending_manual"] = []
        save_state(state)

    for entry in state["features"]:
        branch = "feature/" + entry["id"]
        if run(["git", "merge-base", "--is-ancestor", branch, "HEAD"], cwd=worktree, check=False).returncode == 0:
            continue
        say("Merging {} ...".format(branch))
        merge = run(["git", "-c", "merge.conflictStyle=diff3", "merge", "--no-ff", "--no-edit", branch],
                    cwd=worktree, check=False)
        if merge.returncode == 0:
            continue
        conflicted = unmerged_files(worktree)
        if not conflicted:
            raise Stop("Merging {} failed:\n{}".format(branch, (merge.stdout + merge.stderr).strip()))
        left = []
        for relative in conflicted:
            if resolve_file(worktree, relative):
                state["auto_resolved"].append("{} ({})".format(relative, entry["id"]))
            else:
                left.append(relative)
        if left:
            state["pending_manual"] = ["{} ({})".format(relative, entry["id"]) for relative in left]
            save_state(state)
            raise Stop("Merging {} left conflicts that need a person: {}. They are in {}. Resolve them, `git add` "
                       "them, and run .agents/skills/github-flow/scripts/batch.sh integrate again.".format(
                           branch, ", ".join(left), worktree), EXIT_CONFLICT)
        git("commit", "--no-edit", cwd=worktree)
        save_state(state)

    progress = worktree / "PROGRESS.md"
    if progress.exists():
        counts = feature_counts((worktree / "feature_list.json").read_text(encoding="utf-8"))
        text = progress.read_text(encoding="utf-8")
        recounted = recount_progress(text, counts)
        if recounted != text:
            progress.write_text(recounted, encoding="utf-8")
            git("add", "PROGRESS.md", cwd=worktree)
            git("commit", "-m", "docs: recount accepted features after the batch {} merges".format(state["number"]),
                cwd=worktree)

    head = git("rev-parse", "HEAD", cwd=worktree)
    if state.get("checks_sha") != head:
        state["checks"] = run_checks(worktree, [entry["id"] for entry in state["features"]])
        state["checks_sha"] = head
        save_state(state)

    git("push", "-u", "origin", state["branch"], cwd=worktree)
    existing = json.loads(run(["gh", "pr", "list", "--state", "all", "--head", state["branch"], "--base", BASE_BRANCH,
                               "--json", "number,url"]).stdout or "[]")
    if existing:
        state["pr"], state["pr_url"] = existing[0]["number"], existing[0]["url"]
    else:
        catalog = features_by_id(worktree)
        details = {}
        for entry in state["features"]:
            feature_worktree = WORKTREES_ROOT / entry["id"]
            commits = git("log", "--format=%h", "--reverse", "{}..feature/{}".format(state["base_sha"], entry["id"]),
                          cwd=worktree).split()
            details[entry["id"]] = {"title": catalog[entry["id"]]["title"], "commits": commits,
                                    "usage": session_usage(feature_worktree, entry["id"]),
                                    "report": session_report(feature_worktree, entry["id"])}
        body_file = worktree / "build" / "batch-pr-body.md"
        body_file.parent.mkdir(parents=True, exist_ok=True)
        body_file.write_text(build_pr_body(state, details), encoding="utf-8")
        title = "Batch {}: {}".format(state["number"], ", ".join(entry["id"] for entry in state["features"]))
        url = run(["gh", "pr", "create", "--base", BASE_BRANCH, "--head", state["branch"], "--title", title,
                   "--body-file", str(body_file)], cwd=worktree).stdout.strip().splitlines()[-1]
        state["pr"], state["pr_url"] = int(url.rstrip("/").rsplit("/", 1)[-1]), url
    save_state(state)
    say("")
    say("Result: batch {} is ready for review in PR #{}: {}".format(state["number"], state["pr"], state["pr_url"]))
    say("After it is merged, run .agents/skills/github-flow/scripts/batch.sh next to start the next batch.")
    return 0


# --- status ----------------------------------------------------------------------------------


def cmd_status() -> int:
    state = load_state()
    if state is None:
        say("Result: no batch is in progress. Start one with .agents/skills/github-flow/scripts/batch.sh next.")
        return 0
    say("Batch {} from {} {} (branch {}).".format(state["number"], BASE_BRANCH, state["base_sha"][:7],
                                                  state["branch"]))
    for entry in state["features"]:
        say("  {}: {}{}".format(entry["id"], entry["status"].replace("_", " "),
                                " ({})".format(entry["commit"]) if entry.get("commit") else ""))
    if not state["features"]:
        say("  no features yet")
    accepted = sum(1 for entry in state["features"] if entry["status"] == "accepted")
    if state.get("pr"):
        say("Result: batch {} is in PR #{}: {}".format(state["number"], state["pr"], state.get("pr_url", "")))
    else:
        say("Result: batch {} has {} of {} features accepted.".format(state["number"], accepted, BATCH_SIZE))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog=".agents/skills/github-flow/scripts/batch.sh", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    next_parser = commands.add_parser("next", help="run the next feature of the batch in its own session")
    next_parser.add_argument("--note", default="", help="the owner's decisions for this feature")
    next_parser.add_argument("--no-decisions", action="store_true",
                             help="run a feature that has no spec without owner decisions")
    integrate_parser = commands.add_parser("integrate", help="merge the batch, run the checks, and open the PR")
    integrate_parser.add_argument("--partial", action="store_true",
                                  help="ship a batch with fewer than {} features".format(BATCH_SIZE))
    commands.add_parser("status", help="show the current batch")
    args = parser.parse_args(argv)
    try:
        if args.command == "next":
            return cmd_next(args.note, args.no_decisions)
        if args.command == "integrate":
            return cmd_integrate(args.partial)
        return cmd_status()
    except Stop as stop:
        say("Result: " + str(stop))
        return stop.code


if __name__ == "__main__":
    sys.exit(main())
