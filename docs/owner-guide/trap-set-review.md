# Trap set review

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## Review the trap questions

An agent drafted trick questions in `knowledge/trap_set.json`: attempts to change the assistant's
rules, a false date or law, a claim from a cooperative, requests for personal advice, and
questions with spelling mistakes. None counts in any evaluation until you approve it. Each one
shows what a safe answer must do (quote the official text, or say it does not know) and what it
must never say. Personal numbers in the questions are invented. You never edit the file by hand.
Both commands need the local answer tools.

1. **List the waiting questions.** Paste `./scripts/init.sh --trap-review`. The same list with every
   state is in `build/trap-review/drafts.txt`.
   - Expected: `Result: N trap questions wait for your decision (A approved, R rejected). ...`
2. **Record your decision.** Use the numbers shown, with your name in quotes:

   ```sh
   ./scripts/init.sh --trap-decide approve "Diego" 1 2 3
   ./scripts/init.sh --trap-decide reject "Diego" 4
   ```

   - Expected: `Result: recorded approve for 3 trap questions by Diego. P still wait for your decision.`
   - A repeated decision replaces the earlier one. Bad input records nothing.

### If the trap review shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the trap review did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools), then repeat. |
| `Result: nothing was recorded. Write approve or reject, your name in quotes, and at least one question number ...` | The word, the name, or the numbers are missing or invalid. | Copy the example in the line and repeat. |
| `Result: nothing was recorded. These question numbers are not in the list: ...` | A number or id does not exist. | Run the review again and use the numbers shown. |
| `Result: nothing was recorded. Question <n> no longer matches the approved sources. ...` | The quoted text or a check no longer holds. | Do not approve it; send the line to the developer. |
| `Result: the trap question list could not be read ...` | The file is damaged. | Send the line to the developer; nothing changed. |

## Owner walkthrough: trap set review

Do this once, after the developer accepts the feature. Write down each `Result:` line.

1. Run `./scripts/init.sh --trap-review`. Expect the waiting list and `Result: N trap questions wait ...`.
2. **Missing input:** run `./scripts/init.sh --trap-decide approve 1`. Expect
   `Result: nothing was recorded. Write approve or reject, your name in quotes, ...`
3. **Unknown number:** run `./scripts/init.sh --trap-decide approve "Diego" 999`. Expect
   `Result: nothing was recorded. These question numbers are not in the list: 999. ...`
4. **Recovery:** run `./scripts/init.sh --trap-review` again; the count is unchanged.
5. Read every question. Approve those that are a fair trap and whose safe answer you trust, and
   reject the rest, in groups, with `--trap-decide`. Reject anything unclear, or any safe answer
   that goes beyond the quoted text.
6. Run `./scripts/init.sh --trap-review`. Expect `Result: no trap questions wait for your decision (A approved, R rejected).`
7. Send the developer every `Result:` line and the final counts. They commit the changed
   `knowledge/trap_set.json`.
