"""Entradas Docker dos mesmos agentes usados pelo cenário local."""
import os
import sys
from studies.scenarios.logistics.agents.mission_planner import mission_planner


def make_agent(kind):
    if kind == "planner":
        factory, name, port = mission_planner, "mission-planner", 60054
    elif kind == "assistant":
        from studies.scenarios.logistics.agents.mission_assistant import mission_assistant
        factory, name, port = mission_assistant, "mission-assistant", 60056
    else:
        raise ValueError(f"unknown logistics agent: {kind}")
    return factory(agent_id=os.getenv("AGENT_ID", f"{name}-01"),
                   name=os.getenv("AGENT_NAME", name),
                   host=os.getenv("AGENT_HOST", "localhost"),
                   port=int(os.getenv("AGENT_PORT", str(port))),
                   registry_addr=os.getenv("REGISTRY_ADDR", "localhost:50051"))


if __name__ == "__main__":
    make_agent(sys.argv[1]).run()
