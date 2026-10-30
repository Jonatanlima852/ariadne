import logging
import os
import threading
import time
from collections.abc import Mapping
from concurrent import futures

import grpc
from google.protobuf import timestamp_pb2

from contract.v1 import contract_pb2, contract_pb2_grpc
from ariadne_sdk.models import Task, TaskResult

log = logging.getLogger(__name__)


class _AgentServicer(contract_pb2_grpc.AgentServiceServicer):
    """Adapta o AgentService gRPC para o método execute_task do Agent."""

    def __init__(self, agent):
        self._agent = agent

    def ExecuteTask(self, request, context):
        self._agent._task_started()
        started = time.perf_counter()
        started_at = timestamp_pb2.Timestamp()
        started_at.GetCurrentTime()
        try:
            if self._agent.event_sink:
                self._agent.event_sink("AGENT_TASK_STARTED", request.task)
            result = self._agent._execute_contract_task(request.task)
            result.started_at.CopyFrom(started_at)
            if self._agent.event_sink:
                self._agent.event_sink(
                    "AGENT_TASK_FINISHED", request.task, result=result,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    caller_active=context.is_active(),
                )
            return contract_pb2.ExecuteTaskResponse(result=result)
        finally:
            self._agent._task_finished()


AGENT_KINDS = ("unknown", "deterministic", "bdi", "llm", "hybrid")


def agent_kind_name(value) -> str:
    """Normaliza o nome da família de um agente ("bdi", "llm", ...)."""
    name = str(value or "unknown").lower().removeprefix("agent_kind_")
    if name not in AGENT_KINDS:
        raise ValueError(f"agent kind must be one of {', '.join(AGENT_KINDS)}: {value!r}")
    return name


