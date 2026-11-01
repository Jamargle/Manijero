# Owner guide

Copy-paste steps for every routine operation. Run each command from the project folder (the
folder that contains `scripts/`). Each command ends with one `Result:` line that says what
happened and, when something went wrong, the next step. Internals live in
[`backend/README.md`](../backend/README.md) and in the feature specs, not here.

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
- `Port 8000 is in use by the real local answer service` — close the window where
  `./scripts/init.sh --backend` is running (or press Ctrl+C in it), then repeat step 2.
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
