"""The batch loop ``.agents/skills/github-flow/scripts/batch.sh`` (``batch_flow.py`` beside it).

Unit tests cover the conflict resolvers and helpers. The end-to-end tests build a throwaway
project in a temporary folder: a bare ``origin``, a main checkout with the real batch scripts and
selector, and fake ``feature-session.sh``, ``init.sh``, and ``gh`` that only record what they were
asked to do. No real agent, GitHub call, or project check runs.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
REPO_ROOT = Path(__file__).resolve().parents[4]
BATCH = ".agents/skills/github-flow/scripts/batch.sh"

_spec = importlib.util.spec_from_file_location("batch_flow", SKILL_SCRIPTS / "batch_flow.py")
bf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bf)


# --- helpers ---------------------------------------------------------------------------------


def test_next_batch_number_follows_the_highest_integration_branch() -> None:
    names = ["main", "integration/2026-11-01-batch-3", "origin/integration/2026-11-02-batch-4", "feature/x"]
    assert bf.next_batch_number(names) == 5
    assert bf.next_batch_number(["main"]) == 1


def test_next_batch_number_skips_numbers_of_archived_batches_whose_branch_is_gone() -> None:
    archived = bf.archived_batch_numbers(["batch-1.json", "batch-8.json", "current.json", "batch-x.json", "batch7-next-1.log"])
    assert archived == [1, 8]
    assert bf.next_batch_number(["main", "integration/2026-11-08-batch-1"], archived) == 9
    assert bf.next_batch_number(["main"], []) == 1


def test_open_pull_request_never_reuses_a_merged_or_closed_pr() -> None:
    merged = {"number": 202, "url": "u202", "state": "MERGED"}
    closed = {"number": 203, "url": "u203", "state": "CLOSED"}
    opened = {"number": 206, "url": "u206", "state": "OPEN"}
    assert bf.open_pull_request([merged, closed]) is None
    assert bf.open_pull_request([merged, opened]) == opened
    assert bf.open_pull_request([]) is None


def test_choose_feature_takes_the_first_ready_feature_not_in_the_batch() -> None:
    status = "\n".join([
        "SUMMARY total=4",
        "FEATURE id=held status=on_hold ready=no unmet=- role=on_hold spec=yes",
        "FEATURE id=a status=not_started ready=yes unmet=- role=planner spec=no",
        "FEATURE id=b status=not_started ready=no unmet=a role=planner spec=no",
        "FEATURE id=c status=not_started ready=yes unmet=- role=planner spec=no",
    ])
    assert bf.choose_feature(status, []) == "a"
    assert bf.choose_feature(status, ["a"]) == "c"
    assert bf.choose_feature(status, ["a", "c"]) is None


def test_recount_progress_fixes_both_counts() -> None:
    text = "**Feature status** — 77 of 120 features are accepted, ok. The 44 `not_started` features remain."
    counts = {"total": 120, "accepted": 79, "not_started": 40}
    assert bf.recount_progress(text, counts) == (
        "**Feature status** — 79 of 120 features are accepted, ok. The 40 `not_started` features remain.")


# --- conflict resolvers ----------------------------------------------------------------------


def test_token_merge_keeps_both_insertions_at_one_point_ours_first() -> None:
    base = "including `c` (build),"
    ours = "including `a` (one), `c` (build),"
    theirs = "including `b` (two), `c` (build),"
    assert bf.token_merge(base, ours, theirs) == "including `a` (one), `b` (two), `c` (build),"


def test_token_merge_keeps_ours_for_a_clashing_count_and_reflowed_whitespace() -> None:
    base = "Now 76 of 120 are\naccepted."
    ours = "Now 77 of 120 are accepted."
    theirs = "Now 78 of 120 are\naccepted, and more."
    assert bf.token_merge(base, ours, theirs) == "Now 77 of 120 are accepted, and more."


def test_token_merge_refuses_two_different_rewrites_of_the_same_words() -> None:
    assert bf.token_merge("the old rule", "the new rule", "the other rule") is None


def test_union_keeps_rows_both_sides_appended() -> None:
    assert bf.union_or_merge("| a |\n", "", "| b |\n") == "| a |\n| b |\n"
    assert bf.union_or_merge("| a |\n", "", "| a |\n") == "| a |\n"


def test_newest_status_lines_keeps_the_more_advanced_status_per_feature() -> None:
    ours = '    {"id": "a", "status": "accepted"},\n    {"id": "b", "status": "not_started"},\n'
    theirs = '    {"id": "a", "status": "not_started"},\n    {"id": "b", "status": "accepted"},\n'
    assert bf.newest_status_lines(ours, "", theirs) == (
        '    {"id": "a", "status": "accepted"},\n    {"id": "b", "status": "accepted"},\n')
    assert bf.newest_status_lines("not a feature line\n", "", theirs) is None


def test_resolve_conflicts_leaves_code_to_a_person() -> None:
    assert bf.resolver_for("backend/app/settings.py") is None
    assert bf.resolver_for("scripts/init.sh") is None
    assert bf.resolver_for("docs/progress/session-log.md") is bf.union_or_merge
    assert bf.resolver_for("docs/owner-guide/qa.md") is bf.union_or_merge
    text = "top\n<<<<<<< HEAD\nthe new rule\n||||||| base\nthe old rule\n=======\nthe other rule\n>>>>>>> x\n"
    assert bf.resolve_conflicts(text, bf.union_or_merge) is None
    text = "top\n<<<<<<< HEAD\n| a |\n||||||| base\n=======\n| b |\n>>>>>>> x\nend\n"
    assert bf.resolve_conflicts(text, bf.union_or_merge) == "top\n| a |\n| b |\nend\n"


def test_pr_body_lists_features_usage_and_closes_issues() -> None:
    state = {"number": 5, "base_sha": "abcdef0123", "features": [
        {"id": "a", "issue": 7, "note": "card in chat", "status": "accepted"},
        {"id": "b", "issue": 8, "note": "", "status": "accepted"}],
        "auto_resolved": ["feature_list.json (b)"], "manual": [], "checks": [["--verify", "Full tier passed."]]}
    details = {"a": {"title": "Do A", "commits": ["1111111"], "usage": {"turns": 3, "minutes": 2.0, "cost": 1.5},
                     "report": "A done."},
               "b": {"title": "Do B", "commits": [], "usage": None, "report": None}}
    body = bf.build_pr_body(state, details)
    assert "| `a`: Do A | `1111111` | #7 | [record](docs/validations/a.md) |" in body
    assert "- **`a`:** card in chat" in body and "`b`:**" not in body
    assert "| **Batch** | | | **$1.50** |" in body
    assert "Closes #7, Closes #8." in body
    assert "- `--verify`: Full tier passed." in body


# --- end to end ------------------------------------------------------------------------------

FEATURES = [
    ("a", []), ("b", []), ("c", []), ("d", []), ("e", ["a"]),
]

FAKE_SESSION = """#!{python}
# Fake feature session: accept the feature, log it, and commit, like a real headless session.
import json, os, re, subprocess, sys
args = sys.argv[1:]
feature = args[-1]
with open(os.environ["BATCH_TEST_CALLS"], "a") as calls:
    calls.write(json.dumps({{"session": args}}) + "\\n")
