"""Cliente público para a mensageria direta do runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping

import grpc
from google.protobuf import timestamp_pb2

from contract.v1 import contract_pb2, contract_pb2_grpc
from ariadne_sdk.models import mapping_to_struct, struct_to_dict


def _message_type(value):
    name = str(value).upper()
    if not name.startswith("MESSAGE_TYPE_"):
        name = f"MESSAGE_TYPE_{name}"
    return contract_pb2.MessageType.Value(name)


@dataclass(frozen=True)
class Message:
    message_id: str
    conversation_id: str
    correlation_id: str
    sender_id: str
    receiver_id: str
    type: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    trace_id: str = ""
    reply_to: str = ""
    ttl_ms: int = 0
    task_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_proto(cls, message):
        return cls(
            message_id=message.message_id,
            conversation_id=message.conversation_id,
            correlation_id=message.correlation_id,
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            type=contract_pb2.MessageType.Name(message.type),
            payload=(
                struct_to_dict(message.payload)
                if message.HasField("payload") else {}
            ),
            trace_id=message.trace.trace_id,
            reply_to=message.reply_to,
            ttl_ms=message.ttl_ms,
            task_id=message.task_id,
            metadata=(
                struct_to_dict(message.metadata)
                if message.HasField("metadata") else {}
            ),
        )


class MessagingClient:
    def __init__(self, address, sender_id, *, stub=None):
        self.sender_id = sender_id
        self._channel = None
        if stub is None:
            self._channel = grpc.insecure_channel(address)
            stub = contract_pb2_grpc.MessagingServiceStub(self._channel)
        self._stub = stub

    def publish(
        self, receiver_id, *, message_type="INFORM", payload=None,
        conversation_id=None, correlation_id=None, trace_id,
        reply_to="", ttl_ms=0, task_id="", metadata=None,
    ):
        now = timestamp_pb2.Timestamp()
        now.GetCurrentTime()
        message_id = str(uuid.uuid4())
        response = self._stub.PublishMessage(contract_pb2.PublishMessageRequest(
            message=contract_pb2.MessageEnvelope(
                message_id=message_id,
                conversation_id=conversation_id or str(uuid.uuid4()),
                correlation_id=correlation_id or "",
                sender_id=self.sender_id,
                receiver_id=receiver_id,
                type=_message_type(message_type),
                payload=mapping_to_struct(payload),
                timestamp=now,
                trace=contract_pb2.TraceContext(trace_id=trace_id),
                reply_to=reply_to,
                ttl_ms=ttl_ms,
                task_id=task_id,
                metadata=mapping_to_struct(metadata),
            )
        ))
        if not response.ack.accepted:
            raise RuntimeError(response.ack.error.message or "message rejected")
        return response.ack.message_id

    def stream(self, receiver_id=None) -> Iterator[Message]:
        identifier = receiver_id or self.sender_id
        responses = self._stub.StreamMessages(
            contract_pb2.StreamMessagesRequest(receiver_id=identifier)
        )
        for response in responses:
            yield Message.from_proto(response)

    def close(self):
        if self._channel is not None:
            self._channel.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
