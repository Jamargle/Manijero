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
