# Knowledge review pull requests

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

A prepared knowledge update can be reviewed as one GitHub pull request to `main`, with the
proposed source and passage change, the review evidence, and how the reviewed test questions
answer before and after. **You merge it yourself in the browser.** The tool never merges, never
turns on auto-merge, and never force-pushes. Merging changes the files on GitHub; publishing a
new knowledge release is a separate step afterwards.

## Protect main (one time)

Paste `./scripts/init.sh --knowledge-review-protect`. It reads the `protected-main` ruleset, says
what will change, and asks you to type `yes`: only pull requests can change `main` with no
approval required (your merge is the approval); commits GitHub cannot link to an account need no
extra approval, so the review pull request the tool opens stays mergeable by you; the checks
`fast` and `full` must pass; force pushes are blocked; people and apps already allowed to bypass
it stay allowed, and any other rule already on it stays in place. Expect
`Result: main is now protected by protected-main.` Running it again says `already protected`.
To undo later, open the repository on GitHub, go to **Settings > Rules > protected-main**, and
set enforcement to **Disabled**.

## Open the review

Paste `./scripts/init.sh --knowledge-review-open`. It opens one pull request per ready package
on branch `knowledge-review/<package>` and prints `opened: <address>`. Packages that are not
ready, whose approved knowledge changed since preparation, or whose checks fail are named with
the first thing to do and are not sent. An existing branch without a saved request is refused
(`branch exists`), never overwritten.

## Read it and merge it yourself

Open the address in your browser. The top says the owner merges it and that the evaluation
counts are report-only, not a quality or legal-coverage claim. Then:

1. Read **Evaluation results**: expected-answer agreement, unexpected answers, source and passage
   matches before and after.
2. Read **Automated checks** and the **Review evidence**, especially the proposed changes.
3. Wait until the `fast` and `full` checks are green.
4. Press **Merge pull request** yourself. Nothing is published by that click.

Running the open command again only reports `already open`, `merged on GitHub`, or `closed
without merging`; it never creates a second request for the same package.

After the merge, send the knowledge to QA with `./scripts/init.sh --qa-knowledge-deploy` (see
[`qa.md`](qa.md), "Send approved knowledge to QA"), or build and publish a release by hand with the
separate release steps in [`backend/README.md`](../../backend/README.md) ("Knowledge reindex and release"). A merged
request, a green check, or the evaluation counts do not prove broader legal coverage or better
answers.

| You see | What it means | What to do |
|---|---|---|
| `The GitHub tool (gh) is not installed.` | GitHub's command-line tool is missing. | Install it from https://cli.github.com, then run again. |
| `The GitHub tool is not logged in.` | The tool has no account. | Run `gh auth login`, then run again. |
| `The knowledge review folder is missing.` | No review package was prepared. | Ask a developer to prepare one. |
| `The approved knowledge changed since this package was prepared.` | `main` moved after preparation. | Prepare a new package. |
| `(branch exists)` in the package line | An earlier attempt left the branch. | Remove it on GitHub, then prepare again. |
| `GitHub has no ruleset named protected-main.` | Protect was not set up. | Create that ruleset on GitHub, then retry. |
