import { Icon, StatusBadge, formatMs } from './ui.jsx';

export default function RunBrowser({ runs, loading, error, onRefresh, onSelect, onSample }) {
  return <main className="runs-layout">
    <section className="runs-heading">
      <div><span className="kicker">EXECUÇÕES LOCAIS</span><h1>Escolha uma execução.</h1><p>A interface lê as evidências disponíveis em <code>.ariadne/runs</code> por meio da API local.</p></div>
      <button className="secondary" onClick={onRefresh} disabled={loading}><Icon name="refresh"/>Atualizar</button>
    </section>
    {error && <div className="api-error"><Icon name="warning"/><div><strong>Não foi possível acessar a API</strong><p>{error}</p><code>uv run --project tools/inspector/api uvicorn app:app --app-dir tools/inspector/api --port 8787</code></div></div>}
    <section className="run-grid">
      {runs.map(run => <button className="run-card" key={run.id} onClick={() => onSelect(run.id)}>
        <div className="run-card-top"><StatusBadge status={run.status}/><Icon name="arrow"/></div>
        <h2>{run.scenario}</h2><code>{run.id}</code>
        <div className="run-stats"><span><small>Duração</small>{formatMs(run.elapsed_ms)}</span><span><small>Eventos</small>{run.event_count}</span><span><small>Ambiente</small>{run.environment || '—'}</span></div>
      </button>)}
      {!loading && !error && !runs.length && <div className="no-runs"><Icon name="layers" size={28}/><h2>Nenhuma execução encontrada</h2><p>Execute um cenário e atualize esta página.</p></div>}
      {loading && <div className="no-runs"><span className="spinner"/><h2>Lendo execuções…</h2></div>}
    </section>
    <section className="sample-banner"><div><span className="kicker">DEMONSTRAÇÃO</span><h2>Explore sem executar um cenário</h2><p>Abra o exemplo registrado de timeout e reassignment.</p></div><button className="primary" onClick={onSample}><Icon name="play"/>Abrir exemplo</button></section>
  </main>;
}
