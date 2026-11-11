# Help text: --help and the standard-command list printed by --check.
usage() {
  cat <<'EOF'
Usage: ./scripts/init.sh [--check|--fast|--verify|--feature <id>|--backend-tests [targets]|--setup-python [dev|hybrid|docparse]|--backend|--mock|--mock-status|--mock-stop|--local-rag-setup|--local-rag-status|--local-rag-start|--local-rag-service-status|--local-rag-load-test|--local-rag-stop|--container-build|--container-start|--container-status|--container-stop|--monitoring-start|--monitoring-status|--monitoring-stop|--pilot-token-save|--demo-rehearsal|--golden-review|--golden-decide|--trap-review|--trap-decide|--glossary-review|--glossary-decide|--grounding-judge-setup|--grounding-judge-report|--usability-record|--local-smoke|--qa-check|--environments-status|--qa-settings-setup|--qa-deploy|--qa-update|--qa-rollback|--qa-status|--qa-stop|--qa-knowledge-deploy|--qa-knowledge-rollback|--qa-alerts-setup|--qa-alerts-start|--qa-alerts-stop|--qa-alerts-status|--qa-alerts-test|--knowledge-updates-on|--knowledge-updates-run|--knowledge-updates-status|--knowledge-updates-off|--knowledge-review-open|--knowledge-review-protect|--reranker-download|--reranker-measure|--reranker-on|--reranker-off|--android|--android-run|--desktop|--android-qa|--desktop-qa|--help]

  --check                   Check Java and the Gradle wrapper, then print standard commands (default)
  --fast                    Shared host tests, contract examples, backend unit tests, and the five
                            offline evaluators, run concurrently (no Android SDK or Desktop build
                            needed). Fails if any single check fails.
  --verify                  Full gate: --fast, the quality gate over the reviewed metrics baseline,
                            then the Android host tests and the Android/Desktop builds (--full is an alias)
  --feature <id>            Run the focused verification published in docs/specs/<id>.md
  --backend-tests [target]  Run the backend pytest suite, or only the given targets, from backend/
  --setup-python [profile]  Build or reuse the shared backend virtualenv (dev, or hybrid for
                            torch/chromadb, or docparse for pymupdf4llm/docling/pytesseract) and
                            link it as backend/.venv (or backend/.venv-hybrid, backend/.venv-docparse)
  --backend                 Link the shared backend virtualenv if needed and launch the local API
  --mock                    Start the mock answer service in the background (fixed contract
                            example answers, no Python needed) and print the app addresses
  --mock-status             Say whether the mock answer service is running, and where
  --mock-stop               Stop the mock answer service
  --local-rag-setup         Guided one-time setup of the local answer tools: shows the download
                            sizes, asks, then downloads and builds what is missing (needs Ollama)
  --local-rag-status        Read-only check of the six local answer-tool parts, in plain words
  --local-rag-start         Start the real local answer service in the background (hybrid search,
                            local drafting, 127.0.0.1 only) once all six parts are ready
  --local-rag-service-status
                            Say whether the local answer service runs, can answer, and where
  --local-rag-stop          Stop the local answer service
  --local-rag-load-test     With the service running, ask the reviewed questions from 10 clients
                            for about five minutes and report answer times and throughput (one
                            aggregate report under the local home; no pass or fail)
  --container-build         Build the answer service image in Docker Desktop with the published
                            knowledge release and the search model (no drafting model)
  --container-start         Run that image in the background on 127.0.0.1 (drafting through
                            Ollama on this Mac)
  --container-status        Say whether the container runs, can answer, and where
  --container-stop          Stop and remove the answer service container
  --monitoring-start        Start the health dashboard (Prometheus and Grafana in Docker Desktop) and
                            print its browser address (127.0.0.1 only)
  --monitoring-status       Say whether the health dashboard runs and answers
  --monitoring-stop         Stop and remove the health dashboard (its history is kept)
  --pilot-token-save        Save the copied pilot token (macOS clipboard) for the next test builds
                            (Android debug, --desktop); it never prints the token
  --demo-rehearsal          With the local answer service running, rehearse the demo: service steps
                            plus a temporary, synthetic reviewed update (see docs/demo-script.md)
  --golden-review           List the golden questions that wait for your decision, with their
                            official source text; the full list goes to build/golden-review/drafts.txt
  --golden-decide approve|reject "<name>" <number-or-id>...
                            Record your decision for the listed golden questions (nothing is
                            recorded if anything is wrong)
  --trap-review             List the trap questions that wait for your decision, with what a safe
                            answer must do; the full list goes to build/trap-review/drafts.txt
  --trap-decide approve|reject "<name>" <number-or-id>...
                            Record your decision for the listed trap questions (nothing is
                            recorded if anything is wrong)
  --glossary-review         List the colloquial -> official word pairs that wait for your decision;
                            the full list goes to build/glossary-review/pairs.txt
  --glossary-decide approve|reject "<name>" <number-or-id>...
                            Record your decision for the listed word pairs (nothing is recorded if
                            anything is wrong)
  --colloquial-review       List the everyday rewordings of the golden questions that wait for
                            your decision; the full list goes to build/colloquial-ab/variants.txt
  --colloquial-decide approve|reject "<name>" <number-or-id>...
                            Record your decision for the listed colloquial variants (nothing is
                            recorded if anything is wrong)
  --grounding-judge-setup   One time: download the small second model that checks drafted sentences
                            (needs Ollama; about 4.7 GB) and verify it is the reviewed one
  --grounding-judge-report  Draft the reviewed and golden questions with the local drafting model, have
                            the second model check each sentence, and write build/grounding-judge/report.json
                            (counts only; scores are unchecked against human review)
  --reranker-download       One time: download the optional second reading model (about 2.3 GB) and
                            check it against the reviewed copy (see docs/owner-guide/reranker.md)
  --reranker-measure        Compare it with today's search on the golden and trap questions and print
                            one Result: line with the on/off verdict (counts only; nothing is switched)
  --reranker-on             Switch the reranker on (refused unless the model checks out)
  --reranker-off            Switch the reranker off
  --usability-record        Save one usability-session participant's results under an anonymous
                            code (P1, P2...) and print a plain summary (see docs/owner-guide/usability-session.md)
  --local-smoke             With the local answer service running, ask it one fixed question through
                            the Desktop app and the app on the running Android emulator; one PASS or
                            FAIL line each (installs the debug app over the existing one, data kept)
  --qa-check                With QA deployed, check end to end that the QA Desktop app reaches QA,
                            shows a sourced answer to a made-up question, and gets its Útil rating
                            accepted; one PASS or FAIL line per step (needs the QA access key)
  --environments-status     Read-only: say in plain words what the local, QA, and prod
                            environments each have (nothing is deployed or contacted)
  --qa-settings-setup       Prepare the QA settings file and access keys on this computer
  --qa-deploy               Run QA from the built image, reachable over HTTPS through Tailscale
                            Funnel, for made-up test questions only
  --qa-update               Ship the newest built image to QA (the earlier one is kept)
  --qa-rollback             Put the earlier QA image back (run it again to roll forward)
  --qa-status               Say whether QA runs, answers, and is reachable
  --qa-stop                 Take QA off the internet and stop it
  --qa-knowledge-deploy     Send the approved knowledge merged to main to QA, checked first,
                            with an automatic way back if QA's checks fail
  --qa-knowledge-rollback   Put QA's earlier knowledge back (run it again to roll forward)
                            (placeholder server address; nothing is deployed)
  --qa-alerts-setup         One time: store the Telegram bot token and find your chat
  --qa-alerts-start         Turn on the check that runs every 5 minutes and messages you on
                            Telegram when QA is down, not ready, erroring, or unreachable
  --qa-alerts-stop          Turn the QA alert check off (Telegram details are kept)
  --qa-alerts-status        Say whether the alert check is on and what its last run found
  --qa-alerts-test          Send one test alert to Telegram
  --knowledge-updates-on    Turn on the daily knowledge update run (10:20, stops at "ready for review")
  --knowledge-updates-run   Run the whole knowledge update cycle now (one hour at most)
  --knowledge-updates-status  Say whether the daily run is on and how the last run went
  --knowledge-updates-off   Turn the daily run off (the history is kept)
  --knowledge-review-open   Open one GitHub pull request for each ready knowledge review package;
                            you read and merge it on GitHub, and nothing is published on merge
  --knowledge-review-protect  Protect main on GitHub: pull requests only, fast and full must pass,
                            no force pushes (asks before changing anything)
  --android                 Build the Android debug APK
  --android-run             Build, start an emulator if needed, install, and launch the app
  --desktop                 Launch the Desktop app
  --android-qa              Build the Manijero QA Android debug APK (its own app, QA address and key)
  --desktop-qa              Launch the Manijero QA Desktop app (its own data folder, QA address and key)
  --help                   Show this help

Tiers keep a small change cheap to check: --feature for one feature, --fast for the
whole no-device surface, --verify for the release-shaped gate.

Output is compact: one line per passing check and the tail of a failing log; full
logs are kept in build/verify-logs/. Set MANIJERO_VERBOSE=1 to print them inline.
EOF
}

