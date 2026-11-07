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
  `./scripts/init.sh --local-rag-stop` or `./scripts/init.sh --container-stop` (or, if a developer started it with
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
| `Port 8000 is in use by a Manijero answer service that this command did not start ...` | The answer service runs in a container, or a developer started one with `./scripts/init.sh --backend`. | Run `./scripts/init.sh --container-stop` (or press Ctrl+C in the `--backend` window), then repeat step 2. |
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

## Measure answer speed under pilot load

This command asks the 14 reviewed questions from 10 pretend users at once for about five minutes and
tells you how long answers took and how many the service handled. It only asks questions and writes
one report; it never changes your lands, the service, or the knowledge. It does not say whether the
answers are right, and the numbers are for this computer only.

1. **Start the service** if it is not running: `./scripts/init.sh --local-rag-start`. The check
   `./scripts/init.sh --local-rag-service-status` should show three `OK` lines.
2. **Measure.** Paste:

   ```sh
   ./scripts/init.sh --local-rag-load-test
   ```

   - Expected: `Checking the local answer service...`, the service address, a plan line
     (`The plan: 14 reviewed questions, 2 warm-up questions, 10 clients, one more every second for 10 seconds, 3 minutes at once, about five minutes.`), the warm-up line, then after a few minutes:
     `Ramp: … questions finished, … did not answer.` and
     `Steady phase: … questions finished, … did not answer.`, a line
     `  Median … s, p95 … s, slowest … s.`, a line
     `  Requests per second: … (… successful questions over … s).`, a line
     `  Answers: … answered, … abstained, … needed a land choice.`, and
     `The report is saved as: ~/manijero/local/reports/local-load-….json`.
   - Then three honesty lines (the numbers describe this Mac at that moment, the 8 s p95 is only a
     reference, and a low p95 can hide answers written without the drafting model), and
     `Result: the load test finished; the report is in ~/manijero/local/reports/local-load-….json.`
   - Leave the Terminal open and wait; stopping it with Ctrl+C cancels the measurement.

### If the load test shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the load test did not run. Start the local answer service with ./scripts/init.sh --local-rag-start, ...` | The service is not running. | Start it, then run the command again. |
| `The local answer tools are not set up yet. ...`, then `Result: the load test did not run. Do the first step shown above.` | The local answer tools were never set up. | Follow [Set up the local answer tools](#set-up-the-local-answer-tools), then run the command again. |
| A `PROBLEM ...` line, then `Result: the load test did not run. Do the first step shown above.` | A service check is not `OK` (for example Ollama is closed). | Do what the `PROBLEM` line says, then run the command again. |
| `Another load test is running in another Terminal window.` | One is already running. | Wait for its `Result:` line, then run it again. |
| `Result: the load test finished, but … questions failed. ...` | Some questions did not answer; the timing numbers are incomplete. | Run it once more. If it repeats, send the report file to a developer. |
| `Result: the load test finished, but the local answer service changed during the run, ...` | The service stopped, restarted, or its knowledge changed during the run. | Run `./scripts/init.sh --local-rag-start`, then run the test again. |
| `Result: the load test was stopped.` | You pressed Ctrl+C. | Run it again when you are ready; nothing was changed. |
| `Something unexpected went wrong. ... <log file>` | The command itself failed. | Send that log file to a developer. |

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

## Rehearse the live demo

Run this before showing Manijero to anyone. It checks the running local answer service and the
review step, and prints one line per step. It changes nothing: it never writes your lands or the
approved knowledge, and the review step uses a temporary, synthetic copy that it removes.

1. **Start the service** if it is not running: `./scripts/init.sh --local-rag-start`.
2. **Rehearse.** Paste:

   ```sh
   ./scripts/init.sh --demo-rehearsal
   ```

   - Expected: four `PASS` lines — `PASS  Service: /health and /ready answer`,
     `PASS  Grounded answer: ... land_scope general`, `PASS  Trap abstention: no sources`, and
     `PASS  Reviewed update: draft blocked, human approval, temporary merge (synthetic)` — and
     `Result: the demo rehearsal passed (4 of 4 steps) against http://127.0.0.1:8000. The
     reviewed update used synthetic fixtures; canonical knowledge was not changed.`
   - If the service is not running it prints `SKIP` lines for the service steps, still runs the
     review step, and ends with
     `Result: the demo rehearsal is incomplete ... Start it with ./scripts/init.sh --local-rag-start, then run this command again.`
3. **Read the script before the demo:** [demo-script.md](demo-script.md) gives the order, the two
   fixed questions, the app steps to do by hand, and what you must not promise.

### If the rehearsal shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the demo rehearsal did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](#set-up-the-local-answer-tools), then repeat step 2. |
| `SKIP  Service: /health and /ready answer: the service is not reachable.` or `... running but not ready.` | The service is not running or is still starting. | Do step 1 (or wait a minute), then repeat step 2. |
| `FAIL  Grounded answer: ...` | The fixed question did not return an answer with approved sources. | Do not demo that question; send the `Result:` line to a developer. |
| `FAIL  Trap abstention: ...` | The trap question answered instead of abstaining. | Do not demo that question; send the `Result:` line to a developer. |
| `FAIL  Reviewed update: ...` | The review step did not prepare, block, approve, and merge its temporary copy as it must. | Do not explain the reviewed update; send the `Result:` line to a developer. |
| `Result: the demo rehearsal failed ...` | At least one step failed. | Read the `FAIL` line, fix that step, then repeat step 2. |

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

## Owner walkthrough: load test

Do this once the local service works, preferably when you can leave the computer alone for about
ten minutes. Write down each `Result:` line and the numbers the test prints, and send them to the
person who asked for them.

1. **Check the service.** Run `./scripts/init.sh --local-rag-service-status`. Expect three `OK`
   lines and its running `Result:`. If not, run `./scripts/init.sh --local-rag-start` first.
2. **Missing prerequisite:** run `./scripts/init.sh --local-rag-stop`, then
   `./scripts/init.sh --local-rag-load-test`. Expect
   `Result: the load test did not run. Start the local answer service with ./scripts/init.sh --local-rag-start, then run this command again.`
3. **Missing model:** start the service, then quit Ollama (llama icon, `Quit Ollama`), then run
   `./scripts/init.sh --local-rag-load-test`. Expect one `PROBLEM` line about the model and
   `Result: the load test did not run. Do the first step shown above.`
4. **Measure:** open Ollama again, wait 10 seconds, then run
   `./scripts/init.sh --local-rag-load-test`. The first warm-up answer may be slow while the
   drafting model loads. Expect the plan, the two warm-up times, the steady summary, the honesty
   note, and `Result: the load test finished; the report is in <path>.` after about five minutes.
   Report the median, p95, slowest, requests per second, finished and failed counts, the answer
   kinds, and the report path.
5. Send the report file to the person who asked (it contains only counts and times), then run
   `./scripts/init.sh --local-rag-stop`.

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

## Install Docker Desktop (one time)

The answer service can also run as a *container*: one packaged copy of the service, its search
software, the published knowledge, and the search model, run by the free Docker Desktop app. It
answers exactly like `--local-rag-start`, and it is the copy the QA server will later run. Only
one of the two can run at a time.

1. Download Docker Desktop for Mac (Apple chip) from
   https://www.docker.com/products/docker-desktop/ and install it like any app. It is free for
   personal and small-business use.
2. Open **Docker** from the Applications folder once, accept its terms, and skip the sign-in.
   Wait until it says **Engine running**. You can close its window; it keeps running in the menu
   bar (the whale icon).

## Build the answer service image

Run this after [Set up the local answer tools](#set-up-the-local-answer-tools) has finished, and
again after every setup that changed something.

1. **Make sure Docker Desktop is open** (the whale icon is in the menu bar).
2. **Build.** Paste:

   ```sh
   ./scripts/init.sh --container-build
   ```

   - Expected: `Checking what the image needs...`, a line saying the first build can take 10 to
     30 minutes, the log file, a `Still building (... minutes so far)...` line every minute, then
     the image name, the knowledge release, the approximate size, and
     `Result: the image manijero-backend:<release>-<code> was built with knowledge release <release>.`
   - Running it again with nothing changed ends
     `Result: nothing new was built; manijero-backend:... is already up to date.`

### If the build shows something else

| You see | What it means | What to do |
|---|---|---|
| `Docker Desktop is not installed ...` | Docker Desktop is missing. | Follow [Install Docker Desktop](#install-docker-desktop-one-time), then repeat step 2. |
| `Docker Desktop is not open, or it is still starting.` | Docker Desktop is closed or starting. | Open it, wait until it says it is running, then repeat step 2. |
| `The local answer tools are not set up yet.` or a line with `Run ./scripts/init.sh --local-rag-setup` | A part the image needs is missing or out of date. | Follow [Set up the local answer tools](#set-up-the-local-answer-tools), then repeat step 2. |
| `... not saved in Git ...` or `... base-image pin ... is not valid.` | The Manijero folder has a developer change. | Send a developer the line you see. |
| `Another container command is running ...` | Another Terminal window is busy with it. | Wait until that window shows its `Result:` line, then repeat step 2. |
| `The image could not be built. ...` | The build failed (often a full disk). | In Docker Desktop, open **Settings > Resources** and check there is free disk space, then repeat step 2. If it fails again, send the log file named on the screen to a developer. |

## Start the answer service in a container

1. **Make sure Docker Desktop and Ollama are open** (the whale and llama icons are in the menu
   bar), and that the local answer service is stopped (`./scripts/init.sh --local-rag-stop`).
2. **Start.** Paste:

   ```sh
   ./scripts/init.sh --container-start
   ```

   - Expected: `Checking the answer service image...`, then
     `Starting the answer service in the container (this can take up to two minutes)...`, the
     image name, the Desktop address `http://127.0.0.1:8000`, the Android emulator address
     `http://10.0.2.2:8000`, the next steps, and
     `Result: the answer service in the container started at http://127.0.0.1:8000.` Closing the
     Terminal window does not stop it.
3. **Open an app** with `./scripts/init.sh --desktop` or `./scripts/init.sh --android-run`.
   Nothing needs changing in the apps.

### If the start shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: nothing new was started; the answer service in the container is already running ...` | It was already running. | Nothing to do; go to step 3. |
| `There is no answer service image ...` | The image was never built. | Follow [Build the answer service image](#build-the-answer-service-image), then repeat step 2. |
| `... holds an older knowledge release or another campaign ...` | A setup changed the knowledge after the build. | Build again, then repeat step 2. |
| `PROBLEM  Drafting model: Ollama is not running.` | Ollama is closed. | Open the Ollama app, wait 10 seconds, then repeat step 2. |
| `Port 8000 is in use by the local answer service ...` | `--local-rag-start` is running. | Run `./scripts/init.sh --local-rag-stop`, then repeat step 2. |
| `Port 8000 is in use by the mock answer service.` | The mock answer service is running. | Run `./scripts/init.sh --mock-stop`, then repeat step 2. |
| `Port 8000 is in use by ...` (anything else) | Another program uses the address. | Close it (or press Ctrl+C in a `--backend` window), then repeat step 2. |
| `A container named manijero-backend exists ... Manijero did not create it.` | Someone made a container with that name. | Ask a developer; Manijero never touches it. |
| `An earlier answer service container ended without being stopped; it was cleared.` | The computer restarted or Docker Desktop was closed. | Nothing to do; the start continues. |
| Any other `Result: the answer service in the container did not start.` | It stopped while starting. | Repeat step 2 once. If it fails again, send the log file named in the message to a developer. |

## Check the answer service in a container

1. **Check.** Paste:

   ```sh
   ./scripts/init.sh --container-status
   ```

   - Expected when running: four lines `OK  Container`, `OK  Answers`, `OK  Search`, and
     `OK  Drafting`, the two app addresses, and
     `Result: the answer service in the container is running at http://127.0.0.1:8000.`

| You see | What it means | What to do |
|---|---|---|
| `Result: the answer service in the container is not running. ...` | It is not running (or Docker Desktop is closed). | Follow [Start the answer service in a container](#start-the-answer-service-in-a-container). |
| `PROBLEM  Drafting: Ollama is not running. ...` | Answers continue, but without the drafting model. | Open the Ollama app, wait 10 seconds, then check again. |
| `PROBLEM  Drafting: ... the container cannot reach it.` | The container cannot talk to Ollama. | Stop and start the container. If it happens again, send the newest `container-...log` file from `manijero/local/logs` to a developer. |
| `PROBLEM  Search: a newer knowledge release was published ...` | A setup built new knowledge after the build. | Build, then stop and start the container. |
| `PROBLEM  Answers: ...` | The service is stuck or the knowledge is not ready. | Stop and start the container; if it repeats, run `./scripts/init.sh --local-rag-status` and do its first step. |

## Stop the answer service in a container

1. **Stop.** Paste:

   ```sh
   ./scripts/init.sh --container-stop
   ```

   - Expected: `Stopping the answer service in the container...`, the log file with its output,
     and `Result: the answer service in the container has stopped.` Docker Desktop, Ollama, and
     the image stay as they are.
2. If it says `Result: the answer service in the container was not running, so there was nothing to stop.`,
   there is nothing to do.

Images are never deleted automatically. If Docker Desktop runs short of disk space, ask a
developer before deleting anything.

## Owner walkthrough: container

Do this once, after [Owner walkthrough: local answer service](#owner-walkthrough-local-answer-service),
in a Terminal opened at the Manijero folder. For each step, write down the `Result:` line (and
anything that looked different from this guide) and send them to the developer.

1. Follow [Install Docker Desktop](#install-docker-desktop-one-time). Report the version shown in
   Docker Desktop under **About Docker Desktop**.
2. Run `./scripts/init.sh --local-rag-status` and expect `Result: all 6 parts are ready.` Run
   `./scripts/init.sh --local-rag-service-status` and expect it is not running (otherwise run
   `./scripts/init.sh --local-rag-stop`). Report both `Result:` lines.
3. **Missing prerequisite:** quit Docker Desktop (whale icon > **Quit Docker Desktop**). Run
   `./scripts/init.sh --container-build`. Expect the line starting
   `Docker Desktop is not open` and
   `Result: the image was not built. Open the Docker Desktop app, wait until it says it is running, then run this command again.`
   Report both lines.
4. Open Docker Desktop, wait until it says it is running, and run
   `./scripts/init.sh --container-build`. Report the `Result:` line, the size, roughly how many
   minutes it took, and whether the log file named on the screen contains the word `nvidia`.
5. Run `./scripts/init.sh --container-build` again. Expect
   `Result: nothing new was built; ... is already up to date.` Report it.
6. Run `./scripts/init.sh --container-start`. Expect
   `Result: the answer service in the container started at http://127.0.0.1:8000.` Report it and
   the two app addresses.
7. Close the Terminal window, open a new one at the Manijero folder, and run
   `./scripts/init.sh --container-start`. Expect
   `Result: nothing new was started; the answer service in the container is already running at http://127.0.0.1:8000.`
8. Run `./scripts/init.sh --container-status`. Expect four `OK` lines and
   `Result: the answer service in the container is running at http://127.0.0.1:8000.` Report them.
9. **Recovery:** quit Ollama, run `./scripts/init.sh --container-status`, and expect a line that
   starts `PROBLEM  Drafting:` and a `Result:` line that ends `a check needs attention: do the first step shown above.`
   Open Ollama, wait 10 seconds, and run it again: expect four `OK` lines. Report both `Result:` lines.
10. Run `./scripts/init.sh --container-stop` and expect
    `Result: the answer service in the container has stopped.` Run it again and expect
    `... was not running, so there was nothing to stop.` Run `./scripts/init.sh --container-status`
    and expect `Result: the answer service in the container is not running. ...` Report all three.

## Open the health dashboard

A free page on this Mac that says, in plain words, whether the answer service is working. It needs
[Docker Desktop](#install-docker-desktop-one-time) open. It is not an alarm: it only shows what is
happening while it runs, and it does not tell you when something stops.

1. **Start.** Paste `./scripts/init.sh --monitoring-start`. The first time it downloads two images
   (a few minutes). Expected: `Open http://127.0.0.1:3000 in your web browser.` and
   `Result: the health dashboard started at http://127.0.0.1:3000.`
2. **Open** that address in your web browser. Each box starts with a state word:

| Word (colour) | What it means | What to do |
|---|---|---|
| `OK` (green) | This check is fine. | Nothing. |
| `Warning` (amber) | Something is slower, rarer, or less reliable than usual. | Do the first step in the box; look again in a few minutes. |
| `Problem` (red) | People are probably affected. | Do the first step in the box; if it stays, tell a developer. |
| `Not enough data` / `Not set up yet` (grey) | Nobody asked anything lately, or QA does not exist yet. | Nothing. |

3. **Check** any time with `./scripts/init.sh --monitoring-status`; expect
   `Result: the health dashboard is running at http://127.0.0.1:3000.`
4. **Stop** with `./scripts/init.sh --monitoring-stop`; expect `Result: the health dashboard has stopped.`
   The history is kept for the next start.

| You see | What it means | What to do |
|---|---|---|
| `Docker Desktop is not open ...` | Docker Desktop is closed. | Open it, wait until it says it is running, then run the command again. |
| `Port 3000 is in use by another program.` | Another program uses the dashboard's port. | Close that program, then start again. |
| Boxes say `No information yet` | The dashboard has no data yet. | Wait a minute, then run `./scripts/init.sh --monitoring-status`. |
| `Problem ... cannot reach the answer service` for Local | The local service is not running. | Start it with `./scripts/init.sh --local-rag-start` (or `--container-start`). |

## Owner walkthrough: health dashboard

Do this once, in a Terminal opened at the Manijero folder, with Docker Desktop open and the local
answer service stopped. Write down each `Result:` line and anything unclear on the page.

1. Run `./scripts/init.sh --monitoring-start` and open the printed address. Report the `Result:`
   line and how many minutes the first start took.
2. Read the **Local** row. With the service stopped, expect `Problem` boxes for the service that say
   what to do, and grey boxes for the rest. Say whether you understood each box without help.
3. Start the service (`./scripts/init.sh --local-rag-start`), wait two minutes, and reload the page.
   Expect the Local service box to read `OK`. Report what the other boxes say.
4. **Missing prerequisite:** quit Docker Desktop and run `./scripts/init.sh --monitoring-start`.
   Expect the line `Docker Desktop is not open ...` and a `Result: the health dashboard did not start. ...` line.
5. **Recovery:** open Docker Desktop and run the start again; expect the address and a started `Result:`.
6. Run `./scripts/init.sh --monitoring-stop`, then `--monitoring-status`; report both `Result:` lines.

## Give the apps the pilot token

When you are given a pilot token for the pilot answer service, save it once. The test apps you
build after that send it with every question, so the pilot service answers them. Test apps are the
Android app from `./scripts/init.sh --android` and the Desktop app from
`./scripts/init.sh --desktop`. Release or packaged apps never carry the token. The people testing
the apps never see or type it. Without a saved token the apps work as before with the mock and
local answer services.

1. **Copy the token.** Select the whole token you were given and copy it (Command-C). Copy
   nothing else after it.
2. **Save it.** Paste:

   ```sh
   ./scripts/init.sh --pilot-token-save
   ```

   - Expected: `Result: the pilot token is saved. The next test build will send it.`
   - The command never shows the token. It keeps it in the file `pilot-token.local` in the
     Manijero folder, which is never shared or uploaded. Do not send that file to anyone.
3. **Build the test apps again** with `./scripts/init.sh --android` or
   `./scripts/init.sh --desktop`. Only test apps built after step 2 send the token.

To use a new token, copy it and run the same command again. Expect
`Result: the pilot token is saved; it replaced the previous one. The next test build will send it.`

### If the result differs

Nothing is saved, and any token saved before stays as it was.

| Result line | What to do |
|---|---|
| `Result: the clipboard is empty. Copy the pilot token first, then run this command again.` | Copy the token (step 1), then run the command again. |
| `Result: the clipboard does not hold a pilot token. Copy the whole token again, then run this command again.` | Part of the token, or extra text, was copied. Copy exactly the whole token again, then run the command again. |
| `Result: this command could not read the clipboard; it needs a Mac. Ask the developer for help.` | Run it on your Mac, or ask the developer. |
| `Result: the pilot token could not be saved, and nothing changed. Ask the developer for help.` | Send this line to the developer. |

If an app build stops with `pilot-token.local is not a valid pilot token. Run ./scripts/init.sh --pilot-token-save again.`,
copy the token and do step 2 again.

## Your environments

Manijero has three environments: local (your computer, the default), QA (a test copy on a server
that is not chosen yet), and prod (not planned yet). To see what each one has:

1. In the Manijero folder, run `./scripts/init.sh --environments-status`.
2. Expect three lines (`OK`, `ATTENTION`, `PROBLEM`, or `NOT SET UP` for local, QA, and prod) and a
   `Result:` line. It changes nothing and contacts no server.

| What it shows | What to do |
|---|---|
| `Result: the local environment is not set up yet. Run ./scripts/init.sh --local-rag-setup.` | Run that command (see "Set up the local answer tools"). |
| `ATTENTION  local: the settings file does not say it is for the local environment` | Run `./scripts/init.sh --local-rag-setup`; it adds two lines to your settings file and changes nothing else. |
| `ATTENTION  local: the local access keys are missing or incomplete` | Run `./scripts/init.sh --local-rag-setup`; it makes them. |
| `PROBLEM  QA: ...` | Do what the line says, usually `./scripts/init.sh --qa-settings-setup`. |

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

## Check the QA Desktop app

With QA deployed, one command checks that the `Manijero QA` Desktop app reaches QA, shows an answer with sources to a made-up question, and gets its `Útil` rating accepted. It needs the QA access key (`--qa-settings-setup`), Java, and no clicking. Run `./scripts/init.sh --qa-check`; the first run can take a few minutes.

Expect `PASS  Service`, `PASS  Answer`, `PASS  Feedback`, then `Result: the QA check passed: QA is reachable, answers with sources, and accepts feedback from the Desktop app.` Each run adds one `Útil` to QA's feedback count. Nothing is checked on an Android phone or emulator.

| What it shows | What to do |
|---|---|
| `No QA address is saved ...` or `... still a placeholder` | Run `./scripts/init.sh --qa-deploy`, then this command again. |
| `The QA access key was not found ...` | Run `./scripts/init.sh --qa-settings-setup`, then this command again. |
| `FAIL  Service: QA does not answer ...` | Run `./scripts/init.sh --qa-status` and do its first step, then run this command again. |
| `FAIL  Answer: ... saved address ...` | In `./scripts/init.sh --desktop-qa` open `Ayuda > Herramientas de prueba > Conexión`, press `Usar la dirección predeterminada`, then run this command again. |
| `FAIL  Answer: ...` (no reply, error, or no source) or `FAIL  Feedback: ...` | Do the one step it names (`--qa-status`, or send `build/qa-check/desktop.log` to a developer). The first question after QA starts can be slow; run it again once. |
| `FAIL  Answer: the check could not run ...` | Send `build/qa-check/desktop.log` to a developer. |

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

## Your settings file

The setup creates one settings file, `settings.env`, in the `manijero/local` folder inside your
home folder. It holds the PAC campaign year the answers use (`MANIJERO_ACTIVE_CAMPAIGN=2026`) and
two lines that say this file is for the local environment (`MANIJERO_ENVIRONMENT=local` and
`MANIJERO_DEPLOYMENT_PROFILE=development`); leave those two alone. The setup never overwrites the
file; on an older file it only adds the two lines. If a developer asks you to change the year, edit
only the four digits after the `=` sign in TextEdit and save. Then run the setup again: it rebuilds
the knowledge for the new year without downloading anything. The QA settings file is in
`manijero/qa` and works the same way.

## Where things are kept

Everything the setup downloads or builds is kept in the `manijero/local` folder inside your home
folder, except the Ollama model (Ollama keeps it) and the search software (kept with the
Manijero folder). Log files are in `manijero/local/logs`. The access keys are in the `credentials`
folder of each environment (`manijero/local` and `manijero/qa`); never share, copy, or move them.
Do not delete or move these folders. Removing the downloaded tools is not supported yet.
