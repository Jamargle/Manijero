"""Usability session: kit guards, the results recorder, refusals, file safety, init.sh dispatch.

Offline: every recorder run uses a temporary ``MANIJERO_USABILITY_HOME`` and scripted answers; the
real ``~/manijero`` is never touched.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from app import usability_results as ur  # noqa: E402
import usability_record as rec  # noqa: E402

KIT = REPO_ROOT / "docs" / "usability-session"
INIT = REPO_ROOT / "scripts" / "init.sh"
STRINGS = REPO_ROOT / "shared/src/commonMain/composeResources/values/strings.xml"
KIT_FILES = (
    "guion-facilitador.md", "nota-consentimiento.md", "tareas.md", "hoja-observacion.md", "preguntas-finales.md",
)
QUOTED_LABELS = (
    "Antes de empezar", "Entendido", "Mis terrenos", "Añadir terreno", "Nombre del terreno", "Zona o paraje",
    "Guardar terreno", "Elige el terreno de tu pregunta", "Tiene en cuenta todos tus terrenos.", "Fuentes",
    "Abrir documento oficial", "Quitar", "Terrenos eliminados", "Borrar para siempre", "Ayuda", "Ver bienvenida",
)


def kit(name: str) -> str:
    return (KIT / name).read_text(encoding="utf-8")


# --- Kit guards ----------------------------------------------------------------------------


def test_kit_has_five_files() -> None:
    for name in KIT_FILES:
        assert (KIT / name).is_file(), name
    assert sorted(p.name for p in KIT.iterdir()) == sorted(KIT_FILES)


def test_consent_note_promises_privacy() -> None:
    text = kit("nota-consentimiento.md").lower()
    for phrase in (
        "no a ti", "parar cuando quieras", "no grabamos tu cara ni tu voz", "no guardamos tu nombre",
        "datos inventados", "de palabra", "no hay firma",
    ):
        assert phrase in text, phrase


def test_tasks_in_order_with_pinned_labels() -> None:
    tasks = kit("tareas.md")
    positions = [tasks.index("## Tarjeta {}.".format(n)) for n in (1, 2, 3, 4)]
    assert positions == sorted(positions)
    assert "¿Hasta cuándo puedo presentar la solicitud única de 2026 para mis terrenos?" in tasks
    assert "Olivar de prueba A" in tasks and "Olivar de prueba B" in tasks
    assert tasks.index("**Antes de empezar**") < tasks.index("**Mis terrenos**") < tasks.index("**Fuentes**")


def test_every_quoted_label_exists_unchanged_in_app_strings() -> None:
    strings = STRINGS.read_text(encoding="utf-8")
    everything = "\n".join(kit(name) for name in KIT_FILES)
    for label in QUOTED_LABELS:
        assert ">{}<".format(label) in strings, label
        assert label in everything, label
    # Format strings are matched by their fixed prefix.
    assert ">Publica: %1$s<" in strings


def test_observation_sheet_fields() -> None:
    sheet = kit("hoja-observacion.md")
    for text in ("Código de participante", "Completada", "Necesitó ayuda", "Abandonó", "Minutos",
                 "¿la aplicación pidió elegir un terreno?", "No escribas nombres, teléfonos ni números"):
        assert text in sheet, text
    for forbidden in ("Nombre:", "Teléfono:", "Edad", "Email", "Correo:"):
        assert forbidden not in sheet, forbidden


def test_facilitator_script_commands_rules_and_honest_task_3() -> None:
    script = kit("guion-facilitador.md")
    for text in (
        "./scripts/init.sh --qa-status", "./scripts/init.sh --desktop-qa", "./scripts/init.sh --usability-record",
        "Manijero QA", "**Quitar**", "**Borrar para siempre**", "**Ver bienvenida**", "2 minutos", "5 minutos",
        "¿Qué piensas que pasa ahora?", "**no** muestre **Elige el terreno de tu pregunta**",
        "**Tiene en cuenta todos tus terrenos.**",
    ):
        assert text in script, text


def test_owner_guide_section_title_and_size() -> None:
    guide = (REPO_ROOT / "docs" / "owner-guide.md").read_text(encoding="utf-8")
    match = re.search(r"^## Owner walkthrough: usability session\n(.*?)(?=^## |\Z)", guide, re.S | re.M)
    assert match, "missing section"
    assert len(match.group(0).splitlines()) <= 66


# --- Screening -----------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["Juan", "1", "P0", "P100", "", "P", "p-1", "P1 P2"])
def test_codes_refused(text: str) -> None:
    assert ur.validate_code(text) is None


@pytest.mark.parametrize("text, code", [("P1", "P1"), (" p12 ", "P12"), ("P99", "P99")])
def test_codes_accepted(text: str, code: str) -> None:
    assert ur.validate_code(text) == code


@pytest.mark.parametrize(
    "note",
    [
        "habló con Pedro", "se llama paco", "me llamo antonio", "la señora no encontró el botón", "don luis dudó",
        "vive en calle olivo", "c/ mayor", "avenida de andalucia", "llama al 600123456", "su correo es a@b.com",
        "dni 12345678Z", "NIE X1234567L", "iban ES9121000418450200051332", "referencia 123456",
        "sr. lópez", "plaza mayor", "portal 3", "Se llama ana",
    ],
)
def test_notes_refused(note: str) -> None:
    assert ur.screen_note(note) is not None


@pytest.mark.parametrize(
    "note",
    [
        "", "no encontró el botón Ayuda", "pulsó Quitar dos veces",
        "usó 23:45:1:12:3 como referencia", "dudó con Mis Terrenos y Fuentes", "p1 tardó más. Picual y Secano",
        "preguntó por la PAC y SIGPAC",
    ],
)
def test_notes_allowed(note: str) -> None:
    assert ur.screen_note(note) is None


def test_app_words_with_capitals_pass() -> None:
    assert ur.screen_note("pulsó Ayuda y luego Entendido") is None
    assert ur.screen_note("miró Fuentes y Mis Terrenos") is None


# --- Recorder ------------------------------------------------------------------------------


class Script:
    """Scripted answers; records every prompt and output line. ``None`` answers mean end of input."""

    def __init__(self, answers: List[Optional[str]]) -> None:
        self.answers = list(answers)
        self.prompts: List[str] = []
        self.lines: List[str] = []

    def ask(self, prompt: str) -> Optional[str]:
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else None

    def out(self, line: str) -> None:
        self.lines.append(line)

    @property
    def text(self) -> str:
        return "\n".join(self.prompts + self.lines)


def participant_answers(code: str, outcomes=("1", "2", "1", "3"), minutes=("2", "10", "4", "6"), shown="no",
                        notes=("", "", "", ""), debrief="") -> List[str]:
    answers = [code]
    for index in range(4):
        answers += [outcomes[index], minutes[index]]
        if index == 2:
            answers.append(shown)
        answers.append(notes[index])
    answers += [debrief, "yes"]
    return answers


def run(tmp_path: Path, answers: List[Optional[str]], argv=()) -> "tuple[int, Script, Path]":
    script = Script(answers)
    env = {ur.HOME_ENV: str(tmp_path / "home")}
    code = rec.run(list(argv), env, ask=script.ask, out=script.out, checkout=REPO_ROOT)
    return code, script, tmp_path / "home" / ur.RESULTS_NAME


def result_line(script: Script) -> str:
    lines = [line for line in script.lines if line.startswith("Result:")]
    assert len(lines) == 1, script.lines
    return lines[0]


def test_two_participants_saved_and_summarised(tmp_path: Path) -> None:
    code, first, path = run(tmp_path, participant_answers("P1"))
    assert code == 0
    assert result_line(first) == "Result: P1 was saved; the results file holds 1 participant: {}.".format(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    code, second, _ = run(tmp_path, participant_answers("P2", outcomes=("1", "1", "2", "1"), shown="y"))
    assert code == 0
    assert result_line(second) == "Result: P2 was saved; the results file holds 2 participants: {}.".format(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "usability-results-v1"
    assert [p["code"] for p in data["participants"]] == ["P1", "P2"]
    task3 = data["participants"][1]["tasks"][2]
    assert task3 == {"task": "land_question", "outcome": "needed_help", "minutes": 4, "note": "",
                     "land_choice_shown": True}
    assert "land_choice_shown" not in data["participants"][0]["tasks"][0]
    assert "Participants saved: 2" in second.lines
    assert "Task 1 (first_use): 2 completed, 0 needed help, 0 gave up; median 2 min" in second.lines
    assert "Task 2 (add_two_lands): 1 completed, 1 needed help, 0 gave up; median 10 min" in second.lines
    assert "The app asked to choose a land: 1 of 2 participants" in second.lines
    assert not re.search(r"20\d\d-\d\d-\d\d|\d\d:\d\d:\d\d", path.read_text(encoding="utf-8"))
    assert list(path.parent.glob(".usability-*")) == []


def test_land_choice_no_is_reported(tmp_path: Path) -> None:
    _, script, _ = run(tmp_path, participant_answers("P1"))
    assert "The app asked to choose a land: 0 of 1 participants" in script.lines


def test_participants_sorted_numerically(tmp_path: Path) -> None:
    run(tmp_path, participant_answers("P10"))
    _, _, path = run(tmp_path, participant_answers("P2"))
    codes = [p["code"] for p in json.loads(path.read_text(encoding="utf-8"))["participants"]]
    assert codes == ["P2", "P10"]


def test_note_accepted_and_stored(tmp_path: Path) -> None:
    notes = ("dudó con Ayuda", "", "señaló la línea", "")
    _, _, path = run(tmp_path, participant_answers("P1", notes=notes, debrief="le gustó la letra grande"))
    stored = json.loads(path.read_text(encoding="utf-8"))["participants"][0]
    assert stored["tasks"][0]["note"] == "dudó con Ayuda"
    assert stored["debrief_note"] == "le gustó la letra grande"


def test_bad_code_refused_without_echo(tmp_path: Path) -> None:
    code, script, path = run(tmp_path, ["Maria Lopez"] + participant_answers("P1"))
    assert code == 0 and path.exists()
    assert ur.MSG_CODE_REFUSED in script.lines
    assert "Maria" not in script.text and "Lopez" not in script.text
    assert "Maria" not in path.read_text(encoding="utf-8")


def test_refused_note_never_echoed_or_stored(tmp_path: Path) -> None:
    secret = "llama al 600123456 Pedro"
    answers = ["P1", "1", "2", secret, "dudó", "2", "10", "", "1", "4", "no", "", "3", "6", "", "", "yes"]
    code, script, path = run(tmp_path, answers)
    assert code == 0, script.lines
    assert any(line.startswith("That note may hold a name") for line in script.lines)
    for blob in (script.text, path.read_text(encoding="utf-8")):
        assert "600123456" not in blob and "Pedro" not in blob
    assert json.loads(path.read_text(encoding="utf-8"))["participants"][0]["tasks"][0]["note"] == "dudó"


def test_three_refusals_stop_the_run(tmp_path: Path) -> None:
    code, script, path = run(tmp_path, ["Juan", "Pedro", "Ana", "P1"])
    assert code == 1 and not path.exists() and not path.parent.exists()
    assert result_line(script) == "Result: nothing was saved. Run ./scripts/init.sh --usability-record again."


def test_three_bad_notes_stop_the_run(tmp_path: Path) -> None:
    code, script, path = run(tmp_path, ["P1", "1", "2", "Pedro", "Maria", "calle sol"])
    assert code == 1 and not path.exists()
    assert result_line(script).startswith("Result: nothing was saved.")


def test_bad_outcome_and_minutes_are_retried(tmp_path: Path) -> None:
    answers = ["P1", "9", "1", "-3", "61", "5", "", "1", "2", "", "1", "3", "no", "", "1", "1", "", "", "yes"]
    code, script, path = run(tmp_path, answers)
    assert code == 0, script.lines
    assert "Type 1, 2, or 3." in script.lines
    assert json.loads(path.read_text(encoding="utf-8"))["participants"][0]["tasks"][0]["minutes"] == 5


def test_end_of_input_saves_nothing(tmp_path: Path) -> None:
    code, script, path = run(tmp_path, ["P1", "1", "3"])
    assert code == 1 and not path.exists()
    assert result_line(script).startswith("Result: nothing was saved.")


def test_declined_recap_leaves_file_identical(tmp_path: Path) -> None:
    _, _, path = run(tmp_path, participant_answers("P1"))
    before = path.read_bytes()
    answers = participant_answers("P2")
    answers[-1] = "no"
    code, script, _ = run(tmp_path, answers)
    assert code == 1 and path.read_bytes() == before
    assert result_line(script).startswith("Result: nothing was saved.")


def test_keyboard_interrupt_saves_nothing(tmp_path: Path) -> None:
    script = Script([])

    def interrupt(prompt: str) -> Optional[str]:
        raise KeyboardInterrupt

    env = {ur.HOME_ENV: str(tmp_path / "home")}
    code = rec.run([], env, ask=interrupt, out=script.out, checkout=REPO_ROOT)
    assert code == 1 and not (tmp_path / "home" / ur.RESULTS_NAME).exists()
    assert result_line(script).startswith("Result: nothing was saved.")


def test_replace_existing_asks_yes(tmp_path: Path) -> None:
    _, _, path = run(tmp_path, participant_answers("P1"))
    code, script, _ = run(tmp_path, ["P1", "yes"] + participant_answers("P1", outcomes=("3", "3", "3", "3"))[1:])
    assert code == 0
    assert any("P1 is already saved" in prompt for prompt in script.prompts)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["participants"]) == 1
    assert data["participants"][0]["tasks"][0]["outcome"] == "gave_up"


def test_replace_declined_changes_nothing(tmp_path: Path) -> None:
    _, _, path = run(tmp_path, participant_answers("P1"))
    before = path.read_bytes()
    code, script, _ = run(tmp_path, ["P1", "no"])
    assert code == 1 and path.read_bytes() == before
    assert result_line(script).startswith("Result: nothing was saved.")


@pytest.mark.parametrize("content", ["{not json", '{"schema": "other", "participants": []}',
                                     '{"schema": "usability-results-v1", "participants": [{"code": "Juan"}]}'])
def test_unreadable_file_changes_nothing(tmp_path: Path, content: str) -> None:
    path = tmp_path / "home" / ur.RESULTS_NAME
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")
    code, script, _ = run(tmp_path, participant_answers("P1"))
    assert code == 1 and path.read_text(encoding="utf-8") == content
    assert result_line(script) == (
        "Result: the results file could not be read, so nothing was saved. Send {} to the developer.".format(path)
    )
    assert script.prompts == []


def test_home_inside_checkout_refused(tmp_path: Path) -> None:
    script = Script(participant_answers("P1"))
    inside = REPO_ROOT / "build" / "usability-test-never-created"
    code = rec.run([], {ur.HOME_ENV: str(inside)}, ask=script.ask, out=script.out, checkout=REPO_ROOT)
    assert code == 1 and not inside.exists() and script.prompts == []


def test_extra_argument_is_misuse(tmp_path: Path) -> None:
    code, script, path = run(tmp_path, participant_answers("P1"), argv=["extra"])
    assert code == 2 and script.prompts == [] and not path.parent.exists()


# --- init.sh -------------------------------------------------------------------------------


def run_init(args: List[str], stdin: str, home: Path) -> "subprocess.CompletedProcess[str]":
    env: Dict[str, str] = dict(os.environ)
    env[ur.HOME_ENV] = str(home)
    return subprocess.run(
        ["bash", str(INIT)] + args, input=stdin, capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        timeout=120,
    )


def test_init_extra_argument_exits_2_without_prompt(tmp_path: Path) -> None:
    done = run_init(["--usability-record", "extra"], "P1\n", tmp_path / "home")
    assert done.returncode == 2
    assert "Run --usability-record on its own, with nothing after it." in done.stderr
    assert "Participant code" not in done.stdout and not (tmp_path / "home").exists()


def test_init_records_a_participant(tmp_path: Path) -> None:
    if not (BACKEND_ROOT / ".venv" / "bin" / "python").exists():
        pytest.skip("backend virtualenv not set up")
    stdin = "\n".join(participant_answers("P1")) + "\n"
    home = tmp_path / "home"
    done = run_init(["--usability-record"], stdin, home)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.strip().splitlines()[-1] == (
        "Result: P1 was saved; the results file holds 1 participant: {}.".format(home / ur.RESULTS_NAME)
    )
    assert "Traceback" not in done.stdout + done.stderr


def test_init_lists_command_and_gitignore_guard() -> None:
    text = INIT.read_text(encoding="utf-8")
    assert text.count("--usability-record") >= 4
    assert "usability-results*.json" in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
