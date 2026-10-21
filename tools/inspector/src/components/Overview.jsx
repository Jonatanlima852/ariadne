import { Icon, StatusBadge, display, formatMs } from "./ui.jsx";

function MetricCard({ icon, label, children, accent }) {
  return (
    <article className={`metric-card ${accent || ""}`}>
      <div className="metric-icon">
        <Icon name={icon} />
      </div>
      <div>
        <span>{label}</span>
        <strong>{children}</strong>
      </div>
    </article>
  );
}

export default function Overview({ report, origin }) {
  const outcome = window.TGInspector.domainOutcome(report);
  return (
    <>
      <section className="hero-card">
        <div>
          <span className="kicker">{origin}</span>
          <h1>{report.scenario}</h1>
          <p>
            Snapshot de evidências da execução. Os valores vêm dos arquivos
            registrados, não de serviços ativos.
          </p>
        </div>
        <StatusBadge status={report.status} />
      </section>
      <section className="metrics-grid">
        <MetricCard icon="activity" label="Estado" accent="green">
          {report.status}
        </MetricCard>
        <MetricCard icon="layers" label="Resultado">
          {report.kind}
        </MetricCard>
        <MetricCard icon="clock" label="Duração total">
          {formatMs(report.summary.elapsed_ms)}
        </MetricCard>
        <MetricCard icon="file" label="Eventos">
          {report.events.length}
        </MetricCard>
      </section>
      {report.demo && (
        <section className="content-card">
          <h2>{report.demo.title}</h2>
          <p>{report.demo.description}</p>
          <p>
            Origem: {report.demo.origin} · {report.demo.recorded_at}
          </p>
          <p>{report.demo.limits}</p>
        </section>
      )}
      <section className="content-card">
        <h2>Como interpretar o resultado</h2>
        {report.analysis && (
          <p>
            Avaliação selecionada: {report.analysis.id} ·{" "}
            {report.analysis.generated_at}
          </p>
        )}
        <div className="outcome-grid">
          <div>
            <small>Execução completa</small>
            <strong>{report.status}</strong>
          </div>
          <div>
            <small>Workflow/amostra selecionada</small>
            <strong>{report.result.status || "Não informado"}</strong>
          </div>
          <div>
            <small>Decisão do agente</small>
            <strong>{outcome.mission}</strong>
          </div>
          <div>
            <small>Avaliação de domínio</small>
            <strong>{outcome.validity}</strong>
          </div>
        </div>
        <p className="section-note">
          Concluir uma execução não comprova a validade da resposta. Uma recusa
          pode ser correta quando a missão é impossível.
        </p>
      </section>
      <section className="context-strip">
        <div>
          <span>Trace ID</span>
          <code>{display(report.trace)}</code>
        </div>
        <div>
          <span>Ambiente</span>
          <strong>{display(report.environment)}</strong>
        </div>
        <div>
          <span>Arquivos</span>
          <strong>{report.names.length} reconhecidos</strong>
        </div>
      </section>
      {report.summary.error && (
        <p className="error-message">
          <Icon name="warning" />
          {report.summary.error}
        </p>
      )}
      {!!report.warnings.length && (
        <section className="warning-list">
          <h2>
            <Icon name="warning" />
            Pontos de atenção
          </h2>
          {report.warnings.map((warning, index) => (
            <p key={index}>{warning}</p>
          ))}
        </section>
      )}
    </>
  );
}