data = json.load(open("feature_list.json"))
for item in data["features"]:
    if item["id"] == feature:
        item["status"] = "accepted"
accepted = sum(1 for item in data["features"] if item["status"] == "accepted")
lines = ["{{\\n", '  "features": [\\n']
lines += ["    " + json.dumps(item) + ("," if i < len(data["features"]) - 1 else "") + "\\n"
          for i, item in enumerate(data["features"])]
lines += ["  ]\\n", "}}\\n"]
open("feature_list.json", "w").write("".join(lines))
progress = open("PROGRESS.md").read()
progress = re.sub(r"\\d+ of 5 features are accepted, including ",
                  "{{}} of 5 features are accepted, including `{{}}` (done), ".format(accepted, feature), progress)
open("PROGRESS.md", "w").write(progress)
with open("docs/progress/session-log.md", "a") as log:
    log.write("| {{}} accepted |\\n".format(feature))
os.makedirs("build/agent-sessions", exist_ok=True)
with open("build/agent-sessions/usage.tsv", "a") as usage:
    usage.write("stamp\\tfeature\\tturns\\tminutes\\tinput\\toutput\\tcache_read\\tcache_write\\tcost_usd\\n")
    usage.write("1\\t{{}}\\t10\\t5.0\\t1\\t1\\t1\\t1\\t2.5000\\n".format(feature))
