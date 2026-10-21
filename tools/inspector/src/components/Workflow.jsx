import { useMemo, useState } from "react";
import { JsonDetails, display } from "./ui.jsx";

export default function Workflow({ report }) {
  const [cursor, setCursor] = useState(0);
  const [selected, setSelected] = useState(null);
  const model = useMemo(() => {
    try {
      return window.TGInspector.graph(report);
    } catch (error) {
      return { nodes: [], error: error.message };
    }
  }, [report]);
  if (model.error) return <p role="alert">{model.error}</p>;
  const replay = window.TGInspector.replay(report, cursor);
  const columns = new Map();
  const positions = Object.fromEntries(
    model.nodes.map((node) => {
      const row = columns.get(node.level) || 0;
      columns.set(node.level, row + 1);
      return [node.id, { x: 25 + node.level * 300, y: 30 + row * 145 }];
    }),
  );
  const width = Math.max(
    600,
    ...model.nodes.map((node) => positions[node.id].x + 275),
  );
  const height = Math.max(
    210,
    ...model.nodes.map((node) => positions[node.id].y + 145),
  );
  const chosen = model.nodes.find((node) => node.id === selected);
  const result = report.rows.find((row) => row.name === selected);
  const current = replay.current;
  const labels = {
    WORKFLOW_STARTED: "Workflow iniciado",
    WORKFLOW_COMPLETED: "Workflow concluído",
    WORKFLOW_FAILED: "Workflow falhou",
    WORKFLOW_STEP_STARTED: "Etapa iniciada",
    WORKFLOW_STEP_COMPLETED: "Etapa concluída",
    TASK_CREATED: "Tarefa criada",
    TASK_ASSIGNED: "Tarefa atribuída",
    TASK_REASSIGNED: "Tarefa reatribuída",
    TASK_TIMEOUT: "Prazo da tentativa esgotado",
    TASK_COMPLETED: "Tarefa concluída",
    TASK_FAILED: "Tentativa falhou",
  };
  return (
    <section className="content-card">
      <div className="section-heading">
        <div>
          <span className="kicker">ESTRUTURA E EXECUÇÃO</span>
          <h2>Workflow e replay</h2>
        </div>
      </div>
      <p className="section-note">
        Reprodução manual de eventos registrados. As setas representam
        dependências de tarefas coordenadas pelo runtime, não mensagens entre
        agentes.
      </p>
      {!model.declared && (
        <p className="warning-list">
          Este registro não contém a definição do workflow. As etapas aparecem
          sem conexões inferidas.
        </p>
      )}
      <div className="replay-controls">
        <button onClick={() => setCursor(0)} disabled={!cursor}>
          Reiniciar
        </button>
        <button onClick={() => setCursor(cursor - 1)} disabled={!cursor}>
          Anterior
        </button>
        <strong>
          Evento {cursor} de {replay.events.length}
        </strong>
        <button
          className="primary"
          onClick={() => setCursor(cursor + 1)}
          disabled={cursor >= replay.events.length}
        >
          Próximo evento
        </button>
        <button
          onClick={() => setCursor(replay.events.length)}
          disabled={cursor >= replay.events.length}
        >
          Ir ao fim
        </button>
      </div>
      <div className="replay-caption" aria-live="polite">
        {current ? (
          <>
            <strong>{labels[current.type] || current.type}</strong>
            <span>
              {current.agent_id || "Runtime"} ·{" "}
              {current.timestamp || "Horário não informado"}
            </span>
            <code>{current.details || current.step_id || current.task_id}</code>
          </>
        ) : (
          <>
            <strong>Início da reprodução</strong>
            <span>Avance para acompanhar atribuições, falhas e conclusão.</span>
          </>
        )}
      </div>
      <div className="graph-scroll">
        <svg
          className="workflow-graph"
          width={width}
          height={height}
          role="img"
          aria-label="Grafo de dependências do workflow"
        >
          <defs>
            <marker
              id="workflow-arrow"
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="3"
              orient="auto"
            >
              <path d="M0,0 L0,6 L8,3 z" fill="currentColor" />
            </marker>
          </defs>
          {model.nodes.flatMap((node) =>
            (node.depends_on || []).map((parent) => {
              const from = positions[parent],
                to = positions[node.id];
              return (
                <path
                  key={`${parent}/${node.id}`}
                  className="graph-edge"
                  d={`M${from.x + 245},${from.y + 50} C${from.x + 275},${from.y + 50} ${to.x - 30},${to.y + 50} ${to.x},${to.y + 50}`}
                  markerEnd="url(#workflow-arrow)"
                />
              );
            }),
          )}
          {model.nodes.map((node) => {
            const position = positions[node.id],
              state = replay.states[node.id];
            const highlighted =
              current &&
              (current.step_id === node.id ||
                (current.task_id &&
                  report.rows.find((row) => row.name === node.id)?.task_id ===
                    current.task_id));
            return (
              <g
                key={node.id}
                transform={`translate(${position.x},${position.y})`}
              >
                <rect
                  width="245"
                  height="110"
                  rx="12"
                  className={`graph-node ${highlighted ? "highlighted" : ""} ${selected === node.id ? "selected" : ""}`}
                />
                <foreignObject x="10" y="8" width="225" height="95">
                  <button
                    className="graph-node-button"
                    onClick={() => setSelected(node.id)}
                    aria-pressed={selected === node.id}
                  >
                    <strong>{node.id}</strong>
                    <span>{state.status}</span>
                    <small>{state.agent || "Agente ainda não atribuído"}</small>
                  </button>
                </foreignObject>
              </g>
            );
          })}
        </svg>
      </div>
      {!model.nodes.length && <p>Nenhuma etapa disponível.</p>}
      {!replay.events.length && (
        <p>
          Não há eventos do runtime disponíveis para reproduzir esta seleção.
        </p>
      )}
      {chosen && (
        <div className="workflow-details">
          <h3>{chosen.id}</h3>
          <p>{chosen.goal || "Objetivo não registrado no manifesto."}</p>
          <p>
            Capacidades: {chosen.capabilities?.join(", ") || "Não informadas"} ·
            Agente neste ponto: {display(replay.states[chosen.id].agent)}
          </p>
          <JsonDetails
            title="Entrada declarada (bindings são resolvidos durante a execução)"
            data={chosen.payload}
          />
          <JsonDetails
            title="Transferências de resultados"
            data={chosen.input_bindings || []}
          />
          {result && (
            <JsonDetails
              title="Resultado final registrado (independente da posição do replay)"
              data={result}
            />
          )}
        </div>
      )}
      {current && <JsonDetails title="Evento atual completo" data={current} />}
    </section>
  );
}
