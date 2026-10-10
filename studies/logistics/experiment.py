"""LOGISTICS_STRATEGY=bdi-only ./tg run studies/logistics/experiment.py"""
import os
from tg_sdk import Scenario, Step
from studies.logistics.bdi import logistics_agent
from studies.logistics.data import load_case, load_world

case = load_case(os.getenv("LOGISTICS_CASE", "avoid-contamination"))
world = load_world()
strategy = os.getenv("LOGISTICS_STRATEGY", "bdi-only")

if strategy == "bdi-only":
    agents = [logistics_agent()]
    tasks = [Step("logistics-execution", case["request"], name="execute",
                  payload={"world": world, "mission": case["mission"]})]
elif strategy in ("llm-only", "hybrid"):
    from studies.logistics.llm import LogisticsLlmAgent
    agents = [LogisticsLlmAgent()]
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
    metadata={"study": "logistics", "strategy": strategy, "case": case, "world": world,
              "model": getattr(agents[0], "model", None)},
)