open("build/agent-sessions/{{}}-1.log".format(feature), "w").write(json.dumps({{"result": feature + " accepted."}}) + "\\n")
subprocess.run(["git", "add", "-A", "."], check=True)
subprocess.run(["git", "commit", "-q", "-m", "feat: complete " + feature], check=True)
print("Session for", feature, "done.")
"""

FAKE_INIT = """#!{python}
import json, os, sys
with open(os.environ["BATCH_TEST_CALLS"], "a") as calls:
    calls.write(json.dumps({{"init": sys.argv[1:]}}) + "\\n")
if sys.argv[1:] == ["--setup-python"]:
    os.makedirs("backend/.venv", exist_ok=True)
print("[ok]   backend-tests      3 passed")
print("Fast tier passed.")
"""

FAKE_GH = """#!{python}
# Fake gh: issues and PRs live in a JSON file next to the calls log.
import json, os, sys
state_path = os.environ["BATCH_TEST_GH"]
state = json.load(open(state_path)) if os.path.exists(state_path) else {{"issues": [], "prs": []}}
args = sys.argv[1:]
with open(os.environ["BATCH_TEST_CALLS"], "a") as calls:
    calls.write(json.dumps({{"gh": args}}) + "\\n")
def value(flag):
    return args[args.index(flag) + 1]
if args[:2] == ["issue", "list"]:
    print(json.dumps(state["issues"]))
elif args[:2] == ["issue", "create"]:
    number = len(state["issues"]) + 1
    state["issues"].append({{"number": number, "title": value("--title")}})
    print("https://github.com/o/r/issues/{{}}".format(number))
elif args[:2] == ["pr", "list"]:
    print(json.dumps([{{"number": p["number"], "url": p["url"]}} for p in state["prs"] if p["head"] == value("--head")]))
elif args[:2] == ["pr", "create"]:
    number = 100 + len(state["prs"])
    url = "https://github.com/o/r/pull/{{}}".format(number)
    state["prs"].append({{"number": number, "url": url, "head": value("--head"), "state": "OPEN",
                         "title": value("--title"), "body": open(value("--body-file")).read()}})
    print(url)
elif args[:2] == ["pr", "view"]:
    print([p for p in state["prs"] if p["number"] == int(args[2])][0]["state"])
