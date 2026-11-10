"""Deterministic, report-only metrics over the reviewed, golden, and trap sets.

One report per version: retrieval (hit@k, MRR) from what ``/ask`` actually ranked,
abstention and clarification correctness, numeric/date accuracy, and faithfulness only when
the pinned local judge ran. Every report is keyed by a ``version_id`` that hashes its input
files and settings, so the same inputs and fakes produce byte-identical files.

Nothing here is a gate: no metric value changes an exit code, and no threshold is read. The
command writes only under ``build/eval-reports/`` and never touches ``knowledge/``.

Standard library plus the existing trap-set helpers; the command adds the answer-eval,
golden-set, and grounding-judge modules. Only :func:`metric_block` and :func:`summarize`
define metrics; everything else is I/O, versioning, or presentation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app import trap_set

SCHEMA_VERSION = "eval-metrics-report-v1"
K = 5
RETRIEVAL_MODE = "bm25"
CASE_SETS = ("reviewed", "golden", "trap")
NOT_JUDGED_SKIPPED = "skipped"
NOT_JUDGED_NO_SENTENCES = "no_judged_sentences"
NOT_JUDGED_UNREADABLE = "judge_report_unreadable"
# Kept locally so no app module imports the judge tooling; the unit tests assert these
# match app.grounding_judge.
JUDGED_VERDICTS = ("supported", "not_supported", "unclear")
JUDGE_VERDICTS = JUDGED_VERDICTS + (
    "uncited",
    "citation_invalid",
    "unjudged_invalid_output",
    "unjudged_error",
)
JUDGE_REVIEW = "unchecked_against_human_review"
DRAFTS_FROM = "local_generator"
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,40}$")
JUDGE_ABORT = re.compile(r"did not run \(([a-z_]+)\)")
ASCII_DIGIT = re.compile(r"[0-9]")

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"

# Row keys: ids, set, type/category, statuses, ranks, retrieved ids, match flags, fact counts.
ROW_KEYS = (
    "id",
    "case_set",
    "question_type",
    "category",
    "expected_status",
    "actual_status",
    "expected_state_match",
    "expected_passages",
    "first_expected_rank",
    "retrieved_passage_ids",
    "abstention_reason_match",
    "must_not_say_hits",
    "numeric_facts",
    "numeric_correct",
    "clarification_ids_match",
)

FAILURES: Mapping[str, str] = {
    "invalid_inputs": "the knowledge files or the case lists could not be read; a developer must check them.",
    "unsafe_report_path": "the reports folder is not allowed; it must be outside knowledge/ and must not overwrite an input.",
    "ask_failed": "the in-process /ask route did not return a valid answer; a developer must check the backend.",
    "internal_error": "something unexpected stopped the run; a developer can read build/eval-reports/last-error.log.",
}

LIMITS = (
    "Retrieval and clarification metrics come from the app's own /ask response inspection.",
    "The golden and reviewed items are owner-reviewed sets; this report makes no claim about the law.",
    "Faithfulness covers local-generator drafts only, and the judge's scores are unchecked against human review.",
    "Report only: no pass or fail threshold, no CI gate, and no metric-dependent exit code.",
)


class MetricsAbort(Exception):
    """A fixed failure that ends the run before any report is written."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# --- row helpers (no metric definitions) -------------------------------------------------


def first_expected_rank(
    inspection: Any, expected: Sequence[str]
) -> Optional[int]:
    """Smallest rank of an expected passage in the top-k inspection, else ``None``."""

    if not expected or not isinstance(inspection, Mapping):
        return None
    retrieval = inspection.get("retrieval")
    if not isinstance(retrieval, Mapping):
        return None
    wanted = set(expected)
    ranks = [
        item["rank"]
        for item in retrieval.get("passages") or ()
        if isinstance(item, Mapping)
        and item.get("passage_id") in wanted
        and isinstance(item.get("rank"), int)
    ]
    return min(ranks) if ranks else None


