# Owner guide

Copy-paste steps for running Manijero yourself. Every operation is one command, typed in the
Terminal window opened at the Manijero folder. Every command ends with a line that starts with
`Result:`. That line tells you whether it worked or what to do next. Internals for developers
are in [`backend/README.md`](../../backend/README.md).

**Open Terminal at the Manijero folder:** in Finder, right-click the `Manijero` folder and choose
**New Terminal at Folder**. Type or paste each command exactly as written, then press Enter.

## Which guide to open

In the order you usually need them:

1. [Mock answer service](mock-service.md): try the apps with fixed example answers; no setup needed.
2. [Local answer service](local-answer-service.md): set up and check the local answer tools, then
   start, check, and stop the service that gives real answers on this computer.
3. [Load test, smoke test, and demo rehearsal](local-checks.md): measure answer speed, check both
   apps against the local service, and rehearse the live demo.
4. [Golden set review](golden-set-review.md): approve or reject the drafted test questions.
5. [Pilot token, environments, and settings](pilot-token-and-settings.md): save the pilot token,
   see your environments, change the settings file, and where things are kept.
6. [Answer service in a container](container.md): install Docker Desktop, build the image, and
   start, check, and stop the container.
7. [Health dashboard](monitoring.md): see in a web page whether the answer service is working.
8. [QA](qa.md): prepare QA, set up Tailscale, deploy and manage QA, check the QA Desktop app, and
   build the QA test apps.
9. [QA alerts](qa-alerts.md): get a Telegram message when QA stops working.
10. [Usability session](usability-session.md): run and record a session with test participants.
11. [Grounding judge](grounding-judge.md): download the second model that checks drafted sentences and
    produce its counts report (scores unchecked against human review).

An "Owner walkthrough" section near the end of a guide holds one-time acceptance steps whose
`Result:` lines you report to the developer.
