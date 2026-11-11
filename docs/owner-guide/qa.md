# QA

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## Prepare QA on this computer

This makes the QA settings file and QA access keys on this computer only. Nothing is deployed and no
server is contacted.

1. Run `./scripts/init.sh --qa-settings-setup`.
2. Expect `Result: QA is prepared on this computer. Nothing was deployed.` The QA address is a
   placeholder until a QA server is chosen. The access key is never shown on screen.
3. Run it again any time: `Result: QA was already prepared; nothing was changed.`

| What it shows | What to do |
|---|---|
| `The QA access keys are incomplete ...` then `Make new QA access keys? Type yes and press Enter:` | Type `yes` to replace both key files; any copy of the old QA key stops working. Anything else changes nothing. |
| `... in a Terminal window to make new QA access keys.` | Open the Terminal app, go to the Manijero folder, and run the command there. |
| `... must say MANIJERO_DEPLOYMENT_PROFILE=pilot; it is never treated as local` | Open the QA settings file named in the message in TextEdit and fix the line it names. |
| `The folder ... is inside the Manijero folder` | Ask a developer; the QA folder must be outside the Manijero folder. |

## Set up Tailscale (one time)

QA is reachable from phones through Tailscale Funnel (free). You do this once; no command does it for you.

1. Create a free account at <https://login.tailscale.com/start> and install the Tailscale app for Mac. Open it and log in.
2. In the Tailscale admin page (<https://login.tailscale.com/admin/dns>), under DNS, turn on **HTTPS Certificates**.
3. In the admin page under **Access controls**, make sure your account may use Funnel (the page offers a button called **Funnel** or **Add Funnel to policy**; press it).
4. Check: open Terminal and run `tailscale status`. Expect your Mac listed. If `tailscale` is not found, open the Tailscale app once and try again.

## Deploy, update, roll back, check, and stop QA

QA runs the answer service from the image on this Mac and is for made-up test questions only. Docker Desktop and Ollama must be open. First run `./scripts/init.sh --container-build` and `./scripts/init.sh --qa-settings-setup`.

| To do this | Run | Expect |
|---|---|---|
| Deploy QA | `./scripts/init.sh --qa-deploy`, then type `yes` | `Result: QA is running at https://<mac>.<tailnet>.ts.net for test data only.` |
| Ship a newer image | `./scripts/init.sh --container-build`, then `./scripts/init.sh --qa-update` and `yes` | `Result: QA was updated to ...` |
| Go back one version | `./scripts/init.sh --qa-rollback` and `yes` (again to go forward) | `Result: QA was rolled back to ...` |
| Check | `./scripts/init.sh --qa-status` | `OK` lines and `Result: QA is running at ...` |
| Take QA off the internet | `./scripts/init.sh --qa-stop` | `Result: QA has stopped and is no longer reachable from the internet.` |

A line starting `PROBLEM` or a `Result:` that begins `QA was not ...` names its one fix; do it and run the command again. QA stops when the Mac sleeps or restarts: run `--qa-deploy` again (it restarts the same version). The warning `Test data only` is a rule, not a filter: never type real questions or land details into QA.

## Send approved knowledge to QA

After you merge a knowledge review pull request on GitHub (see [`knowledge-review-pull-requests.md`](knowledge-review-pull-requests.md)), QA does not change by itself. QA must be running (`--qa-status` all `OK`), Docker Desktop open, and `./scripts/init.sh --local-rag-setup` done once.

1. Run `./scripts/init.sh --qa-knowledge-deploy`. It reads the merged `main` from GitHub, checks the new knowledge (this can take several minutes), shows which knowledge release QA will switch from and to, and asks for `yes`.
2. Type `yes`. QA restarts (up to two minutes) and is checked again. Expect `Result: QA now answers from knowledge release <id> (main at <short code>)...`.
3. If something looks wrong, run `./scripts/init.sh --qa-knowledge-rollback` and `yes`. Running it again goes forward again. `./scripts/init.sh --qa-status` shows the `Knowledge:` line.

If QA's checks fail after the switch, the command puts the earlier knowledge back by itself and says so. Nothing is sent without `yes`, and your Manijero folder is not changed. The `Result:` lines you may see:

| `Result:` starts | What to do |
|---|---|
| `QA now answers from knowledge release ...` | Done. Test it on your phone. |
| `QA already has the approved knowledge from main` | Nothing to do: merge a review pull request first. |
| `the approved knowledge was not sent to QA. <fix>` | Nothing changed. Do the one fix it names, then run the command again. |
| `the approved knowledge was not sent to QA: <reason>. QA keeps ...` | The new knowledge failed a check. Send the log file shown to a developer. |
| `the new knowledge failed the QA checks (...), so QA went back ...` | QA is safe on the earlier knowledge. Send the log file to a developer. |
| `... QA was stopped and is off the internet` | Run `--qa-knowledge-rollback`, then `--qa-deploy`. |
| `QA was rolled back to knowledge release ...` | The rollback worked. |
| `there is no earlier QA knowledge to go back to` | Nothing to go back to yet. |

The first time, the command takes the knowledge QA already runs inside its image as the earlier version. It never deploys by itself. Acceptance of this command is automated (`test_qa_knowledge_commands.py`); there is no owner walkthrough.

## Check the QA Desktop app

With QA deployed, one command checks that the `Manijero QA` Desktop app reaches QA, shows an answer with sources to a made-up question, and gets its `Útil` rating accepted. It needs the QA access key (`--qa-settings-setup`), Java, and no clicking. Run `./scripts/init.sh --qa-check`; the first run can take a few minutes.

Expect `PASS  Service`, `PASS  Answer`, `PASS  Feedback`, then `Result: the QA check passed: QA is reachable, answers with sources, and accepts feedback from the Desktop app.` Each run adds one `Útil` to QA's feedback count. Nothing is checked on an Android phone or emulator.

| What it shows | What to do |
|---|---|
| `No QA address is saved ...` or `... still a placeholder` | Run `./scripts/init.sh --qa-deploy`, then this command again. |
| `The QA access key was not found ...` | Run `./scripts/init.sh --qa-settings-setup`, then this command again. |
| `FAIL  Service: QA does not answer ...` | Run `./scripts/init.sh --qa-status` and do its first step, then run this command again. |
| `FAIL  Answer: ... saved address ...` | In `./scripts/init.sh --desktop-qa` open `Ayuda > Herramientas de prueba > Conexión`, press `Usar la dirección predeterminada`, then run this command again. |
| `FAIL  Answer: ...` (no reply, error, or no source) or `FAIL  Feedback: ...` | Do the one step it names (`--qa-status`; for "older version" run `--container-build` from the up-to-date main checkout, `--qa-update` answering yes, then `--qa-check` again; or send `build/qa-check/desktop.log` to a developer). The first question after QA starts can be slow; run it again once. |
| `FAIL  Answer: the QA access key did not reach the check app ...` | Run `./scripts/init.sh --qa-settings-setup`, then this command again. |
| `FAIL  Answer: the check app was not built as the QA app ...` or `FAIL  Answer: the check could not run ...` | Send `build/qa-check/desktop.log` to a developer. |

## Owner walkthrough: QA check

1. Run `./scripts/init.sh --qa-status`; expect `Result: QA is running at ...` (deploy first if not).
2. Run `./scripts/init.sh --qa-check`; expect the three `PASS` lines and the passed `Result:`.
3. Run `./scripts/init.sh --qa-stop`, then `--qa-check`; expect `FAIL  Service: ...` and the service-step result. Run `--qa-deploy` to restore.

## Owner walkthrough: QA

Manual acceptance for QA deployment. Write the result of each step in the session notes.

1. Do "Set up Tailscale (one time)".
2. Run `./scripts/init.sh --qa-deploy`; type `yes`. Expect the `Result: QA is running at https://...` line.
3. On your phone, open the printed address plus `/health` in the browser. Expect a short status.
4. Run `./scripts/init.sh --qa-check`. Expect three `PASS` lines and `Result: the QA check passed: ...` (see "Check the QA Desktop app").
5. Run `./scripts/init.sh --container-build`, then `./scripts/init.sh --qa-update` (`yes`), then `--qa-rollback` (`yes`). Expect each `Result:` line.
6. Missing prerequisite: quit the Tailscale app, run `./scripts/init.sh --qa-deploy` or `--qa-status`. Expect a line naming Tailscale and the "Set up Tailscale" step; open Tailscale and run it again.
7. Run `./scripts/init.sh --qa-stop`. Expect the stopped `Result:`; the phone address no longer answers.

## Build the QA test apps

The QA apps are named `Manijero QA`. They install beside your normal Manijero app and keep their
own data. Run `./scripts/init.sh --qa-settings-setup` first (see "Prepare QA on this computer"), so
the QA apps carry the QA access key.

1. **Android:** run `./scripts/init.sh --android-qa`.
   - Expect `Result: the Manijero QA app was built: androidApp/build/outputs/apk/debug/androidApp-debug.apk`.
2. **Desktop:** run `./scripts/init.sh --desktop-qa`. The `Manijero QA` window opens. Its notes and
   lands are kept apart from the normal app.
3. **The QA address.** `./scripts/init.sh --qa-deploy` saves the address in `qa-address.local` in
   the Manijero folder (never shared or uploaded), so run it first, then build. Before QA is
   deployed you will see
   `The QA address is a placeholder (https://qa.manijero.invalid) until the QA server is chosen; this app cannot reach QA yet.`
   That is expected: the app builds, but it cannot reach QA yet. Build again after each new deploy
   to a different address.

| What it shows | What to do |
|---|---|
| `qa-address.local is not a valid QA address. Write one https:// address on one line, for example https://qa.example.org` | Open `qa-address.local` in TextEdit, keep one `https://` address on one line, and build again. |
| `The QA access key is not valid. Run ./scripts/init.sh --qa-settings-setup again.` | Run that command, answer `yes` if it asks, then build again. |
| `manijeroEnvironment must be local or qa; prod is not configured.` | Use the commands above; do not type your own build settings. |

The normal commands `--android`, `--android-run`, and `--desktop` still build the normal app.
