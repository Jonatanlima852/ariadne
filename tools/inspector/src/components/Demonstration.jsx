import { useEffect, useMemo, useState } from "react";
import ReadableResult from "./ReadableResult.jsx";

function Avatar({ type = "Agente" }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="agent-avatar">
      {type === "LLM" ? (
        <>
          <path d="M9 10h30v22H23l-8 7v-7H9z" />
          <path d="M16 18h16M16 24h10" />
        </>
      ) : type === "BDI" ? (
        <>
          <path d="M12 11h24v28H12zM18 11V7h12v4" />
          <path d="m16 20 3 3 5-6M26 21h6m-16 9 3 3 5-6M26 31h6" />
        </>
      ) : (
        <>
          <rect x="9" y="13" width="30" height="26" rx="9" />
          <path d="M24 13V7m-3 0h6M16 32h16" />
          <circle cx="17" cy="23" r="2" />
          <circle cx="31" cy="23" r="2" />
        </>
      )}
    </svg>
  );
}

export default function Demonstration({ report, onDetails, onAnalysis }) {
  const scene = useMemo(
    () => window.AriadnePresentation.describe(report),
    [report],
  );
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selected, setSelected] = useState(null);
  const last = scene.frames.length - 1;
  useEffect(() => {
    if (!playing || index >= last) {
      if (playing) setPlaying(false);
      return;
    }
    const timer = setTimeout(
      () => setIndex((value) => Math.min(last, value + 1)),
      2200 / speed,
    );
    return () => clearTimeout(timer);
  }, [playing, index, last, speed]);
  const snapshot = window.AriadnePresentation.at(scene, index);
  const current = snapshot.frame;
  const agentCount = scene.agents.length;
  const height = Math.max(390, 130 + agentCount * 155);
  const middle = height / 2;
  const positions = Object.fromEntries(
    scene.agents.map((agent, i) => [agent.id, { x: 720, y: 120 + i * 155 }]),
  );
  const point = (place) =>
    positions[place] ||
    {
      runtime: { x: 365, y: middle },
      response: { x: 1050, y: middle },
      request: { x: 100, y: middle },
    }[place];
  const selectedAgent = scene.agents.find((agent) => agent.id === selected);
  const outcome = window.TGInspector.domainOutcome(report);
  const output =
    report.result.output ??
    (report.rows.length === 1 ? report.rows[0].output : undefined);
  const time =
    current.elapsed == null
      ? ""
      : `${current.elapsed.toLocaleString("pt-BR", { maximumFractionDigits: 3 })} s após o início`;
  const step = (direction) => {
    setPlaying(false);
    setIndex((value) => Math.max(0, Math.min(last, value + direction)));
  };
  return (
    <div className="demonstration">
      <header className="demo-heading">
        <span className="kicker">AGENTES EM COOPERAÇÃO</span>
        <h1>{scene.title}</h1>
        <p>{scene.description}</p>
      </header>
      <div className="mission-strip">
        <span className="mission-symbol" aria-hidden="true">
          ↗
        </span>
        <div>
          <small>O pedido</small>
          <p>{scene.request}</p>
        </div>
        <span className="participant-count">
          {agentCount} {agentCount === 1 ? "agente" : "agentes"} ·{" "}
          {scene.tasks.length} {scene.tasks.length === 1 ? "etapa" : "etapas"}
        </span>
      </div>
      <section
        className="theatre"
        aria-label="Percurso das tarefas pelos agentes"
      >
        <div className="theatre-heading">
          <h2>O caminho do trabalho</h2>
          <span>Reprodução de uma execução registrada</span>
        </div>
        <div className="agent-scene-scroll">
          <svg
            viewBox={`0 0 1180 ${height}`}
            className="agent-scene"
            role="group"
            aria-label="Pedido, Ariadne, agentes participantes e resposta"
          >
            <defs>
              <marker
                id="journey-arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M0 0 10 5 0 10z" fill="context-stroke" />
              </marker>
            </defs>
            <path
              d={`M165 ${middle} H290`}
              className={`journey-line ${index > 0 ? "traversed" : ""}`}
              markerEnd="url(#journey-arrow)"
            />
            <path
              d={`M365 ${middle - 65} V30 H1050 V${middle - 55}`}
              className={`journey-line response-line ${current.kind === "finished" ? "current" : ""}`}
              markerEnd="url(#journey-arrow)"
            />
            <text x="1000" y="20" textAnchor="end" className="route-label">
              Resposta reunida pelo Ariadne
            </text>
            {scene.agents.map((agent) => {
              const p = positions[agent.id],
                state = snapshot.agents[agent.id];
              return (
                <g key={agent.id}>
                  <path
                    d={`M440 ${middle} C530 ${middle} 520 ${p.y} 600 ${p.y}`}
                    className={`journey-line ${state.tone !== "waiting" ? "traversed" : ""} ${current.agent === agent.id ? "current" : ""}`}
                    markerStart="url(#journey-arrow)"
                    markerEnd="url(#journey-arrow)"
                  />
                  <rect
                    x="600"
                    y={p.y - 52}
                    width="240"
                    height="105"
                    rx="22"
                    className={`agent-station ${state.tone} ${selected === agent.id ? "selected" : ""}`}
                  />
                  <foreignObject x="608" y={p.y - 48} width="224" height="98">
                    <button
                      className="agent-station-button"
                      onClick={() =>
                        setSelected(selected === agent.id ? null : agent.id)
                      }
                      aria-pressed={selected === agent.id}
                    >
                      <Avatar type={agent.type} />
                      <span>
                        <small>{agent.type}</small>
                        <strong>{agent.name}</strong>
                        <em>{state.label}</em>
                      </span>
                    </button>
                  </foreignObject>
                </g>
              );
            })}
            <g transform={`translate(100,${middle})`}>
              <circle r="52" className="scene-endpoint" />
              <text textAnchor="middle" y="5" className="endpoint-symbol">
                ↗
              </text>
              <text textAnchor="middle" y="85" className="station-label">
                Pedido
              </text>
            </g>
            <g transform={`translate(365,${middle})`}>
              <rect
                x="-75"
                y="-65"
                width="150"
                height="130"
                rx="35"
                className="runtime-station"
              />
              <text textAnchor="middle" y="-5" className="runtime-letter">
                A
              </text>
              <text textAnchor="middle" y="30" className="runtime-name">
                Ariadne
              </text>
              <text textAnchor="middle" y="98" className="station-label">
                Coordena o trabalho
              </text>
            </g>
            <g transform={`translate(1050,${middle})`}>
              <circle
                r="52"
                className={`scene-endpoint ${current.kind === "finished" ? "done" : ""}`}
              />
              <text textAnchor="middle" y="8" className="endpoint-symbol">
                {current.kind === "finished" ? "✓" : "…"}
              </text>
              <text textAnchor="middle" y="85" className="station-label">
                Resposta
              </text>
            </g>
            {scene.tasks.map((task, i) => {
              const state = snapshot.tasks[task.id],
                p = point(state.place);
              const slot = scene.tasks
                .slice(0, i)
                .filter(
                  (other) => snapshot.tasks[other.id].place === state.place,
                ).length;
              if (!p) return null;
              return (
                <g
                  key={task.id}
                  className={`task-token ${state.tone}`}
                  style={{
                    transform: `translate(${p.x - 38}px, ${p.y + 105 + slot * 28}px)`,
                  }}
                >
                  <rect width="76" height="25" rx="8" />
                  <text x="38" y="17" textAnchor="middle">
                    Tarefa {task.number}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
        <div className="journey-legend">
          <span>
            <i className="legend-dot" />
            Agente em atividade
          </span>
          <span>
            <i className="legend-dot warning" />
            Tentativa com dificuldade
          </span>
          <span>
            As tarefas são coordenadas pelo Ariadne. As conexões não representam
            mensagens diretas entre agentes.
          </span>
        </div>
        {selectedAgent && (
          <div className="participant-detail">
            <Avatar type={selectedAgent.type} />
            <div>
              <h3>{selectedAgent.name}</h3>
              <p>{selectedAgent.role}</p>
            </div>
            <button onClick={onDetails}>Ver registro técnico</button>
          </div>
        )}
        <div className="story-caption" aria-live="polite">
          <span className="story-number">
            {String(index + 1).padStart(2, "0")}
          </span>
          <div>
            <p>{current.text}</p>
            {time && <small>Tempo real: {time}</small>}
          </div>
        </div>
        {last > 0 ? (
          <div className="story-controls">
            <button
              className="play-story"
              onClick={() => {
                if (index === last) setIndex(0);
                setPlaying(!playing);
              }}
            >
              {playing
                ? "Ⅱ Pausar"
                : index === last
                  ? "↺ Reproduzir novamente"
                  : "▶ Reproduzir"}
            </button>
            <button
              onClick={() => step(-1)}
              disabled={index === 0}
              aria-label="Acontecimento anterior"
            >
              ←
            </button>
            <span>
              {index + 1} de {last + 1}
            </span>
            <button
              onClick={() => step(1)}
              disabled={index === last}
              aria-label="Próximo acontecimento"
            >
              →
            </button>
            <label>
              Ritmo{" "}
              <select
                value={speed}
                onChange={(event) => setSpeed(Number(event.target.value))}
              >
                <option value="0.5">Lento</option>
                <option value="1">Normal</option>
                <option value="2">Rápido</option>
              </select>
            </label>
            <button
              onClick={() => {
                setPlaying(false);
                setIndex(last);
              }}
            >
              Ver desfecho
            </button>
            <small>Ritmo didático; não representa a duração real.</small>
          </div>
        ) : (
          <p className="no-data">
            Sem eventos suficientes para reproduzir o percurso. Os participantes
            e a resposta registrada continuam disponíveis.
          </p>
        )}
      </section>
      <section className="story-outcome">
        <div>
          <span className="kicker">DESFECHO REGISTRADO</span>
          <h2>
            {window.AriadnePresentation.status(
              report.result.status || report.status,
            )}
          </h2>
          <ReadableResult value={output} onDetails={onDetails} />
          {outcome.evaluation && (
            <p className="domain-verdict">{outcome.validity}</p>
          )}
          <p className="section-note">
            Resposta final da execução, independente do ponto da reprodução.
          </p>
        </div>
        <button onClick={onAnalysis}>Explorar a análise →</button>
      </section>
      {scene.tasks.length > 1 && (
        <section className="task-story">
          <h2>Como as etapas se conectam</h2>
          {scene.tasks.map((task) => (
            <article key={task.id}>
              <span>{task.number}</span>
              <div>
                <h3>{task.name}</h3>
                <p>
                  {task.dependencies.length
                    ? `Depende ${task.dependencies.length === 1 ? "da etapa" : "das etapas"} ${task.dependencies.map((id) => scene.tasks.find((item) => item.id === id)?.number || "?").join(", ")}${task.bindings.length ? " e recebe resultados anteriores." : "."}`
                    : "Sem dependência declarada de outras etapas."}
                </p>
              </div>
            </article>
          ))}
        </section>
      )}
      {report.warnings.length > 0 && (
        <p className="story-notice">
          Há observações sobre a integridade deste registro.{" "}
          <button onClick={onDetails}>Consultar detalhes</button>
        </p>
      )}
    </div>
  );
}
