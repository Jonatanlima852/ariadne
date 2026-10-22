import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../sdk/python/src"))

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from ariadne_sdk import BdiAgent, plan
from studies.scenarios.logistics.planning import plan_mission

from beliefs import KNOWN_ROUTES, direct_distance, known_destinations_from

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [route-planner] %(message)s",
)
log = logging.getLogger(__name__)

# casa frases como "de A para B" ou "from A to B" no goal em linguagem
# natural — usado como reserva quando o payload estruturado não traz
# origin/destination (ex.: outro agente só preencheu task.bdi.goal)
_GOAL_ROUTE_PATTERN = re.compile(
    r"(?:de|from)\s+(?P<origin>\w+)\s+(?:para|to)\s+(?P<destination>\w+)",
    re.IGNORECASE,
)


class RoutePlanningAgent(BdiAgent):
    """Agente BDI de planejamento de rotas: o desejo é "ir de uma origem
    a um destino"; ariadne_sdk.BdiAgent cuida de selecionar o plano e montar
    o resultado — este agente só sabe extrair o desejo da task e
    interpretar crenças externas vindas via BdiExtension."""

    capabilities = ["route-planning", "logistics-execution"]
    beliefs = KNOWN_ROUTES
    default_agent_id = "route-planner-01"
    default_name = "Route Planner"
    default_port = 60054
    runtime_name = "python-sdk-bdi"

    def desire(self, task):
        """Lê origem e destino, com dois caminhos possíveis:

        1. task.payload (campos 'origin'/'destination') — caminho
           estruturado, preferido.
        2. task.bdi.goal — reserva para quando outro agente (ex.: um
           agente LLM) descreveu o objetivo em linguagem natural via
           BdiExtension em vez de montar o payload estruturado.
        """
        if task.payload.get("mission") and task.payload.get("world"):
            return {
                "kind": "logistics-mission",
                "mission": task.payload["mission"],
                "world": task.payload["world"],
            }

        origin = task.payload.get("origin")
        destination = task.payload.get("destination")
        if origin is not None and destination is not None:
            return {"kind": "route", "origin": str(origin), "destination": str(destination)}

        if task.bdi.get("goal"):
            match = _GOAL_ROUTE_PATTERN.search(task.bdi["goal"])
            if match:
                log.info(
                    "desejo extraído de task.bdi.goal task_id=%s goal=%r",
                    task.task_id, task.bdi["goal"],
                )
                return {"kind": "route", "origin": match.group("origin"), "destination": match.group("destination")}

        return None

    @plan(name="safe_logistics_mission", priority=100)
    def safe_logistics_mission(self, desire, beliefs):
        if desire.get("kind") != "logistics-mission":
            return None
        return plan_mission(desire["world"], desire["mission"])

    @plan(name="direct_route")
    def direct_route(self, desire, beliefs):
        if desire.get("kind") != "route":
            return None
        origin, destination = desire["origin"], desire["destination"]
        distance = direct_distance(origin, destination, beliefs)
        if distance is None:
            return None
        return {
            "cost": distance,
            "reasoning_summary": (
                f"existe uma conexão direta de {origin} para {destination} "
                f"nas crenças (distância {distance})."
            ),
            "origin": origin,
            "destination": destination,
            "route": [origin, destination],
            "distance": distance,
        }

    @plan(name="via_intermediate")
    def via_intermediate(self, desire, beliefs):
        if desire.get("kind") != "route":
            return None
        origin, destination = desire["origin"], desire["destination"]
        best = None
        for intermediate in known_destinations_from(origin, beliefs):
            if intermediate == destination:
                continue
            first_leg = direct_distance(origin, intermediate, beliefs)
            second_leg = direct_distance(intermediate, destination, beliefs)
            if first_leg is None or second_leg is None:
                continue
            total = first_leg + second_leg
            if best is None or total < best["distance"]:
                best = {"intermediate": intermediate, "distance": total}
        if best is None:
            return None
        return {
            "cost": best["distance"],
            "reasoning_summary": (
                f"escala em {best['intermediate']} encontrada nas crenças "
                f"(distância total {best['distance']})."
            ),
            "origin": origin,
            "destination": destination,
            "route": [origin, best["intermediate"], destination],
            "distance": best["distance"],
        }

    @plan(name="unknown_route", priority=-100)
    def unknown_route(self, desire, beliefs):
        if desire.get("kind") != "route":
            return None
        origin, destination = desire["origin"], desire["destination"]
        return {
            "reasoning_summary": (
                f"nenhuma rota conhecida (direta ou com escala) de {origin} "
                f"para {destination}."
            ),
            "origin": origin,
            "destination": destination,
            "route": [],
            "distance": None,
        }

    def merge_external_beliefs(self, beliefs_text):
        """Interpreta task.bdi.beliefs como uma lista JSON de rotas, ex.:

            [{"from": "A", "to": "E", "distance": 12}, ...]

        e mescla no mapa de crenças do agente. Esse é o ponto que permite
        a outro agente (ex.: um agente LLM que consultou um mapa externo)
        entregar conhecimento novo através do contrato comum, em vez de
        cada agente viver isolado com suas próprias crenças fixas.
        """
        try:
            routes = json.loads(beliefs_text)
        except (json.JSONDecodeError, TypeError):
            log.warning("task.bdi.beliefs não é um JSON válido — ignorando")
            return

        added = 0
        for route in routes:
            try:
                key = (route["from"], route["to"])
                self.beliefs[key] = route["distance"]
                added += 1
            except (KeyError, TypeError):
                log.warning("entrada de crença externa ignorada (formato inesperado): %r", route)

        if added:
            log.info("crenças externas mescladas via task.bdi.beliefs: %d rota(s)", added)

    def handle(self, task):
        log.info("task received task_id=%s goal=%s", task.task_id, task.goal)
        result = super().handle(task)
        log.info("task finished task_id=%s status=%s", task.task_id, result.status)
        return result


def main():
    RoutePlanningAgent.from_env().run()


if __name__ == "__main__":
    main()
