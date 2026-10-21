import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUNS_ROOT = Path(os.getenv("ARIADNE_RUNS_DIR", REPOSITORY_ROOT / ".ariadne" / "runs")).resolve()
ALLOWED_FILES = {
    "manifest.json",
    "results.jsonl",
    "execution.jsonl",
    "demo.json",
    "summary.json",
    "result.json",
    "result.evaluation.json",
    "events.jsonl",
    "message-events.jsonl",
    "status",
    "environment",
    "scenario",
}
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_RESPONSE_BYTES = 20 * 1024 * 1024

app = FastAPI(title="Ariadne Runtime Inspector API", version="0.1.0")
CAMPAIGNS_ROOT = Path(os.getenv("ARIADNE_CAMPAIGNS_DIR", REPOSITORY_ROOT / ".ariadne/campaigns")).resolve()
EVALUATIONS_ROOT = Path(os.getenv("ARIADNE_EVALUATIONS_DIR", REPOSITORY_ROOT / ".ariadne/evaluations")).resolve()
SAMPLES_ROOT = REPOSITORY_ROOT / "tools/inspector/samples"


def roots():
    return {"runs": RUNS_ROOT, "campaigns": CAMPAIGNS_ROOT,
            "evaluations": EVALUATIONS_ROOT, "samples": SAMPLES_ROOT}


def evidence_path(source, identifier):
    root = roots().get(source)
    parts = identifier.split("/")
    if root is None or any(not RUN_ID.fullmatch(part) or part in (".", "..") for part in parts):
        raise HTTPException(400, "invalid evidence reference")
    if len(parts) != 1 and not (source == "campaigns" and len(parts) == 3 and parts[1] == "runs"):
        raise HTTPException(400, "invalid evidence nesting")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise HTTPException(404, "evidence not found")
    if not current.is_dir() or not current.resolve().is_relative_to(root.resolve()):
        raise HTTPException(404, "evidence not found")
    return current


def catalog_entry(path, source):
    reference = {"source": source, "id": path.name}
    if source == "campaigns":
        data = collection_document(path / "campaign.json", "runs")
        return {**reference, "scenario": data.get("name", path.name), "status": data.get("status", "UNKNOWN"),
                "started_at": data.get("created_at"), "observations": len(data.get("runs", []))}
    if source == "evaluations" or (source == "samples" and (path / "logistics-results.json").is_file()):
        data = collection_document(path / "logistics-results.json", "rows")
        return {**reference, "scenario": path.name, "status": "AVALIADA", "started_at": data.get("generated_at"),
                "demo": _read_json(path / "demo.json")}
    summary = _run_summary(path)
    manifest = _read_json(path / "manifest.json")
    metadata = manifest.get("metadata", {})
    demo = _read_json(path / "demo.json")
    return {**summary, **reference, "strategy": metadata.get("strategy"),
            "case_id": metadata.get("case", {}).get("id"), "demo": demo,
            "presentation": metadata.get("presentation", {}),
            "participant_count": len(manifest.get("agents", [])), "step_count": len(manifest.get("steps", []))}


def analysis_links(path):
    """Associação por caminho de entrada, sem ler caminhos arbitrários do relatório."""
    matches = []
    for candidate in EVALUATIONS_ROOT.iterdir() if EVALUATIONS_ROOT.is_dir() else []:
        if not candidate.is_dir() or candidate.is_symlink() or not RUN_ID.fullmatch(candidate.name):
            continue
        try:
            document = _read_json(candidate / "logistics-results.json")
            sources = document.get("sources", []) + [item.get("source", "") for item in document.get("campaigns", [])]
            if str(path.resolve()) not in sources:
                continue
            matches.append({"source": "evaluations", "id": candidate.name,
                            "generated_at": document.get("generated_at"),
                            "rows": [row for row in document.get("rows", []) if row.get("execution_id") == path.name]})
        except (OSError, ValueError, TypeError, AttributeError, HTTPException):
            continue
    return matches


def collection_document(path, field):
    document = _read_json(path)
    if not isinstance(document.get(field), list):
        raise HTTPException(422, f"invalid or incomplete {path.name}: expected {field} array")
    return document


def reference_for_path(value):
    path = Path(value)
    if not path.is_absolute():
        return None
    for source in ("runs", "campaigns"):
        root = roots()[source]
        try:
            identifier = str(path.relative_to(root))
            evidence_path(source, identifier)
            return {"source": source, "id": identifier}
        except (ValueError, HTTPException):
            continue
    return None


