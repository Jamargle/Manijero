# QA alerts

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains.

## Set up Telegram alerts (one time)

QA alerts send you a Telegram message when QA stops working. You make the Telegram bot once; no command does that for you.

1. In Telegram, search for **BotFather** (the one with a blue check) and send `/newbot`. Choose a name and a user name ending in `bot`.
2. BotFather replies with a long **token** (numbers, a colon, letters). Keep that chat open; do not share the token.
3. Open your new bot in Telegram, press **Start**, and send it any message.
4. Run `./scripts/init.sh --qa-alerts-setup`. Paste the token when asked (nothing shows while you paste) and press Enter. When it asks, send your bot one more message and press Enter.
5. Expect `Result: Telegram alerts are set up. Send a test with ./scripts/init.sh --qa-alerts-test.` The token and chat are stored only on this Mac, in `manijero/alerts/credentials`.

If it says `No private message to your bot was found`, send the bot a message in Telegram and run the command again.

## Turn QA alerts on, check, test, and off

The alert check runs on this Mac every 5 minutes while it is awake. A sleeping or switched-off Mac sends nothing. On first start macOS may show "Background item added"; leave it allowed.

| To do this | Run | Expect |
|---|---|---|
| Send a test message | `./scripts/init.sh --qa-alerts-test` | `Result: a test alert was sent. Check Telegram on your phone.` |
| Turn alerts on | `./scripts/init.sh --qa-alerts-start` | `Result: QA alerts are on. The check runs every 5 minutes while this Mac is awake.` |
| Check | `./scripts/init.sh --qa-alerts-status` | `OK` lines and `Result: QA alerts are on and the last check found no problem.` |
| Turn alerts off | `./scripts/init.sh --qa-alerts-stop` | `Result: QA alerts are off.` |

Start needs the Telegram setup, a deployed QA (`--qa-deploy`), and the QA access keys. A `Result:` that begins `QA alerts were not turned on` or `the test alert was not sent` names its one fix. You get one message when a problem has lasted two checks in a row, a reminder every 4 hours at most, and `Manijero QA is back to normal` when it clears. Stopping QA with `--qa-stop` is not a problem.

| The message says (after `Manijero QA:`) | First thing to do |
|---|---|
| `QA is down: Docker Desktop is not open.` | Open Docker Desktop, then run `./scripts/init.sh --qa-deploy`. |
| `QA is down: the QA service is not running or does not answer.` | Run `./scripts/init.sh --qa-status`. |
| `QA is running but not ready to answer questions.` | Run `./scripts/init.sh --qa-status`. |
| `QA failed on N% of questions in the last 15 minutes.` | Open the health dashboard, then run `./scripts/init.sh --qa-status`. |
| `QA works on your Mac but phones cannot reach it.` | Open the Tailscale app, check you are logged in, then run `./scripts/init.sh --qa-status`. |

## Owner walkthrough: QA alerts

Manual acceptance for QA alerts. Write the result of each step in the session notes.

1. Do "Set up Telegram alerts (one time)".
2. Run `./scripts/init.sh --qa-alerts-test`. Expect the message on your phone.
3. With QA running (`--qa-status` shows `OK`), run `./scripts/init.sh --qa-alerts-start`, then `--qa-alerts-status`. Expect the `Result:` lines above.
4. Quit Docker Desktop. Within about 10 minutes expect the message `QA is down: Docker Desktop is not open.`
5. Open Docker Desktop and run `./scripts/init.sh --qa-deploy` if QA is not back. Within about 10 minutes expect `Manijero QA is back to normal`.
6. Run `./scripts/init.sh --qa-alerts-stop`. Expect `Result: QA alerts are off.`
