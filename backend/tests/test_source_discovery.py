import json
from datetime import datetime, timezone

from app.source_discovery import CONFIG_VERSION, REGISTRIES, _boja_calendar, discover


def config(tmp_path, ids=("boe",)):
    entries = []
    for rid in ids:
        meta = REGISTRIES[rid]
        url = meta["url"].format(date="20261027", year="2026", number="1")
        entries.append({"id": rid, "url": url, "format": meta["format"], "issuer": meta["issuer"]})
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": CONFIG_VERSION, "registries": entries}))
    return path


def test_repeat_and_changed_observation_are_retained_and_pending(tmp_path, monkeypatch):
    from app import source_discovery as module
    samples = [b'<response><status><code>200</code></status><data><item><identificador>BOE-X-1</identificador><titulo>Title</titulo><url_pdf>https://www.boe.es/boe/dias/2026/10/27/pdfs/x.pdf</url_pdf></item></data></response>'] * 2
    monkeypatch.setattr(module, "_fetch", lambda *args: samples.pop(0))
    config_path, state = config(tmp_path), tmp_path / "state.json"
    t = datetime(2026, 10, 27, tzinfo=timezone.utc)
    a = discover(config_path, state, t)
    b = discover(config_path, state, t)
    data = json.loads(state.read_text())
    assert a["candidate_count"] == b["candidate_count"] == 1
    candidate = next(iter(data["candidates"].values()))
    assert candidate["review_status"] == "pending"
    assert len(candidate["observations"]) == 1


def test_failure_retains_last_success_and_unconfigured_coverage(tmp_path, monkeypatch):
    from app import source_discovery as module
    path = tmp_path / "state.json"
    success = b'<response><status><code>200</code></status><data><item><identificador>BOE-X-1</identificador><titulo>Title</titulo><url_pdf>https://www.boe.es/boe/dias/2026/10/27/pdfs/x.pdf</url_pdf></item></data></response>'
    monkeypatch.setattr(module, "_fetch", lambda *args: success)
    discover(config(tmp_path), path)
    last_success = json.loads(path.read_text())["registries"]["boe"]["last_success_at"]
    monkeypatch.setattr(module, "_fetch", lambda *args: (_ for _ in ()).throw(OSError()))
    report = discover(config(tmp_path), path)
    state = json.loads(path.read_text())
    assert report["registries"][0]["status"] == "unchecked"
    assert report["registries"][1]["failure"] == "not_configured"
    assert state["registries"]["boe"]["last_success_at"] == last_success
    assert len(state["candidates"]) == 1


def test_boja_synthetic_dataset_adapter_and_unsafe_document_rejected(tmp_path, monkeypatch):
    from app import source_discovery as module
    calendar = json.dumps({"columns": [{"name": "number"}, {"name": "date"}], "rows": [[1, "01/01/2026"]]}).encode()
    bulletin = json.dumps({"hits": 1, "total_hits": 1, "schema": {}, "results": [{"id": "boja.1", "summaryNoHtml": "Test", "pdf": [{"publicUrl": "https://evil.example/a"}]}]}).encode()
    responses = [calendar, bulletin]
    monkeypatch.setattr(module, "_fetch", lambda *args: responses.pop(0))
    report = discover(config(tmp_path, ("boja",)), tmp_path / "state.json")
    assert report["candidate_count"] == 0
    assert report["registries"][0]["rejected_unsafe_records"] == 1


def test_boja_documented_results_and_pdf_link_are_adapted(tmp_path, monkeypatch):
    from app import source_discovery as module
    calendar = json.dumps({"columns": [{"name": "number"}, {"name": "date"}], "rows": [[1, "02/01/2026"], [1, "02/01/2026"]]}).encode()
    bulletin = json.dumps({"hits": 1, "total_hits": 1, "schema": {}, "results": [{"id": "boja.2026.1.1", "title": "disposition-id", "summaryNoHtml": "Human-readable title", "pdf": [{"publicUrl": "https://juntadeandalucia.es/eboja/2026/1/doc.pdf"}]}]}).encode()
    responses = [calendar, bulletin]
    calls = []
    def fetch(url, accept):
        calls.append(url)
        return responses.pop(0)
    monkeypatch.setattr(module, "_fetch", fetch)
    report = discover(config(tmp_path, ("boja",)), tmp_path / "state.json")
    state = json.loads((tmp_path / "state.json").read_text())
    assert report["candidate_count"] == 1
    candidate = next(iter(state["candidates"].values()))
    assert candidate["publication_url"].endswith("doc.pdf")
    assert candidate["title"] == "Human-readable title"
    assert len(calls) == 2 and "number=1" in calls[1]
    assert candidate["registry_url"] == calls[1]


