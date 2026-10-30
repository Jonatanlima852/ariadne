"""Dois agentes trocam um envelope pelo serviço de mensagens do runtime.

Da raiz: ``./ariadne run studies/scenarios/messaging/scenario.py``. O agente
``agent-a`` publica um pedido para ``agent-b``; numa etapa dependente,
``agent-b`` recebe o envelope e devolve o que chegou, para comparar
identificador, remetente, payload e correlação.
"""
import os

from ariadne_sdk import Agent, MessagingClient, Scenario, Step


def send(task):
    with MessagingClient(os.environ["MESSAGING_ADDR"], "agent-a") as sender:
        message_id = sender.publish(
            "agent-b", message_type="REQUEST", payload={"question": task.goal},
            conversation_id="conversation-basic", correlation_id=task.task_id,
            trace_id=task.trace.get("trace_id", task.task_id), task_id=task.task_id, ttl_ms=5000,
        )
    return {"message_id": message_id, "receiver_id": "agent-b"}


def receive(task):
    with MessagingClient(os.environ["MESSAGING_ADDR"], "agent-b") as receiver:
        message = next(receiver.stream())
    return {
        "message_id": message.message_id, "sender_id": message.sender_id,
        "receiver_id": message.receiver_id, "payload": dict(message.payload),
        "conversation_id": message.conversation_id, "correlation_id": message.correlation_id,
        "matches_sent": message.message_id == task.payload.get("expected_message_id"),
    }


sent = Step("send-message", "ping", name="send")
received = Step(
    "receive-message", "Receba o envelope enviado", name="receive",
    payload={"expected_message_id": sent.output["message_id"]},
)

scenario = Scenario(
    agents=[
        Agent(name="agent-a", capabilities=["send-message"], handler=send),
        Agent(name="agent-b", capabilities=["receive-message"], handler=receive),
    ],
    tasks=[sent, received],
)
