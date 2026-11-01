# Owner guide

Copy-paste steps for running Manijero yourself. Every operation is one command, typed in the
Terminal window opened at the Manijero folder. Every command ends with a line that starts with
`Result:`. That line tells you whether it worked or what to do next. Internals for developers
are in [`backend/README.md`](../backend/README.md).

**Open Terminal at the Manijero folder:** in Finder, right-click the `Manijero` folder and choose
**New Terminal at Folder**. Type or paste each command exactly as written, then press Enter.

## Try the apps with the mock answer service

The mock answer service is a stand-in for the real answer service. It needs no Python and gives
fixed example answers, not real or legal ones. It is only for trying the apps on this computer:
the Desktop app and the Android emulator.

### Start it

1. Open a terminal in the project folder.
2. Run:

   ```sh
   ./scripts/init.sh --mock
   ```

3. Expected result: the command may say `Preparing the mock answer service (the first run can take
   a few minutes)...`, then prints the Desktop address `http://127.0.0.1:8000`, the Android
   emulator address `http://10.0.2.2:8000`, the next steps, and ends with
   `Result: the mock answer service started at http://127.0.0.1:8000.` The terminal is free again.
4. Open an app with `./scripts/init.sh --desktop` or `./scripts/init.sh --android-run`. Nothing
   needs changing in the apps.

If the result differs:

- `Result: nothing new was started; the mock answer service is already running ...` — it was
  already running. Nothing to do; go to step 4.
- `Port 8000 is in use by the real local answer service` — run
  `./scripts/init.sh --local-rag-stop` (or, if a developer started it with
  `./scripts/init.sh --backend`, press Ctrl+C in that window), then repeat step 2.
- `Port 8000 is in use by another program` — close the other program that uses port 8000 (or
  restart the computer), then repeat step 2.
- `Port 8000 is in use by a mock answer service started from a different folder` — run
  `./scripts/init.sh --mock-stop` in that other project folder, then repeat step 2.
- `the example file contracts/examples/... is missing` (or `does not match the answer format`) —
  an example file was removed or changed. Download the project again, then repeat step 2.
- Any other `Result: the mock answer service did not start` — repeat step 2 once. If it fails
  again, send the log file named in the message (`build/mock-answer-server/8000.log`).

### What each answer looks like in the app

- No lands saved: a question shows the example answer with its source card.
- One active land: a question shows the "cannot confirm" (abstained) message.
- Two or more active lands: the app asks which lands the question is about; choosing them shows
  the example answer.

### Check whether it is running

1. Run:

   ```sh
   ./scripts/init.sh --mock-status
   ```

2. Expected result when running: `Result: the mock answer service is running at
   http://127.0.0.1:8000.` with the two app addresses.
3. When it is not running, it prints `Result: the mock answer service is not running. Start it
   with ./scripts/init.sh --mock.` Follow "Start it" above. If it also says `An earlier mock
   answer service ended without being stopped; its leftover record was cleared.`, the computer was
   restarted or the service stopped by itself; that is already fixed, so just start it again.

### Stop it

1. Run:

   ```sh
   ./scripts/init.sh --mock-stop
   ```

2. Expected result: `Result: the mock answer service has stopped.`
3. If it says `Result: the mock answer service was not running, so there was nothing to stop.`,
   nothing was running; there is nothing to do.

## Set up the local answer tools

Do this once on a new computer, and again whenever a developer asks you to. It is safe to repeat:
it never downloads something that is already present and correct.

1. **Install Ollama (only the first time).** Download it from <https://ollama.com/download>,
   install it, and open it once.
   - Expected: the Ollama llama icon appears in the menu bar at the top of the screen.
2. **Make sure Ollama is open.** If the llama icon is not in the menu bar, open **Ollama** from
   the Applications folder.
