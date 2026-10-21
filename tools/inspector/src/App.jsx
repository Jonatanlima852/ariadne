import {useEffect, useMemo, useState} from 'react';
import {inspectorApi} from './api.js';
import Overview from './components/Overview.jsx';
import RawData from './components/RawData.jsx';
import Results from './components/Results.jsx';
import RunBrowser from './components/RunBrowser.jsx';
import Sidebar from './components/Sidebar.jsx';
import Timeline from './components/Timeline.jsx';
import Workflow from './components/Workflow.jsx';
import Demonstration from './components/Demonstration.jsx';
import Collection from './components/Collection.jsx';
import {Footer, TopBar} from './components/TopBar.jsx';
const location = () => Object.fromEntries(new URLSearchParams(window.location.hash.slice(1)));
export default function App() {
  const [route, setRoute] = useState(location);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const changed = () => setRoute(location());
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, []);
  const navigate = next => {window.location.hash = new URLSearchParams(next).toString();};
  const source = route.source || 'samples';
  useEffect(() => {
    let cancelled = false;
    setDetail(null); setError('');
    if (!route.id) {setLoading(false); return;}
    setLoading(true);
    const pending = source === 'embedded' ? Promise.resolve({kind: 'run', files: window.TGInspectorSample.files}) : inspectorApi.evidence(source, route.id);
    pending.then(value => {if (!cancelled) setDetail(value);})
      .catch(failure => {if (!cancelled) setError(failure.message);})
      .finally(() => {if (!cancelled) setLoading(false);});
    return () => {cancelled = true;};
  }, [source, route.id]);
  const parsed = useMemo(() => {
    if (detail?.kind !== 'run') return {};
    try {
      const report = window.TGInspector.parse(detail.files, route.sample);
      const analysis = detail.analyses?.find(item => item.id === route.analysis);
      report.evaluation = analysis?.rows.find(row => row.sample === report.sample)?.evaluation;
      report.analysis = analysis;
      return {report};
    } catch (failure) {return {parseError: failure.message};}
  }, [detail, route.sample, route.analysis]);
  const report = parsed.report;
  const reset = () => navigate({source: source === 'embedded' ? 'samples' : source});
  const select = item => navigate({source: item.source, id: item.id, ...(item.sample ? {sample: item.sample} : {})});
  const aliases = {overview: 'analysis', workflow: 'demonstration', results: 'details', timeline: 'details', raw: 'details'};
  const active = aliases[route.tab] || (['analysis', 'details'].includes(route.tab) ? route.tab : 'demonstration');
  const tab = value => navigate({...route, tab: value});
  return <div className={`app-shell ${report ? 'report-shell' : ''}`}>
    <TopBar onReset={route.id ? reset : null}/>
    {!route.id && <RunBrowser source={source} onSource={value => navigate({source: value})} onSelect={select} onSample={() => navigate({source: 'embedded', id: 'recovery'})}/>}
    {loading && <main className="content-card"><p role="status">Preparando a demonstração…</p></main>}
    {(error || parsed.parseError) && <main className="content-card"><p role="alert">{error || parsed.parseError}</p><button onClick={reset}>Voltar</button></main>}
    {detail && detail.kind !== 'run' && <Collection key={`${source}/${route.id}`} detail={detail} onSelect={select}/>}
    {report && <div className="workspace story-layout">
      <Sidebar active={active} onChange={tab} report={report}/>
      <main className="report-main">
        {active === 'demonstration' && <Demonstration key={`${source}/${route.id}/${report.sample}`} report={report} onDetails={() => tab('details')} onAnalysis={() => tab('analysis')}/>}
        {active === 'analysis' && <>
          <div className="sample-controls"><h1>Análise da execução</h1>
            {report.samples.length > 0 && <label>Repetição <select value={report.sample} onChange={event => navigate({...route, sample: event.target.value})}>{report.samples.map(item => <option key={item.sample} value={item.sample}>{item.sample} — {window.AriadnePresentation.status(item.status)}</option>)}</select></label>}
            {detail.analyses?.length > 0 && <label>Avaliação <select value={route.analysis || ''} onChange={event => navigate({...route, analysis: event.target.value})}><option value="">Sem avaliação selecionada</option>{detail.analyses.map((item, i) => <option key={item.id} value={item.id}>Análise {i + 1} · {item.generated_at ? new Date(item.generated_at).toLocaleString('pt-BR') : 'Data não informada'}</option>)}</select></label>}
          </div><Overview report={report}/><button className="return-story" onClick={() => tab('demonstration')}>Ver esta repetição na demonstração →</button>
        </>}
        {active === 'details' && <section className="technical-view"><h1>Detalhes técnicos</h1><p>Identificadores, eventos e arquivos originais da execução.</p><code>{route.id}</code>
          {report.warnings.length > 0 && <div className="warning-list">{report.warnings.map((warning, i) => <p key={i}>{warning}</p>)}</div>}
          <details open={route.tab === 'results'}><summary>Tarefas e respostas completas</summary><Results report={report}/></details>
          <details open={route.tab === 'timeline'}><summary>Eventos e identificadores</summary><Timeline key={`${route.id}/${report.sample}`} report={report}/></details>
          <details><summary>Definição técnica do workflow</summary><Workflow key={`${route.id}/${report.sample}`} report={report}/></details>
          <details open={route.tab === 'raw'}><summary>Arquivos e proveniência</summary><RawData report={report}/></details>
        </section>}
      </main>
    </div>}
    <Footer/>
  </div>;
}
