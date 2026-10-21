import { useEffect, useState } from "react";
import { inspectorApi } from "../api.js";
import { Icon, StatusBadge, formatMs } from "./ui.jsx";
const SOURCES = {
  samples: "Demonstrações",
  runs: "Minhas execuções",
  campaigns: "Campanhas",
  evaluations: "Avaliações",
};
const SIZE = 12;
export default function RunBrowser({ source, onSource, onSelect, onSample }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState({ items: [], total: 0, warnings: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setPage(0);
    setStatus("");
    setQuery("");
  }, [source]);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      inspectorApi
        .catalog({ source, q: query, status, offset: page * SIZE, limit: SIZE })
        .then((result) => {
          if (!cancelled) setData(result);
        })
        .catch((failure) => {
          if (!cancelled) setError(failure.message);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [source, query, status, page, revision]);
  return (
    <main className="runs-layout">
      <section className="runs-heading">
        <div>
          <span className="kicker">DESCUBRA O ARIADNE</span>
          <h1>Veja os agentes trabalhando juntos.</h1>
          <p>
            Escolha uma história para acompanhar o pedido, os participantes e a resposta.
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => setRevision(revision + 1)}
          disabled={loading}
        >
          <Icon name="refresh" />
          Atualizar
        </button>
      </section>
      <nav className="catalog-tabs" aria-label="Tipo de evidência">
        {Object.entries(SOURCES).map(([key, title]) => (
          <button
            key={key}
            aria-pressed={key === source}
            onClick={() => onSource(key)}
          >
            {title}
          </button>
        ))}
      </nav>
      <div className="toolbar">
        <label className="search-box">
          <Icon name="search" />
          <input
            aria-label="Buscar evidências"
            placeholder="Nome, caso, estratégia ou identificador…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <select
          aria-label="Estado da execução"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(0);
          }}
        >
          <option value="">Todos os estados</option>
          {[
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "RUNNING",
            "AVALIADA",
            "UNKNOWN",
          ].map((value) => (
            <option key={value} value={value}>{window.AriadnePresentation.status(value)}</option>
          ))}
        </select>
      </div>
      {error && (
        <p className="api-error" role="alert">
          {error} · Inicie os serviços com ./ariadne inspect.
        </p>
      )}
      {data.warnings.map((warning) => (
        <p key={warning} className="error-message">
          {warning}
        </p>
      ))}
      {loading ? (
        <p role="status">Lendo catálogo…</p>
      ) : (
        !error && (
          <>
            <section className="run-grid">
              {data.items.map((run) => (
                <button
                  className="run-card"
                  key={run.id}
                  onClick={() => onSelect(run)}
                >
                  <div className="run-card-top">
                    <StatusBadge status={run.status} />
                    <Icon name="arrow" />
                  </div>
                  <div className="cast-preview" aria-hidden="true"><span>↗</span><i/><span className="cast-runtime">A</span><i/><span>♙</span>{run.participant_count > 1 && <span>♙</span>}<i/><span>✓</span></div>
                  <h2>{run.presentation?.title || run.demo?.title || window.AriadnePresentation.title(run.scenario)}</h2>
                  <p>
                    {run.presentation?.description || run.demo?.description ||
                      (run.participant_count ? `${run.participant_count} agentes · ${run.step_count} etapas. Abra para acompanhar o percurso.` : "Explore os resultados registrados deste experimento.")}
                  </p>
                  <div className="run-stats">
                    <span>
                      <small>Registrado em</small>
                      {run.started_at
                        ? new Date(run.started_at).toLocaleString("pt-BR")
                        : "Não informado"}
                    </span>
                    <span>
                      <small>Duração</small>
                      {formatMs(run.elapsed_ms)}
                    </span>
                  </div>
                </button>
              ))}
            </section>
            {!data.items.length && (
              <p className="no-data">
                Nenhuma evidência encontrada nesta seleção.
              </p>
            )}
            <div className="pager">
              <button disabled={page === 0} onClick={() => setPage(page - 1)}>
                Anterior
              </button>
              <span>
                {data.total} registros · página {page + 1} de{" "}
                {Math.max(1, Math.ceil(data.total / SIZE))}
              </span>
              <button
                disabled={(page + 1) * SIZE >= data.total}
                onClick={() => setPage(page + 1)}
              >
                Próxima
              </button>
            </div>
          </>
        )
      )}
      <section className="sample-banner">
        <div>
          <h2>Recuperação de tarefa</h2>
          <p>Exemplo registrado disponível mesmo sem a API.</p>
        </div>
        <button className="primary" onClick={onSample}>
          Abrir exemplo embutido
        </button>
      </section>
    </main>
  );
}