3. **Start the setup.** Paste:

   ```sh
   ./scripts/init.sh --local-rag-setup
   ```

   - Expected: `Checking this computer and what is already set up...`, then a list that starts
     with `Setup will download:`. It names each download with its size and a total, then asks:
     `Type yes and press Enter to start (anything else cancels):`. On a first setup the list can
     include the search software (about 1.2 GB), the search model bge-m3 (2.3 GB), and the
     drafting model (15.2 GB). A model you already have is not listed.
   - If you see `Result: everything is already set up.` instead, nothing is missing. You are
     done.
4. **Agree to the downloads.** Type `yes` and press Enter.
   - Expected: lines such as `Step 1 of 6: ...` and download progress. A first setup can take
     an hour or more on a slow connection. At the end you see six lines that start with `OK`
     and `Result: everything is set up.`
5. **Confirm.** Paste the same command again:

   ```sh
   ./scripts/init.sh --local-rag-setup
   ```

   - Expected: six `OK` lines and
     `Result: everything is already set up. Nothing was downloaded or changed.`

### If the setup shows something else

| You see | What it means | What to do |
|---|---|---|
| `Ollama is not installed on this computer.` | Step 1 is missing. | Install Ollama from <https://ollama.com/download>, open it, then repeat step 3. |
| `Ollama is installed but not running.` | Ollama is closed. | Open the Ollama app, wait a few seconds, then repeat step 3. |
| `...have changes that are not committed to Git.` | The knowledge files were edited and not saved by a developer. | Ask a developer to commit or undo the change, then repeat step 3. |
| `There is not enough free space on the disk that holds ...` | The disk is too full for the downloads (the message says how much is needed). | Free up space, for example empty the Trash, then repeat step 3. |
| `Another setup is already running on this computer.` | A setup is still running in another Terminal window. | Wait until that window shows its `Result:` line, then repeat step 3. |
| `Nothing was changed.` | You answered something other than `yes`. | Repeat step 3 when you are ready. |
| The setup stopped (you pressed Control-C, closed the window, or the internet dropped) | Finished parts are kept. | Repeat step 3. It continues where it stopped and only downloads what is still missing. |
| `...differs from the reviewed version...` | A download is not the reviewed version, so it was not used. | Do not change anything. Send the log file path shown on screen to a developer. |
| `The new knowledge release did not pass its checks: ...` | The knowledge in this folder failed a check, so the previous knowledge stays in use. | Send the log file path shown on screen to a developer. |
| `The settings file ... has a problem on line N: ...` | A line in the settings file was mistyped. | Open the settings file in TextEdit, fix that line as the message says, save, then repeat step 3. |
| `Something unexpected went wrong.` | An unplanned error. Finished parts are kept. | Repeat step 3. If you see this again, send the log file path shown on screen to a developer. |

## Check the local answer tools

Run this whenever you want to know whether everything is ready. It only looks; it never
downloads or changes anything.

1. **Check.** Paste:

   ```sh
   ./scripts/init.sh --local-rag-status
   ```

   - Expected: six lines, one for each part (search software, search model, passage index,
     vector store, knowledge release, drafting model), each starting with `OK`, and then
     `Result: all 6 parts are ready.`

### If the check shows something else

Each line that does not start with `OK` starts with `MISSING` or `PROBLEM`. It says what is
wrong and the first thing to do. Do the step on the first line that is not `OK`, then run the
check again.

