import { useState } from "react";
import { JsonDetails } from "./ui.jsx";
import LogisticsFlow from "./LogisticsFlow.jsx";

const CONFIGS = ["single-llm", "ariadne", "ariadne-lean"];
const LABEL = { "single-llm": "Single LLM", ariadne: "Ariadne", "ariadne-lean": "Ariadne enxuta" };
const COLOR = { "single-llm": "#2f65ad", ariadne: "#19735b", "ariadne-lean": "#9a642e" };
const fmt = (value, digits = 2) => Number.isFinite(value)
  ? value.toLocaleString("pt-BR", { maximumFractionDigits: digits }) : "Não disponível";
const tokens = row => Number.isFinite(row.input_tokens) && Number.isFinite(row.output_tokens)
  ? row.input_tokens + row.output_tokens : null;
const value = (row, field) => field === "total_tokens" ? tokens(row) : row[field];
const sum = (rows, field) => {
  const values = rows.map(row => value(row, field));
  return values.every(Number.isFinite) ? values.reduce((a, b) => a + b, 0) : null;
};

function PairedChart({ rows, field, title }) {
  const configs = CONFIGS.filter(config => rows.some(row => row.configuration === config));
  const cases = [...new Set(rows.map(row => row.case))];
  const groups = cases.map(id => ({ id, values: configs.map(config => {
    const values = rows.filter(row => row.case === id && row.configuration === config).map(row => value(row, field));
    return { config, n: values.length, average: values.length && values.every(Number.isFinite)
      ? values.reduce((a, b) => a + b, 0) / values.length : null };
  }) }));
  const maximum = Math.max(1, ...groups.flatMap(group => group.values.map(item => item.average ?? 0)));
  const width = 1100, left = 300, plot = 690, groupHeight = Math.max(60, configs.length * 22 + 16), height = groups.length * groupHeight + 40;
  return <section className="content-card logistics-chart">
    <h2>{title}</h2>
    <p>Média por caso e configuração. Cada barra informa o número de observações; os eixos começam em zero.</p>
    <div className="logistics-legend">{configs.map(config => <span key={config}><i style={{ background: COLOR[config] }}/>{LABEL[config]}</span>)}</div>
    <div className="table-scroll"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title} style={{ minWidth: 780, width: "100%" }}>
      {groups.map((group, index) => <g key={group.id} transform={`translate(0,${index * groupHeight + 10})`}>
        <text x={left - 12} y={24} textAnchor="end" fontSize="12">{group.id}</text>
        {group.values.map((item, j) => <g key={item.config}>
          <rect x={left} y={j * 22} width={item.average == null ? 0 : item.average / maximum * plot} height={16} fill={COLOR[item.config]} rx="3"/>
          <text x={left + (item.average ?? 0) / maximum * plot + 7} y={j * 22 + 12} fontSize="11">{fmt(item.average)} · n={item.n}</text>
          <title>{group.id} · {LABEL[item.config]}: {fmt(item.average)}, n={item.n}</title>
        </g>)}
      </g>)}
    </svg></div>
  </section>;
}

function Progress({ rows, selected }) {
  const pair = rows.filter(row => row.case === selected.case && (row.repetition || 1) === (selected.repetition || 1));
  const end = Math.max(1, ...pair.map(row => row.state?.time || 0));
  const total = Math.max(1, selected.total_orders || 0);
  const x = t => 55 + t / end * 820, y = n => 205 - n / total * 165;
  return <section className="content-card"><h2>Entregas ao longo da operação</h2>
    <p>{selected.case} · repetição {selected.repetition || 1}. Minutos do mundo simulado, separados do tempo real das chamadas.</p>
    <svg viewBox="0 0 930 250" role="img" aria-label="Entregas acumuladas por minuto simulado">
      <path d="M55 35V205H875" fill="none" stroke="#a9b7b0"/>
      {[0, total].map(n => <text key={n} x="40" y={y(n) + 4} textAnchor="end" fontSize="12">{n}</text>)}
      {[0, end].map(t => <text key={t} x={x(t)} y="225" textAnchor="middle" fontSize="12">{fmt(t)}</text>)}
      {pair.map(row => {
        const deliveries = Object.values(row.state?.deliveries || {}).map(d => d.time).sort((a, b) => a - b);
        let points = `${x(0)},${y(0)}`;
        deliveries.forEach((time, i) => { points += ` ${x(time)},${y(i)} ${x(time)},${y(i + 1)}`; });
        points += ` ${x(end)},${y(deliveries.length)}`;
        return <polyline key={row.configuration} points={points} fill="none" stroke={COLOR[row.configuration]} strokeWidth="3" strokeDasharray={row.configuration === "single-llm" ? "7 4" : undefined}/>;
      })}
      <text x="465" y="245" textAnchor="middle" fontSize="12">Minutos simulados</text>
    </svg>
    <div className="logistics-legend">{pair.map(row => <span key={row.configuration}><i style={{ background: COLOR[row.configuration] }}/>{LABEL[row.configuration]}</span>)}</div>
  </section>;
}

