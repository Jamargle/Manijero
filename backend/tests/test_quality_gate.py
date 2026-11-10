"""Pure tests for the reviewed-baseline quality gate.

Every baseline here is synthetic. The tests cover the review and schema guards, the
staleness rules, the zero-tolerance comparison in its fixed order, the single plain
lines, and the only writer (``record_baseline``). No app, network, or real file is used.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app import quality_gate as qg

DIGEST = "a" * 64


def _metrics() -> dict[str, Any]:
    return {
        "fixtures_retrieval": {
            "questions": 7,
            "hits_at_1": 6,
            "hits_at_3": 6,
            "hits_at_5": 6,
            "mrr": 0.8571,
        },
        "fixtures_abstention": {"questions": 10, "correct": 10},
        "reviewed_retrieval": {
            "questions": 12,
            "hits_at_1": 9,
            "hits_at_3": 11,
            "hits_at_5": 11,
            "mrr": 0.8333,
        },
        "reviewed_abstention": {"expected": 5, "correct": 5},
    }


def _baseline_inputs() -> dict[str, Any]:
    return {
        "retrieval_fixture": {
            "catalog": DIGEST,
            "passages": DIGEST,
            "questions": DIGEST,
        },
        "abstention_fixture": {
            "catalog": DIGEST,
            "passages": DIGEST,
            "questions": DIGEST,
        },
        "reviewed_sample": {"cases": DIGEST},
    }


def _review() -> dict[str, str]:
    return {
        "reviewed_by": "Jose",
        "reviewed_on": "2026-11-10",
        "reason": "initial measured fixture baseline approved",
    }


def _baseline(**overrides: Any) -> dict[str, Any]:
    document = qg.build_baseline(
        review=_review(), inputs=_baseline_inputs(), metrics=_metrics()
    )
    document.update(copy.deepcopy(overrides))
    return document


def _write(path: Path, document: Any) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# --- review and schema -------------------------------------------------------------------


def test_baseline_requires_complete_review(tmp_path: Path) -> None:
    without_review = _baseline()
    without_review.pop("review")
    variants = [
        without_review,
        _baseline(review={}),
        _baseline(review={k: v for k, v in _review().items() if k != "reason"}),
        _baseline(review={**_review(), "reviewed_by": "  "}),
        _baseline(review={**_review(), "reason": ""}),
        _baseline(review={**_review(), "reviewed_on": "2026-1-1"}),
        _baseline(review={**_review(), "reviewed_on": "not-a-date"}),
    ]
    for variant in variants:
        document = qg.load_baseline(_write(tmp_path / "baseline.json", variant))
        assert qg.review_problem(document) == "baseline_unreviewed"
    complete = qg.load_baseline(_write(tmp_path / "ok.json", _baseline()))
    assert qg.review_problem(complete) is None


def test_baseline_rejects_unknown_keys_and_bad_types(tmp_path: Path) -> None:
    variants = [
        _baseline(extra=True),
        _baseline(schema_version="eval-quality-gate-baseline-v0"),
        _baseline(review={**_review(), "role": "owner"}),
        _baseline(settings={**qg.SETTINGS, "extra": "x"}),
        _baseline(metrics={**_metrics(), "extra": {}}),
    ]
    bad_mrr = _metrics()
    bad_mrr["reviewed_retrieval"]["mrr"] = "0.8333"
    variants.append(_baseline(metrics=bad_mrr))
    bad_digest = _baseline_inputs()
    bad_digest["retrieval_fixture"]["catalog"] = "short"
    variants.append(_baseline(inputs=bad_digest))
    for variant in variants:
        with pytest.raises(qg.GateAbort) as caught:
            qg.load_baseline(_write(tmp_path / "baseline.json", variant))
        assert caught.value.code == "baseline_invalid"


def test_baseline_rejects_non_finite_mrr(tmp_path: Path) -> None:
    for non_finite in (float("nan"), float("inf"), float("-inf")):
        metrics = _metrics()
        metrics["reviewed_retrieval"]["mrr"] = non_finite
        with pytest.raises(qg.GateAbort) as caught:
            qg.load_baseline(
                _write(tmp_path / "baseline.json", _baseline(metrics=metrics))
            )
        assert caught.value.code == "baseline_invalid"


def test_stale_on_digest_settings_as_of_or_campaign() -> None:
    assert qg.settings_match(qg.SETTINGS)
    assert not qg.settings_match({**qg.SETTINGS, "as_of": "2026-10-14"})
    assert not qg.settings_match({**qg.SETTINGS, "active_campaign": "2025"})
    current = _baseline_inputs()
    assert qg.inputs_match(current, _baseline_inputs())
    changed = copy.deepcopy(current)
    changed["reviewed_sample"]["cases"] = "b" * 64
    assert not qg.inputs_match(current, changed)


# --- comparison --------------------------------------------------------------------------


def test_each_hit_at_k_drop_blocks() -> None:
    measured = _metrics()
    for key, metric in (
        ("hits_at_1", "hit@1"),
        ("hits_at_3", "hit@3"),
        ("hits_at_5", "hit@5"),
    ):
        baseline = _metrics()
        baseline["reviewed_retrieval"][key] += 1
        drops = qg.compare(baseline, measured)
        assert [(drop["group"], drop["metric"]) for drop in drops] == [
            ("reviewed sample", metric)
        ]
        assert drops[0]["new"].endswith("/12")


def test_abstention_drop_blocks() -> None:
    measured = _metrics()
    measured["fixtures_abstention"]["correct"] = 9
    measured["reviewed_abstention"]["correct"] = 4
    drops = qg.compare(_metrics(), measured)
    assert [(drop["group"], drop["metric"], drop["old"], drop["new"]) for drop in drops] == [
        ("fixtures", "abstention", "10/10", "9/10"),
        ("reviewed sample", "abstention", "5/5", "4/5"),
    ]


def test_any_mrr_fall_blocks() -> None:
    baseline = _metrics()
    baseline["fixtures_retrieval"]["mrr"] = 0.8572
    drops = qg.compare(baseline, _metrics())
    assert drops == [
        {
            "group": "fixtures",
            "metric": "MRR",
            "old": "0.8572",
            "new": "0.8571",
        }
    ]
    baseline = _metrics()
    baseline["reviewed_retrieval"]["mrr"] = 0.8611
    measured = _metrics()
    measured["reviewed_retrieval"]["mrr"] = 0.8610
    drops = qg.compare(baseline, measured)
    assert drops == [
        {
            "group": "reviewed sample",
            "metric": "MRR",
            "old": "0.8611",
            "new": "0.8610",
        }
    ]


def test_improvement_passes_and_lists_no_drop() -> None:
    measured = _metrics()
    measured["fixtures_retrieval"]["hits_at_1"] += 1
    measured["reviewed_retrieval"]["mrr"] = 0.9
    measured["fixtures_abstention"]["correct"] = 10
    assert qg.compare(_metrics(), measured) == []


def test_drops_are_named_in_fixed_order() -> None:
    baseline = _metrics()
    baseline["fixtures_retrieval"].update(
        {"hits_at_1": 7, "hits_at_3": 7, "hits_at_5": 7, "mrr": 0.9571}
    )
    baseline["reviewed_retrieval"].update(
        {"hits_at_1": 10, "hits_at_3": 12, "hits_at_5": 12, "mrr": 0.9333}
    )
    measured = _metrics()
    measured["fixtures_abstention"]["correct"] = 9
    measured["reviewed_abstention"]["correct"] = 4
    drops = qg.compare(baseline, measured)
    assert [(drop["group"], drop["metric"]) for drop in drops] == [
        ("fixtures", "hit@1"),
        ("fixtures", "hit@3"),
        ("fixtures", "hit@5"),
        ("fixtures", "abstention"),
        ("fixtures", "MRR"),
        ("reviewed sample", "hit@1"),
        ("reviewed sample", "hit@3"),
        ("reviewed sample", "hit@5"),
        ("reviewed sample", "abstention"),
        ("reviewed sample", "MRR"),
    ]


def test_result_and_not_enforced_lines_are_single_and_text_free() -> None:
    passed = qg.passed_line(_metrics(), _review())
    baseline = _metrics()
    baseline["reviewed_retrieval"]["hits_at_1"] = 10
    failed = qg.failed_line(qg.compare(baseline, _metrics()))
    for line in (passed, failed):
        assert line.startswith("Result: quality gate ")
        assert "\n" not in line
        assert "question" not in line.lower()
        assert "passage" not in line.lower()
        assert "backend/" not in line
    assert "6/7 hit@1" in passed
    assert "10/12 to 9/12" in failed
    for code in (
        "baseline_unreviewed",
        "baseline_invalid",
        "baseline_stale",
        "ask_failed",
        "internal_error",
    ):
        line = qg.not_enforced_line(code)
        assert line.startswith("Result: quality gate not enforced: ")
        assert line.count("\n") == 0


def test_zero_question_group_renders_na_and_enforces_nothing() -> None:
    empty = _metrics()
    empty["fixtures_retrieval"] = {
        "questions": 0,
        "hits_at_1": 0,
        "hits_at_3": 0,
        "hits_at_5": 0,
        "mrr": 0.0,
    }
    empty["fixtures_abstention"] = {"questions": 0, "correct": 0}
    measured = _metrics()
    measured["fixtures_retrieval"] = empty["fixtures_retrieval"]
    measured["fixtures_abstention"] = empty["fixtures_abstention"]
    assert qg.compare(empty, measured) == []
    line = qg.passed_line(measured, _review())
    assert "fixtures n/a hit@1, n/a hit@3, n/a hit@5, MRR n/a" in line
    assert "fixtures abstention n/a" in line


# --- recording ---------------------------------------------------------------------------


def test_record_refuses_without_reviewer_or_reason() -> None:
    for reviewer, reason in (
        ("", "reason"),
        ("   ", "reason"),
        ("Jose", ""),
        ("Jose", "  "),
    ):
        with pytest.raises(qg.RecordRefusal):
            qg.review_block(reviewer, reason, "2026-11-10")
    with pytest.raises(qg.RecordRefusal):
        qg.review_block("Jose", "reason", "10-11-2026")


def test_record_refuses_regression_without_accept_flag(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    earlier = _metrics()
    earlier["reviewed_retrieval"]["hits_at_1"] = 10
    qg.write_baseline_atomically(
        qg.build_baseline(
            review=_review(), inputs=_baseline_inputs(), metrics=earlier
        ),
        path,
    )

    with pytest.raises(qg.RecordRefusal) as caught:
        qg.record_baseline(
            path=path,
            metrics=_metrics(),
            review=_review(),
            inputs=_baseline_inputs(),
        )
    assert "accept-regression" in str(caught.value)

    changes = qg.record_baseline(
        path=path,
        metrics=_metrics(),
        review=_review(),
        inputs=_baseline_inputs(),
        accept_regression=True,
    )
    assert changes == ["reviewed sample hit@1: 10/12 -> 9/12"]
    assert json.loads(path.read_text(encoding="utf-8"))["metrics"] == _metrics()


def test_record_writes_canonical_sorted_baseline(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "quality_gate_baseline.json"
    changes = qg.record_baseline(
        path=path, metrics=_metrics(), review=_review(), inputs=_baseline_inputs()
    )
    assert changes == []
    text = path.read_text(encoding="utf-8")
    document = json.loads(text)
    assert text == qg.canonical_json(document)
    assert text.endswith("\n")
    assert text.index('"inputs"') < text.index('"metrics"') < text.index('"review"')
    assert '\n  "review": {' in text
    assert document["settings"] == qg.SETTINGS
    assert document["review"] == _review()