# Plain-language list of the standard commands, printed by --check after the toolchain check.
print_standard_commands() {
  cat <<'EOF'

Manijero MVP — the Android and Desktop apps render the shared Kotlin Multiplatform UI and behavior in shared/src/commonMain. See PROGRESS.md and feature_list.json for the accepted feature set and current status.

Verification tiers:
  ./scripts/init.sh --feature <id>  # focused checks published in docs/specs/<id>.md
  ./scripts/init.sh --fast          # shared host tests + contract examples + backend tests + offline evaluators (concurrent)
  ./scripts/init.sh --verify        # --fast + Android host tests + Android debug APK + Desktop build

Build and run:
  ./scripts/init.sh --setup-python # build or reuse the shared backend virtualenv (once per requirements change)
  ./scripts/init.sh --backend    # start the local API (Ctrl+C to stop)
  ./scripts/init.sh --mock       # start the mock answer service: fixed example answers, no Python (--mock-status, --mock-stop)
  ./scripts/init.sh --local-rag-setup  # set up the local answer tools once (see docs/owner-guide/local-answer-service.md)
  ./scripts/init.sh --local-rag-status # check the local answer tools in plain words
  ./scripts/init.sh --local-rag-start  # start the real local answer service in the background (--local-rag-service-status, --local-rag-stop)
  ./scripts/init.sh --local-rag-load-test  # with it running: answer times and throughput from 10 clients for about five minutes
  ./scripts/init.sh --container-build  # build the answer service image in Docker Desktop (see docs/owner-guide/container.md)
  ./scripts/init.sh --container-start  # run it in the background (--container-status, --container-stop)
  ./scripts/init.sh --local-smoke      # with it running: ask it once through the Desktop and Android emulator apps
  ./scripts/init.sh --qa-check         # with QA deployed: reachable, sourced answer, feedback accepted (Desktop, no clicking)
  ./scripts/init.sh --demo-rehearsal   # with it running: rehearse the demo (docs/demo-script.md)
  ./scripts/init.sh --usability-record # save one usability-session participant (docs/usability-session/)
  ./scripts/init.sh --environments-status # what the local, QA, and prod environments each have
  ./scripts/init.sh --qa-settings-setup   # prepare QA settings and access keys on this computer (deploys nothing)
  ./scripts/init.sh --qa-deploy           # run QA over HTTPS for test data only (--qa-update, --qa-rollback, --qa-status, --qa-stop)
  ./scripts/init.sh --android    # androidApp/build/outputs/apk/debug/androidApp-debug.apk
  ./scripts/init.sh --android-run # build and launch on an Android emulator
  ./scripts/init.sh --desktop    # launch the Desktop app
  ./scripts/init.sh --android-qa # build the Manijero QA Android app (installs beside the local one)
  ./scripts/init.sh --desktop-qa # launch the Manijero QA Desktop app

The Android and Desktop apps use the local /ask service. Start it with --local-rag-start (or keep --backend running in a separate
terminal) while trying either app, or start the mock answer service with --mock to try every answer state without Python.
EOF
}
