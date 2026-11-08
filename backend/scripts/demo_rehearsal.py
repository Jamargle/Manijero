#!/usr/bin/env python3
"""Rehearse the demo against the running local answer service and the review gate.

Owner entry point behind ``./scripts/init.sh --demo-rehearsal`` (steps in
``docs/owner-guide/local-checks.md``, live order in ``docs/demo-script.md``)::

    ./scripts/init.sh --local-rag-start
    ./scripts/init.sh --demo-rehearsal

It drives the three service-level demo steps (reachability/readiness, a grounded
answer with approved sources, and a trap abstention) plus the human-reviewed
knowledge-update gate, and prints one ``PASS``/``FAIL``/``SKIP`` line per step and
exactly one ``Result:`` line. Exit codes: ``0`` every step passed, ``1`` a step
failed or was skipped, ``2`` misuse.

Boundaries:

- read-only for the service and canonical ``knowledge/``. The reviewed-update
  step runs on one temporary copy of ``backend/tests/fixtures/change_impact``
  that is removed afterwards, and records one clearly synthetic reviewer name;
- the two requests use ``land_context.mode = "general"`` with no lands and
  ``retain_for_improvement = false``; the default address is loopback;
- output carries no question, answer, passage, land, or token text: only fixed
  step labels, reason codes, source counts, and the service address;
- it starts nothing (no service, Ollama, container, emulator, or app) and makes
  no non-loopback call; a missing service prints ``SKIP`` and the one command
  that fixes it;
- the demo content is the reviewed PAC 2026 corpus plus the existing synthetic
  review fixtures; the reviewed update is declared synthetic in its label.

Standard library only, plus ``app.review_package`` and ``app.abstention`` for the
reviewed-update gate and the fixed abstention codes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"
CATALOG_PATH = KNOWLEDGE_ROOT / "source_catalog.json"
PASSAGES_PATH = KNOWLEDGE_ROOT / "passages.json"
REVIEW_FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "change_impact"

sys.path.insert(0, str(BACKEND_ROOT))
# The rehearsal writes only its temporary workspace: no __pycache__ under backend/app either.
sys.dont_write_bytecode = True

# Fixed, non-personal questions chosen from knowledge/pac_answer_eval.json: the
# first is recorded as correctly answered, the second as an abstention.
GROUNDED_QUESTION = "¿Cuál es la fecha final para presentar la solicitud única de 2026?"
TRAP_QUESTION = "¿Qué importe de ayuda me corresponde por hectárea?"

PROBE_TIMEOUT_SECONDS = 5
ASK_TIMEOUT_SECONDS = 120
MAX_RESPONSE_BYTES = 1_000_000

SERVICE_NAME = "Service"
GROUNDED_NAME = "Grounded answer"
TRAP_NAME = "Trap abstention"
REVIEW_NAME = "Reviewed update"

SERVICE_LABEL = "Service: /health and /ready answer"
GROUNDED_LABEL = "Grounded answer"
TRAP_LABEL = "Trap abstention"
REVIEW_LABEL = "Reviewed update: draft blocked, human approval, temporary merge (synthetic)"
GROUNDED_PASS = "Grounded answer: {count} approved sources, land_scope general"
TRAP_PASS = "Trap abstention: no sources"

RUN_FIX = "Start it with ./scripts/init.sh --local-rag-start, then run this command again."
FAIL_FIX = "Read the FAIL line, fix that step, then run this command again."
SYNTHETIC_NOTE = (
    "The reviewed update used synthetic fixtures; canonical knowledge was not changed."
)

# The fixed synthetic reviewed update. The reviewer name is clearly a rehearsal
# identity, never a real person, and the corpus addition declares itself synthetic.
AS_OF = date(2099, 10, 27)
REVIEWER = "Revisora de ensayo"
AUTHOR = "preparador-sintetico"
SUCCESS_ID = "7825dfd2af88508fc05c2e393052def95604929145ccd2f2771f71bb30936814"
NEW_SOURCE = "fixture-rd-2200-2099"
NEW_PASSAGE = "fixture-pasaje-rd-2200-art-1"
NEW_PASSAGE_TEXT = "Texto sintético de revisión; no afirma ningún plazo real."
REVIEW_SUMMARY = (
    "Ensayo sintético: añade el Real Decreto 2200/2099 de prueba. "
    "No es una norma real y no cambia el conocimiento aprobado."
)

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class _Unreachable(Exception):
    """The service could not be reached at all (refused, timed out, or no route)."""


@dataclass
class Step:
    """One rehearsal step: a short name, its outcome, and the printed line."""

    name: str
    status: str
    text: str


def default_url(environ: Optional[Mapping[str, str]] = None) -> str:
    """Loopback address of the local answer service, port from the environment."""
    values = os.environ if environ is None else environ
    port = (values.get("MANIJERO_LOCAL_RAG_PORT", "") or "").strip() or "8000"
    return "http://127.0.0.1:{}".format(port)


def ask_payload(question: str) -> Dict[str, Any]:
    """The closed ``/ask`` request shape: general mode, no lands, no retention."""
    return {
        "question": question,
        "land_context": {"mode": "general", "lands": []},
        "retain_for_improvement": False,
    }


def _normalize_url(value: str) -> str:
    parts = urllib.parse.urlsplit((value or "").strip())
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, "")
    )


def _json(body: bytes) -> Optional[Any]:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _request(
    url: str, payload: Optional[Dict[str, Any]] = None, timeout: int = PROBE_TIMEOUT_SECONDS
) -> Tuple[int, bytes]:
    """Return ``(status, body)``; raise :class:`_Unreachable` when nothing answers."""
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if data is not None else "GET"
    )
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_RESPONSE_BYTES)
    except (urllib.error.URLError, OSError):
        raise _Unreachable() from None


def _approved_url_sets() -> Tuple[Set[str], Set[str]]:
    """Every approved catalog URL, and the subset that belongs to campaign 2026."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    approved = [
        source
        for source in catalog.get("sources", [])
        if isinstance(source, dict) and source.get("review_status") == "approved"
    ]
    try:
        every = {_normalize_url(source["original_url"]) for source in approved}
    except (KeyError, TypeError):
        raise ValueError("invalid_catalog") from None
    campaign = {
        _normalize_url(source["original_url"])
        for source in approved
        if source.get("campaign") == "2026"
    }
    return every, campaign


