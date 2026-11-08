"""Anonymous usability-session results: code and note screening, record model, store, summary.

Operator-only support for ``./scripts/init.sh --usability-record`` (see
``backend/scripts/usability_record.py`` and ``docs/owner-guide/usability-session.md``). The answer service never
imports this module.

The results file keeps only anonymous participant codes (``P1``..``P99``), fixed outcome codes,
whole minutes, and short notes that passed a lexical screen. The screen is a safety net, not a
guarantee: it cannot recognise every name or address, so the facilitator is also told not to
write them. Refused text is never returned, printed, or stored: the screens return a refusal
kind only.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.input_guardrails import screen_question

SCHEMA = "usability-results-v1"
HOME_ENV = "MANIJERO_USABILITY_HOME"  # tests only
RESULTS_NAME = "usability-results.json"

TASK_IDS = ("first_use", "add_two_lands", "land_question", "sources")
LAND_TASK = "land_question"
OUTCOMES = ("completed", "needed_help", "gave_up")
OUTCOME_BY_INPUT = {"1": "completed", "2": "needed_help", "3": "gave_up"}
MAX_MINUTES = 60
MAX_NOTE = 200
MAX_DEBRIEF = 400
MAX_CODE_NUMBER = 99

MSG_CODE_REFUSED = "Use the code from the sheet, like P1. Do not type names."
MSG_NOTE_REFUSED = (
    "That note may hold a name, phone number, email, address, or ID. Write it again without "
    "personal details, in small letters (app words such as Ayuda may keep their capital)."
)

APP_WORDS = frozenset(
    "Manijero QA Asistente Ayuda Mis Terrenos Añadir Guardar Entendido Fuentes Fuente Publica "
    "Abrir Quitar Borrar Continuar Preguntar Elige Conexión PAC SIGPAC FEGA Junta Andalucía "
    "Picual Hojiblanca Secano Regadío".split()
)
NAME_CUES = (
    "se llama", "me llamo", "llamado", "llamada", "apellido", "don", "doña", "señor", "señora",
    "sr.", "sra.",
)
ADDRESS_CUES = ("calle", "c/", "avenida", "avda", "plaza", "portal")

_CODE = re.compile(r"^P([1-9][0-9]?)$")
_DIGIT_RUN = re.compile(r"[0-9]{5,}")
_CUE_PATTERNS = [
    re.compile(r"(?<!\w)" + re.escape(cue) + r"(?!\w)", re.IGNORECASE) for cue in NAME_CUES + ADDRESS_CUES
]
_EDGE = re.compile(r"^[^\w]+|[^\w]+$")


class ResultsFileError(Exception):
    """The results file exists but cannot be read or is not the expected shape."""


def validate_code(text: str) -> Optional[str]:
    """Return the normalised ``P<n>`` code, or ``None`` when it is not P1..P99."""

    match = _CODE.match(text.strip().upper()) if isinstance(text, str) else None
    return "P" + match.group(1) if match else None


def code_number(code: str) -> int:
    return int(code[1:])


def screen_note(text: str) -> Optional[str]:
    """Return a refusal kind for a note that may hold personal data, else ``None``."""

    if _DIGIT_RUN.search(text):
        return "digits"
    for pattern in _CUE_PATTERNS:
        if pattern.search(text):
            return "cue"
    for word in text.split():
        bare = _EDGE.sub("", word)
        if bare and bare[0].isupper() and bare not in APP_WORDS and validate_code(bare) is None:
            return "capital"
    if screen_question(text) == "personal_data":
        return "personal_data"
    return None


@dataclass(frozen=True)
class TaskResult:
    task: str
    outcome: str
    minutes: int
    note: str = ""
    land_choice_shown: Optional[bool] = None

    def to_json(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "task": self.task,
            "outcome": self.outcome,
            "minutes": self.minutes,
            "note": self.note,
        }
        if self.task == LAND_TASK:
            data["land_choice_shown"] = bool(self.land_choice_shown)
        return data


@dataclass(frozen=True)
class Participant:
    code: str
    tasks: Sequence[TaskResult]
    debrief_note: str = ""

    def to_json(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "tasks": [task.to_json() for task in self.tasks],
            "debrief_note": self.debrief_note,
        }


@dataclass
class ResultsFile:
    participants: List[Participant] = field(default_factory=list)

    def has(self, code: str) -> bool:
        return any(p.code == code for p in self.participants)

    def with_participant(self, participant: Participant) -> "ResultsFile":
        kept = [p for p in self.participants if p.code != participant.code]
        kept.append(participant)
        kept.sort(key=lambda p: code_number(p.code))
        return ResultsFile(kept)

    def to_json(self) -> Dict[str, Any]:
        return {"schema": SCHEMA, "participants": [p.to_json() for p in self.participants]}


# --- Store ---------------------------------------------------------------------------------


def results_home(env: Mapping[str, str]) -> Path:
    configured = env.get(HOME_ENV, "").strip()
    return Path(configured).expanduser() if configured else Path.home() / "manijero" / "usability"


def is_inside(path: Path, root: Path) -> bool:
    resolved = path.expanduser().resolve()
    base = root.resolve()
    return resolved == base or base in resolved.parents


def _fail() -> ResultsFileError:
    return ResultsFileError("unexpected results file")


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise _fail()
    return value


def _parse_task(raw: Any, expected: str) -> TaskResult:
    allowed = {"task", "outcome", "minutes", "note"} | ({"land_choice_shown"} if expected == LAND_TASK else set())
    if not isinstance(raw, dict) or set(raw) != allowed or raw["task"] != expected:
        raise _fail()
    minutes = raw["minutes"]
    if raw["outcome"] not in OUTCOMES or type(minutes) is not int or not 0 <= minutes <= MAX_MINUTES:
        raise _fail()
    shown: Optional[bool] = None
    if expected == LAND_TASK:
        shown = raw["land_choice_shown"]
        if type(shown) is not bool:
            raise _fail()
    return TaskResult(expected, raw["outcome"], minutes, _text(raw["note"], MAX_NOTE), shown)


def _parse(raw: Any) -> ResultsFile:
    if not isinstance(raw, dict) or set(raw) != {"schema", "participants"} or raw["schema"] != SCHEMA:
        raise _fail()
    if not isinstance(raw["participants"], list):
        raise _fail()
    participants: List[Participant] = []
    for item in raw["participants"]:
        if not isinstance(item, dict) or set(item) != {"code", "tasks", "debrief_note"}:
            raise _fail()
        code = item["code"]
        tasks = item["tasks"]
        if validate_code(code) != code or not isinstance(tasks, list) or len(tasks) != len(TASK_IDS):
            raise _fail()
        parsed = [_parse_task(t, expected) for t, expected in zip(tasks, TASK_IDS)]
        participants.append(Participant(code, parsed, _text(item["debrief_note"], MAX_DEBRIEF)))
    codes = [p.code for p in participants]
    if len(set(codes)) != len(codes):
        raise _fail()
    return ResultsFile(participants)


def load(path: Path) -> ResultsFile:
    """Read the results file; a missing file is an empty one. Raises ``ResultsFileError``."""

    if not path.exists():
        return ResultsFile()
    try:
        return _parse(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ResultsFileError("unreadable results file") from exc


def save(path: Path, results: ResultsFile) -> None:
    """Write atomically: folder 0700, file 0600, temp file in the same folder, then rename."""

    folder = path.parent
    if not folder.exists():
        folder.mkdir(parents=True, mode=0o700)
        os.chmod(folder, 0o700)
    handle, temp_name = tempfile.mkstemp(prefix=".usability-", suffix=".tmp", dir=str(folder))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(results.to_json(), stream, ensure_ascii=False, indent=2, sort_keys=False)
            stream.write("\n")
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


# --- Summary -------------------------------------------------------------------------------


def _median_text(values: Sequence[int]) -> str:
    median = statistics.median(values)
    return str(int(median)) if float(median).is_integer() else "{:.1f}".format(median)


def summary_lines(results: ResultsFile) -> List[str]:
    """Plain counts and median minutes per task; no notes."""

    count = len(results.participants)
    lines = ["Participants saved: {}".format(count)]
    for index, task_id in enumerate(TASK_IDS):
        tasks = [p.tasks[index] for p in results.participants]
        if not tasks:
            continue
        counts = {outcome: sum(1 for t in tasks if t.outcome == outcome) for outcome in OUTCOMES}
        lines.append(
            "Task {} ({}): {} completed, {} needed help, {} gave up; median {} min".format(
                index + 1, task_id, counts["completed"], counts["needed_help"], counts["gave_up"],
                _median_text([t.minutes for t in tasks]),
            )
        )
    if count:
        shown = sum(1 for p in results.participants if p.tasks[TASK_IDS.index(LAND_TASK)].land_choice_shown)
        lines.append("The app asked to choose a land: {} of {} participants".format(shown, count))
    return lines
