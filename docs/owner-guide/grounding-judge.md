# Grounding judge

Steps for the owner. Open Terminal at the Manijero folder and read the `Result:` line as the
[owner guide index](README.md) explains. The judge is a second, small local model that reads each
sentence the local drafting model wrote and says whether the official passages it cites back it up.
It only counts; it never changes an answer. Its scores are **unchecked against human review**: do not
read them as how good the answers are.

You need the local answer tools and the drafting model first ([local answer service](local-answer-service.md)),
and the Ollama app open.

## Download the judge model (one time)

1. Paste `./scripts/init.sh --grounding-judge-setup`. Ollama shows its own progress for about 4.7 GB.
   - Expected: `Result: the grounding judge model is ready.`
   - A second run says `Result: the grounding judge model is already ready; nothing was downloaded.`

## Produce the report

1. Paste `./scripts/init.sh --grounding-judge-report` and wait; it prints `Checked case <n> of <N>`.
   - Expected: `Result: judged S draft sentences from D drafts (P supported, N not supported, U unclear, X not judged); judge scores are unchecked against human review. Report: build/grounding-judge/report.json.`
2. The report holds counts and each judged sentence. Send the developer the `Result:` line.

### If the command shows something else

| You see | What it means | What to do |
|---|---|---|
| `Result: the grounding judge command did not run. Run ./scripts/init.sh --local-rag-setup.` | The local answer tools are not set up. | Run that command, then repeat. |
| `Result: Ollama is not installed. ...` | The Ollama app is missing. | Install it from ollama.com, open it, repeat. |
| `Result: Ollama is not running. ...` | The Ollama app is closed. | Open the Ollama app, repeat. |
| `Result: the grounding judge model could not be downloaded. ...` | The download failed. | Check the internet connection, repeat the setup. |
| `Result: the downloaded grounding judge model is not the reviewed one, ...` | The download is not the reviewed model. | Send the line to the developer; nothing was changed. |
| `Result: the grounding judge model is not pinned yet. ...` / `... record is not valid. ...` | The judge record needs a developer. | Send the line to the developer. |
| `Result: the grounding judge report did not run (generator_unavailable): ...` | The drafting model is missing. | Run `./scripts/init.sh --local-rag-setup`, repeat. |
| `Result: the grounding judge report did not run (judge_unavailable): ...` | The judge model is missing. | Run `./scripts/init.sh --grounding-judge-setup`, repeat. |
| `Result: the grounding judge report did not run (ollama_unavailable): ...` | Ollama is closed. | Open the Ollama app, repeat. |
| `Result: the grounding judge report did not run (...): ...` with another name | An input or record needs a developer. | Send the line to the developer; no report was written. |

## Owner walkthrough: grounding judge

Do this once, after the developer accepts the feature. Write down each `Result:` line.

1. Run `./scripts/init.sh --grounding-judge-setup`. Expect `Result: the grounding judge model is ready.` (or `already ready`).
2. Run it again. Expect `Result: the grounding judge model is already ready; nothing was downloaded.`
3. **Missing prerequisite:** quit the Ollama app, then run `./scripts/init.sh --grounding-judge-report`.
   Expect `Result: the grounding judge report did not run (ollama_unavailable): ...`
4. **Recovery:** open the Ollama app and run `./scripts/init.sh --grounding-judge-report`. Expect
   `Checked case 1 of ...` lines, then the `Result: judged S draft sentences ...` line.
5. Send the developer every `Result:` line. They record the counts, labelled unchecked, in the acceptance record.
