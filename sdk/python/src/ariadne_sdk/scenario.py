"""Descrição de um experimento, sem canais, clientes ou estado de execução."""

from dataclasses import dataclass, field
from typing import Any, Sequence

from ariadne_sdk.experiment import Step, compile_steps
from ariadne_sdk.mission import Mission


@dataclass
class Scenario:
    """``tasks`` declara um DAG fixo; ``mission`` delega a decomposição a um
    planejador. Um cenário usa um ou outro, nunca os dois."""

    name: str = "experiment"
    agents: Sequence[Any] = field(default_factory=tuple)
    tasks: Sequence[Step] = field(default_factory=tuple)
    metadata: dict = field(default_factory=dict)
    artifacts: Sequence[str] = field(default_factory=tuple)
    mission: Mission | None = None
    # Variáveis de ambiente consultadas ao carregar a descrição; preenchido pelo loader.
    environment: Sequence[str] = field(default_factory=tuple)

    def definition(self):
        if self.mission is not None:
            if not isinstance(self.mission, Mission):
                raise ValueError("scenario.mission must be a Mission")
            if self.tasks:
                raise ValueError("declare either scenario.tasks or scenario.mission, not both")
            self.mission.validate()
            return []
        return compile_steps(self.tasks)
