"""Evidências brutas da execução; análise e gráficos pertencem ao consumidor."""

from datetime import datetime, timezone
import json
import threading


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, document):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class EventLog:
    def __init__(self, path, **identity):
        self.path = path
        self.identity = identity
        self.lock = threading.Lock()

    def emit(self, event_type, **fields):
        event = {"timestamp": utc_now(), **self.identity, "type": event_type, **fields}
        with self.lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
