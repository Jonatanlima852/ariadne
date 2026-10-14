import json
from pathlib import Path

import app as module
from fastapi.testclient import TestClient


def create_run(root: Path, run_id="ariadne-test-001") -> Path:
    run = root / run_id
    run.mkdir()
    (run / "scenario").write_text("failure-reassignment\n")
    (run / "status").write_text("COMPLETED\n")
    (run / "summary.json").write_text(json.dumps({"elapsed_ms": 125.5, "started_at": "2026-10-08T00:00:00Z"}))
    (run / "result.json").write_text(json.dumps({"results": {}}))
    (run / "events.jsonl").write_text('{"type":"TASK_ASSIGNED"}\ninvalid\n{"type":"TASK_COMPLETED"}\n')
    return run


def test_lists_and_loads_runs(tmp_path, monkeypatch):
    create_run(tmp_path)
    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path.resolve())
    client = TestClient(module.app)

    listing = client.get("/api/runs").json()["runs"]
    assert listing[0]["scenario"] == "failure-reassignment"
    assert listing[0]["event_count"] == 3
    detail = client.get("/api/runs/ariadne-test-001").json()
    assert detail["run"]["status"] == "COMPLETED"
    assert {item["name"] for item in detail["files"]} >= {"result.json", "events.jsonl"}


def test_events_ignore_invalid_lines(tmp_path, monkeypatch):
    create_run(tmp_path)
    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path.resolve())
    response = TestClient(module.app).get("/api/runs/ariadne-test-001/events").json()
    assert [event["type"] for event in response["events"]] == ["TASK_ASSIGNED", "TASK_COMPLETED"]
    assert response["next"] == 2


def test_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path.resolve())
    client = TestClient(module.app)
    assert client.get("/api/runs/not%2Fsafe").status_code in {400, 404}


def test_does_not_follow_evidence_symlinks(tmp_path, monkeypatch):
    run = create_run(tmp_path)
    secret = tmp_path / "secret.json"
    secret.write_text('{"secret": true}')
    (run / "result.json").unlink()
    (run / "result.json").symlink_to(secret)
    monkeypatch.setattr(module, "RUNS_ROOT", tmp_path.resolve())

    detail = TestClient(module.app).get("/api/runs/ariadne-test-001").json()
    assert detail["run"]["has_result"] is False
    assert "result.json" not in {item["name"] for item in detail["files"]}
