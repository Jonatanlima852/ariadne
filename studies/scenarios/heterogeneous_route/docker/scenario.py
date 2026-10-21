"""Executa o cenário heterogêneo definido neste diretório."""

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

if __name__ == "__main__":
    runpy.run_path(
        ROOT / "studies/scenarios/heterogeneous_route/client/heterogeneous_demo.py",
        run_name="__main__",
    )
