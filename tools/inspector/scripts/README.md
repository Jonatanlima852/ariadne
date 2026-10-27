# Exportação de evidências do Inspector

Estes utilitários exportam dados existentes; não iniciam episódios nem chamam LLMs.
Execute a partir da raiz do repositório:

```sh
node tools/inspector/scripts/export-logistics-flow.mjs --help
node tools/inspector/scripts/export-logistics-flow.mjs \
  --input studies/scenarios/logistics/v2/results/stress-lean/results.json \
  --case s08-cascading-disruptions --configuration ariadne-lean \
  --output /tmp/logistics-flow
uv run --no-project --with playwright --with pillow python \
  tools/inspector/scripts/render-logistics-media.py /tmp/logistics-flow --gif
```

O exportador usa Node e o renderizador compartilhado em `../src/logisticsFlow.js`.
Produz HTML offline, SVGs, quadros e proveniência, sem dependências npm adicionais.
O renderizador de mídia usa Playwright, Pillow e Chrome local (ou Chromium
instalado para Playwright) para produzir PNGs e GIF. As dependências temporárias
não alteram o projeto do Inspector.

Consulte o [guia do Inspector](../README.md) e o
[roteiro da logística](../../../studies/scenarios/logistics/v2/docs/presentation.md).