function Episode({ row, rows }) {
  const [tab, setTab] = useState("flow");
  const roles = [...new Set((row.calls || []).map(call => call.role))].map(role => {
    const calls = row.calls.filter(call => call.role === role);
    const measured = calls.map(call => call.metadata?.latency_ms);
    const usages = calls.map(call => call.metadata?.usage);
    return { role, calls, seconds: measured.every(Number.isFinite) ? measured.reduce((a, b) => a + b, 0) / 1000 : null,
      tokens: usages.every(u => Number.isFinite(u?.input_tokens) && Number.isFinite(u?.output_tokens))
        ? usages.reduce((n, u) => n + u.input_tokens + u.output_tokens, 0) : null };
  });
  const maxTokens = Math.max(1, ...roles.map(role => role.tokens || 0));
  return <>
    <Progress rows={rows} selected={row}/>
    <section className="content-card logistics-episode" id="logistics-episode">
      <h2>{row.case} · {LABEL[row.configuration]} · repetição {row.repetition || 1}</h2>
      <p>{row.delivered}/{row.total_orders} entregues · {row.on_time} no prazo · {fmt(row.simulation_minutes)} min simulados · {fmt(row.wall_seconds)} s reais</p>
      <p>Encerramento: {row.stop_reason}</p>
      {row.error && <p role="alert" className="error-message">{row.error}</p>}
      <nav className="catalog-tabs" aria-label="Detalhes do episódio">{[["flow", "Percurso dos agentes"], ["history", "Ações e ocorrências"], ["agents", "Agentes e consumo"], ["raw", "Dados e relato"]].map(([id, label]) => <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {tab === "flow" && <LogisticsFlow row={row}/>}
      {tab === "history" && <>
        <div className="table-scroll"><table><thead><tr><th>Minuto</th><th>Veículo</th><th>Ação / ocorrência</th><th>Resultado</th></tr></thead><tbody>
          {(row.state?.history || []).map((item, i) => {
            const a = item.action;
            return <tr key={i} className={item.incident ? "logistics-incident" : ""}>
              <td>{a ? `${fmt(item.time_before)} → ${fmt(item.time_after)}` : fmt(item.time)}</td>
              <td>{a?.vehicle || item.incident?.vehicle || "—"}</td>
              <td>{a ? `${a.type}${a.from ? ` ${a.from} → ${a.to}` : ""}${a.order ? ` · ${a.order}` : ""}${a.depot ? ` · depósito ${a.depot}` : ""}${a.source_vehicle ? ` · origem ${a.source_vehicle}` : ""}` : item.incident.description || item.incident.type}</td>
              <td>{a ? item.accepted ? "Aceita" : `Rejeitada: ${item.reason}` : "Revisão solicitada"}</td>
            </tr>;
          })}
        </tbody></table></div>
        <h3>Pedidos e prazos</h3>
        <div className="table-scroll"><table><thead><tr><th>Pedido</th><th>Destino</th><th>Prioridade</th><th>Prazo</th><th>Entregue no minuto</th><th>No prazo</th></tr></thead><tbody>
          {Object.values(row.state?.orders || {}).map(order => {
            const delivered = row.state?.deliveries?.[order.id];
            return <tr key={order.id}><td>{order.id}</td><td>{order.destination}</td><td>{order.priority}</td><td>{order.deadline}</td><td>{delivered ? fmt(delivered.time) : "Não entregue"}</td><td>{delivered ? delivered.on_time ? "Sim" : "Não" : "—"}</td></tr>;
          })}
        </tbody></table></div>
      </>}
      {tab === "agents" && <>
        <p>Tempos das chamadas vêm dos metadados do SDK. Quando uma medição não foi registrada, o valor fica indisponível.</p>
        {roles.map(role => <article key={role.role} className="logistics-role"><strong>{role.role}</strong><span>{role.calls.length} chamadas · {fmt(role.seconds)} s · {fmt(role.tokens, 0)} tokens</span>
          <div className="logistics-track"><div style={{ width: `${(role.tokens || 0) / maxTokens * 100}%` }}/></div>
          <JsonDetails title="Decisões, planos selecionados e respostas" data={role.calls}/>
        </article>)}
      </>}
      {tab === "raw" && <>
        <h3>Relato registrado</h3><p className="logistics-explanation">{row.explanation}</p>
        <p>O relato pode conter erros de linguagem ou interpretação. As entregas e restrições são conferidas pelo estado e pelas ações acima.</p>
        <JsonDetails title="Estado final" data={row.state}/>
        <JsonDetails title="Workflows registrados" data={row.workflows}/>
        <JsonDetails title="Agentes registrados e contêineres" data={row.registered_agents}/>
      </>}
    </section>
  </>;
}

export default function Logistics({ detail, onRefresh }) {
  const [caseId, setCaseId] = useState("");
  const [metric, setMetric] = useState("wall_seconds");
  const [selected, setSelected] = useState(0);
  const all = detail.rows || [], manifest = detail.document || {};
  const rows = all.filter(row => !caseId || row.case === caseId);
  const current = rows[Math.min(selected, Math.max(0, rows.length - 1))];
  const demo = manifest.execution_kind === "deterministic-integration-demo";
  const fields = { wall_seconds: "Tempo real (s)", total_tokens: "Tokens totais", delivered: "Pedidos entregues", on_time: "Entregas no prazo", distance: "Distância", energy_consumed: "Energia de movimento", wall_seconds_before_report: "Tempo antes do relatório (s)" };
  return <main className="runs-layout logistics-view">
    <section className="content-card">
      <span className="kicker">LOGÍSTICA V2 · {demo ? "INTEGRAÇÃO DETERMINÍSTICA" : "COLETA COM LLM REAL"}</span>
      <h1>Single LLM e equipe Ariadne</h1>
      <button className="secondary" onClick={onRefresh}>Atualizar coleta</button>
      <p>{manifest.suite || "basic"} · {manifest.model || "sem modelo real"} · {all.length} observações registradas{manifest.planned_observations ? ` de ${manifest.planned_observations} previstas` : ""}.</p>
      <p>{demo ? "Substitutos determinísticos verificam integração; estes tempos não medem desempenho de LLM." : "Métricas registradas pelo domínio. Atendimento parcial, erro operacional, tempo real e tempo simulado são apresentados separadamente."}</p>
      <p>Os totais incluem todas as observações selecionadas; repetições contribuem novamente para esses totais. Consulte n e a comparação por caso.</p>
      <div className="toolbar"><label>Casos <select aria-label="Filtrar caso logístico" value={caseId} onChange={e => { setCaseId(e.target.value); setSelected(0); }}><option value="">Todos</option>{[...new Set(all.map(row => row.case))].map(id => <option key={id}>{id}</option>)}</select></label>
        <label>Métrica <select aria-label="Métrica do gráfico" value={metric} onChange={e => setMetric(e.target.value)}>{Object.entries(fields).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>
      </div>
      <div className="logistics-summaries">{CONFIGS.filter(config => rows.some(row => row.configuration === config)).map(config => {
        const group = rows.filter(row => row.configuration === config);
        return <article key={config} style={{ borderTopColor: COLOR[config] }}><h2>{LABEL[config]}</h2><p>{group.length} observações · {group.filter(row => row.error).length} erros operacionais</p>
          <strong>{fmt(sum(group, "delivered"), 0)} / {fmt(sum(group, "total_orders"), 0)} entregues</strong>
          <p>{fmt(sum(group, "on_time"), 0)} no prazo · {fmt(sum(group, "rejected_actions"), 0)} ações rejeitadas</p>
          <p>{fmt(sum(group, "wall_seconds"))} s somados · {fmt(sum(group, "total_tokens"), 0)} tokens · {fmt(sum(group, "llm_calls"), 0)} chamadas LLM</p>
          <p>Distância {fmt(sum(group, "distance"))} · Energia {fmt(sum(group, "energy_consumed"))}</p>
        </article>;
      })}</div>
    </section>
    <PairedChart rows={rows} field={metric} title={fields[metric]}/>
    <section className="content-card"><h2>Observações por caso</h2>
      <p>Selecione uma observação para acompanhar ações, incidentes, pedidos, planos BDI e consumo por agente.</p>
      <div className="table-scroll"><table><thead><tr><th>Caso / repetição</th><th>Configuração</th><th>Entregas</th><th>No prazo</th><th>Tempo real</th><th>Tokens</th><th>Resultado</th></tr></thead><tbody>
        {rows.map((row, i) => <tr key={`${row.case}-${row.configuration}-${row.repetition || 1}-${i}`} className={current === row ? "logistics-selected" : ""}>
          <td><button aria-pressed={current === row} onClick={() => setSelected(i)}>{row.case} · r{row.repetition || 1}</button></td><td>{LABEL[row.configuration]}</td><td>{row.delivered}/{row.total_orders}</td><td>{row.on_time}</td><td>{fmt(row.wall_seconds)} s</td><td>{fmt(tokens(row), 0)}</td><td>{row.error ? "Erro operacional" : row.result === "complete" ? "Completo" : "Parcial"}</td>
        </tr>)}
      </tbody></table></div>
    </section>
    {current && <Episode key={`${current.case}-${current.configuration}-${current.repetition || 1}`} row={current} rows={rows}/>}
    <section className="content-card"><JsonDetails title="Manifesto, condições e proveniência" data={manifest}/></section>
  </main>;
}
