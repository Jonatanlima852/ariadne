import { formatMs, StatusBadge } from "./ui.jsx";
import ReadableResult from "./ReadableResult.jsx";
export default function Overview({ report }) {
  const outcome = window.TGInspector.domainOutcome(report);
  const scene = window.AriadnePresentation.describe(report);
  return (
    <div className="analysis-view">
      <section className="content-card">
        <h2>{scene.title}</h2>
        <div className="outcome-grid">
          <div>
            <small>Execução completa</small>
            <StatusBadge status={report.status} />
          </div>
          <div>
            <small>Repetição selecionada</small>
            <StatusBadge status={report.result.status} />
          </div>
          <div>
            <small>Duração do pedido</small>
            <strong>
              {formatMs(
                report.result.client_duration_ms ?? report.result.duration_ms,
              )}
            </strong>
          </div>
          <div>
            <small>Preparação, execução e encerramento</small>
            <strong>{formatMs(report.summary.elapsed_ms)}</strong>
          </div>
        </div>
        <p className="section-note">
          As durações têm escopos diferentes. Não são uma medida isolada do
          custo do runtime.
        </p>
      </section>
      <section className="content-card">
        <h2>Avaliação da resposta</h2>
        <p>
          {outcome.mission === "Sem decisão de viabilidade"
            ? "Este resultado não declara a viabilidade de uma missão."
            : outcome.mission}
        </p>
        <strong>{outcome.validity}</strong>
        <p className="section-note">
          Uma execução concluída não comprova a validade da resposta. Uma recusa
          pode ser correta quando a missão é impossível.
        </p>
      </section>
      {report.demo && (
        <section className="content-card">
          <h2>Sobre este exemplo</h2>
          <p>{report.demo.limits}</p>
          <p>Registrado em {report.demo.recorded_at}.</p>
        </section>
      )}
      <section className="content-card">
        <h2>Participantes e resultados</h2>
        {report.rows.map((row, index) => (
          <article className="analysis-step" key={row.name}>
            <h3>
              Etapa {index + 1} ·{" "}
              {scene.agents.find((agent) => agent.id === row.agent_id)?.name ||
                "Agente não informado"}
            </h3>
            <StatusBadge status={row.status} />
            <ReadableResult
              value={row.output}
              onDetails={() => {
                window.location.hash = new URLSearchParams({
                  ...Object.fromEntries(
                    new URLSearchParams(window.location.hash.slice(1)),
                  ),
                  tab: "details",
                }).toString();
              }}
            />
          </article>
        ))}
      </section>
    </div>
  );
}
