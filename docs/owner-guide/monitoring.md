# Health dashboard

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## Open the health dashboard

A free page on this Mac that says, in plain words, whether the answer service is working. It needs
[Docker Desktop](container.md#install-docker-desktop-one-time) open. It is not an alarm: it only shows what is
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
