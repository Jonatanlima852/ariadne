import logging
import os
import time
import threading
from dataclasses import dataclass
from typing import Any, Mapping

try:
    from pydantic import BaseModel
except ImportError as error:
    raise ImportError("LLM support requires ariadne-sdk[llm]; in this checkout use uv sync --project sdk/python --extra llm") from error

from ariadne_sdk.agent import Agent
from ariadne_sdk.models import Task, TaskResult

log = logging.getLogger(__name__)


class LlmValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str


@dataclass(frozen=True)
class LlmCapability:
    """Declara prompt(goal, payload), schema e mapeamento de uma capacidade."""
    name: str
    prompt: Any
    output_schema: type[BaseModel]
    result_mapper: Any = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("LLM capability requires a name")
        if not callable(self.prompt) and not isinstance(self.prompt, Prompt):
            raise TypeError("prompt must be Prompt or callable(goal, payload)")
        if not isinstance(self.output_schema, type) or not issubclass(self.output_schema, BaseModel):
            raise TypeError("output_schema must be a Pydantic BaseModel class")
        if self.result_mapper is not None and not callable(self.result_mapper):
            raise TypeError("result_mapper must be callable")


def llm_capability(capability_id, *, output_schema, result_mapper=None):
    """Declara uma capability OpenAI com saída estruturada.

    ``output_schema`` é um modelo Pydantic entregue ao Responses API.
    ``result_mapper`` é opcional e converte o modelo validado em um dict
    de domínio antes de o SDK montar o ``TaskResult``.
    """
    if not isinstance(output_schema, type) or not issubclass(output_schema, BaseModel):
        raise TypeError("output_schema must be a Pydantic BaseModel class")

    def decorate(method):
        method._ariadne_llm_capability = {
            "id": capability_id,
            "output_schema": output_schema,
            "result_mapper": result_mapper,
        }
        return method

    return decorate


_OPERATIONAL_FIELDS = {
    "task_id",
    "agent_id",
    "assigned_agent_id",
    "trace",
    "trace_id",
    "span_id",
    "parent_span_id",
    "status",
    "attempt",
    "retry_policy",
    "selection_policy",
    "created_at",
    "completed_at",
}


def _reject_operational_fields(value: Any, path="output"):
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in _OPERATIONAL_FIELDS:
                raise LlmValidationError(
                    f"model output cannot define operational field: {path}.{key}"
                )
            _reject_operational_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_operational_fields(nested, f"{path}[{index}]")


def _usage_metadata(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif not isinstance(usage, Mapping):
        usage = {
            key: getattr(usage, key)
            for key in ("input_tokens", "output_tokens", "total_tokens")
            if getattr(usage, key, None) is not None
        }
    return {key: value for key, value in dict(usage).items() if value is not None}


class LlmAgent(Agent):
    """Agente OpenAI com contrato, dispatch e structured output no SDK."""

    runtime_name = "python-sdk-openai"
    model = "gpt-5.6-luna"

    def __init__(self, model=None, openai_client=None, handlers=None,
                 prompt=None, output_schema=None, result_mapper=None, **kwargs):
        super().__init__(**kwargs)
        self.model = model or os.getenv("LLM_MODEL", type(self).model)
        self._openai = openai_client
        self._client_lock = threading.Lock()
        self._handlers = self._discover_handlers()
        if prompt is not None or output_schema is not None:
            if handlers is not None or len(self.capabilities) != 1:
                raise ValueError("prompt/output_schema require exactly one capability and no handlers")
            handlers = [LlmCapability(self.capabilities[0], prompt, output_schema, result_mapper)]
        for declaration in handlers or ():
            if not isinstance(declaration, LlmCapability):
                raise TypeError("handlers must contain LlmCapability declarations")
            if declaration.name in self._handlers:
                raise ValueError(f"duplicate LLM capability: {declaration.name}")
            handler = declaration.prompt
            if isinstance(handler, Prompt):
                handler = lambda goal, context, value=handler: value
            self._handlers[declaration.name] = (handler, {
                "output_schema": declaration.output_schema, "result_mapper": declaration.result_mapper,
            })
        if not self.capabilities:
            self.capabilities = list(self._handlers)
        if not self._handlers or set(self.capabilities) != set(self._handlers):
            raise ValueError("declared capabilities must match LLM handlers")

    def _client(self):
        # Construir/validar uma descrição não exige credenciais nem clientes.
        with self._client_lock:
            if self._openai is None:
                try:
                    from openai import OpenAI
                except ImportError as error:
                    raise RuntimeError("install ariadne-sdk[llm] to execute LLM agents") from error
                self._openai = OpenAI()
            return self._openai

    def _discover_handlers(self):
        handlers = {}
        for name in dir(self):
            method = getattr(self, name)
            declaration = getattr(method, "_ariadne_llm_capability", None)
            if declaration is None:
                continue
            capability = declaration["id"]
            if capability in handlers:
                raise ValueError(f"duplicate LLM capability: {capability}")
            handlers[capability] = (method, declaration)
        return handlers

    def _requested_capability(self, task):
        requested = [
            item for item in task.required_capabilities if item in self._handlers
        ]
        if len(requested) != 1:
            raise LlmValidationError(
                "task must request exactly one supported LLM capability"
            )
        return requested[0]

    def handle(self, task: Task) -> TaskResult:
        retryable = False
        started = time.perf_counter()
        try:
            capability = self._requested_capability(task)
            handler, declaration = self._handlers[capability]
            context = dict(task.payload)
            prompt = handler(task.goal, context)
            if not isinstance(prompt, Prompt):
                raise LlmValidationError("LLM capability handler must return Prompt")

            response = self._client().responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                text_format=declaration["output_schema"],
            )
            parsed = response.output_parsed
            if parsed is None:
                raise LlmValidationError(
                    "OpenAI response did not contain structured output"
                )

            mapper = declaration["result_mapper"]
            output = mapper(parsed) if mapper else parsed.model_dump()
            if not isinstance(output, dict):
                raise LlmValidationError("result_mapper must return an object")
            _reject_operational_fields(output)
        except (LlmValidationError, ValueError) as error:
            message = str(error)
        except Exception as error:
            log.exception(
                "OpenAI call failed task_id=%s error_type=%s",
                task.task_id,
                type(error).__name__,
            )
            message = f"OpenAI call failed ({type(error).__name__})"
            retryable = True
        else:
            metadata = {
                "provider": "openai",
                "model": self.model,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
            usage = _usage_metadata(response)
            if usage:
                metadata["usage"] = usage
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status="TASK_STATUS_COMPLETED",
                trace=task.trace,
                output=output,
                metadata=metadata,
            )

        return TaskResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            status="TASK_STATUS_FAILED",
            trace=task.trace,
            error_code="ERROR_CODE_EXECUTION_FAILED",
            error_message=message,
            retryable=retryable,
        )

    def execute_task(self, task):
        """Compatibilidade temporária com chamadas locais baseadas em protobuf."""
        friendly = task if isinstance(task, Task) else Task.from_proto(task)
        result = self.handle(friendly)
        return result if isinstance(task, Task) else result.to_proto()