@app.get("/api/catalog")
def catalog(source: str = "runs", q: str = "", status: str = "",
            offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    root = roots().get(source)
    if root is None:
        raise HTTPException(400, "unknown source")
    items, warnings = [], []
    for path in root.iterdir() if root.is_dir() else []:
        if not path.is_dir() or path.is_symlink() or not RUN_ID.fullmatch(path.name):
            continue
        try:
            item = catalog_entry(path, source)
            if q.casefold() not in json.dumps(item, ensure_ascii=False).casefold():
                continue
            if status and item.get("status") != status:
                continue
            items.append(item)
        except (OSError, ValueError, TypeError, AttributeError, HTTPException):
            warnings.append(f"Não foi possível ler {path.name}")
    items.sort(key=lambda item: (item.get("started_at") or "", item["id"]), reverse=True)
    return {"items": items[offset:offset + limit], "total": len(items), "warnings": warnings}


@app.get("/api/evidence")
def evidence(source: str, identifier: str):
    path = evidence_path(source, identifier)
    if source == "evaluations" or (source == "samples" and (path / "logistics-results.json").is_file()):
        document = collection_document(path / "logistics-results.json", "rows")
        references = {Path(value).name: reference_for_path(value) for value in document.get("sources", [])}
        return {"kind": "evaluation", "document": document,
                "references": references, "demo": _read_json(path / "demo.json")}
    if source == "campaigns" and "/" not in identifier:
        document = collection_document(path / "campaign.json", "runs")
        observations = []
        for entry in document.get("runs", []):
            relative = entry.get("directory", "")
            try:
                run = evidence_path(source, f"{identifier}/{relative}")
                available = (run / "manifest.json").is_file()
            except HTTPException:
                available = False
            observations.append({**entry, "available": available,
                                 "source": source, "id": f"{identifier}/{relative}"})
        return {"kind": "campaign", "document": document, "observations": observations,
                "analyses": analysis_links(path)}
    return {"kind": "run", "files": _run_files(path), "analyses": analysis_links(path)}


def _is_regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _read_text(path: Path, limit: int = MAX_RESPONSE_BYTES) -> str:
    if not _is_regular_file(path):
        return ""
    if path.stat().st_size > limit:
        raise HTTPException(413, f"file is larger than {limit} bytes: {path.name}")
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json(path: Path) -> dict:
    content = _read_text(path)
    if not content:
        return {}
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _run_path(run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise HTTPException(400, "invalid run id")
    candidate = (RUNS_ROOT / run_id).resolve()
    if candidate.parent != RUNS_ROOT or not candidate.is_dir():
        raise HTTPException(404, "run not found")
    return candidate


def _run_summary(path: Path) -> dict:
    summary = _read_json(path / "summary.json")
    status = _read_text(path / "status", 1024).strip() or summary.get("status") or "UNKNOWN"
    scenario = _read_text(path / "scenario", 4096).strip() or summary.get("scenario") or "unknown"
    return {
        "id": path.name,
        "scenario": scenario,
        "status": status,
        "started_at": summary.get("started_at"),
        "elapsed_ms": summary.get("elapsed_ms"),
        "environment": _read_text(path / "environment", 4096).strip() or None,
        "has_result": _is_regular_file(path / "result.json"),
        "event_count": sum(_count_lines(path / name) for name in ("events.jsonl", "message-events.jsonl")),
        "updated_at": path.stat().st_mtime,
    }


def _count_lines(path: Path) -> int:
    if not _is_regular_file(path):
        return 0
    with path.open("rb") as stream:
        return sum(1 for line in stream if line.strip())


def _run_files(path: Path) -> list[dict]:
    files, total = [], 0
    for name in sorted(ALLOWED_FILES):
        target = path / name
        if not _is_regular_file(target):
            continue
        size = target.stat().st_size
        total += size
        if total > MAX_RESPONSE_BYTES:
            raise HTTPException(413, "recognized run files exceed 20 MB")
        files.append({"name": name, "path": f"{path.name}/{name}", "content": _read_text(target)})
    return files


def _events(path: Path) -> list[dict]:
    result = []
    for name in ("events.jsonl", "message-events.jsonl"):
        target = path / name
        if not _is_regular_file(target):
            continue
        for line_number, line in enumerate(_read_text(target).splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and isinstance(event.get("type"), str):
                result.append({**event, "source": name, "line": line_number})
    return result


@app.get("/api/health")
def health():
    return {"status": "ok", "runs_root": str(RUNS_ROOT), "session": os.getenv("ARIADNE_INSPECTOR_SESSION")}


@app.get("/api/runs")
def list_runs(limit: int = Query(50, ge=1, le=200)):
    if not RUNS_ROOT.is_dir():
        return {"runs": []}
    paths = sorted((path for path in RUNS_ROOT.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True)
    return {"runs": [_run_summary(path) for path in paths[:limit]]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    path = _run_path(run_id)
    return {"run": _run_summary(path), "files": _run_files(path)}


@app.get("/api/runs/{run_id}/events")
def get_events(run_id: str, after: int = Query(0, ge=0)):
    events = _events(_run_path(run_id))
    return {"events": events[after:], "next": len(events)}


@app.get("/api/runs/{run_id}/stream")
async def stream_events(run_id: str):
    path = _run_path(run_id)

    async def generate():
        cursor = 0
        while True:
            events = _events(path)
            for event in events[cursor:]:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            cursor = len(events)
            yield f"event: heartbeat\ndata: {cursor}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
