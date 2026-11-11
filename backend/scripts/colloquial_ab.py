#!/usr/bin/env python3
"""List, decide, check, prepare, and run the colloquial A/B comparison.

Owner commands, run through ``./scripts/init.sh`` (steps in
``docs/owner-guide/colloquial-variants-review.md``)::

    ./scripts/init.sh --colloquial-review
    ./scripts/init.sh --colloquial-decide approve|reject "<name>" <number-or-id>...

``list`` prints the variants that wait for a decision, writes every variant with its state to
``build/colloquial-ab/variants.txt``, and ends with one ``Result:`` line. ``decide`` records a
named reviewer's decision and rewrites the file atomically; bad input records nothing. ``check``
is for developers and validators (explicit paths, exit 0/1, ids only).

``prepare`` asks the already-pinned loopback model for official terms and writes a cache of ids
and accepted terms only; ``run`` scores the approved variants, the approved golden parents, and
the approved traps through the in-process app three times, differing only in query expansion,
and writes ``build/colloquial-ab/reports/<version_id>/report.json``. Both are offline except for
``prepare``'s loopback model call, and neither writes under ``knowledge/``.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Iterator, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.dont_write_bytecode = True

from app import colloquial_ab as ab  # noqa: E402
from app import eval_metrics, golden_set, question_glossary, trap_set  # noqa: E402
from app.answer_eval import (  # noqa: E402
    VERSION as ANSWER_EVAL_VERSION,
    AnswerEvalError,
    load_case_document,
)
from app.retrieval import load_passage_set  # noqa: E402
from app.source_catalog import load_catalog  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"
DEFAULT_CATALOG = KNOWLEDGE / "source_catalog.json"
DEFAULT_PASSAGES = KNOWLEDGE / "passages.json"
DEFAULT_CASES = KNOWLEDGE / "pac_answer_eval.json"
DEFAULT_GOLDEN = KNOWLEDGE / "golden_set.json"
DEFAULT_TRAPS = KNOWLEDGE / "trap_set.json"
DEFAULT_VARIANTS = ROOT / "backend" / "config" / "colloquial_variants.json"
DEFAULT_ROOT = ROOT / "build" / "colloquial-ab"

USAGE_LINE = (
    "Result: nothing was recorded. Write approve or reject, your name in quotes, and at least "
    'one variant number, for example: ./scripts/init.sh --colloquial-decide approve "Diego" 1 2 3'
)
DAMAGED_LINE = (
    "Result: the colloquial variant list could not be read, and nothing was recorded. "
    "Send this line to the developer."
)
DAMAGED_LIST_LINE = (
    "Result: the colloquial variant list could not be read. Send this line to the developer."
)
STALE_FILE_LINE = (
    "Result: nothing was recorded. The colloquial variant list does not match the approved "
    "golden questions. Ask the developer to update it, then repeat."
)


def _unknown_line(refs: str) -> str:
    return (
        f"Result: nothing was recorded. These variant numbers are not in the list: {refs}. "
        "Run ./scripts/init.sh --colloquial-review and use the numbers shown there."
    )


def _entry_line(number: str) -> str:
    return (
        f"Result: nothing was recorded. Colloquial variant {number} cannot be approved as "
        "written. Reject it, or send this line to the developer."
    )


def _log_error(root: Path) -> None:
    ab.write_error_log(root, traceback.format_exc())


# Environment that would change how the app answers; cleared for the duration of the arms.
REMOVED_ENV = (
    "MANIJERO_GENERATION_PROVIDER",
    "MANIJERO_LOCAL_MODEL",
    "MANIJERO_GEMINI_MODEL",
    "MANIJERO_ANSWER_TRACE",
    "MANIJERO_RERANKER",
    "MANIJERO_RETRIEVAL_MODE",
    "MANIJERO_STRUCTURED_INDEX",
    "MANIJERO_STRUCTURED_INDEX_DIR",
    "MANIJERO_KNOWLEDGE_RELEASE_ROOT",
    question_glossary.SETTING_ENV,
)
ANSWER_CACHE_ENV = "MANIJERO_ANSWER_CACHE"


@contextlib.contextmanager
def _isolated_environment() -> Iterator[None]:
    """Extractive BM25 drafting with the cache off, then every key restored."""

    keys = REMOVED_ENV + (ANSWER_CACHE_ENV,)
    saved = {key: os.environ.get(key) for key in keys}
    try:
        for key in REMOVED_ENV:
            os.environ.pop(key, None)
        os.environ[ANSWER_CACHE_ENV] = "off"
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# --- Inputs -----------------------------------------------------------------------------


def _load_reviewed(args: argparse.Namespace) -> Tuple[Any, Any, List[dict], dict, dict]:
    catalog = load_catalog(args.catalog)
    passages = load_passage_set(args.passages)
    cases, coverage = load_case_document(args.cases, catalog, passages)
    golden = golden_set.load_golden(args.golden, catalog, passages, cases, coverage)
    return catalog, passages, cases, coverage, golden


def _run_inputs(
    args: argparse.Namespace,
) -> Tuple[Any, Any, List[dict], dict, dict, dict, dict]:
    """Every reviewed file plus the traps, loaded once for prepare or run."""

    catalog, passages, cases, coverage, golden = _load_reviewed(args)
    approved_golden = golden_set.approved_cases(golden)
    traps = trap_set.load_traps(
        args.traps,
        catalog,
        passages,
        cases + approved_golden,
        dict(coverage, areas=coverage["areas"] + golden["additional_areas"]),
        golden,
    )
    return catalog, passages, cases, coverage, golden, approved_golden, traps


def _glossary_record() -> Tuple[Any, str]:
    glossary, _reason = question_glossary.load_question_glossary(
        {question_glossary.SETTING_ENV: "on"}, question_glossary.DEFAULT_PATH
    )
    if glossary is None:
        raise ab.ColloquialAbort("invalid_inputs")
    return glossary, hashlib.sha256(question_glossary.DEFAULT_PATH.read_bytes()).hexdigest()


def _approved(document: Mapping[str, Any], golden: Any, cases: Any, digest: str, coverage: dict):
    try:
        return ab.approved_cases(
            document, golden, cases, digest, coverage.get("omissions", ())
        )
    except ab.VariantsError:
        raise ab.ColloquialAbort("invalid_inputs") from None


def _scored_cases(approved: Sequence[Mapping[str, Any]], approved_golden: Any, traps: Any):
    golden_types = {case["id"]: case.get("question_type") for case in approved_golden}
    tagged = [dict(case) for case in approved]
    tagged += [
        dict(case, case_set=ab.CASE_SET_GOLDEN, question_type=golden_types.get(case["id"]))
        for case in approved_golden
    ]
    tagged += [dict(case, case_set=ab.CASE_SET_TRAP) for case in trap_set.approved_cases(traps)]
    return tagged


def _pairs(document: Mapping[str, Any]) -> List[Tuple[str, str, str]]:
    return [
        (entry["id"], entry["colloquial"], entry["official"])
        for entry in document["entries"]
        if entry["review_state"] == "approved"
    ]


def _pinned_rewriter(record: Any):
    """The only model seam of ``prepare``: the pinned record over loopback ``/api/chat``."""

    from app.gemini_generation import GeminiDraftRequest
    from app.local_generation import OllamaTransport

    transport = OllamaTransport(record, response_format=ab.TERMS_JSON_SCHEMA)

    def send(question: str) -> str:
        return transport.send(
            GeminiDraftRequest(
                model=record.model,
                instruction=ab.TERMS_INSTRUCTION,
                instruction_version=ab.TERMS_INSTRUCTION_VERSION,
                payload_json=json.dumps({"question": question}, ensure_ascii=False),
                max_output_tokens=record.max_output_tokens,
                timeout_seconds=record.timeout_seconds,
            )
        )

    return send


def _pinned_model(args: argparse.Namespace) -> Any:
    from app.local_generation import (
        evaluate_local_model_record,
        load_local_model_record,
    )

    gate, record = evaluate_local_model_record(
        load_local_model_record(), as_of=args.as_of
    )
    if record is None or not gate.passed:
        raise ab.ColloquialAbort("model_unavailable")
    return record


def _cache_failures(
    document: Any, key: str, model: str, digest: str
) -> List[str]:
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "model",
        "digest",
        "cases",
        "counts",
        "cache_key",
    }:
        return ["wrong_schema"]
    if (
        document["schema_version"] != ab.REWRITES_VERSION
        or document["model"] != model
        or document["digest"] != digest
        or document["cache_key"] != key
        or not isinstance(document["cases"], list)
        or not isinstance(document["counts"], dict)
    ):
        return ["wrong_schema"]
    for entry in document["cases"]:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"id", "terms", "status"}
            or not isinstance(entry["id"], str)
            or not isinstance(entry["terms"], list)
            or any(not isinstance(term, str) for term in entry["terms"])
            or entry["status"] not in ab.MODEL_STATUSES
        ):
            return ["invalid_case"]
    return []


# --- Commands ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    try:
        passages = load_passage_set(args.passages)
        catalog = load_catalog(args.catalog)
        golden = golden_set.read_document(args.golden)
        document = ab.read_variants(args.variants)
        cases, coverage = load_case_document(args.cases, catalog, passages)
        del cases
        counts = ab.state_counts(document)
        args.build_dir.mkdir(parents=True, exist_ok=True)
        golden_set.write_atomically(
            args.build_dir / "variants.txt",
            ab.render_list(
                document,
                golden,
                catalog,
                passages,
                coverage["omissions"],
                only_waiting=False,
            ),
        )
        text = ab.render_list(
            document, golden, catalog, passages, coverage["omissions"], only_waiting=True
        )
    except Exception:  # noqa: BLE001
        _log_error(args.build_dir)
        print(DAMAGED_LIST_LINE)
        return 1
    if text:
        print(text)
    tail = f"({counts['approved']} approved, {counts['rejected']} rejected)"
    waiting = counts["draft"]
    if waiting:
        print(
            f"Result: {waiting} colloquial variants wait for your decision {tail}. "
            "The same list is in build/colloquial-ab/variants.txt."
        )
    else:
        print(f"Result: no colloquial variants wait for your decision {tail}.")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    words: List[str] = list(args.words)
    decision = words[0] if words else ""
    name = words[1] if len(words) > 1 else ""
    refs = words[2:]
    if decision not in ("approve", "reject") or not golden_set.valid_name(name) or not refs:
        print(USAGE_LINE)
        return 1
    try:
        catalog = load_catalog(args.catalog)
        passages = load_passage_set(args.passages)
        cases, coverage = load_case_document(args.cases, catalog, passages)
        golden = golden_set.read_document(args.golden)
        recorded, waiting = ab.decide(
            args.variants,
            decision,
            name,
            refs,
            date.today() if args.today is None else args.today,
            golden,
            cases,
            hashlib.sha256(args.golden.read_bytes()).hexdigest(),
            coverage["omissions"],
        )
    except ab.DecisionError as exc:
        print(
            USAGE_LINE
            if exc.kind == "usage"
            else _unknown_line(exc.detail)
            if exc.kind == "unknown"
            else STALE_FILE_LINE
            if exc.kind == "file"
            else _entry_line(exc.detail)
        )
        return 1
    except Exception:  # noqa: BLE001
        _log_error(args.build_dir)
        print(DAMAGED_LINE)
        return 1
    print(
        f"Result: recorded {decision} for {recorded} colloquial variants by {name}. "
        f"{waiting} still wait for your decision."
    )
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        catalog = load_catalog(args.catalog)
        passages = load_passage_set(args.passages)
        cases, coverage = load_case_document(args.cases, catalog, passages)
        golden = golden_set.load_golden(args.golden, catalog, passages, cases, coverage)
        document = ab.read_variant_document(args.variants)
    except Exception as exc:  # noqa: BLE001
        print(f"colloquial check: cannot read the inputs: {type(exc).__name__}")
        return 1
    failures = ab.check_variants(
        document,
        golden,
        cases,
        hashlib.sha256(args.golden.read_bytes()).hexdigest(),
        coverage["omissions"],
    )
    for line in failures:
        print(line)
    if failures:
        print(f"colloquial check: {len(failures)} failures")
        return 1
    counts = ab.state_counts(document)
    parents = {entry["parent_id"] for entry in document["variants"]}
    approved_parents = {
        item["id"] for item in golden["items"] if item["review_state"] == "approved"
    }
    print(
        "colloquial check: {} variants OK (approved={}, draft={}, rejected={}); "
        "{} approved golden parents, {} covered, {} orphans".format(
            len(document["variants"]),
            counts["approved"],
            counts["draft"],
            counts["rejected"],
            len(approved_parents),
            len(parents & approved_parents),
            len(approved_parents - parents),
        )
    )
    return 0


def cmd_prepare(args: argparse.Namespace, root: Path, rewriter: Optional[Any]) -> int:
    inputs = (args.catalog, args.passages, args.cases, args.golden, args.traps, args.variants)
    try:
        root = ab.check_output_root(root, inputs)
        catalog, passages, cases, coverage, golden, _approved_golden, _traps = _run_inputs(args)
        del catalog, passages
        document = ab.read_variants(args.variants)
        digest = hashlib.sha256(args.golden.read_bytes()).hexdigest()
        approved = _approved(document, golden, cases, digest, coverage)
        if not approved:
            raise ab.ColloquialAbort("no_approved_variants")
        glossary, glossary_digest = _glossary_record()
        record = _pinned_model(args)
        active_rewriter = rewriter if rewriter is not None else _pinned_rewriter(record)
        cache = ab.prepare_rewrites(
            approved, glossary, record=record, rewriter=active_rewriter
        )
        key = ab.rewrite_cache_key(
            approved,
            glossary_digest=glossary_digest,
            model=record.model,
            digest=record.digest,
        )
        document_out = dict(cache, cache_key=key)
        target = root / "rewrites" / (key + ".json")
        ab.write_document_atomically(document_out, target)
        counts = cache["counts"]
        print(
            "Result: prepared model rewrites for {} approved colloquial variants with {}: "
            "{} rewritten, {} empty, {} rejected, {} skipped. Cache: {}.".format(
                len(approved),
                record.model,
                counts[ab.MODEL_REWRITTEN],
                counts[ab.MODEL_EMPTY],
                counts[ab.MODEL_REJECTED],
                counts[ab.MODEL_SKIPPED_SCREENED],
                eval_metrics.display_path(target),
            )
        )
        return 0
    except ab.ColloquialAbort as error:
        print(ab.abort_line(error.code))
        return 2
    except Exception:  # noqa: BLE001 - the trace goes to a log file, never to the terminal
        _log_error(root)
        print(ab.abort_line("internal_error"))
        return 2


def _load_cache(
    root: Path, key: str, model: str, digest: str, expected_ids: Sequence[str]
) -> dict:
    """The cache for this exact key, or a fixed missing/stale abort."""

    directory = root / "rewrites"
    target = directory / (key + ".json")
    try:
        raw = target.read_bytes()
    except OSError:
        raise ab.ColloquialAbort(
            "rewrites_stale"
            if directory.is_dir() and any(directory.glob("*.json"))
            else "rewrites_missing"
        ) from None
    try:
        document = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ab.ColloquialAbort("rewrites_stale") from None
    if _cache_failures(document, key, model, digest):
        raise ab.ColloquialAbort("rewrites_stale")
    if [entry["id"] for entry in document["cases"]] != list(expected_ids):
        raise ab.ColloquialAbort("rewrites_stale")
    for status in ab.MODEL_STATUSES:
        if document["counts"].get(status) != sum(
            1 for entry in document["cases"] if entry["status"] == status
        ):
            raise ab.ColloquialAbort("rewrites_stale")
    return document


def cmd_run(args: argparse.Namespace, root: Path) -> int:
    inputs = (args.catalog, args.passages, args.cases, args.golden, args.traps, args.variants)
    try:
        if not eval_metrics.LABEL_PATTERN.match(args.label):
            raise ab.ColloquialAbort("invalid_inputs")
        root = ab.check_output_root(root, inputs)
        catalog, passages, cases, coverage, golden, approved_golden, traps = _run_inputs(args)
        document = ab.read_variants(args.variants)
        digest = hashlib.sha256(args.golden.read_bytes()).hexdigest()
        approved = _approved(document, golden, cases, digest, coverage)
        if not approved:
            raise ab.ColloquialAbort("no_approved_variants")
        glossary, glossary_digest = _glossary_record()
        record = _pinned_model(args)
        key = ab.rewrite_cache_key(
            approved,
            glossary_digest=glossary_digest,
            model=record.model,
            digest=record.digest,
        )
        cache = _load_cache(
            root,
            key,
            record.model,
            record.digest,
            [case["id"] for case in approved],
        )
        terms_by_id = {
            entry["id"]: list(entry["terms"])
            for entry in cache["cases"]
            if entry["terms"]
        }
        status_by_id = {entry["id"]: entry["status"] for entry in cache["cases"]}
        questions = {case["id"]: case["question"] for case in approved}
        terms_by_question = {
            questions[case_id]: terms
            for case_id, terms in terms_by_id.items()
            if case_id in questions
        }
        glossary_doc = json.loads(
            question_glossary.DEFAULT_PATH.read_text(encoding="utf-8")
        )
        pairs = _pairs(glossary_doc)
        scored = _scored_cases(approved, approved_golden, traps)
        with _isolated_environment():
            results = ab.run_arms(
                scored,
                catalog,
                passages,
                as_of=args.as_of,
                campaign=args.active_campaign,
                glossary=glossary,
                model_terms_by_question=terms_by_question,
                model_terms_by_id=terms_by_id,
                model_status_by_id=status_by_id,
                pairs=pairs,
            )
        baseline = results["no_rewriting"]
        baseline_hits, answered = ab.hit_at_5(baseline)
        trap_count = sum(1 for row in baseline if row["case_set"] == ab.CASE_SET_TRAP)
        arm_blocks: dict[str, dict[str, Any]] = {}
        for mode in ab.MODES:
            rows = results[mode]
            hits, _of = ab.hit_at_5(rows)
            changed = sum(
                1
                for case in approved
                if mode != "no_rewriting"
                and _expanded(mode, glossary, terms_by_question, case["question"])
                != case["question"]
            )
            regressions = ab.trap_regressions(baseline, rows)
            arm_blocks[mode] = {
                "hit_at_5": {
                    "hits": hits,
                    "of": answered,
                    "value": round(hits / answered, 4) if answered else None,
                },
                "changed_queries": changed,
                "traps": trap_count,
                "trap_regressions": len(regressions),
                "trap_regression_ids": sorted(regressions),
            }
        verdicts = {
            mode: ab.adoption(
                variant_counts=ab.state_counts(document),
                baseline_hits=baseline_hits,
                candidate_hits=arm_blocks[mode]["hit_at_5"]["hits"],
                changed_queries=arm_blocks[mode]["changed_queries"],
                regressions=arm_blocks[mode]["trap_regressions"],
            )
            for mode in ("glossary", "glossary_plus_model")
        }
        adoption_block = {
            "rule": "hit@5 strictly greater than no_rewriting and zero approved traps worse",
            "arms": verdicts,
            "information_only": {
                "glossary_plus_model_vs_glossary": {
                    "hit_at_5_delta": arm_blocks["glossary_plus_model"]["hit_at_5"]["hits"]
                    - arm_blocks["glossary"]["hit_at_5"]["hits"],
                    "trap_regressions_delta": arm_blocks["glossary_plus_model"][
                        "trap_regressions"
                    ]
                    - arm_blocks["glossary"]["trap_regressions"],
                    "changed_queries_delta": arm_blocks["glossary_plus_model"][
                        "changed_queries"
                    ]
                    - arm_blocks["glossary"]["changed_queries"],
                    "note": "information only; the rule is judged against no_rewriting",
                }
            },
            "defaults_changed": False,
        }
        version = ab.version_block(
            catalog=args.catalog,
            passages=args.passages,
            cases=args.cases,
            golden=args.golden,
            traps=args.traps,
            variants=args.variants,
            glossary=glossary_digest,
            model=record.model,
            model_digest=record.digest,
            as_of=args.as_of.isoformat(),
            active_campaign=args.active_campaign,
            label=args.label,
            schema_versions={
                "answer_eval": ANSWER_EVAL_VERSION,
                "golden_set": golden_set.VERSION,
                "trap_set": trap_set.VERSION,
                "report": ab.SCHEMA_VERSION,
            },
        )
        report_id = ab.version_id(version)
        rows = [row for mode in ab.MODES for row in results[mode]]
        rewrites = cache["counts"]
        report = ab.build_report(
            version=version,
            report_id=report_id,
            variants=ab.state_counts(document),
            arms=arm_blocks,
            adoption_block=adoption_block,
            rewrites=rewrites,
            rows=rows,
        )
        report_path = root / "reports" / report_id / "report.json"
        ab.write_document_atomically(report, report_path)
        print(ab.result_line(report, report_path))
        return 0
    except ab.ColloquialAbort as error:
        print(ab.abort_line(error.code))
        return 2
    except AnswerEvalError:
        print(ab.abort_line("ask_failed"))
        return 2
    except Exception:  # noqa: BLE001 - the trace goes to a log file, never to the terminal
        _log_error(root)
        print(ab.abort_line("internal_error"))
        return 2


def _expanded(
    mode: str,
    glossary: Any,
    terms_by_question: Mapping[str, Sequence[str]],
    question: str,
) -> str:
    expansion = (
        ab.GlossaryPlusModel(glossary, terms_by_question)
        if mode == "glossary_plus_model"
        else glossary
    )
    return expansion.expand(question)


# --- Parser -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "decide", "check", "prepare", "run"):
        command = sub.add_parser(name)
        command.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
        command.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
        command.add_argument("--passages", type=Path, default=DEFAULT_PASSAGES)
        command.add_argument("--cases", type=Path, default=DEFAULT_CASES)
        command.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
        command.add_argument("--traps", type=Path, default=DEFAULT_TRAPS)
        if name in ("list", "decide"):
            command.add_argument("--build-dir", type=Path, default=DEFAULT_ROOT)
        if name == "decide":
            command.add_argument("--today", type=date.fromisoformat, default=None)
            command.add_argument("words", nargs="*")
        if name in ("prepare", "run"):
            command.add_argument("--reports-root", type=Path, default=DEFAULT_ROOT)
            command.add_argument("--active-campaign", default="2026")
            command.add_argument("--as-of", type=date.fromisoformat, required=True)
            command.add_argument("--label", default="repository")
    return parser


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    reports_root: Optional[Path] = None,
    rewriter: Optional[Any] = None,
    today: Optional[date] = None,
) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "command", None) == "decide":
        if today is not None and args.today is None:
            args.today = today
    root = Path(reports_root) if reports_root is not None else getattr(
        args, "reports_root", DEFAULT_ROOT
    )
    if args.command == "list":
        return cmd_list(args)
    if args.command == "decide":
        return cmd_decide(args)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "prepare":
        return cmd_prepare(args, root, rewriter)
    return cmd_run(args, root)


if __name__ == "__main__":
    raise SystemExit(main())
