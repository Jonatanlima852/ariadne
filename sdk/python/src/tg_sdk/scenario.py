"""Descrição de um experimento, sem canais, clientes ou estado de execução."""

from dataclasses import dataclass, field
from typing import Any, Sequence

from tg_sdk.experiment import Step, compile_steps


@dataclass
class Scenario:
    name: str = "experiment"
    agents: Sequence[Any] = field(default_factory=tuple)
    tasks: Sequence[Step] = field(default_factory=tuple)
    metadata: dict = field(default_factory=dict)
    artifacts: Sequence[str] = field(default_factory=tuple)

    def definition(self):
        return compile_steps(self.tasks)
