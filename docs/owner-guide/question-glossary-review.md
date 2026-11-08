# Question glossary review

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## Review the word pairs

A word pair joins a word growers use ("papeleo") with the official term ("solicitud"). When you
approve a pair, the search also looks for the official term; the grower's own words are kept and
the answer never says anything in their name. Nothing applies until you approve it. You never edit
the file by hand. Both commands need the local answer tools.

1. **List the waiting pairs.** Paste `./scripts/init.sh --glossary-review`. For each pair you see
   the number, the grower's words, the official term, where it came from, how many approved
   passages contain the official term, and, for pairs from a test question, the words that would be
   added to that question. The same list with every state is in `build/glossary-review/pairs.txt`.
   - Expected: `Result: N word pairs wait for your decision (A approved, R rejected). ...`
2. **Record your decision.** Use the numbers shown, with your name in quotes:

   ```sh
   ./scripts/init.sh --glossary-decide approve "Diego" 1 2 3
   ./scripts/init.sh --glossary-decide reject "Diego" 4
   ```

   - Expected: `Result: recorded approve for 3 word pairs by Diego. P still wait for your decision.`
   - A repeated decision replaces the earlier one. Bad input records nothing.
   - Reject a pair if the official term is broader than the grower's word or could mislead.

### If the review shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the glossary review did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools), then repeat. |
| `Result: nothing was recorded. Write approve or reject, your name in quotes, and at least one word pair number ...` | The word, the name, or the numbers are missing or invalid. | Copy the example in the line and repeat. |
| `Result: nothing was recorded. These word pair numbers are not in the list: ...` | A number or id does not exist. | Run the review again and use the numbers shown. |
| `Result: nothing was recorded. Word pair <n> cannot be approved as written. ...` | The pair breaks a safety rule. | Reject it, or send the line to the developer. |
| `Result: the word pair list could not be read ...` | The file is damaged. | Send the line to the developer; nothing changed. |

## Owner walkthrough: word pair review

Do this once, after the developer accepts the feature. Write down each `Result:` line.

1. Run `./scripts/init.sh --glossary-review`. Expect the waiting list and `Result: 15 word pairs wait ...`.
2. **Missing name:** run `./scripts/init.sh --glossary-decide approve 1`. Expect
   `Result: nothing was recorded. Write approve or reject, your name in quotes, ...`
3. **Unknown number:** run `./scripts/init.sh --glossary-decide approve "Diego" 999`. Expect
   `Result: nothing was recorded. These word pair numbers are not in the list: 999. ...`
4. **Recovery:** run `./scripts/init.sh --glossary-review` again; the count is unchanged.
5. Approve the pairs you trust and reject the rest, in groups, with `--glossary-decide`.
6. Run `./scripts/init.sh --glossary-review`. Expect `Result: no word pairs wait for your decision (A approved, R rejected).`
7. Send the developer every `Result:` line and the final counts. They run the glossary check and
   commit the changed `backend/config/question_glossary.json`.