# --- Steps ------------------------------------------------------------------


def _service_step(base_url: str) -> Tuple[Step, str]:
    """Probe ``/health`` and ``/ready``; return the step and a skip reason (empty when ready)."""
    unreachable = "the service is not reachable."
    try:
        health_status, health_body = _request(base_url + "/health")
    except _Unreachable:
        return Step(SERVICE_NAME, "SKIP", SERVICE_LABEL + ": " + unreachable), unreachable
    health = _json(health_body)
    if health_status != 200 or not isinstance(health, dict) or health.get("status") != "ok":
        return (
            Step(SERVICE_NAME, "FAIL", SERVICE_LABEL + ": /health did not answer as expected."),
            "the service check failed.",
        )

    try:
        ready_status, ready_body = _request(base_url + "/ready")
    except _Unreachable:
        return Step(SERVICE_NAME, "SKIP", SERVICE_LABEL + ": " + unreachable), unreachable
    ready = _json(ready_body)
    if ready_status == 503 or (isinstance(ready, dict) and ready.get("status") == "unavailable"):
        reason = "the service is running but not ready."
        return Step(SERVICE_NAME, "SKIP", SERVICE_LABEL + ": " + reason), reason
    if ready_status != 200 or not isinstance(ready, dict) or ready.get("status") != "ready":
        return (
            Step(SERVICE_NAME, "FAIL", SERVICE_LABEL + ": /ready did not answer as expected."),
            "the service check failed.",
        )
    return Step(SERVICE_NAME, "PASS", SERVICE_LABEL), ""


def _cited_passage_ids(inspection: Any) -> Optional[List[Any]]:
    if not isinstance(inspection, dict):
        return None
    outcome = inspection.get("outcome")
    if not isinstance(outcome, dict):
        return None
    cited = outcome.get("cited_passage_ids")
    return cited if isinstance(cited, list) else None


def _grounded_step(base_url: str) -> Step:
    label = GROUNDED_LABEL
    try:
        every, campaign = _approved_url_sets()
    except (OSError, ValueError):
        return Step(GROUNDED_NAME, "FAIL", label + ": the approved catalog could not be read.")
    try:
        status, body = _request(
            base_url + "/ask", ask_payload(GROUNDED_QUESTION), timeout=ASK_TIMEOUT_SECONDS
        )
    except _Unreachable:
        return Step(GROUNDED_NAME, "SKIP", label + ": the service is not reachable.")
    response = _json(body)
    if status != 200 or not isinstance(response, dict):
        return Step(GROUNDED_NAME, "FAIL", label + ": the service did not return a usable answer.")
    if response.get("status") != "answered":
        return Step(GROUNDED_NAME, "FAIL", label + ": the reply was not an answer.")
    answer = response.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return Step(GROUNDED_NAME, "FAIL", label + ": the answer text is missing.")
    sources = response.get("sources")
    if not isinstance(sources, list) or not sources:
        return Step(GROUNDED_NAME, "FAIL", label + ": no source was returned.")
    urls: List[str] = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("url"), str):
            return Step(GROUNDED_NAME, "FAIL", label + ": a source has no usable address.")
        urls.append(_normalize_url(source["url"]))
    if any(url not in every for url in urls):
        return Step(GROUNDED_NAME, "FAIL", label + ": a source is not in the approved catalog.")
    if not any(url in campaign for url in urls):
        return Step(
            GROUNDED_NAME, "FAIL", label + ": no source belongs to the approved 2026 catalog."
        )
    if response.get("land_scope") != "general":
        return Step(GROUNDED_NAME, "FAIL", label + ": the reply was not scoped as general.")
    if "inspection" in response and response["inspection"] is not None:
        cited = _cited_passage_ids(response["inspection"])
        if not cited:
            return Step(GROUNDED_NAME, "FAIL", label + ": the inspection cited no passage.")
    return Step(GROUNDED_NAME, "PASS", GROUNDED_PASS.format(count=len(sources)))