def numeric_facts(case: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[int, int]:
    """``(facts, correct)``: digit facts of an expected answer found verbatim in the answer."""

    if case.get("expected_status") != "answered":
        return 0, 0
    answer = actual.get("answer") or ""
    facts = [
        fact
        for fact in case.get("critical_facts") or ()
        if isinstance(fact, str) and ASCII_DIGIT.search(fact)
    ]
    return len(facts), sum(1 for fact in facts if fact in answer)


def case_row(
    case: Mapping[str, Any],
    actual: Mapping[str, Any],
    case_set: str,
    question_type: Optional[str] = None,
) -> Dict[str, Any]:
    """One per-case row. It never holds question, answer, passage, or land text."""

    inspection = actual.get("inspection")
    expected_passages = list(case.get("expected_passage_ids") or ())
    retrieved: List[str] = []
    if isinstance(inspection, Mapping):
        retrieval = inspection.get("retrieval")
        if isinstance(retrieval, Mapping):
            retrieved = [
                item["passage_id"]
                for item in retrieval.get("passages") or ()
                if isinstance(item, Mapping) and isinstance(item.get("passage_id"), str)
            ]
    trap = trap_set.row_extra(dict(case), dict(actual))
    facts, correct = numeric_facts(case, actual)
    lands = {land.get("id") for land in (case.get("land_context") or {}).get("lands", [])}
    choices = actual.get("land_ids_to_choose") or ()
    row: Dict[str, Any] = {
        "id": case["id"],
        "case_set": case_set,
        "expected_status": case["expected_status"],
        "actual_status": actual.get("status"),
        "expected_state_match": actual.get("status") == case["expected_status"],
        "expected_passages": len(expected_passages),
        "first_expected_rank": first_expected_rank(inspection, expected_passages),
        "retrieved_passage_ids": retrieved,
        "abstention_reason_match": trap.get("abstention_reason_match"),
        "must_not_say_hits": len(trap.get("must_not_say_found") or ()),
        "numeric_facts": facts,
        "numeric_correct": correct,
        "clarification_ids_match": set(choices) <= lands,
    }
    if question_type is not None:
        row["question_type"] = question_type
    if "category" in case:
        row["category"] = case["category"]
    return row


def canonical_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Only the reviewed row keys, so an evaluator row cannot leak extra fields."""

    return {key: row[key] for key in ROW_KEYS if key in row}


# --- metrics -----------------------------------------------------------------------------


def metric_block(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Hit@1/3/5, MRR, and counts over rows that expect at least one passage."""

    subset = [row for row in rows if row.get("expected_passages", 0) > 0]
    total = len(subset)
    ranks = [row.get("first_expected_rank") for row in subset]
    hits_1 = sum(1 for rank in ranks if rank is not None and rank <= 1)
    hits_3 = sum(1 for rank in ranks if rank is not None and rank <= 3)
    hits_at_5 = [rank for rank in ranks if rank is not None and rank <= 5]
    block: Dict[str, Any] = {
        "questions": len(subset),
        "hits_at_1": sum(1 for rank in ranks if rank is not None and rank <= 1),
        "hits_at_3": sum(1 for rank in ranks if rank is not None and rank <= 3),
        "hits_at_5": len(hits_at_5),
    }
    if total == 0:
        block.update(
            {"hit_at_1": None, "hit_at_3": None, "hit_at_5": None, "mrr": None}
        )
        return block
    reciprocal = sum(0.0 if rank is None else 1.0 / rank for rank in ranks)
    block.update(
        {
            "hit_at_1": round(hits_1 / total, 4),
            "hit_at_3": round(hits_3 / total, 4),
            "hit_at_5": round(len(hits_at_5) / total, 4),
            "mrr": round(reciprocal / total, 4),
        }
    )
    return block


def summarize(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Every metric block overall, by case set, by golden type, and by trap category."""

    def abstention(local: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        expected = [row for row in local if row.get("expected_status") == "abstained"]
        correct = [
            row
            for row in expected
            if row.get("actual_status") == "abstained"
            and (row.get("category") is None or row.get("abstention_reason_match") is True)
        ]
        return {
            "expected": len(expected),
            "correct": len(correct),
            "status_matched": sum(
                1 for row in expected if row.get("actual_status") == "abstained"
            ),
            "wrongly_answered": sum(
                1 for row in expected if row.get("actual_status") == "answered"
            ),
            "over_abstained": sum(
                1
                for row in local
                if row.get("expected_status") == "answered"
                and row.get("actual_status") == "abstained"
            ),
            "share": round(len(correct) / len(expected), 4) if expected else None,
        }

    def clarification(local: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        expected = [
            row for row in local if row.get("expected_status") == "needs_land_clarification"
        ]
        return {
            "expected": len(expected),
            "status_matched": sum(
                1
                for row in expected
                if row.get("actual_status") == "needs_land_clarification"
            ),
            "ids_matched": sum(
                1
                for row in expected
                if row.get("actual_status") == "needs_land_clarification"
                and row.get("clarification_ids_match") is True
            ),
        }

    def numeric(local: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        answered = [
            row for row in local if row.get("expected_status") == "answered"
        ]
        facts = sum(row.get("numeric_facts", 0) for row in answered)
        correct = sum(row.get("numeric_correct", 0) for row in answered)
        return {
            "facts": facts,
            "correct": correct,
            "share": round(correct / facts, 4) if facts else None,
            "must_not_say_hits": sum(row.get("must_not_say_hits", 0) for row in local),
        }

    def breakdown(metric: Any) -> Dict[str, Any]:
        by_set = {
            name: metric([row for row in rows if row.get("case_set") == name])
            for name in CASE_SETS
        }
        # Golden types come from the rows: this module must not import the golden-set
        # review tooling, and the real golden doc uses every type today.
        types = sorted(
            {
                row["question_type"]
                for row in rows
                if isinstance(row.get("question_type"), str)
            }
        )
        by_type = {
            name: metric([row for row in rows if row.get("question_type") == name])
            for name in types
        }
        by_category = {
            name: metric([row for row in rows if row.get("category") == name])
            for name in trap_set.CATEGORIES
        }
        return {
            "overall": metric(rows),
            "by_case_set": by_set,
            "by_golden_question_type": by_type,
            "by_trap_category": by_category,
        }

    return {
        "retrieval": breakdown(metric_block),
        "abstention": breakdown(abstention),
        "clarification": breakdown(clarification),
        "numeric": breakdown(numeric),
    }


# --- version -----------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def version_block(
    *,
    catalog: Path,
    passages: Path,
    cases: Path,
    golden: Path,
    traps: Path,
    glossary: str,
    as_of: str,
    active_campaign: str,
    label: str,
    schema_versions: Mapping[str, str],
) -> Dict[str, Any]:
    """The exact inputs and settings a report is keyed by."""

    return {
        "as_of": as_of,
        "active_campaign": active_campaign,
        "label": label,
        "retrieval_mode": RETRIEVAL_MODE,
        "k": K,
        "catalog_sha256": _sha256(catalog),
        "passages_sha256": _sha256(passages),
        "cases_sha256": _sha256(cases),
        "golden_sha256": _sha256(golden),
        "trap_sha256": _sha256(traps),
        "glossary": glossary,
        "schema_versions": dict(schema_versions),
    }


def version_id(version: Mapping[str, Any]) -> str:
    """First 16 hex characters of the SHA-256 of the canonical version JSON."""

    digest = hashlib.sha256(canonical_json(version).encode("utf-8")).hexdigest()
    return digest[:16]


def display_path(path: Path) -> str:
    """A stable path string: relative to the repository when possible, never absolute."""

    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.name


# --- faithfulness ------------------------------------------------------------------------


def _not_judged(reason: str) -> Dict[str, Any]:
    return {"status": "not_judged", "reason": reason}


def faithfulness_from_judge(
    exit_code: Optional[int], captured_stdout: str, report_path: Optional[Path]
) -> Dict[str, Any]:
    """Map the in-process judge runner to ``judged`` or ``not_judged`` with a reason.

    ``exit_code`` is ``None`` when ``--no-judge`` skipped the runner. A run that judged no
    sentence never reports a zero share; it reports ``no_judged_sentences`` instead.
    """

    if exit_code is None:
        return _not_judged(NOT_JUDGED_SKIPPED)
    if exit_code != 0:
        match = JUDGE_ABORT.search(captured_stdout or "")
        return _not_judged(match.group(1) if match is not None else "internal_error")
    if report_path is None:
        return _not_judged(NOT_JUDGED_UNREADABLE)
    try:
        document = json.loads(Path(report_path).read_text(encoding="utf-8"))
        summary = document["summary"]
        overall = summary["overall"]
        verdicts = overall["verdicts"]
        judged = sum(
            int(verdicts.get(verdict, 0)) for verdict in JUDGED_VERDICTS
        )
        if judged == 0:
            return _not_judged(NOT_JUDGED_NO_SENTENCES)
        blocks = {
            name: summary["by_case_set"][name] for name in ("reviewed", "golden")
        }
        return {
            "status": "judged",
            "supported_share": overall["supported_share"],
            "verdicts": {
                verdict: int(verdicts.get(verdict, 0))
                for verdict in JUDGE_VERDICTS
            },
            "by_case_set": {
                name: {
                    "sentences": int(block["sentences"]),
                    "verdicts": {
                        verdict: int(block["verdicts"].get(verdict, 0))
                        for verdict in JUDGE_VERDICTS
                    },
                    "supported_share": block["supported_share"],
                }
                for name, block in blocks.items()
            },
            "judge": {
                "model": document["judge"]["model"],
                "digest": document["judge"]["digest"],
            },
            "generator": {
                "model": document["generator"]["model"],
                "digest": document["generator"]["digest"],
            },
            "drafts_from": DRAFTS_FROM,
            "judge_review": JUDGE_REVIEW,
            "report": display_path(Path(report_path)),
        }
    except (
        AttributeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ):  # one fixed reason, never a path or parser message
        return _not_judged(NOT_JUDGED_UNREADABLE)


# --- report ------------------------------------------------------------------------------


def build_report(
    *,
    version: Mapping[str, Any],
    report_id: str,
    rows: Sequence[Mapping[str, Any]],
    faithfulness: Mapping[str, Any],
) -> Dict[str, Any]:
    counts = {name: 0 for name in CASE_SETS}
    for row in rows:
        counts[row["case_set"]] += 1
    counts["total"] = len(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "version": dict(version),
        "version_id": report_id,
        "case_counts": counts,
        "metrics": summarize(rows),
        "faithfulness": dict(faithfulness),
        "cases": [canonical_row(row) for row in rows],
        "limits": list(LIMITS),
        "report_only": True,
    }


def _render(value: Any) -> str:
    return "n/a" if value is None else json.dumps(value)


def result_line(report: Mapping[str, Any], report_path: Path) -> str:
    counts = report["case_counts"]
    metrics = report["metrics"]
    retrieval = metrics["retrieval"]["overall"]
    abstention = metrics["abstention"]["overall"]
    numeric = metrics["numeric"]["overall"]
    faithfulness = report["faithfulness"]
    if faithfulness["status"] == "judged":
        judged_text = (
            f"{_render(faithfulness['supported_share'])} supported "
            "(unchecked against human review)"
        )
    else:
        judged_text = f"not judged ({faithfulness['reason']})"
    return (
        "Result: evaluated {total} questions ({reviewed} reviewed, {golden} golden, "
        "{trap} trap) for version {report_id}: hit@1 {hit1}, hit@3 {hit3}, hit@5 {hit5}, "
        "MRR {mrr} over {questions} questions with an expected passage; abstention correct "
        "{correct} of {expected}; numbers and dates correct {numeric_correct} of "
        "{numeric_facts}; faithfulness: {faithfulness}. Report only, no gate. "
        "Report: {path}.".format(
            total=counts["total"],
            reviewed=counts["reviewed"],
            golden=counts["golden"],
            trap=counts["trap"],
            report_id=report["version_id"],
            hit1=_render(retrieval["hit_at_1"]),
            hit3=_render(retrieval["hit_at_3"]),
            hit5=_render(retrieval["hit_at_5"]),
            mrr=_render(retrieval["mrr"]),
            questions=retrieval["questions"],
            correct=abstention["correct"],
            expected=abstention["expected"],
            numeric_correct=numeric["correct"],
            numeric_facts=numeric["facts"],
            faithfulness=judged_text,
            path=display_path(Path(report_path)),
        )
    )


def abort_line(code: str) -> str:
    text = FAILURES.get(code, FAILURES["internal_error"])
    return f"Result: the metrics report did not run ({code}): {text} Nothing was written."


# --- writing ------------------------------------------------------------------------------


def check_reports_root(root: Path, inputs: Sequence[Path]) -> Path:
    """Refuse a reports root inside ``knowledge/`` or on an input file."""

    target = Path(root).resolve()
    knowledge = KNOWLEDGE_ROOT.resolve()
    try:
        target.relative_to(knowledge)
    except ValueError:
        pass
    else:
        raise MetricsAbort("unsafe_report_path")
    for path in inputs:
        if target == Path(path).resolve():
            raise MetricsAbort("unsafe_report_path")
    return target


def canonical_json(document: Mapping[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_report_atomically(document: Mapping[str, Any], target: Path) -> None:
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(canonical_json(document), encoding="utf-8")
    os.replace(temporary, target)


def write_error_log(root: Path, text: str) -> None:
    try:
        Path(root).mkdir(parents=True, exist_ok=True)
        (Path(root) / "last-error.log").write_text(text, encoding="utf-8")
    except OSError:
        pass
