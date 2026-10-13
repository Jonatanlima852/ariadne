import argparse
import json
import os
import sys
import uuid

import grpc
from google.protobuf import json_format

sys.path.insert(
    0,
    os.getenv(
        "TG_SDK_PATH",
        os.path.join(os.path.dirname(__file__), "../../../../sdk/python/src"),
    ),
)

from contract.v1 import contract_pb2, contract_pb2_grpc


def parse_args():
    parser = argparse.ArgumentParser(
        description="Submete uma task ao TG Runtime e imprime o resultado."
    )
    parser.add_argument(
        "--orchestrator",
        default=os.getenv("ORCHESTRATOR_ADDR", "localhost:50052"),
        help="Endereço do orchestrator (default: localhost:50052)",
    )
    parser.add_argument(
        "--goal",
        default="Tarefa de teste",
        help="Objetivo da task em linguagem natural",
    )
    parser.add_argument(
        "--type",
        default="TEST",
        dest="task_type",
        help="Tipo da task (default: TEST)",
    )
    parser.add_argument(
        "--capability",
        default="echo",
        help="Capability necessária para executar a task (default: echo)",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="ID da task (gerado automaticamente se omitido)",
    )
    parser.add_argument(
        "--selection-policy",
        choices=["first-available", "round-robin", "least-loaded", "random"],
        default="first-available",
        help="Política de seleção do agente (default: first-available)",
    )
    return parser.parse_args()


def status_name(status_code):
    names = {
        contract_pb2.TASK_STATUS_UNKNOWN: "UNKNOWN",
        contract_pb2.TASK_STATUS_CREATED: "CREATED",
        contract_pb2.TASK_STATUS_QUEUED: "QUEUED",
        contract_pb2.TASK_STATUS_ASSIGNED: "ASSIGNED",
        contract_pb2.TASK_STATUS_RUNNING: "RUNNING",
        contract_pb2.TASK_STATUS_COMPLETED: "COMPLETED",
        contract_pb2.TASK_STATUS_FAILED: "FAILED",
        contract_pb2.TASK_STATUS_CANCELLED: "CANCELLED",
        contract_pb2.TASK_STATUS_REASSIGNED: "REASSIGNED",
        contract_pb2.TASK_STATUS_TIMEOUT: "TIMEOUT",
    }
    return names.get(status_code, f"STATUS({status_code})")


def main():
    args = parse_args()

    task_id = args.task_id or str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    task = contract_pb2.Task(
        task_id=task_id,
        type=args.task_type,
        goal=args.goal,
        required_capabilities=[args.capability],
        selection_policy=contract_pb2.SelectionPolicy.Value(
            "SELECTION_POLICY_" + args.selection_policy.replace("-", "_").upper()
        ),
        trace=contract_pb2.TraceContext(trace_id=trace_id),
    )

    print(f"Conectando ao orchestrator em {args.orchestrator}...")
    print(f"  task_id    : {task_id}")
    print(f"  goal       : {args.goal}")
    print(f"  type       : {args.task_type}")
    print(f"  capability : {args.capability}")
    print(f"  policy     : {args.selection_policy}")
    print(f"  trace_id   : {trace_id}")
    print()

    channel = grpc.insecure_channel(args.orchestrator)
    stub = contract_pb2_grpc.OrchestratorServiceStub(channel)

    try:
        response = stub.SubmitTask(contract_pb2.SubmitTaskRequest(task=task))
    except grpc.RpcError as e:
        print(f"Erro gRPC: {e.code()} — {e.details()}")
        sys.exit(1)

    if response.HasField("error") and response.error.code != contract_pb2.ERROR_CODE_UNKNOWN:
        print(f"Task falhou no runtime:")
        print(f"  erro    : {response.error.message}")
        print(f"  retry   : {response.error.retryable}")
        sys.exit(1)

    result = response.result
    print(f"Resultado:")
    print(f"  status   : {status_name(result.status)}")
    print(f"  agent_id : {result.agent_id}")
    print(f"  concluido: {result.completed_at.ToDatetime()}")
    if result.HasField("error") and result.error.message:
        print(f"  erro     : {result.error.message}")
    if result.HasField("output") and result.output.fields:
        print("  output   :")
        print(
            json.dumps(
                json_format.MessageToDict(result.output),
                ensure_ascii=False,
                indent=2,
            )
        )
    if result.HasField("metadata") and result.metadata.fields:
        print("  metadata :")
        print(
            json.dumps(
                json_format.MessageToDict(result.metadata),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
