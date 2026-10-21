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


def test_catalog_paginates_filters_and_does_not_follow_directory_symlinks(tmp_path, monkeypatch):
    root = tmp_path / 'runs'
    root.mkdir()
    create_run(root, 'one')
    create_run(root, 'two')
    (root / 'outside').symlink_to(tmp_path, target_is_directory=True)
    monkeypatch.setattr(module, 'RUNS_ROOT', root.resolve())
    client = TestClient(module.app)
    result = client.get('/api/catalog', params={'source': 'runs', 'limit': 1}).json()
    assert result['total'] == 2
    second = client.get('/api/catalog', params={'source': 'runs', 'limit': 1, 'offset': 1}).json()
    assert result['items'][0]['id'] != second['items'][0]['id']
    assert client.get('/api/catalog', params={'q': 'one'}).json()['total'] == 1
    assert client.get('/api/catalog', params={'status': 'FAILED'}).json()['total'] == 0
    assert client.get('/api/evidence', params={'source': 'runs', 'identifier': 'outside'}).status_code == 404


def test_campaign_keeps_failed_observations_and_checks_nested_paths(tmp_path, monkeypatch):
    campaign = tmp_path / 'campaign-one'
    runs = campaign / 'runs'
    runs.mkdir(parents=True)
    run = create_run(runs)
    (run / 'manifest.json').write_text('{"repeat": 2}')
    (run / 'results.jsonl').write_text('{"sample": 1}')
    (campaign / 'campaign.json').write_text(json.dumps({'runs': [
        {'directory': 'runs/ariadne-test-001', 'status': 'COMPLETED'},
        {'directory': 'runs/missing', 'status': 'FAILED'},
        {'directory': '../../outside', 'status': 'FAILED'},
    ]}))
    monkeypatch.setattr(module, 'CAMPAIGNS_ROOT', tmp_path.resolve())
    client = TestClient(module.app)
    data = client.get('/api/evidence', params={'source': 'campaigns', 'identifier': campaign.name}).json()
    assert [row['available'] for row in data['observations']] == [True, False, False]
    detail = client.get('/api/evidence', params={'source': 'campaigns', 'identifier': f'{campaign.name}/runs/ariadne-test-001'}).json()
    assert {'manifest.json', 'results.jsonl'} <= {item['name'] for item in detail['files']}
    assert client.get('/api/evidence', params={'source': 'campaigns', 'identifier': 'campaign-one/../outside'}).status_code == 400


def test_analysis_association_uses_recorded_source_and_preserves_evaluation(tmp_path, monkeypatch):
    root = tmp_path / 'runs'
    root.mkdir()
    run = create_run(root)
    evaluations = tmp_path / 'evaluations'
    evaluation = evaluations / 'analysis-one'
    evaluation.mkdir(parents=True)
    document = {'sources': [str(run)], 'rows': [{'execution_id': run.name, 'sample': 1, 'evaluation': {'valid': False}}]}
    (evaluation / 'logistics-results.json').write_text(json.dumps(document))
    monkeypatch.setattr(module, 'RUNS_ROOT', root.resolve())
    monkeypatch.setattr(module, 'EVALUATIONS_ROOT', evaluations.resolve())
    client = TestClient(module.app)
    data = client.get('/api/evidence', params={'source': 'runs', 'identifier': run.name}).json()
    assert data['analyses'][0]['rows'][0]['evaluation']['valid'] is False
    result = client.get('/api/evidence', params={'source': 'evaluations', 'identifier': evaluation.name}).json()
    assert result['document'] == document
    assert result['references'][run.name] == {'source': 'runs', 'id': run.name}
