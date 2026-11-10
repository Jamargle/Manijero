# Colloquial variants review

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## What a variant is

A variant is a plain, everyday rewording of one test question a grower would ask ("¿cuándo tengo
que mandar los papeles de la PAC?" instead of the official wording). The developer drafted one for
each approved test question. Approving a variant means only that it may be scored in an offline,
report-only comparison of three search setups: no rewriting, the approved word glossary, and the
glossary plus terms suggested by the local model. Nothing applies to the app, the service, or a
release, and no setting changes. You never edit the file by hand. Both commands need the local
answer tools.

## Review and decide

1. **List the waiting variants.** Paste `./scripts/init.sh --colloquial-review`. For each variant
   you see its number, the everyday wording, and the test question it belongs to. The same list
   with every state is in `build/colloquial-ab/variants.txt`.
   - Expected: `Result: 49 colloquial variants wait for your decision (0 approved, 0 rejected). ...`
2. **Record your decision.** Use the numbers shown, with your name in quotes:

   ```sh
   ./scripts/init.sh --colloquial-decide approve "Diego" 1 2 3
   ./scripts/init.sh --colloquial-decide reject "Diego" 4
   ```

   - Expected: `Result: recorded approve for 3 colloquial variants by Diego. 46 still wait for your decision.`
   - A repeated decision replaces the earlier one. Bad input records nothing.
   - Reject a variant if it changes the meaning, adds a number, date, or legal claim, assumes a
     land fact the question did not give, or would give away part of the answer.

### If the review shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the colloquial variant review did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools), then repeat. |
| `Result: nothing was recorded. Write approve or reject, your name in quotes, and at least one variant number ...` | The decision, the name, or the numbers are missing or invalid. | Copy the example in the line and repeat. |
| `Result: nothing was recorded. These variant numbers are not in the list: ...` | A number or id does not exist. | Run the review again and use the numbers shown. |
| `Result: nothing was recorded. Colloquial variant <n> cannot be approved as written. ...` | The variant breaks a safety rule. | Reject it, or send the line to the developer. |
| `Result: nothing was recorded. The colloquial variant list does not match the approved golden questions. ...` | The test questions changed. | Ask the developer to update the list, then repeat. |
| `Result: the colloquial variant list could not be read ...` | The file is damaged. | Send the line to the developer; nothing changed. |

## After your decisions

Send the developer every `Result:` line and the final counts. They run the developer check, ask the
already-installed local model for search terms, and print one report line plus a report under
`build/colloquial-ab/`. That comparison is report-only: it recommends nothing automatically, and
you decide whether any later change is worth a separate feature. An incomplete review means no
comparison is reported. This work is accepted by the validator after an automated command check;
there are no walkthrough steps to run for it.
