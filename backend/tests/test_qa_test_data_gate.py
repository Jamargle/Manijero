"""QA test-data-only exception to the pending privacy review (docs/specs/qa_server_deployment.md, scenario 9).

The pilot launcher and local drafting accept the committed ``pending`` review only for exactly
``MANIJERO_DEPLOYMENT_PROFILE=pilot``, ``MANIJERO_ENVIRONMENT=qa`` and ``MANIJERO_QA_TEST_DATA_ONLY=yes``.
Everything else stays blocked, and the Gemini gate does not change.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict

import pytest

from app import pilot_ops
from app.local_generation import PROVIDER_EXTRACTIVE, PROVIDER_LOCAL, resolve_local_provider
from app.pilot_ops import run_preflight, upsert_client
from app.privacy_review import (
    decide_generation_provider,
    evaluate_gemini_review,
    evaluate_pilot_review,
    load_review_record,
    pilot_gate,
    qa_test_data_mode,
)
import test_local_generation as local_tests
import test_pilot_operations as pilot_tests

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 10, 13)
QA_ENV = {
    "MANIJERO_DEPLOYMENT_PROFILE": "pilot",
    "MANIJERO_ENVIRONMENT": "qa",
    "MANIJERO_QA_TEST_DATA_ONLY": "yes",
}


def committed() -> Dict[str, Any]:
    record = load_review_record()
    assert record is not None and record["pilot_review"]["status"] == "pending"
    return record


def approved() -> Dict[str, Any]:
    return json.loads(pilot_tests.SYNTHETIC_APPROVED_REVIEW.read_text(encoding="utf-8"))


# --- The mode ----------------------------------------------------------------------------------


def test_the_mode_needs_exactly_the_three_values() -> None:
    assert qa_test_data_mode(QA_ENV)
    for key, value in QA_ENV.items():
        assert not qa_test_data_mode({**QA_ENV, key: value.upper()})
        assert not qa_test_data_mode({**QA_ENV, key: value + " "})
        assert not qa_test_data_mode({k: v for k, v in QA_ENV.items() if k != key})
    assert not qa_test_data_mode({**QA_ENV, "MANIJERO_QA_TEST_DATA_ONLY": "yes1"})
    assert not qa_test_data_mode({**QA_ENV, "MANIJERO_QA_TEST_DATA_ONLY": "true"})
    assert not qa_test_data_mode({**QA_ENV, "MANIJERO_DEPLOYMENT_PROFILE": "development"})
    assert not qa_test_data_mode({**QA_ENV, "MANIJERO_ENVIRONMENT": "pilot"})
    assert not qa_test_data_mode({})


def test_a_pending_review_passes_only_in_the_mode_and_says_so() -> None:
    gate = pilot_gate(committed(), QA_ENV, as_of=DAY)
    assert gate.passed and gate.qa_test_data and gate.blockers == ()
    for env in ({}, {**QA_ENV, "MANIJERO_ENVIRONMENT": "QA"}, {**QA_ENV, "MANIJERO_QA_TEST_DATA_ONLY": "yes "}):
        blocked = pilot_gate(committed(), env, as_of=DAY)
        assert not blocked.passed and not blocked.qa_test_data and "privacy_review_pending" in blocked.blockers


def test_only_a_pending_status_is_overridden() -> None:
    rejected = committed()
    rejected["pilot_review"]["status"] = "rejected"
    assert not pilot_gate(rejected, QA_ENV, as_of=DAY).passed
    odd = committed()
    odd["pilot_review"]["status"] = "Pending"
    assert not pilot_gate(odd, QA_ENV, as_of=DAY).passed
    extra = copy.deepcopy(committed())
    extra["pilot_review"]["note"] = "x"
    assert not pilot_gate(extra, QA_ENV, as_of=DAY).passed
    wrong_schema = committed()
    wrong_schema["schema_version"] = "other"
    assert not pilot_gate(wrong_schema, QA_ENV, as_of=DAY).passed
    assert not pilot_gate(None, QA_ENV, as_of=DAY).passed
    assert pilot_gate(None, QA_ENV, as_of=DAY).blockers == ("privacy_review_record_unreadable",)
    assert not pilot_gate({"pilot_review": "pending"}, QA_ENV, as_of=DAY).passed


def test_an_approved_review_passes_without_the_qa_marker() -> None:
    gate = pilot_gate(approved(), {}, as_of=DAY)
    assert gate.passed and not gate.qa_test_data
    assert gate.result == evaluate_pilot_review(approved(), as_of=DAY)


def test_the_gemini_gate_is_unchanged_in_the_mode() -> None:
    assert "pilot_privacy_review_not_passed" in evaluate_gemini_review(
        committed(), as_of=DAY, configured_model="gemini-x"
    ).blockers
    decision = decide_generation_provider(
        {**QA_ENV, "MANIJERO_GENERATION_PROVIDER": "gemini", "MANIJERO_GEMINI_MODEL": "gemini-x"},
        record=committed(),
        as_of=DAY,
    )
    assert decision.provider == "extractive" and not decision.gemini_gate.passed


# --- Local drafting and preflight --------------------------------------------------------------


def _resolve(env: Dict[str, str], review: Any) -> Any:
    return resolve_local_provider(
        {**env, "MANIJERO_GENERATION_PROVIDER": "local", "MANIJERO_LOCAL_MODEL": local_tests.MODEL},
        record_document=json.loads(local_tests.SYNTHETIC_RECORD.read_text(encoding="utf-8")),
        transport=object(),
        as_of=local_tests.FIXED_DAY,
        clock=local_tests.FakeClock(),
        pilot=True,
        review_record=review,
    )


def test_local_drafting_is_enabled_in_the_pilot_profile_only_in_the_mode() -> None:
    allowed = _resolve(QA_ENV, committed())
    assert allowed.provider == PROVIDER_LOCAL and not allowed.blockers
    for env in ({}, {**QA_ENV, "MANIJERO_ENVIRONMENT": "prod"}, {**QA_ENV, "MANIJERO_QA_TEST_DATA_ONLY": "true"}):
        blocked = _resolve(env, committed())
        assert blocked.provider == PROVIDER_EXTRACTIVE and blocked.blockers
    rejected = committed()
    rejected["pilot_review"]["status"] = "rejected"
    assert _resolve(QA_ENV, rejected).provider == PROVIDER_EXTRACTIVE
    assert _resolve({}, approved()).provider == PROVIDER_LOCAL


def _preflight(tmp_path: Path, extra: Dict[str, str]) -> Any:
    environment = {**pilot_tests._pilot_env(tmp_path), **extra}
    return run_preflight(
        environment, as_of=pilot_tests.FIXED_DAY, catalog_path=pilot_tests.CATALOG, passages_path=pilot_tests.PASSAGES
    )


def test_preflight_reports_the_qa_test_data_flag(tmp_path: Path) -> None:
    blocked = _preflight(tmp_path, {})
    assert "privacy_review_pending" in blocked.problems and not blocked.qa_test_data_only
    allowed = _preflight(tmp_path, {"MANIJERO_ENVIRONMENT": "qa", "MANIJERO_QA_TEST_DATA_ONLY": "yes"})
    assert allowed.problems == () and allowed.ok and allowed.privacy_review_passed and allowed.qa_test_data_only
    still_blocked = _preflight(tmp_path, {"MANIJERO_ENVIRONMENT": "qa", "MANIJERO_QA_TEST_DATA_ONLY": "true"})
    assert "privacy_review_pending" in still_blocked.problems


# --- The launcher ------------------------------------------------------------------------------


def _launcher() -> Any:
    spec = importlib.util.spec_from_file_location("serve_pilot_under_test", BACKEND_ROOT / "scripts" / "serve_pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _launcher_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **extra: str) -> Any:
    for key in list(__import__("os").environ):
        if key.startswith("MANIJERO_"):
            monkeypatch.delenv(key)
    for key, value in {**pilot_tests._pilot_env(tmp_path), **extra}.items():
        monkeypatch.setenv(key, value)
    launcher = _launcher()
    monkeypatch.setattr(
        launcher,
        "run_preflight",
        lambda: pilot_ops.run_preflight(
            as_of=pilot_tests.FIXED_DAY, catalog_path=pilot_tests.CATALOG, passages_path=pilot_tests.PASSAGES
        ),
    )
    return launcher


def test_the_launcher_prints_the_warning_in_the_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    launcher = _launcher_env(
        monkeypatch, tmp_path, MANIJERO_ENVIRONMENT="qa", MANIJERO_QA_TEST_DATA_ONLY="yes"
    )
    assert launcher.main(["--preflight-only"]) == 0
    captured = capsys.readouterr()
    warning = (
        "WARNING: QA test-data-only mode. The privacy review is still pending: use only made-up test "
        "questions; no real users."
    )
    assert warning in captured.out and warning in captured.err
    assert "privacy_review: pending (QA test data only)" in captured.out


@pytest.mark.parametrize("extra", [{}, {"MANIJERO_ENVIRONMENT": "qa"}, {"MANIJERO_ENVIRONMENT": "qa", "MANIJERO_QA_TEST_DATA_ONLY": "YES"}])
def test_the_launcher_still_refuses_outside_the_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], extra: Dict[str, str]
) -> None:
    launcher = _launcher_env(monkeypatch, tmp_path, **extra)
    assert launcher.main(["--preflight-only"]) == 2
    captured = capsys.readouterr()
    assert "refused: privacy_review_pending" in captured.err
    assert "WARNING" not in captured.out + captured.err
