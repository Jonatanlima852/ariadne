"""Análise da v3: linhas por missão a partir das evidências e comparação com a v2.

    python -m studies.scenarios.logistics.v3.analysis <campanha ou execuções> [--output DIR] [--no-plots]
Com figuras: uv run --no-project --with matplotlib python -m studies.scenarios.logistics.v3.analysis ...

Cada execução de ``./ariadne run`` ou observação de ``./ariadne campaign``
traz ``manifest.json`` (caso, configuração e modo em ``metadata``) e
``mission-result.json``. A análise transforma cada uma em uma linha por
``mission.episode_metrics``, confere o provedor do planejador (substituto em
modo demo, OpenAI no modo real), grava ``results.json`` e ``comparison.md`` e
chama o analisador da v2 sobre as mesmas colunas (atendimento, prazo, tempo,
tokens, distância, energia, rejeições). Rodadas, ciclos BDI, paralelismo e
reatribuições ficam em ``results.json`` e em ``comparison.md``.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

from studies.scenarios.logistics.v2.benchmarks import analyze as v2
from studies.scenarios.logistics.v3.domain.cases import find_case
from studies.scenarios.logistics.v3.mission import DEMO_PROVIDER, episode_metrics

v2.BASELINE = 'single-llm-v3'
v2.LABELS = {'single-llm-v3': 'Single LLM (missão)', 'ariadne-v3': 'Ariadne v3 (planejador + BDI)'}


def table(rows):
    lines = ['| Caso | Configuração | Entregues | No prazo | Rejeitadas | Segundos | Distância | Energia | Rodadas | LLM | Tokens entrada/saída | Ciclos BDI | Paralelo máx. | Reatrib. | Resultado |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in rows:
        seconds = 'ausente' if r['wall_seconds'] is None else f"{r['wall_seconds']:.3f}"
        lines.append(f"| {r['case']} | {r['configuration']} | {r['delivered']}/{r['total_orders']} | {r['on_time']} | "
                     f"{r['rejected_actions']} | {seconds} | {r['distance']} | {r['energy_consumed']} | {r['rounds']} | "
                     f"{r['llm_calls']} | {r['input_tokens']}/{r['output_tokens']} | {r['bdi_cycles']} | "
                     f"{r['max_parallel_steps']} | {r['reassignments']} | {r['result']} |")
    return '\n'.join(lines) + '\n'


def check_provider(document, *, demo, model):
    """O planejador deve ser o substituto (demo) ou o modelo pedido (real)."""
    for item in document.get('rounds', []):
        metadata = (item.get('planner_result') or {}).get('metadata') or {}
        provider = metadata.get('provider')
        if provider in (None, 'none'):
            continue  # atalho sem modelo (tudo entregue, nada viável)
        expected = DEMO_PROVIDER if demo else 'openai'
        if provider != expected or (not demo and model and metadata.get('model') != model):
            raise ValueError(f"round {item.get('round')}: planner provider/model {provider}/{metadata.get('model')} "
                             f'differs from the requested configuration')


def run_directories(paths):
    """Execuções (contêm ``manifest.json``) ou campanhas (``runs/*/manifest.json``)."""
    found = []
    for path in paths:
        path = Path(path).resolve()
        if (path / 'manifest.json').is_file():
            found.append(path)
        else:
            found.extend(sorted(candidate.parent for candidate in path.glob('runs/*/manifest.json')))
    return list(dict.fromkeys(found))


def row_for(directory, *, model):
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    metadata = manifest.get('metadata') or {}
    case, configuration = find_case(metadata['case']), metadata['configuration']
    demo = metadata.get('execution_kind') == 'deterministic-integration-demo'
    saved = directory / 'mission-result.json'
    document, error = {}, None
    if saved.is_file():
        document = json.loads(saved.read_text(encoding='utf-8'))
        try:
            check_provider(document, demo=demo, model=model)
        except ValueError as failure:
            error = str(failure)
    else:
        summary = json.loads((directory / 'summary.json').read_text(encoding='utf-8')) if (directory / 'summary.json').is_file() else {}
        error = summary.get('error') or f"run {summary.get('status', 'unknown')} without mission-result.json"
    row = episode_metrics(document, case=case, configuration=configuration, demo=demo)
    row.update(run=str(directory), execution_kind=metadata.get('execution_kind'), model=None if demo else model)
    if error:
        row.update(result='error', error=error, stop_reason=error)
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inputs', nargs='+', type=Path, help='pastas de campanha ou de execução')
    parser.add_argument('--output', type=Path, help='pasta dos relatórios; padrão: analysis-<id> dentro da primeira entrada')
    parser.add_argument('--model', help='modelo esperado dos planejadores reais (padrão: LLM_MODEL ou gpt-5.6-luna)')
    parser.add_argument('--title', default='Logística v3: comparação por caso')
    parser.add_argument('--no-plots', action='store_true', help='só CSV e Markdown, sem matplotlib')
    args = parser.parse_args(argv)
    import os
    model = args.model or os.getenv('LLM_MODEL', 'gpt-5.6-luna')
    directories = run_directories(args.inputs)
    if not directories:
        parser.error('no run with manifest.json found in the given paths')
    output = (args.output or args.inputs[0].resolve() / ('analysis-' + uuid.uuid4().hex[:8])).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = [row_for(directory, model=model) for directory in directories]
    kinds = sorted({row['execution_kind'] for row in rows if row.get('execution_kind')})
    (output / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (output / 'comparison.md').write_text(f"Execução: {', '.join(kinds) or 'desconhecida'}. Modelo: {model}. "
                                          f"Laço de missão no orquestrador Go. Gerado em {datetime.now(timezone.utc).isoformat()}.\n\n" + table(rows))
    print(table(rows))
    code = v2.main(['--input', str(output / 'results.json'), '--output', str(output), '--title', args.title] + (['--no-plots'] if args.no_plots else []))
    print(f'Resultados: {output / "results.json"}\nTabela: {output / "comparison.md"}')
    return 1 if any(row.get('error') for row in rows) else code


if __name__ == '__main__':
    sys.exit(main())
