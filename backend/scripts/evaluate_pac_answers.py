#!/usr/bin/env python3
"""Run the reviewed canonical cases through the local FastAPI /ask route."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.ask_api import get_as_of_date, get_active_campaign, get_corpus_documents, get_retrieval_k, CorpusDocuments
from app.source_catalog import load_catalog
from app.retrieval import load_passage_set
from app.answer_eval import (
    AnswerEvalError,
    evaluate,
    load_case_document,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--passages", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--active-campaign", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    try:
        catalog = load_catalog(args.catalog)
        passages = load_passage_set(args.passages)
        cases, coverage = load_case_document(args.cases, catalog, passages)
        docs = CorpusDocuments(catalog=catalog, passages=passages)
        app.dependency_overrides[get_corpus_documents] = lambda: docs
        app.dependency_overrides[get_as_of_date] = lambda: args.as_of
        app.dependency_overrides[get_active_campaign] = lambda: args.active_campaign
        app.dependency_overrides[get_retrieval_k] = lambda: args.k
        if args.k < 1 or args.k > 100:
            raise AnswerEvalError("--k must be between 1 and 100")
        report = evaluate(
            cases,
            TestClient(app),
            catalog,
            passages,
            args.k,
            coverage=coverage,
        )
        report.update({"active_campaign": args.active_campaign, "as_of": args.as_of.isoformat(), "k": args.k,
                       "quality_metrics_are_report_only": True})
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(f"error: {exc if isinstance(exc, AnswerEvalError) else 'evaluation input or runtime failure'}", file=sys.stderr)
        return 2
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    raise SystemExit(main())
