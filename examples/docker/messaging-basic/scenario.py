"""Valida publicação e recebimento de MessageEnvelope correlacionado."""

import os
import json
from dataclasses import asdict
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "sdk/python/src"))

from tg_sdk import MessagingClient


def main():
    address = os.getenv("MESSAGING_ADDR", "localhost:55053")
    with MessagingClient(address, "agent-a") as sender:
        message_id = sender.publish(
            "agent-b",
            message_type="REQUEST",
            payload={"question": "ping"},
            conversation_id="conversation-basic",
            correlation_id="correlation-basic",
            trace_id="trace-basic",
            task_id="task-basic",
            ttl_ms=5000,
        )
    with MessagingClient(address, "agent-b") as receiver:
        message = next(receiver.stream())

    assert message.message_id == message_id
    assert message.sender_id == "agent-a"
    assert message.receiver_id == "agent-b"
    assert message.payload == {"question": "ping"}
    assert message.conversation_id == "conversation-basic"
    assert message.correlation_id == "correlation-basic"
    assert message.trace_id == "trace-basic"
    if report_path := os.getenv("SCENARIO_REPORT_PATH"):
        Path(report_path).write_text(json.dumps(asdict(message), indent=2) + "\n")
    print(
        "CENÁRIO APROVADO "
        f"message_id={message.message_id} trace_id={message.trace_id}"
    )


if __name__ == "__main__":
    main()