json.dump(state, open(state_path, "w"))
"""


def _write_tool(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.format(python=sys.executable), encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def project(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("GIT_"):
            environment.pop(key)
    bin_dir = tmp_path / "bin"
    _write_tool(bin_dir / "gh", FAKE_GH)
    environment.update({
        "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "MANIJERO_PYTHON": sys.executable,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PATH": "{}:{}".format(bin_dir, environment.get("PATH", "/usr/bin:/bin")),
        "BATCH_TEST_CALLS": str(tmp_path / "calls.jsonl"), "BATCH_TEST_GH": str(tmp_path / "gh.json"),
    })

    def git(*args: str, cwd: Path) -> str:
        return subprocess.run(["git", *args], cwd=cwd, env=environment, check=True, text=True,
                              capture_output=True).stdout.strip()

    origin = tmp_path / "origin.git"
    git("init", "-q", "--bare", "-b", "main", str(origin), cwd=tmp_path)
    main = tmp_path / "Proj"
    git("clone", "-q", str(origin), str(main), cwd=tmp_path)
    git("checkout", "-q", "-b", "main", cwd=main)
    (main / "scripts").mkdir()
    shutil.copy2(REPO_ROOT / "scripts" / "select-feature.sh", main / "scripts" / "select-feature.sh")
    (main / BATCH).parent.mkdir(parents=True)
    for name in ("batch.sh", "batch_flow.py"):
        shutil.copy2(SKILL_SCRIPTS / name, (main / BATCH).parent / name)
    _write_tool(main / "scripts" / "feature-session.sh", FAKE_SESSION)
    _write_tool(main / "scripts" / "init.sh", FAKE_INIT)
    features = [{"id": fid, "area": "x", "title": "Do " + fid.upper(), "status": "not_started", "depends_on": deps,
                 "spec": "docs/specs/{}.md".format(fid), "validation": "docs/validations/{}.md".format(fid)}
                for fid, deps in FEATURES]
    lines = ["{\n", '  "features": [\n']
    lines += ["    " + json.dumps(item) + ("," if i < len(features) - 1 else "") + "\n"
              for i, item in enumerate(features)]
    lines += ["  ]\n", "}\n"]
    (main / "feature_list.json").write_text("".join(lines), encoding="utf-8")
    (main / "PROGRESS.md").write_text("# Progress\n\n**Feature status** — 0 of 5 features are accepted, including "
                                      "nothing yet. The 5 `not_started` features remain.\n", encoding="utf-8")
    (main / "docs" / "progress").mkdir(parents=True)
    (main / "docs" / "progress" / "session-log.md").write_text("| Log |\n", encoding="utf-8")
    (main / "docs" / "specs").mkdir()
    for fid in ("b", "c", "e"):  # a and d have no spec, so they need owner decisions
        (main / "docs" / "specs" / "{}.md".format(fid)).write_text("spec\n", encoding="utf-8")
    (main / ".gitignore").write_text("build/\n", encoding="utf-8")
    git("add", "-A", ".", cwd=main)
    git("commit", "-q", "-m", "start", cwd=main)
    git("push", "-q", "-u", "origin", "main", cwd=main)

    def batch(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["./" + BATCH, *args], cwd=main, env=environment, text=True,
                              capture_output=True)

    def calls() -> list:
        path = tmp_path / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def gh_state() -> dict:
        return json.loads((tmp_path / "gh.json").read_text())

    def set_pr_state(value: str) -> None:
        state = gh_state()
        for pr in state["prs"]:
            pr["state"] = value
        (tmp_path / "gh.json").write_text(json.dumps(state))

    return {"main": main, "origin": origin, "batch": batch, "calls": calls, "gh": gh_state, "git": git,
            "set_pr_state": set_pr_state, "worktrees": tmp_path / "Proj-worktrees"}


def test_a_full_batch_runs_three_features_and_opens_one_pr(project) -> None:
    batch, main = project["batch"], project["main"]

    first = batch("next")
    assert first.returncode == bf.EXIT_DECISIONS, first.stdout + first.stderr
    assert "Next feature: a" in first.stdout and "--note" in first.stdout
    assert not [call for call in project["calls"]() if "session" in call]

    accepted = batch("next", "--note", "card in chat")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "Result: a is accepted" in accepted.stdout and "1 of 3 accepted" in accepted.stdout
    [session] = [call["session"] for call in project["calls"]() if "session" in call]
    assert session[:2] == ["--headless", "--note"] and "card in chat" in session[2] and session[-1] == "a"

    for expected in ("b", "c"):  # e waits on a, which is not on main yet
        result = batch("next")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Result: {} is accepted".format(expected) in result.stdout
    assert "Batch 1 is full" in result.stdout

    full = batch("next")
    assert full.returncode == bf.EXIT_WAIT and "already has 3 accepted" in full.stdout

    integrated = batch("integrate")
    assert integrated.returncode == 0, integrated.stdout + integrated.stderr
    assert "ready for review in PR #100" in integrated.stdout

    branch = "integration/{}-batch-1".format(datetime.date.today().isoformat())
    merged = project["worktrees"] / "integration-batch-1"
    statuses = {item["id"]: item["status"] for item in json.loads((merged / "feature_list.json").read_text())["features"]}
    assert statuses == {"a": "accepted", "b": "accepted", "c": "accepted", "d": "not_started", "e": "not_started"}
    progress = (merged / "PROGRESS.md").read_text()
    assert "3 of 5 features are accepted, including `a` (done), `b` (done), `c` (done), nothing yet." in progress
    assert "The 2 `not_started` features" in progress
    assert (merged / "docs/progress/session-log.md").read_text() == "| Log |\n| a accepted |\n| b accepted |\n| c accepted |\n"
    assert project["git"]("ls-remote", "--heads", str(project["origin"]), branch, cwd=main)

    [pr] = project["gh"]()["prs"]
    assert pr["head"] == branch and pr["title"] == "Batch 1: a, b, c"
    assert "Closes #1, Closes #2, Closes #3." in pr["body"] and "- **`a`:** card in chat" in pr["body"]
    assert "**$7.50**" in pr["body"] and "a accepted." in pr["body"]
    checks = [call["init"] for call in project["calls"]() if "init" in call]
    assert checks == [["--setup-python"], ["--feature", "a"], ["--feature", "b"], ["--feature", "c"], ["--verify"]]
    assert not [call for call in project["calls"]() if call.get("gh", [None])[:2] == ["pr", "merge"]]

    waiting = batch("next")
    assert waiting.returncode == bf.EXIT_WAIT and "waiting for review in PR #100" in waiting.stdout

    project["set_pr_state"]("MERGED")
    after = batch("next")
    assert after.returncode == bf.EXIT_DECISIONS, after.stdout + after.stderr
    assert "Batch 1 was merged" in after.stdout and "Started batch 2" in after.stdout
    assert (main / "build" / "batches" / "batch-1.json").exists()


def test_integrate_stops_on_a_code_conflict_and_continues_after_a_person_resolves_it(project) -> None:
    batch, main, git = project["batch"], project["main"], project["git"]
    (main / "app.py").write_text("VALUE = 1\n")
    git("add", "app.py", cwd=main)
    git("commit", "-q", "-m", "app", cwd=main)
    git("push", "-q", "origin", "main", cwd=main)

    assert batch("next", "--no-decisions").returncode == 0
    for fid, value in (("a", "2"),):
        worktree = project["worktrees"] / fid
        (worktree / "app.py").write_text("VALUE = {}\n".format(value))
        git("commit", "-q", "-am", "change app", cwd=worktree)
    assert batch("next").returncode == 0
    worktree = project["worktrees"] / "b"
    (worktree / "app.py").write_text("VALUE = 3\n")
    git("commit", "-q", "-am", "change app", cwd=worktree)

    stopped = batch("integrate", "--partial")
    assert stopped.returncode == bf.EXIT_CONFLICT, stopped.stdout + stopped.stderr
    assert "app.py" in stopped.stdout and "need a person" in stopped.stdout

    merged = project["worktrees"] / "integration-batch-1"
    again = batch("integrate", "--partial")
    assert again.returncode == bf.EXIT_CONFLICT and "still have conflicts" in again.stdout

    (merged / "app.py").write_text("VALUE = 3\n")
    git("add", "app.py", cwd=merged)
    done = batch("integrate", "--partial")
    assert done.returncode == 0, done.stdout + done.stderr
    [pr] = project["gh"]()["prs"]
    assert "Resolved by hand: `app.py (b)`" in pr["body"]


def test_integrate_refuses_a_short_batch_without_partial_and_a_worktree_run(project) -> None:
    batch = project["batch"]
    assert batch("next", "--no-decisions").returncode == 0
    short = batch("integrate")
    assert short.returncode == bf.EXIT_WAIT and "1 of 3 features" in short.stdout

    from_worktree = subprocess.run(["./" + BATCH, "status"], cwd=project["worktrees"] / "a", text=True,
                                   capture_output=True, env=dict(os.environ, MANIJERO_PYTHON=sys.executable))
    assert from_worktree.returncode == 0  # status only reads; next and integrate refuse
    refused = subprocess.run(["./" + BATCH, "integrate"], cwd=project["worktrees"] / "a", text=True,
                             capture_output=True, env=dict(os.environ, MANIJERO_PYTHON=sys.executable))
    assert refused.returncode == bf.EXIT_ERROR and "not from a worktree" in refused.stdout
