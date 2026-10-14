import unittest

from contract.v1 import contract_pb2
from ariadne_sdk import MessagingClient


class FakeMessagingStub:
    def __init__(self):
        self.published = None

    def PublishMessage(self, request):
        self.published = request.message
        return contract_pb2.PublishMessageResponse(ack=contract_pb2.MessageAck(
            message_id=request.message.message_id, accepted=True,
        ))

    def StreamMessages(self, request):
        message = contract_pb2.MessageEnvelope()
        message.CopyFrom(self.published)
        message.receiver_id = request.receiver_id
        return iter([message])


class MessagingClientTests(unittest.TestCase):
    def test_publish_and_stream_preserve_contract_fields(self):
        stub = FakeMessagingStub()
        client = MessagingClient("unused", "agent-a", stub=stub)
        message_id = client.publish(
            "agent-b", message_type="request", payload={"value": 42},
            conversation_id="conversation", correlation_id="correlation",
            trace_id="trace", task_id="task", ttl_ms=1000,
        )

        received = next(client.stream("agent-b"))

        self.assertEqual(received.message_id, message_id)
        self.assertEqual(received.type, "MESSAGE_TYPE_REQUEST")
        self.assertEqual(received.payload, {"value": 42.0})
        self.assertEqual(received.correlation_id, "correlation")
        self.assertEqual(received.trace_id, "trace")
        self.assertEqual(received.task_id, "task")


if __name__ == "__main__":
    unittest.main()