class Agent:
    """Classe base para agentes do Ariadne Runtime.

    Cuida do registro no Registry e do servidor gRPC do AgentService.
    Use handler ou implemente handle com a lógica de negócio. execute_task
    permanece disponível para subclasses legadas que usam protobuf.
    """

    def __init__(self, agent_id=None, name=None, capabilities=None,
                 host="127.0.0.1", port=0, registry_addr="localhost:50051",
                 runtime="python-sdk", contract_version="2.0.0",
                 heartbeat_interval_seconds=None, reported_load=None, handler=None,
                 listen_host="[::]", kind=None):
        self.name = name or getattr(type(self), "default_name", type(self).__name__)
        self.agent_id = agent_id or getattr(type(self), "default_agent_id", self.name)
        self.capabilities = list(capabilities if capabilities is not None else getattr(type(self), "capabilities", ()))
        self._handler = handler
        self._server = None
        self._registered = False
        self.event_sink = None
        self.host = host
        self.listen_host = listen_host
        self.port = port
        self.registry_addr = registry_addr
        self.runtime = runtime
        self.contract_version = contract_version
        # Família de raciocínio declarada no descritor (contrato 2.0.0):
        # "deterministic", "bdi", "llm", "hybrid" ou "unknown". BdiAgent e
        # LlmAgent ajustam o padrão; o orquestrador copia o valor para
        # TaskResult.agent_kind e para cada TaskAttempt.
        self.kind = agent_kind_name(kind if kind is not None else getattr(type(self), "default_kind", "deterministic"))
        if heartbeat_interval_seconds is None:
            heartbeat_interval_seconds = float(
                os.getenv("HEARTBEAT_INTERVAL_SECONDS", "5")
            )
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds deve ser maior que zero")
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.reported_load = reported_load
        self._current_task_count = 0
        self._task_count_lock = threading.Lock()
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None

    @classmethod
    def from_env(cls, **overrides):
        """Cria um agente usando a configuração operacional padrão.

        Valores explícitos têm precedência sobre variáveis de ambiente.
        Subclasses podem declarar ``default_*`` e ``capabilities`` como
        atributos de classe, mantendo detalhes de deployment fora da lógica.
        """
        defaults = {
            "agent_id": os.getenv(
                "AGENT_ID", getattr(cls, "default_agent_id", cls.__name__.lower())
            ),
            "name": os.getenv(
                "AGENT_NAME", getattr(cls, "default_name", cls.__name__)
            ),
            "capabilities": list(getattr(cls, "capabilities", [])),
            "host": os.getenv("AGENT_HOST", "localhost"),
            "port": int(
                os.getenv("AGENT_PORT", str(getattr(cls, "default_port", 60051)))
            ),
            "registry_addr": os.getenv("REGISTRY_ADDR", "localhost:50051"),
            "runtime": getattr(cls, "runtime_name", "python-sdk"),
        }
        defaults.update(overrides)
        if not defaults["capabilities"]:
            raise ValueError(
                f"{cls.__name__} must declare at least one capability"
            )
        return cls(**defaults)

    def execute_task(self, task):
        """Recebe um contract_pb2.Task e devolve um contract_pb2.TaskResult.

        Subclasses devem sobrescrever este método com a lógica do agente.
        """
        raise NotImplementedError("subclasses devem implementar execute_task")

    def handle(self, task: Task) -> TaskResult | Mapping:
        """Hook público para agentes novos baseados nos modelos do SDK.

        Agentes existentes podem continuar sobrescrevendo ``execute_task`` com
        mensagens protobuf. Novos agentes devem preferir ``handle``.
        """
        if self._handler is None:
            raise NotImplementedError("declare handler ou implemente handle")
        return self._handler(task)

    def _execute_contract_task(self, raw_task):
        """Adapta o contrato gRPC para APIs novas ou legadas do agente."""
        try:
            if self._handler is not None or type(self).handle is not Agent.handle:
                result = self.handle(Task.from_proto(raw_task))
            else:
                result = self.execute_task(raw_task)

            if isinstance(result, Mapping):
                result = TaskResult(
                    task_id=raw_task.task_id, agent_id=self.agent_id,
                    status="TASK_STATUS_COMPLETED", output=result,
                    trace=Task.from_proto(raw_task).trace,
                )
            if isinstance(result, TaskResult):
                return result.to_proto()
            if isinstance(result, contract_pb2.TaskResult):
                return result
            raise TypeError("agent handler must return ariadne_sdk.TaskResult")
        except ValueError as error:
            return self._exception_result(
                raw_task, contract_pb2.ERROR_CODE_INVALID_TASK, error, False
            )
        except TimeoutError as error:
            return self._exception_result(
                raw_task, contract_pb2.ERROR_CODE_TIMEOUT, error, True
            )
        except NotImplementedError as error:
            return self._exception_result(
                raw_task, contract_pb2.ERROR_CODE_EXECUTION_FAILED, error, False
            )
        except Exception as error:
            log.exception(
                "agent_id=%s unhandled task error task_id=%s error_type=%s",
                self.agent_id,
                raw_task.task_id,
                type(error).__name__,
            )
            return self._exception_result(
                raw_task, contract_pb2.ERROR_CODE_EXECUTION_FAILED, error, False
            )

    def _exception_result(self, task, code, error, retryable):
        completed_at = timestamp_pb2.Timestamp()
        completed_at.GetCurrentTime()
        return contract_pb2.TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status=contract_pb2.TASK_STATUS_FAILED,
            completed_at=completed_at,
            trace=task.trace,
            error=contract_pb2.ErrorInfo(
                code=code,
                message=str(error) or type(error).__name__,
                retryable=retryable,
            ),
        )

    def build_descriptor(self):
        return contract_pb2.AgentDescriptor(
            agent_id=self.agent_id,
            name=self.name,
            runtime=self.runtime,
            contract_version=self.contract_version,
            capabilities=[
                contract_pb2.Capability(
                    capability_id=capability_id,
                    name=capability_id,
                )
                for capability_id in self.capabilities
            ],
            endpoint=contract_pb2.AgentEndpoint(
                protocol="grpc",
                address=f"{self.host}:{self.port}",
            ),
            status=contract_pb2.AGENT_STATUS_ALIVE,
            kind=contract_pb2.AgentKind.Value(f"AGENT_KIND_{self.kind.upper()}"),
        )

    def register(self):
        with grpc.insecure_channel(self.registry_addr) as channel:
            stub = contract_pb2_grpc.RegistryServiceStub(channel)
            resp = stub.RegisterAgent(
                contract_pb2.RegisterAgentRequest(agent=self.build_descriptor()), timeout=5,
            )
        if not resp.success:
            raise RuntimeError(f"registration failed: {resp.message}")
        log.info("agent_id=%s registered with registry addr=%s", self.agent_id, self.registry_addr)
        self._registered = True

    def _task_started(self):
        with self._task_count_lock:
            self._current_task_count += 1

    def _task_finished(self):
        with self._task_count_lock:
            self._current_task_count -= 1

    def _task_count(self):
        with self._task_count_lock:
            return self._current_task_count

    def heartbeat(self, stub):
        """Envia um único sinal de saúde ao Registry."""
        now = timestamp_pb2.Timestamp()
        now.GetCurrentTime()
        task_count = self._task_count()
        response = stub.ReportHealth(
            contract_pb2.ReportHealthRequest(
                health=contract_pb2.HealthStatus(
                    agent_id=self.agent_id,
                    status=contract_pb2.AGENT_STATUS_ALIVE,
                    timestamp=now,
                    last_heartbeat_at=now,
                    current_task_count=task_count,
                    load=(
                        float(self.reported_load)
                        if self.reported_load is not None
                        else (1.0 if task_count else 0.0)
                    ),
                )
            ), timeout=5,
        )
        if not response.success:
            raise RuntimeError("heartbeat rejected by registry")

    def _heartbeat_loop(self):
        channel = grpc.insecure_channel(self.registry_addr)
        stub = contract_pb2_grpc.RegistryServiceStub(channel)
        try:
            while not self._heartbeat_stop.is_set():
                try:
                    self.heartbeat(stub)
                    log.debug("agent_id=%s heartbeat sent", self.agent_id)
                except grpc.RpcError as error:
                    log.warning(
                        "agent_id=%s heartbeat failed code=%s details=%s",
                        self.agent_id,
                        error.code(),
                        error.details(),
                    )
                except Exception:
                    log.exception("agent_id=%s heartbeat failed", self.agent_id)
                self._heartbeat_stop.wait(self.heartbeat_interval_seconds)
        finally:
            channel.close()

    def start_heartbeat(self):
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"heartbeat-{self.agent_id}",
            daemon=True,
        )
        self._heartbeat_thread.start()
        log.info(
            "agent_id=%s heartbeat started interval_seconds=%s",
            self.agent_id,
            self.heartbeat_interval_seconds,
        )

    def stop_heartbeat(self):
        self._heartbeat_stop.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=self.heartbeat_interval_seconds + 1)
        self._heartbeat_thread = None

    def _start_server(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
        contract_pb2_grpc.add_AgentServiceServicer_to_server(_AgentServicer(self), server)
        self.port = server.add_insecure_port(f"{self.listen_host}:{self.port}")
        if not self.port:
            raise RuntimeError("não foi possível abrir a porta do agente")
        server.start()
        self._server = server
        log.info("agent_id=%s service started port=%d", self.agent_id, self.port)

    def start(self):
        """Inicia o endpoint antes de anunciar o agente; não bloqueia."""
        if self._server is not None:
            return self
        if not self.capabilities:
            raise ValueError("agent must declare at least one capability")
        try:
            self._start_server()
            self.register()
            with grpc.insecure_channel(self.registry_addr) as channel:
                self.heartbeat(contract_pb2_grpc.RegistryServiceStub(channel))
            self.start_heartbeat()
        except BaseException:
            self.stop()
            raise
        return self

    def stop(self, grace=1):
        """Interrompe heartbeat, remove registro e encerra o endpoint."""
        self.stop_heartbeat()
        if self._registered:
            try:
                with grpc.insecure_channel(self.registry_addr) as channel:
                    contract_pb2_grpc.RegistryServiceStub(channel).UnregisterAgent(
                        contract_pb2.UnregisterAgentRequest(agent_id=self.agent_id), timeout=2,
                    )
            except grpc.RpcError:
                log.warning("could not unregister agent_id=%s", self.agent_id)
            self._registered = False
        if self._server is not None:
            self._server.stop(grace).wait(timeout=grace + 1)
            self._server = None

    def serve(self):
        self._start_server()
        try:
            self._server.wait_for_termination()
        finally:
            self.stop()

    def run(self):
        self.start()
        try:
            self._server.wait_for_termination()
        finally:
            self.stop()
