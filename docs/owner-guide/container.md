# Answer service in a container

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

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

Run this after [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools) has finished, and
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
| `The local answer tools are not set up yet.` or a line with `Run ./scripts/init.sh --local-rag-setup` | A part the image needs is missing or out of date. | Follow [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools), then repeat step 2. |
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

Do this once, after [Owner walkthrough: local answer service](local-answer-service.md#owner-walkthrough-local-answer-service),
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