def test_boja_calendar_deduplicates_issue_numbers_and_enforces_limit():
    calendar = {"columns": [{"name": "number"}, {"name": "date"}], "rows": [[2, "date"], [1, "date"], [2, "date"]]}
    assert _boja_calendar(calendar) == [1, 2]
    too_many = {"columns": [{"name": "number"}, {"name": "date"}], "rows": [[n, "date"] for n in range(1, 402)]}
    try:
        _boja_calendar(too_many)
    except ValueError:
        pass
    else:
        raise AssertionError("calendar bound was not enforced")


def test_boja_incomplete_multi_issue_scan_does_not_commit_partial_candidates(tmp_path, monkeypatch):
    from app import source_discovery as module
    calendar = json.dumps({"columns": [{"name": "number"}, {"name": "date"}], "rows": [[1, "date"], [2, "date"]]}).encode()
    bulletin = json.dumps({"hits": 1, "total_hits": 1, "results": [{"id": "boja.1", "summaryNoHtml": "Title", "pdf": [{"publicUrl": "https://juntadeandalucia.es/eboja/2026/1/doc.pdf"}]}]}).encode()
    responses = [calendar, bulletin]
    def fetch(url, accept):
        if responses:
            return responses.pop(0)
        raise OSError("network failure")
    monkeypatch.setattr(module, "_fetch", fetch)
    state_path = tmp_path / "state.json"
    report = discover(config(tmp_path, ("boja",)), state_path)
    state = json.loads(state_path.read_text())
    assert report["registries"][0]["status"] == "unchecked"
    assert not state["candidates"]


def test_changed_observation_is_retained(tmp_path, monkeypatch):
    from app import source_discovery as module
    base = '<response><status><code>200</code></status><data><item><identificador>BOE-X-1</identificador><titulo>{}</titulo><url_pdf>https://www.boe.es/boe/dias/2026/10/27/pdfs/x.pdf</url_pdf></item></data></response>'
    samples = [base.format("First").encode(), base.format("Changed").encode()]
    monkeypatch.setattr(module, "_fetch", lambda *args: samples.pop(0))
    config_path, state_path = config(tmp_path), tmp_path / "state.json"
    discover(config_path, state_path)
    discover(config_path, state_path)
    candidate = next(iter(json.loads(state_path.read_text())["candidates"].values()))
    assert len(candidate["observations"]) == 2


def test_mixed_valid_and_incomplete_boe_response_is_transactional(tmp_path, monkeypatch):
    from app import source_discovery as module
    valid_item = '<item><identificador>BOE-X-1</identificador><titulo>Title</titulo><url_pdf>https://www.boe.es/boe/dias/2026/10/27/pdfs/x.pdf</url_pdf></item>'
    success = f'<response><status><code>200</code></status>{valid_item}</response>'.encode()
    malformed = f'<response><status><code>200</code></status>{valid_item}<item><identificador>BOE-X-2</identificador></item></response>'.encode()
    responses = [success, malformed]
    monkeypatch.setattr(module, "_fetch", lambda *args: responses.pop(0))
    state_path = tmp_path / "state.json"
    cfg = config(tmp_path)
    discover(cfg, state_path)
    before = json.loads(state_path.read_text())
    result = discover(cfg, state_path)
    after = json.loads(state_path.read_text())
    assert result["registries"][0]["status"] == "unchecked"
    assert after["candidates"] == before["candidates"]
    assert after["registries"]["boe"]["last_success_at"] == before["registries"]["boe"]["last_success_at"]


def test_mixed_valid_and_unrecognized_boja_rows_are_transactional(tmp_path, monkeypatch):
    from app import source_discovery as module
    calendar = json.dumps({"columns": [{"name": "number"}, {"name": "date"}], "rows": [[1, "date"]]}).encode()
    valid = {"id": "boja.1", "summaryNoHtml": "Title", "pdf": [{"publicUrl": "https://juntadeandalucia.es/eboja/2026/1/doc.pdf"}]}
    success = json.dumps({"hits": 1, "results": [valid]}).encode()
    malformed = json.dumps({"hits": 2, "results": [valid, {"unexpected": "row"}]}).encode()
    responses = [calendar, success, calendar, malformed]
    monkeypatch.setattr(module, "_fetch", lambda *args: responses.pop(0))
    state_path = tmp_path / "state.json"
    cfg = config(tmp_path, ("boja",))
    discover(cfg, state_path)
    before = json.loads(state_path.read_text())
    result = discover(cfg, state_path)
    after = json.loads(state_path.read_text())
    assert result["registries"][0]["status"] == "unchecked"
    assert after["candidates"] == before["candidates"]
    assert after["registries"]["boja"]["last_success_at"] == before["registries"]["boja"]["last_success_at"]
