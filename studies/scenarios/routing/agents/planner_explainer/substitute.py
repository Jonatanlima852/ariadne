"""Substituto determinístico do modelo, para testes e demonstrações sem LLM.

Troca apenas a chamada ao provedor: o agente, os prompts, a validação da
decisão e o protocolo do planejador são os mesmos do caminho real. Não é
uma linha de base nem mede a qualidade de um modelo.
"""
import json
from types import SimpleNamespace

from ariadne_sdk import LlmAgent, PlannerDecision
from ariadne_sdk.llm import PlanBindingDraft, PlanDraft, PlanStepDraft

from .capabilities import EXPLANATION_CAPABILITY, ROUTE_CAPABILITY
from .response_models import Explanation

PROVIDER = "deterministic-integration-substitute"


def decide(request):
    """Rodada 1: PLAN com route -> explain. Rodada 2: DONE a partir do histórico."""
    if not request["history"]:
        context = request["context"]
        route_payload = {key: context[key] for key in ("origin", "destination", "graph") if key in context}
        return PlannerDecision(
            action="PLAN", summary="plan the route, then explain it", reason="",
            output_json="", context_update_json="",
            plan=PlanDraft(workflow_id="route-and-explain", final_step_id="explain", steps=[
                PlanStepDraft(
                    step_id="route", type="MISSION_STEP",
                    goal=f"Planejar rota de {context.get('origin')} para {context.get('destination')}",
                    payload_json=json.dumps(route_payload), required_capabilities=[ROUTE_CAPABILITY],
                    depends_on=[], input_bindings=[],
                ),
                PlanStepDraft(
                    step_id="explain", type="MISSION_STEP", goal="Explicar a rota escolhida",
                    payload_json=json.dumps({"goal": request["goal"]}),
                    required_capabilities=[EXPLANATION_CAPABILITY], depends_on=["route"],
                    input_bindings=[
                        PlanBindingDraft(source_step_id="route", source_path="output", target_field="route"),
                        PlanBindingDraft(source_step_id="route", source_path="metadata.selected_plan",
                                         target_field="selected_plan"),
                    ],
                ),
            ]),
        )
    results = {item["step_id"]: item for item in request["history"][-1].get("step_results", [])}
    failed = [step_id for step_id, item in results.items()
              if item.get("status") != "WORKFLOW_STEP_STATUS_COMPLETED"]
    if failed or {"route", "explain"} - set(results):
        return PlannerDecision(action="ABORT", summary="a step failed", plan=None,
                               reason="steps did not complete: " + ", ".join(failed or ["missing"]),
                               output_json="", context_update_json="")
    route = results["route"]["result"]["output"]
    explanation = results["explain"]["result"]["output"]
    return PlannerDecision(
        action="DONE", summary="route planned and explained", reason="", plan=None,
        output_json=json.dumps({"route": route["route"], "distance": route["distance"],
                                "explanation": explanation["explanation"]}),
        context_update_json="",
    )


def explain(request):
    route = request["context"].get("route", {})
    distance = route.get("distance")
    return Explanation(
        explanation=(f"Rota {' -> '.join(route.get('route', []))} com distância "
                     f"{distance if distance is None else format(distance, 'g')}, "
                     f"escolhida pelo plano {request['context'].get('selected_plan')}."),
        reasoning_summary="Substituto determinístico: repete os valores recebidos no contexto.",
        confidence=1.0,
    )


class DemoClient:
    """Imita ``openai.OpenAI().responses.parse`` para os dois esquemas do agente."""

    def __init__(self):
        self.responses = self

    def parse(self, *, model, input, text_format):
        request = json.loads(input[1]["content"])
        value = decide(request) if text_format is PlannerDecision else explain(request)
        return SimpleNamespace(output_parsed=value, usage=None)


class DemoLlmAgent(LlmAgent):
    def handle(self, task):
        result = super().handle(task)
        result.metadata.update(provider=PROVIDER, model="no-real-model")
        return result