| You see | What to do |
|---|---|
| `Result: setup has not run yet.` | Follow [Set up the local answer tools](#set-up-the-local-answer-tools). |
| `PROBLEM  Drafting model: Ollama is not running.` | Open the Ollama app, then run the check again. |
| `... Run ./scripts/init.sh --local-rag-setup ...` | Run the setup; it fixes only what is missing or out of date. |
| `... a developer must ...` | Send a developer the line you see. |

## Start the local answer service

The local answer service gives the apps real answers from the reviewed knowledge, using the
local answer tools set up above. It runs in the background on this computer only, for the
Desktop app and the Android emulator (not a phone). The mock answer service must be stopped
first (`./scripts/init.sh --mock-stop`).

1. **Make sure Ollama is open.** The llama icon must be in the menu bar. If it is not, open
   **Ollama** from the Applications folder and wait 10 seconds.
2. **Start.** Paste:

   ```sh
   ./scripts/init.sh --local-rag-start
   ```

   - Expected: `Checking the local answer tools...`, then
     `Starting the local answer service (this can take up to a minute)...`, then the Desktop
     address `http://127.0.0.1:8000`, the Android emulator address `http://10.0.2.2:8000`, the
     next steps, the log file, and
     `Result: the local answer service started at http://127.0.0.1:8000.` The Terminal is free
     again, and closing the Terminal window does not stop the service.
3. **Open an app** with `./scripts/init.sh --desktop` or `./scripts/init.sh --android-run`.
   Nothing needs changing in the apps. The first question after a start can take longer while
   the drafting model loads.

After a setup that changed something (for example new knowledge), stop the service and start
it again so it uses the new parts.

### If the start shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: nothing new was started; the local answer service is already running ...` | It was already running. | Nothing to do; go to step 3. |
| `PROBLEM  Drafting model: Ollama is not running.` | Ollama is closed. | Open the Ollama app, wait 10 seconds, then repeat step 2. |
| `The local answer tools are not set up yet.` or a line with `Run ./scripts/init.sh --local-rag-setup` | A part is missing or out of date. | Follow [Set up the local answer tools](#set-up-the-local-answer-tools), then repeat step 2. |
| `A setup of the local answer tools is running ...` or `Another start or stop ... is running ...` | Another Terminal window is busy with it. | Wait until that window shows its `Result:` line, then repeat step 2. |
| `Port 8000 is in use by the mock answer service.` | The mock answer service is running. | Run `./scripts/init.sh --mock-stop`, then repeat step 2. |
| `Port 8000 is in use by a Manijero answer service that this command did not start ...` | A developer started one with `./scripts/init.sh --backend`. | Press Ctrl+C in that window, then repeat step 2. |
| `Port 8000 is in use by another program.` | Another program uses the address. | Close that program (or restart the computer), then repeat step 2. |
| `... cannot answer questions yet, so it was ended.` | The knowledge is not ready to answer. | Run `./scripts/init.sh --local-rag-status` and do its first step. |
| Any other `Result: the local answer service did not start.` | It stopped while starting. | Repeat step 2 once. If it fails again, send the log file named in the message to a developer. |

## Check the local answer service

Run this whenever you want to know whether the service is running and can answer. It only
looks; it never starts, stops, or downloads anything.

1. **Check.** Paste:

   ```sh
   ./scripts/init.sh --local-rag-service-status
   ```

   - Expected when running: the address and the time it started, three lines `OK  Answers`,
     `OK  Search`, and `OK  Drafting`, the two app addresses, the log file, and
     `Result: the local answer service is running at http://127.0.0.1:8000.`

### If the check shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the local answer service is not running. ...` | It is not running. | Follow [Start the local answer service](#start-the-local-answer-service). |
| `An earlier local answer service ended without being stopped; its leftover record was cleared.` | The computer restarted or the service stopped by itself. | That is already fixed; just start it again. |
| `PROBLEM  Drafting: Ollama is not running. ...` | Answers continue, but without the drafting model. | Open the Ollama app, wait 10 seconds, then check again. |
| `PROBLEM  Search: a newer knowledge release was published ...` | A setup built new knowledge after the start. | Run `./scripts/init.sh --local-rag-stop`, then `./scripts/init.sh --local-rag-start`. |
| `PROBLEM  Answers: the service does not answer. ...` | The service is stuck. | Stop it and start it again. If it happens again, send the log file named on the screen to a developer. |
| `PROBLEM  Answers: the service runs but cannot answer questions right now. ...` | The knowledge is not ready to answer. | Run `./scripts/init.sh --local-rag-status` and do its first step. |

## Stop the local answer service

1. **Stop.** Paste:

   ```sh
   ./scripts/init.sh --local-rag-stop
   ```

   - Expected: `Result: the local answer service has stopped.` Ollama keeps running; quit it
     from the menu bar if you want.
2. If it says `Result: the local answer service was not running, so there was nothing to stop.`,
   nothing was running; there is nothing to do.

## Smoke-test the apps against the local answer service

This command proves that the Desktop app and the app on the Android emulator can ask the running
local answer service one fixed question and show its reply. You only watch the result: it types
the question and presses `Preguntar` for you. It does not judge whether the answer is correct.

It never changes your lands or the saved `Conexión` address. On the emulator it installs the test
version of the app over the existing one and keeps its data.

1. **Start the service** if it is not running: `./scripts/init.sh --local-rag-start`.
2. **Open the emulator.** Run `./scripts/init.sh --android-run` (or start one from Android Studio's
   Device Manager) and wait until you see its home screen or the app.
3. **Run the smoke test.** Paste:

   ```sh
   ./scripts/init.sh --local-smoke
   ```

   - It prints `Checking the local answer service...`, then
     `Checking the Desktop app (the first run can take a few minutes)...` and
     `Checking the Android emulator app (the first run can take a few minutes)...`. Nothing opens
     on the computer screen; the emulator shows the app for a moment.
   - Expected: one `PASS  Desktop: ...` line, one `PASS  Android emulator: ...` line, and
     `Result: the smoke test passed on Desktop and the Android emulator.`
   - A `PASS` line says whether the app showed an answer with source cards or an honest
     `Sin respuesta segura` reply. Both are a pass.

### If the smoke test shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the smoke test did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](#set-up-the-local-answer-tools). |
| `Result: the smoke test did not run. Start it with ./scripts/init.sh --local-rag-start, ...` | The service is not running. | Start it, then run the smoke test again. |
| A `PROBLEM ...` line, then `Result: the smoke test did not run. Do the step shown above.` | A service check is not `OK` (for example Ollama is closed). | Do what the `PROBLEM` line says, then run the smoke test again. |
| `Java was not found on this computer. ...` | Java is needed to build the apps, and none was found (not even one Gradle downloaded earlier). | Install Temurin 21 from https://adoptium.net, then run the command again. |
| `Another smoke test is running in another Terminal window.` | One is already running. | Wait for its `Result:` line, then run it again. |
| `FAIL  Android emulator: no Android emulator is running. ...` or `... is still starting. ...` | No emulator is ready. | Do step 2, then run it again. |
| `FAIL  Android emulator: adb was not found. ...` | Android Studio's Platform-Tools are missing. | Install them as the line says, then run it again. |
| `FAIL  <app>: the app uses <address>, not <address>. Open Ayuda > Herramientas de prueba > Conexión, ...` | That app was set to another address. | In that app, do what the line says, then run it again. |
| `FAIL  <app>: the app could not reach ...`, `... cannot answer questions right now ...`, `... with an error ...`, or `... no reply within 90 seconds ...` | The app reached the service, or tried, but got no usable reply. | Run `./scripts/init.sh --local-rag-service-status` and do its first step, then run it again. |
| `FAIL  <app>: the check could not run. Details are in build/local-smoke/<app>.log; ...`, `FAIL  Android emulator: the Android test tools do not match this emulator's Android version. ...`, or another `FAIL` line naming a log | The build, install, or check itself failed. | Send that log file to a developer. |
| `The smoke test was stopped.` | You pressed Ctrl+C. | Run it again when you are ready. |

## Owner walkthrough: local smoke test

Do this once, in a Terminal opened at the Manijero folder, after the local answer tools are set up.
Write down each `Result:` line and send them to the developer.

1. Run `./scripts/init.sh --local-rag-start`. Expect
   `Result: the local answer service started at http://127.0.0.1:8000.`
2. Run `./scripts/init.sh --android-run`, then wait for the app to open on the emulator.
3. Run `./scripts/init.sh --local-smoke`. Expect two `PASS` lines and
   `Result: the smoke test passed on Desktop and the Android emulator.` Report both `PASS` lines
   and roughly how long it took.
4. **Missing prerequisite:** run `./scripts/init.sh --local-rag-stop`, then
   `./scripts/init.sh --local-smoke`. Expect
   `Result: the smoke test did not run. Start it with ./scripts/init.sh --local-rag-start, then run this command again.`
5. **Recovery:** run `./scripts/init.sh --local-rag-start`, then `./scripts/init.sh --local-smoke`.
   Expect the step 3 result again.
6. Optional: close the emulator window and run `./scripts/init.sh --local-smoke`. Expect
   `PASS  Desktop: ...`, a `FAIL  Android emulator: ...` line naming `./scripts/init.sh --android-run`,
   and `Result: the smoke test failed on the Android emulator. Do the first step shown above.`
7. Run `./scripts/init.sh --local-rag-stop`. Report each `Result:` line, the two `PASS` lines, and
   whether the emulator app still shows the lands it had before.

## Owner walkthrough: local answer service

Do this once, after [Set up the local answer tools](#set-up-the-local-answer-tools) has finished,
in a Terminal opened at the Manijero folder. For each step, write down the `Result:` line (and
anything that looked different from this guide) and send them to the developer.

1. Run `./scripts/init.sh --local-rag-status`. Expect `Result: all 6 parts are ready.` If not,
   run the setup first. Report the `Result:` line.
2. **Missing prerequisite:** quit Ollama (click the llama icon in the menu bar, then
   **Quit Ollama**). Run `./scripts/init.sh --local-rag-start`. Expect a line
   `PROBLEM  Drafting model: Ollama is not running. Open the Ollama app, then run this command again.`
   and `Result: the local answer service did not start. Open the Ollama app, then run this command again.`
   Report both lines.
3. Open Ollama, wait 10 seconds, and run `./scripts/init.sh --local-rag-start` again. Expect
   `Result: the local answer service started at http://127.0.0.1:8000.` Report the `Result:`
   line, the two app addresses, and roughly how long it took.
4. Close the Terminal window, open a new one at the Manijero folder, and run
   `./scripts/init.sh --local-rag-start`. Expect
   `Result: nothing new was started; the local answer service is already running at http://127.0.0.1:8000.`
   Report the `Result:` line.
5. Run `./scripts/init.sh --local-rag-service-status`. Expect three `OK` lines (Answers, Search,
   Drafting), the two addresses, and
   `Result: the local answer service is running at http://127.0.0.1:8000.` Report the three lines
   and the `Result:` line.
6. **Recovery:** quit Ollama, then run `./scripts/init.sh --local-rag-service-status`. Expect a
   line that starts `PROBLEM  Drafting:` and
   `Result: the local answer service is running at http://127.0.0.1:8000, but a check needs attention: do the first step shown above.`
   Open Ollama, wait 10 seconds, and run it again. Expect three `OK` lines and the running
   `Result:` line. Report both `Result:` lines.
7. Run `./scripts/init.sh --local-rag-stop`. Expect `Result: the local answer service has stopped.`
   Report it.
8. Run `./scripts/init.sh --local-rag-stop` again. Expect
   `Result: the local answer service was not running, so there was nothing to stop.` Report it.
9. Run `./scripts/init.sh --local-rag-service-status`. Expect
   `Result: the local answer service is not running. Start it with ./scripts/init.sh --local-rag-start.`
   Report it.

## Your settings file

The setup creates one settings file, `settings.env`, in the `manijero/local` folder inside your
home folder. It holds one value: the PAC campaign year the answers use
(`MANIJERO_ACTIVE_CAMPAIGN=2026`). The setup never overwrites it. If a developer asks you to
change the year, edit only the four digits after the `=` sign in TextEdit and save. Then run the
setup again: it rebuilds the knowledge for the new year without downloading anything.

## Where things are kept

Everything the setup downloads or builds is kept in the `manijero/local` folder inside your home
folder, except the Ollama model (Ollama keeps it) and the search software (kept with the
Manijero folder). Log files are in `manijero/local/logs`. Do not delete or move these folders.
Removing the downloaded tools is not supported yet.