def _trap_step(base_url: str) -> Step:
    label = TRAP_LABEL
    try:
        status, body = _request(
            base_url + "/ask", ask_payload(TRAP_QUESTION), timeout=ASK_TIMEOUT_SECONDS
        )
    except _Unreachable:
        return Step(TRAP_NAME, "SKIP", label + ": the service is not reachable.")
    response = _json(body)
    if status != 200 or not isinstance(response, dict):
        return Step(TRAP_NAME, "FAIL", label + ": the service did not return a usable reply.")
    if response.get("status") != "abstained":
        return Step(TRAP_NAME, "FAIL", label + ": the reply was not an abstention.")
    sources = response.get("sources")
    if not isinstance(sources, list) or sources:
        return Step(TRAP_NAME, "FAIL", label + ": an abstention carried sources.")
    answer = response.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return Step(TRAP_NAME, "FAIL", label + ": the abstention text is missing.")
    if "inspection" in response and response["inspection"] is not None:
        inspection = response["inspection"]
        outcome = inspection.get("outcome") if isinstance(inspection, dict) else None
        reason = outcome.get("abstention_reason") if isinstance(outcome, dict) else None
        if not isinstance(reason, str) or reason not in _abstention_reasons():
            return Step(TRAP_NAME, "FAIL", label + ": the abstention code is not a known one.")
    return Step(TRAP_NAME, "PASS", TRAP_PASS)


def _abstention_reasons() -> Sequence[str]:
    from app.abstention import ABSTENTION_REASONS

    return ABSTENTION_REASONS


def _canonical_hashes() -> Dict[str, str]:
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (CATALOG_PATH, PASSAGES_PATH)
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def synthetic_proposal() -> Dict[str, Any]:
    """The fixed, synthetic proposal used by the reviewed-update step."""
    state = json.loads((REVIEW_FIXTURES / "ingestion-state.json").read_text(encoding="utf-8"))
    record = state["candidates"][SUCCESS_ID]
    source_entry = {
        "id": NEW_SOURCE,
        "title": record["title"],
        "issuing_body": record["issuer"],
        "original_url": record["publication_url"],
        "published_on": "2099-09-30",
        "downloaded_on": "2099-10-01",
        "verified_on": "2099-10-27",
        "content_sha256": record["original_sha256"],
        "review_status": "approved",
        "reviewed_by": "fixture-reviewer",
        "reviewed_on": "2099-10-27",
        "lifecycle_status": "current",
        "critical": False,
    }
    passage_entry = {
        "id": NEW_PASSAGE,
        "source_id": NEW_SOURCE,
        "location": "Artículo 1",
        "text": NEW_PASSAGE_TEXT,
    }
    return {
        "schema_version": "knowledge-update-proposal-v1",
        "summary": REVIEW_SUMMARY,
        "author": {"identity": AUTHOR, "kind": "human"},
        "candidates": [{"candidate_id": SUCCESS_ID}],
        "catalog": {"add": [source_entry], "update": [], "remove": []},
        "passages": {"add": [passage_entry], "update": [], "remove": []},
        "links": [{"source_id": NEW_SOURCE, "candidate_id": SUCCESS_ID}],
        "unresolved_questions": ["Ensayo sintético: ninguna pregunta real que resolver."],
    }


