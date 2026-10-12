# Manijero backend

This is the initial HTTP service boundary. It currently exposes only the
service liveness check:

```sh
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
curl http://127.0.0.1:8000/health
```

Successful response:

```json
{"status":"ok","service":"manijero-backend"}
```

`/health` reports only that this process is serving HTTP requests. It does not
claim that the retrieval corpus, model provider, or other future dependencies
are available.

## Offline retrieval baseline (no route yet)

`app/retrieval.py` is the offline retrieval boundary over reviewed passages of
approved catalog sources. It is standard-library only, never performs network
access, re-validates the catalog with `app/source_catalog.py`, and refuses to
index when that catalog is invalid. There is still **no** `/ask` route and no
LLM call in this service.

Run the report-only baseline against the synthetic fixtures:

```sh
python3 backend/scripts/evaluate_retrieval.py \
  --catalog backend/tests/fixtures/retrieval/catalog.json \
  --passages backend/tests/fixtures/retrieval/passages.json \
  --eval backend/tests/fixtures/retrieval/eval_questions.jsonl \
  --as-of 2026-10-13 --k 5
```

It prints per-question expected-passage ranks plus `hit@k`, `recall@k`, and MRR
(`--json` for machine-readable output). Thresholds are **not** enforced: the
numbers come from a small synthetic fixture corpus, not from real user questions
or legal documents. See `knowledge/README.md` for the passage-set contract and
the eligibility rules.

Tests:

```sh
cd backend && python -m pytest
```
