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
