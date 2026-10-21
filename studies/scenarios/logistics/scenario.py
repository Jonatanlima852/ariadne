"""LOGISTICS_STRATEGY=bdi-only ./ariadne run studies/scenarios/logistics/scenario.py"""
import os
from ariadne_sdk import Scenario, Step
from studies.scenarios.logistics.agents.bdi import logistics_agent
from studies.scenarios.logistics.data import load_case, load_world

case = load_case(os.getenv("LOGISTICS_CASE", "avoid-contamination"))
world = load_world()
strategy = os.getenv("LOGISTICS_STRATEGY", "bdi-only")

if strategy == "bdi-only":
    agents = [logistics_agent()]
    tasks = [Step("logistics-execution", case["request"], name="execute",
                  payload={"world": world, "mission": case["mission"]})]
elif strategy in ("llm-only", "hybrid"):
    from studies.scenarios.logistics.agents.llm import logistics_llm_agent
    agents = [logistics_llm_agent()]
    if strategy == "llm-only":
        tasks = [Step("logistics-plan", case["request"], name="plan", payload={"world": world})]
    else:
        agents.append(logistics_agent())
        interpret = Step("logistics-interpret", case["request"], name="interpret")
        tasks = [interpret, Step("logistics-execution", "Planeje a missão estruturada", name="execute",
                                 payload={"world": world, "mission": interpret.output["mission"]})]
else:
    raise ValueError(f"unknown logistics strategy: {strategy}")

scenario = Scenario(
    name=f"logistics-{strategy}-{case['id']}", agents=agents, tasks=tasks,
    artifacts=["world.json", "cases.json"],
    metadata={"study": "logistics", "strategy": strategy, "case": case, "world": world,
              "model": getattr(agents[0], "model", None)},
)
