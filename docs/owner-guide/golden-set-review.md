# Golden set review

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## Review the golden questions

An agent drafted plain-Spanish test questions in `knowledge/golden_set.json`. None counts in any
evaluation until you approve it. Each question is shown beside the exact official sentence it
relies on. You never edit the file by hand. Both commands need the local answer tools.

1. **List the waiting questions.** Paste `./scripts/init.sh --golden-review`. Read each one: the
   question, what the answer must say (or a deliberate "no lo sé"), and the quoted official text.
   The same list with every state is in `build/golden-review/drafts.txt`.
   - Expected: `Result: N golden questions wait for your decision (A approved, R rejected). ...`
2. **Record your decision.** Use the numbers shown, with your name in quotes:

   ```sh
   ./scripts/init.sh --golden-decide approve "Diego" 1 2 3
   ./scripts/init.sh --golden-decide reject "Diego" 4
   ```

   - Expected: `Result: recorded approve for 3 golden questions by Diego. P still wait for your decision.`
   - A repeated decision replaces the earlier one. Bad input records nothing.

### If the golden review shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the golden review did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools), then repeat. |
| `Result: nothing was recorded. Write approve or reject, your name in quotes, and at least one question number ...` | The word, the name, or the numbers are missing or invalid. | Copy the example in the line and repeat. |
| `Result: nothing was recorded. These question numbers are not in the list: ...` | A number or id does not exist. | Run the review again and use the numbers shown. |
| `Result: nothing was recorded. Question <n> no longer matches the approved sources. ...` | The quoted text no longer matches the approved sources. | Do not approve it; send the line to the developer. |
| `Result: the golden question list could not be read ...` | The file is damaged. | Send the line to the developer; nothing changed. |

## Owner walkthrough: golden set review

Do this once, after the developer accepts the feature. Write down each `Result:` line.

1. Run `./scripts/init.sh --golden-review`. Expect the waiting list and `Result: 46 golden questions wait ...`.
2. **Missing input:** run `./scripts/init.sh --golden-decide approve 1`. Expect
   `Result: nothing was recorded. Write approve or reject, your name in quotes, ...`
3. **Unknown number:** run `./scripts/init.sh --golden-decide approve "Diego" 999`. Expect
   `Result: nothing was recorded. These question numbers are not in the list: 999. ...`
4. **Recovery:** run `./scripts/init.sh --golden-review` again; the count is unchanged.
5. Read every question beside its quoted source. Approve those you trust and reject the rest, in
   groups, with `--golden-decide`. Reject anything unclear or beyond the quoted text.
6. Run `./scripts/init.sh --golden-review`. Expect `Result: no golden questions wait for your decision (A approved, R rejected).`
7. Send the developer every `Result:` line and the final counts. They commit the changed
   `knowledge/golden_set.json`.
