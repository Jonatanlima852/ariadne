import { useState } from "react";
import { JsonDetails, StatusBadge, formatMs } from "./ui.jsx";
const percent = (value) =>
  typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "Não disponível";
export default function Collection({ detail, onSelect }) {
  const [query, setQuery] = useState("");
  const [strategy, setStrategy] = useState("");
  const [caseId, setCaseId] = useState("");
  const [repetition, setRepetition] = useState("");
  const [page, setPage] = useState(0);
  const document = detail.document;
  const campaign = detail.kind === "campaign";
  const rows = campaign ? detail.observations : document.rows || [];
  const fields = (row) =>
    campaign
      ? {
          strategy: row.parameters?.LOGISTICS_STRATEGY || "",
          caseId: row.parameters?.LOGISTICS_CASE || "",
          repetition: row.repetition,
        }
      : {
          strategy: row.strategy,
          caseId: row.case_id,
          repetition: row.sample || row.repetition,
        };
  const choices = (field) => [
    ...new Set(
      rows
        .map((row) => fields(row)[field])
        .filter((value) => value !== undefined && value !== ""),
    ),
  ];
  const filtered = rows.filter(
    (row) =>
      (!query ||
        JSON.stringify(row)
          .toLocaleLowerCase()
          .includes(query.toLocaleLowerCase())) &&
      (!strategy || fields(row).strategy === strategy) &&
      (!caseId || fields(row).caseId === caseId) &&
      (!repetition || String(fields(row).repetition) === repetition),
  );
  const pages = Math.max(1, Math.ceil(filtered.length / 20)),
    safePage = Math.min(page, pages - 1);
  return (
    <main className="runs-layout">
      <section className="content-card">
        <span className="kicker">
          {campaign ? "CAMPANHA" : "AVALIAÇÃO OFFLINE"}
        </span>
        <h1>
          {detail.demo?.title || document.name || "Resultados logísticos"}
        </h1>
        {detail.demo && (
          <>
            <p>{detail.demo.description}</p>
            <p>
              Origem: {detail.demo.origin} · {detail.demo.recorded_at}
            </p>
            <p>{detail.demo.limits}</p>
          </>
        )}
        {campaign ? (
          <>
            <StatusBadge status={document.status} />
            <p>
              {rows.length} observações registradas de{" "}
              {document.planned_observations ?? "total não informado"}{" "}
              previstas. Abra uma observação para consultar suas amostras e
              eventos.
            </p>
          </>
        ) : (
          <>
            <p>
              Análise registrada em{" "}
              {document.generated_at
                ? new Date(document.generated_at).toLocaleString("pt-BR")
                : "data não informada"}
              . As métricas abaixo vêm do avaliador; não são recalculadas pela
              interface.
            </p>
            {document.model && (
              <p>
                Modelo da coleta: {document.model} ·{" "}
                {document.case_count ?? "Quantidade não informada"} casos ·{" "}
                {document.repetitions ?? "Quantidade não informada"} repetições.
              </p>
            )}
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Estratégia</th>
                    <th>Observações</th>
                    <th>Validade</th>
                    <th>Otimalidade agregada</th>
                    <th>Consistência</th>
                    <th>Latência média</th>
                    <th>Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {(document.summary || []).map((row) => (
                    <tr key={row.strategy}>
                      <td>{row.strategy}</td>
                      <td>{row.runs}</td>
                      <td>{percent(row.valid_rate)}</td>
                      <td>{percent(row.optimal_rate)}</td>
                      <td>{percent(row.consistency_rate)}</td>
                      <td>{formatMs(row.average_latency_ms)}</td>
                      <td>{row.total_tokens}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p>
              A otimalidade agregada inclui rejeições corretas. Confira
              cobertura, denominadores e limitações da coleta antes de comparar
              estratégias.
            </p>
            {(document.limitations || []).map((value, index) => (
              <p key={index} className="section-note">
                {value}
              </p>
            ))}
            <JsonDetails
              title="Cobertura das campanhas"
              data={document.campaigns || []}
            />
          </>
        )}
        {detail.analyses?.length > 0 && (
          <div>
            <h3>Avaliações desta campanha</h3>
            {detail.analyses.map((item, index) => (
              <button key={item.id} onClick={() => onSelect(item)}>
                Avaliação {index + 1}
              </button>
            ))}
          </div>
        )}
        <JsonDetails
          title="Metadados e proveniência"
          data={
            campaign
              ? { ...document, runs: undefined }
              : { ...document, rows: undefined }
          }
        />
      </section>
      <section className="content-card">
        <h2>Observações</h2>
        <div className="toolbar">
          <input
            aria-label="Buscar observações"
            placeholder="Buscar observação…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
          />
          {[
            [strategy, setStrategy, "strategy", "Estratégias"],
            [caseId, setCaseId, "caseId", "Casos"],
            [repetition, setRepetition, "repetition", "Repetições"],
          ].map(([value, setter, field, label]) => (
            <select
              key={field}
              aria-label={label}
              value={value}
              onChange={(event) => {
                setter(event.target.value);
                setPage(0);
              }}
            >
              <option value="">{label}: todas</option>
              {choices(field).map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ))}
        </div>
        {filtered
          .slice(safePage * 20, (safePage + 1) * 20)
          .map((row, index) => (
            <article className="observation" key={index}>
              <h3>
                {fields(row).caseId ||
                  `Observação ${safePage * 20 + index + 1}`}{" "}
                · {fields(row).strategy}
              </h3>
              <p>Repetição/amostra {fields(row).repetition}</p>
              {campaign ? (
                <>
                  <StatusBadge status={row.status} />
                  {row.available ? (
                    <button onClick={() => onSelect(row)}>
                      Abrir execução
                    </button>
                  ) : (
                    <p>
                      Evidências de execução indisponíveis. Consulte o registro
                      abaixo.
                    </p>
                  )}
                </>
              ) : (
                <>
                  <p>
                    {row.runtime_error
                      ? "Falha operacional"
                      : "Sem falha operacional registrada"}{" "}
                    ·{" "}
                    {row.candidate?.feasible === false
                      ? "Missão recusada"
                      : "Plano proposto"}{" "}
                    ·{" "}
                    {row.evaluation?.correct_rejection
                      ? "Rejeição correta"
                      : row.evaluation?.valid === true
                        ? "Resposta válida"
                        : row.evaluation?.valid === false
                          ? "Resposta inválida"
                          : "Validade não informada"}
                  </p>
                </>
              )}
              {!campaign && detail.references?.[row.execution_id] && (
                <button
                  onClick={() =>
                    onSelect({
                      ...detail.references[row.execution_id],
                      sample: row.sample,
                    })
                  }
                >
                  Abrir evidências da execução
                </button>
              )}
              <JsonDetails title="Registro completo" data={row} />
            </article>
          ))}
        {!filtered.length && <p>Nenhuma observação nesta seleção.</p>}
        <div className="pager">
          <button disabled={!safePage} onClick={() => setPage(safePage - 1)}>
            Anterior
          </button>
          <span>
            {filtered.length} observações · {safePage + 1} / {pages}
          </span>
          <button
            disabled={safePage + 1 >= pages}
            onClick={() => setPage(safePage + 1)}
          >
            Próxima
          </button>
        </div>
      </section>
    </main>
  );
}
