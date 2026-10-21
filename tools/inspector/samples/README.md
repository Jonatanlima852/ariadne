# Demonstrações registradas

Estes arquivos são cópias de evidências reais, selecionadas para apresentação.
`demo.json` acrescenta título, objetivo, origem e limites; os arquivos de execução
foram copiados sem reescrever identificadores, horários ou caminhos de proveniência.
Não contêm arquivos de ambiente ou credenciais.

| Pasta | Origem | O que observar |
|---|---|---|
| `echo` | Execução local de `examples/echo.py`, 21/10/2026 | Descoberta, atribuição e resposta |
| `workflow` | Execução local de `examples/workflow.py --repeat 2`, 21/10/2026 | Amostras separadas, dependência e binding de texto |
| `recovery` | Execução local de `examples/recovery.py`, 21/10/2026 | Timeout do agente lento e reassignment |
| `logistics-historical` | Coleta `logistics-20261004T-final-v2`, 04/10/2026 | Respostas e métricas de BDI-only, LLM-only e híbrido |

Os três exemplos locais são determinísticos e não usaram LLM. O exemplo logístico
é cópia integral do [JSON publicado](../../../studies/scenarios/logistics/benchmarks/results/logistics-20261004T-final-v2/logistics-results.json),
com chamadas LLM reais da coleta histórica. Não foi feita nova chamada para esta
biblioteca. A interface o apresenta como avaliação; não fabrica workflow ou eventos
a partir das respostas. As limitações estão no [guia de avaliação](../../../docs/evaluation.md).

O registro embutido em `sample.js` continua sendo a recuperação de 08/10/2026,
com formato anterior, e funciona quando a API está indisponível.

Para renovar a biblioteca, faça uma execução identificada, selecione somente
arquivos reconhecidos pelo Inspector e registre origem/limites em `demo.json`.
Não altere métricas ou dados para melhorar a aparência de uma demonstração.

Os caminhos `examples/` acima são os caminhos históricos da coleta. As definições
atuais estão em [studies/scenarios](../../../studies/README.md); as evidências
não foram reescritas durante a reorganização.
