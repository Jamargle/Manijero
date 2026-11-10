"""Pure-helpers tests for the report-only metrics command (synthetic rows, no app)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app import eval_metrics, grounding_judge, trap_set


# --- synthetic builders ------------------------------------------------------------------


def _case(
    ident: str = "case-1",
    *,
    expected_status: str = "answered",
    passages: tuple[str, ...] = ("p-1",),
    facts: tuple[str, ...] = (),
    category: str | None = None,
    question: str = "¿Cuándo se presenta la PAC?",
    municipality: str = "Écija",
) -> dict[str, Any]:
    case: dict[str, Any] = {
        "id": ident,
        "question": question,
        "land_context": {
            "mode": "selected",
            "lands": [{"id": "land-1", "municipality": municipality}],
        },
        "expected_status": expected_status,
        "expected_passage_ids": list(passages),
        "critical_facts": list(facts),
    }
    if category is not None:
        case["category"] = category
        case["acceptable_abstention_reasons"] = ["no_evidence"]
    return case


def _actual(
    *,
    status: str = "answered",
    answer: str = "",
    ranks: tuple[tuple[int, str], ...] = (),
    no_retrieval: bool = False,
    choices: tuple[str, ...] = (),
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "answer": answer,
        "land_ids_to_choose": list(choices),
    }
    if no_retrieval:
        payload["inspection"] = {"retrieval": None}
    elif ranks:
        payload["inspection"] = {
            "retrieval": {
                "passages": [
                    {"rank": rank, "passage_id": passage_id} for rank, passage_id in ranks
                ]
            }
        }
    return payload


def _row(case: dict[str, Any], actual: dict[str, Any], case_set: str = "golden", **kwargs: Any) -> dict[str, Any]:
    return eval_metrics.case_row(case, actual, case_set, kwargs.get("question_type"))


# --- retrieval ---------------------------------------------------------------------------


def test_hit_at_k_and_mrr_from_ranks_1_2_4_none() -> None:
    rows = [
        _row(_case("a", passages=("p-1",)), _actual(ranks=((1, "p-1"), (2, "p-2")))),
        _row(_case("b", passages=("p-2",)), _actual(ranks=((1, "p-9"), (2, "p-2")))),
        _row(_case("c", passages=("p-1",)), _actual(ranks=((4, "p-1"),))),
        _row(_case("d", passages=("p-1",)), _actual(ranks=((1, "p-9"), (2, "p-8")))),
    ]

    block = eval_metrics.summarize(rows)["retrieval"]["overall"]

    assert [row["first_expected_rank"] for row in rows] == [1, 2, 4, None]
    assert block["questions"] == 4
    assert block["hit_at_1"] == 0.25
    assert block["hit_at_3"] == 0.5
    assert block["hit_at_5"] == 0.75
    assert block["mrr"] == 0.4375
    assert (block["hits_at_1"], block["hits_at_3"], block["hits_at_5"]) == (1, 2, 3)


def test_metrics_null_when_no_expected_passage_cases() -> None:
    rows = [
        _row(_case("a", expected_status="abstained", passages=()), _actual(status="abstained")),
        _row(_case("b", passages=(), facts=("3 meses",)), _actual(answer="3 meses")),
    ]

    block = eval_metrics.metric_block(rows)

    assert block["questions"] == 0
    assert block["hit_at_1"] is None
    assert block["hit_at_3"] is None
    assert block["hit_at_5"] is None
    assert block["mrr"] is None


def test_rank_null_when_inspection_has_no_retrieval() -> None:
    row = _row(_case("a"), _actual(no_retrieval=True))

    assert row["first_expected_rank"] is None
    assert row["retrieved_passage_ids"] == []


# --- abstention and clarification --------------------------------------------------------


def test_abstention_correct_needs_trap_reason_match() -> None:
    rows = [
        _row(
            _case("trap-1", expected_status="abstained", passages=(), category="false_premise"),
            _actual(status="abstained", answer="No lo sé."),
            case_set="trap",
        ),
        _row(
            _case("trap-2", expected_status="abstained", passages=(), category="false_premise"),
            _actual(status="abstained", answer="No lo sé."),
            case_set="trap",
        ),
        _row(
            _case("case-1", expected_status="abstained", passages=()),
            _actual(status="abstained", answer="No lo sé."),
            case_set="reviewed",
        ),
    ]
    # Only a trap row whose actual reason matched counts; reviewed cases need no reason.
    rows[0]["abstention_reason_match"] = False
    rows[1]["abstention_reason_match"] = True

    block = eval_metrics.summarize(rows)["abstention"]["overall"]

    assert block == {
        "expected": 3,
        "correct": 2,
        "status_matched": 3,
        "wrongly_answered": 0,
        "over_abstained": 0,
        "share": 0.6667,
    }


def test_over_abstained_and_wrongly_answered_counted() -> None:
    rows = [
        _row(
            _case("a", expected_status="abstained", passages=()),
            _actual(status="answered", answer="Sí."),
        ),
        _row(_case("b"), _actual(status="abstained", answer="No lo sé.")),
        _row(
            _case("c", expected_status="needs_land_clarification", passages=()),
            _actual(status="needs_land_clarification", choices=("land-1",)),
        ),
    ]

    summary = eval_metrics.summarize(rows)

    assert summary["abstention"]["overall"]["wrongly_answered"] == 1
    assert summary["abstention"]["overall"]["over_abstained"] == 1
    assert summary["clarification"]["overall"] == {
        "expected": 1,
        "status_matched": 1,
        "ids_matched": 1,
    }


# --- numeric -----------------------------------------------------------------------------


def test_numeric_facts_only_digit_facts_count_verbatim() -> None:
    case = _case(
        facts=("3 meses", "sin cifras", "2026", "treinta por ciento"),
    )
    actual = _actual(answer="El plazo es de 3 meses y la campaña 2026.")

    facts, correct = eval_metrics.numeric_facts(case, actual)
    row = _row(case, actual)
    block = eval_metrics.summarize([row])["numeric"]["overall"]

    assert (facts, correct) == (2, 2)
    assert block == {"facts": 2, "correct": 2, "share": 1.0, "must_not_say_hits": 0}


# --- breakdowns and row shape ------------------------------------------------------------


def test_breakdowns_by_set_type_and_category() -> None:
    rows = [
        _row(_case("g-1", passages=("p-1",)), _actual(ranks=((1, "p-1"),)), case_set="golden", question_type="deadline"),
        _row(
            _case("t-1", expected_status="abstained", passages=(), category="typo"),
            _actual(status="abstained"),
            case_set="trap",
        ),
        _row(_case("r-1", passages=("p-2",)), _actual(ranks=((2, "p-2"),)), case_set="reviewed"),
    ]

    summary = eval_metrics.summarize(rows)

    assert set(summary["retrieval"]["by_case_set"]) == {"reviewed", "golden", "trap"}
    assert summary["retrieval"]["by_case_set"]["golden"]["hit_at_1"] == 1.0
    assert summary["retrieval"]["by_case_set"]["trap"]["hit_at_1"] is None
    # Golden types come from the rows present; trap categories use the stable list.
    assert set(summary["retrieval"]["by_golden_question_type"]) == {"deadline"}
    assert summary["retrieval"]["by_golden_question_type"]["deadline"]["questions"] == 1
    assert set(summary["abstention"]["by_trap_category"]) == set(
        trap_set.CATEGORIES
    )
    assert summary["abstention"]["by_trap_category"]["typo"]["expected"] == 1


def test_rows_carry_no_question_answer_or_passage_text() -> None:
    case = _case(question="¿Cuándo se presenta la PAC en Écija?", municipality="Écija")
    actual = _actual(
        answer="La respuesta contiene 3 meses de plazo.",
        ranks=((1, "p-1"),),
    )
    actual["inspection"]["retrieval"]["passages"][0]["excerpt"] = "Texto literal del pasaje"

    document = eval_metrics.build_report(
        version={"label": "repository"},
        report_id="abc",
        rows=[_row(case, actual)],
        faithfulness=eval_metrics.faithfulness_from_judge(None, "", None),
    )
    text = json.dumps(document, ensure_ascii=False)

    for forbidden in ("¿Cuándo se presenta", "La respuesta contiene", "Texto literal", "Écija"):
        assert forbidden not in text
    assert document["cases"][0]["id"] == "case-1"
    assert set(document["cases"][0]) <= set(eval_metrics.ROW_KEYS)


# --- version -----------------------------------------------------------------------------


def _version_files(tmp_path: Path) -> dict[str, Path]:
    files = {}
    for name in ("catalog", "passages", "cases", "golden", "traps"):
        path = tmp_path / f"{name}.json"
        path.write_text(f'{{"kind": "{name}"}}\n', encoding="utf-8")
        files[name] = path
    return files


SCHEMA_VERSIONS = {
    "answer_eval": "pac-answer-eval-v2",
    "golden_set": "golden-set-v1",
    "trap_set": "trap-set-v1",
    "report": eval_metrics.SCHEMA_VERSION,
}


def _version(files: dict[str, Path], *, glossary: str = "off", label: str = "repository") -> dict[str, Any]:
    return eval_metrics.version_block(
        catalog=files["catalog"],
        passages=files["passages"],
        cases=files["cases"],
        golden=files["golden"],
        traps=files["traps"],
        glossary=glossary,
        as_of="2026-11-10",
        active_campaign="2026",
        label=label,
        schema_versions=SCHEMA_VERSIONS,
    )


def test_version_id_changes_with_any_input_digest_glossary_or_label(tmp_path: Path) -> None:
    files = _version_files(tmp_path)
    base = _version(files)
    base_id = eval_metrics.version_id(base)

    assert len(base["catalog_sha256"]) == 64
    assert base["glossary"] == "off"
    assert base["retrieval_mode"] == "bm25"
    assert base["k"] == 5
    assert eval_metrics.version_id(base) == base_id

    for name in files:
        original = files[name].read_text(encoding="utf-8")
        files[name].write_text(original + " ", encoding="utf-8")
        assert eval_metrics.version_id(_version(files)) != base_id
        files[name].write_text(original, encoding="utf-8")

    assert eval_metrics.version_id(_version(files, glossary="a" * 64)) != base_id
    assert eval_metrics.version_id(_version(files, label="other")) != base_id
    assert eval_metrics.version_id(_version(files)) == base_id


# --- faithfulness ------------------------------------------------------------------------


def test_faithfulness_constants_match_the_judge_module() -> None:
    assert eval_metrics.JUDGED_VERDICTS == grounding_judge.JUDGED_VERDICTS
    assert eval_metrics.JUDGE_VERDICTS == grounding_judge.VERDICTS
    assert eval_metrics.JUDGE_REVIEW == grounding_judge.JUDGE_REVIEW


def _judge_report(path: Path, *, verdicts: dict[str, int]) -> Path:
    block = {
        "sentences": sum(verdicts.values()),
        "verdicts": verdicts,
        "supported_share": (
            round(verdicts.get("supported", 0) / sum(
                verdicts.get(name, 0) for name in ("supported", "not_supported", "unclear")
            ), 4)
            if sum(verdicts.get(name, 0) for name in ("supported", "not_supported", "unclear"))
            else None
        ),
    }
    document = {
        "summary": {"overall": block, "by_case_set": {"reviewed": block, "golden": block}},
        "judge": {"model": "qwen2.5:7b-instruct-q4_K_M", "digest": "judge-digest"},
        "generator": {"model": "mistral-small3.2:latest", "digest": "generator-digest"},
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_faithfulness_not_judged_reasons_never_zero(tmp_path: Path) -> None:
    abort = "Result: the grounding judge report did not run (ollama_unavailable): down. Nothing was written."
    no_sentences = _judge_report(tmp_path / "none.json", verdicts={"unjudged_error": 3})
    unreadable = tmp_path / "broken.json"
    unreadable.write_text("{not json", encoding="utf-8")

    cases = {
        "skipped": eval_metrics.faithfulness_from_judge(None, "", None),
        "ollama_unavailable": eval_metrics.faithfulness_from_judge(2, abort, None),
        "no_judged_sentences": eval_metrics.faithfulness_from_judge(0, "", no_sentences),
        "judge_report_unreadable": eval_metrics.faithfulness_from_judge(0, "", unreadable),
    }
    cases["missing_report"] = eval_metrics.faithfulness_from_judge(
        0, "", tmp_path / "absent.json"
    )

    for expected, block in cases.items():
        assert block["status"] == "not_judged"
        assert block["reason"] == ("judge_report_unreadable" if expected == "missing_report" else expected)
        assert "supported_share" not in block
        assert eval_metrics.result_line(
            {
                "case_counts": {"total": 0, "reviewed": 0, "golden": 0, "trap": 0},
                "metrics": eval_metrics.summarize([]),
                "faithfulness": block,
                "version_id": "abc",
            },
            eval_metrics.REPO_ROOT / "build" / "eval-reports" / "abc" / "metrics.json",
        ).find("not judged (") > 0


def test_faithfulness_judged_carries_unchecked_label_and_pins(tmp_path: Path) -> None:
    path = _judge_report(
        tmp_path / "report.json",
        verdicts={"supported": 2, "not_supported": 1, "unclear": 1, "uncited": 2},
    )

    block = eval_metrics.faithfulness_from_judge(0, "judge output", path)

    assert block["status"] == "judged"
    assert block["supported_share"] == 0.5
    assert block["verdicts"]["supported"] == 2
    assert set(block["by_case_set"]) == {"reviewed", "golden"}
    assert block["judge"]["model"] == "qwen2.5:7b-instruct-q4_K_M"
    assert block["generator"]["digest"] == "generator-digest"
    assert block["drafts_from"] == "local_generator"
    assert block["judge_review"] == "unchecked_against_human_review"
    assert not Path(block["report"]).is_absolute()


def test_result_line_shapes_judged_and_not_judged(tmp_path: Path) -> None:
    rows = [
        _row(_case("a", passages=("p-1",)), _actual(ranks=((1, "p-1"),)), question_type="deadline"),
    ]
    judged = _judge_report(
        tmp_path / "report.json", verdicts={"supported": 3, "not_supported": 1}
    )
    faithfulness = eval_metrics.faithfulness_from_judge(0, "", judged)
    document = eval_metrics.build_report(
        version={"label": "repository"},
        report_id="abc123",
        rows=rows,
        faithfulness=faithfulness,
    )

    line = eval_metrics.result_line(document, eval_metrics.REPO_ROOT / "build" / "eval-reports" / "abc123" / "metrics.json")

    assert line.startswith(
        "Result: evaluated 1 questions (0 reviewed, 1 golden, 0 trap) for version abc123: "
    )
    assert "hit@1 1.0, hit@3 1.0, hit@5 1.0, MRR 1.0" in line
    assert "faithfulness: 0.75 supported (unchecked against human review)." in line
    assert line.endswith("Report only, no gate. Report: build/eval-reports/abc123/metrics.json.")

    skipped = eval_metrics.build_report(
        version={"label": "repository"},
        report_id="abc123",
        rows=[],
        faithfulness=eval_metrics.faithfulness_from_judge(None, "", None),
    )
    empty = eval_metrics.result_line(skipped, eval_metrics.REPO_ROOT / "build" / "eval-reports" / "abc123" / "metrics.json")

    assert "hit@1 n/a, hit@3 n/a, hit@5 n/a, MRR n/a over 0 questions" in empty
    assert "abstention correct 0 of 0" in empty
    assert "numbers and dates correct 0 of 0" in empty
    assert "faithfulness: not judged (skipped)." in empty


# --- reports root ------------------------------------------------------------------------


def test_reports_root_inside_knowledge_refused(tmp_path: Path) -> None:
    with pytest.raises(eval_metrics.MetricsAbort) as inside:
        eval_metrics.check_reports_root(
            eval_metrics.KNOWLEDGE_ROOT / "reports", (tmp_path / "cases.json",)
        )
    assert inside.value.code == "unsafe_report_path"

    input_file = tmp_path / "cases.json"
    input_file.write_text("{}", encoding="utf-8")
    with pytest.raises(eval_metrics.MetricsAbort) as equal:
        eval_metrics.check_reports_root(input_file, (input_file,))
    assert equal.value.code == "unsafe_report_path"

    assert eval_metrics.check_reports_root(tmp_path / "out", (input_file,)) == (
        tmp_path / "out"
    ).resolve()
