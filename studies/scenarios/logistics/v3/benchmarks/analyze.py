"""Análise da v3: reutiliza o analisador da v2 com a linha de base ``single-llm-v3``.

  python -m studies.scenarios.logistics.v3.benchmarks.analyze --input .ariadne/logistics-v3/<coleta>/results.json \
    --output /tmp/logistics-v3-analysis --no-plots
Com figuras: uv run --no-project --with matplotlib python -m studies.scenarios.logistics.v3.benchmarks.analyze ...

As colunas lidas são as mesmas da v2 (atendimento, prazo, tempo, tokens,
distância, energia, rejeições); rodadas, ciclos BDI, paralelismo e
reatribuições ficam em ``results.json`` e em ``comparison.md`` da coleta.
"""
import sys

from studies.scenarios.logistics.v2.benchmarks import analyze as v2

v2.BASELINE = 'single-llm-v3'
v2.LABELS = {'single-llm-v3': 'Single LLM (missão)', 'ariadne-v3': 'Ariadne v3 (planejador + BDI)'}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--title' not in argv:
        argv += ['--title', 'Logística v3: comparação por caso']
    return v2.main(argv)


if __name__ == '__main__':
    sys.exit(main())
