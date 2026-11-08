# Usability session

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## Owner walkthrough: usability session

Run this with two or three people who are not used to computers. The kit is in `docs/usability-session/`
(Spanish): facilitator script, consent note, task cards, observation sheet, and debrief questions. Use made-up
land data only. Never write names or phone numbers anywhere.

1. **Prepare QA and the app.** Run `./scripts/init.sh --qa-status`. Expect `Result: QA is running at ...`. Then run
   `./scripts/init.sh --desktop-qa` and keep the `Manijero QA` window open.
2. **Print the kit.** Print the five files. Make one observation sheet per person.
3. **Run each person.** Follow `guion-facilitador.md`: read the consent note, get a spoken yes, write the code (`P1`,
   `P2`...) on the sheet, hand over the four task cards one at a time, then ask the final questions.
4. **Record.** Run `./scripts/init.sh --usability-record` and answer the prompts from the sheet. Expect a recap, then
   `Result: P1 was saved; the results file holds 1 participant: ~/manijero/usability/usability-results.json.`
5. **Reset.** Before the next person, in the QA app: `Quitar` each land, `Borrar para siempre` in `Terrenos eliminados`, then
   `Ayuda` and `Ver bienvenida`. Then repeat steps 3 to 5 with `P2` and `P3`.
6. **Send the summary.** The summary printed after the last person covers everyone saved. Send it with the results file
   path to the developer, including whether the app ever asked to choose a land.

**Missing prerequisite:** if step 1 shows `Result: QA is not running. Start it with ./scripts/init.sh --qa-deploy.`, follow
[Deploy, update, roll back, check, and stop QA](qa.md#deploy-update-roll-back-check-and-stop-qa), then repeat step 1.

**Recovery:** if you typed a wrong result for a person, run the command again with the same code, type `yes` when it says
the code is already saved, and enter the right answers.

### If the usability command shows something else

| You see | What it means | What to do |
|---|---|---|
| `Use the code from the sheet, like P1. Do not type names.` | The code was not `P1` to `P99`. | Type the code from the sheet. |
| `That note may hold a name, phone number, email, address, or ID. ...` | The note looks like personal data. | Write it again in small letters, without names. Your text is not saved or shown. |
| `P1 is already saved. Type yes to replace it:` | That code has a record. | Type `yes` to replace it; anything else keeps the old one. |
| `Result: nothing was saved. Run ./scripts/init.sh --usability-record again.` | You stopped, did not type `yes` at the end, or gave three wrong answers in a row. | Run the command again. |
| `Result: the results file could not be read, so nothing was saved. Send <path> to the developer.` | The results file is damaged. | Send that file to the developer; do not edit it. |
| `Result: the usability results were not recorded. Run ./scripts/init.sh --local-rag-setup.` | The local tools are not set up. | Run that command, then repeat step 4. |