def _review_step(hashes_before: Mapping[str, str]) -> Step:
    """Prepare, gate, and merge the synthetic update inside one temporary workspace."""
    label = REVIEW_LABEL
    try:
        from app.review_package import ReviewPackageError, merge, prepare, record_decision
    except Exception:  # noqa: BLE001 - the operator sees one fixed line, never a traceback
        return Step(REVIEW_NAME, "FAIL", label + ": the review tools could not be loaded.")

    workspace = tempfile.mkdtemp(prefix="manijero-demo-rehearsal-")
    try:
        fixtures = Path(workspace) / "change_impact"
        shutil.copytree(REVIEW_FIXTURES, fixtures)
        proposal_path = fixtures / "proposal.json"
        proposal_path.write_text(_canonical_json(synthetic_proposal()), encoding="utf-8")
        prepared = prepare(
            fixtures / "ingestion-state.json",
            fixtures / "quarantine",
            fixtures / "catalog.json",
            fixtures / "passages.json",
            proposal_path,
            [REVIEWER],
            AS_OF,
            Path(workspace) / "review",
            cases_path=fixtures / "cases.json",
        )
        package = prepared["package"]
        if (
            package.get("merge_readiness") != "ready_for_review"
            or package.get("check_summary", {}).get("failed")
        ):
            return Step(REVIEW_NAME, "FAIL", label + ": the draft package is not ready for review.")

        try:
            merge(
                prepared["package_dir"],
                fixtures / "catalog.json",
                fixtures / "passages.json",
                fixtures / "cases.json",
            )
        except ReviewPackageError as error:
            if error.failure != "approval_required":
                return Step(REVIEW_NAME, "FAIL", label + ": the unapproved merge was refused oddly.")
        else:
            return Step(REVIEW_NAME, "FAIL", label + ": a merge without approval was not refused.")

        record_decision(
            prepared["package_dir"],
            REVIEWER,
            "approve",
            AS_OF,
            note="Aprobación sintética de ensayo; no es una revisión real.",
        )
        merge(
            prepared["package_dir"],
            fixtures / "catalog.json",
            fixtures / "passages.json",
            fixtures / "cases.json",
        )
        after_catalog = json.loads((fixtures / "catalog.json").read_text(encoding="utf-8"))
        after_passages = json.loads((fixtures / "passages.json").read_text(encoding="utf-8"))
        source_ids = {source.get("id") for source in after_catalog.get("sources", [])}
        passage_ids = {passage.get("id") for passage in after_passages.get("passages", [])}
        if NEW_SOURCE not in source_ids or NEW_PASSAGE not in passage_ids:
            return Step(REVIEW_NAME, "FAIL", label + ": the approved merge added no new ids.")
    except Exception:  # noqa: BLE001 - one fixed line; details never reach the operator
        return Step(REVIEW_NAME, "FAIL", label + ": the reviewed update did not complete.")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    if _canonical_hashes() != dict(hashes_before):
        return Step(REVIEW_NAME, "FAIL", label + ": canonical knowledge changed during the run.")
    return Step(REVIEW_NAME, "PASS", label)


# --- Output -----------------------------------------------------------------


def _result_line(base_url: str, steps: Sequence[Step]) -> str:
    total = len(steps)
    passed = sum(1 for step in steps if step.status == "PASS")
    if passed == total:
        return (
            "Result: the demo rehearsal passed ({} of {} steps) against {}. {}"
        ).format(total, total, base_url, SYNTHETIC_NOTE)
    failed = [step.name for step in steps if step.status == "FAIL"]
    skipped = [step.name for step in steps if step.status == "SKIP"]
    details = []
    if failed:
        details.append("failed: " + ", ".join(failed))
    if skipped:
        details.append("skipped: " + ", ".join(skipped))
    if failed:
        outcome = "failed"
        fix = FAIL_FIX
        if skipped:
            fix = FAIL_FIX + " " + RUN_FIX
    else:
        outcome = "incomplete"
        fix = RUN_FIX
    return "Result: the demo rehearsal is {} ({} of {} steps; {}). {}".format(
        outcome, passed, total, "; ".join(details), fix
    )


def run(base_url: str) -> int:
    """Run every step, print one line per step and one ``Result:`` line; return 0/1."""
    hashes_before = _canonical_hashes()
    service, skip_reason = _service_step(base_url)
    steps = [service]
    if not skip_reason:
        steps.append(_grounded_step(base_url))
        steps.append(_trap_step(base_url))
    else:
        steps.append(Step(GROUNDED_NAME, "SKIP", GROUNDED_LABEL + ": " + skip_reason))
        steps.append(Step(TRAP_NAME, "SKIP", TRAP_LABEL + ": " + skip_reason))
    steps.append(_review_step(hashes_before))

    for step in steps:
        print("{}  {}".format(step.status, step.text))
    print(_result_line(base_url, steps))
    return 0 if all(step.status == "PASS" for step in steps) else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="demo_rehearsal.py",
        description="Rehearse the Manijero demo against the running local answer service.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Service address for tests and developers (default: loopback 8000 or the configured port).",
    )
    args = parser.parse_args(argv)
    base_url = (args.url or default_url()).strip().rstrip("/")
    try:
        return run(base_url)
    except KeyboardInterrupt:
        print("Result: the demo rehearsal was stopped before it finished.")
        return 1
    except Exception:  # noqa: BLE001 - never print a traceback to the owner
        print("Result: the demo rehearsal could not finish. Run it again; if it fails again, ask a developer.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
