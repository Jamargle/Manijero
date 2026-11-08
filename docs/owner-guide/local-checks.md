# Load test, smoke test, and demo rehearsal

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

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
| `The local answer tools are not set up yet. ...`, then `Result: the load test did not run. Do the first step shown above.` | The local answer tools were never set up. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools), then run the command again. |
| A `PROBLEM ...` line, then `Result: the load test did not run. Do the first step shown above.` | A service check is not `OK` (for example Ollama is closed). | Do what the `PROBLEM` line says, then run the command again. |
| `Another load test is running in another Terminal window.` | One is already running. | Wait for its `Result:` line, then run it again. |
| `Result: the load test finished, but … questions failed. ...` | Some questions did not answer; the timing numbers are incomplete. | Run it once more. If it repeats, send the report file to a developer. |
| `Result: the load test finished, but the local answer service changed during the run, ...` | The service stopped, restarted, or its knowledge changed during the run. | Run `./scripts/init.sh --local-rag-start`, then run the test again. |
| `Result: the load test was stopped.` | You pressed Ctrl+C. | Run it again when you are ready; nothing was changed. |
| `Something unexpected went wrong. ... <log file>` | The command itself failed. | Send that log file to a developer. |

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
| `Result: the smoke test did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools). |
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
3. **Read the script before the demo:** [demo-script.md](../demo-script.md) gives the order, the two
   fixed questions, the app steps to do by hand, and what you must not promise.

### If the rehearsal shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the demo rehearsal did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools), then repeat step 2. |
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
