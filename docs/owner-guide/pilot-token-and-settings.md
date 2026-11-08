# Pilot token, environments, and settings

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

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
| `Result: the local environment is not set up yet. Run ./scripts/init.sh --local-rag-setup.` | Run that command (see [Set up the local answer tools](local-answer-service.md#set-up-the-local-answer-tools)). |
| `ATTENTION  local: the settings file does not say it is for the local environment` | Run `./scripts/init.sh --local-rag-setup`; it adds two lines to your settings file and changes nothing else. |
| `ATTENTION  local: the local access keys are missing or incomplete` | Run `./scripts/init.sh --local-rag-setup`; it makes them. |
| `PROBLEM  QA: ...` | Do what the line says, usually `./scripts/init.sh --qa-settings-setup`. |

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
