import { useEffect, useMemo, useState } from "react";
import { inspectorApi } from "./api.js";
import Overview from "./components/Overview.jsx";
import RawData from "./components/RawData.jsx";
import Results from "./components/Results.jsx";
import RunBrowser from "./components/RunBrowser.jsx";
import Sidebar from "./components/Sidebar.jsx";
import Timeline from "./components/Timeline.jsx";
import Workflow from "./components/Workflow.jsx";
import Collection from "./components/Collection.jsx";
import { Footer, TopBar } from "./components/TopBar.jsx";

function location() {
  return Object.fromEntries(new URLSearchParams(window.location.hash.slice(1)));
}
export default function App() {
  const [route, setRoute] = useState(location);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const changed = () => setRoute(location());
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  const navigate = (next) => {
    window.location.hash = new URLSearchParams(next).toString();
  };
  const source = route.source || "runs";
  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setError("");
    if (!route.id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const pending =
      source === "embedded"
        ? Promise.resolve({
            kind: "run",
            files: window.TGInspectorSample.files,
          })
        : inspectorApi.evidence(source, route.id);
    pending
      .then((value) => {
        if (!cancelled) setDetail(value);
      })
      .catch((failure) => {
        if (!cancelled) setError(failure.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [source, route.id]);
  const parsed = useMemo(() => {
    if (detail?.kind !== "run") return {};
    try {
      const report = window.TGInspector.parse(detail.files, route.sample);
      const analysis = detail.analyses?.find(
        (item) => item.id === route.analysis,
      );
      report.evaluation = analysis?.rows.find(
        (row) => row.sample === report.sample,
      )?.evaluation;
      report.analysis = analysis;
      return { report };
    } catch (failure) {
      return { parseError: failure.message };
    }
  }, [detail, route.sample, route.analysis]);
  const report = parsed.report;
  const reset = () =>
    navigate({ source: source === "embedded" ? "samples" : source });
  const select = (item) =>
    navigate({
      source: item.source,
      id: item.id,
      ...(item.sample ? { sample: item.sample } : {}),
    });
  const active = route.tab || "overview";
  return (
    <div className={`app-shell ${report ? "report-shell" : ""}`}>
      <TopBar onReset={route.id ? reset : null} />
      {!route.id && (
        <RunBrowser
          source={source}
          onSource={(value) => navigate({ source: value })}
          onSelect={select}
          onSample={() => navigate({ source: "embedded", id: "recovery" })}
        />
      )}
      {loading && (
        <main className="content-card">
          <p role="status">Abrindo evidências…</p>
        </main>
      )}
      {(error || parsed.parseError) && (
        <main className="content-card">
          <p role="alert">{error || parsed.parseError}</p>
          <button onClick={reset}>Voltar ao catálogo</button>
        </main>
      )}
      {detail && detail.kind !== "run" && (
        <Collection
          key={`${source}/${route.id}`}
          detail={detail}
          onSelect={select}
        />
      )}
      {report && (
        <div className="workspace">
          <Sidebar
            active={active}
            onChange={(tab) => navigate({ ...route, tab })}
            report={report}
          />
          <main className="report-main">
            <div className="sample-controls">
              <span>Registro salvo · {route.id}</span>
              {report.samples.length > 0 && (
                <label>
                  Amostra{" "}
                  <select
                    value={report.sample}
                    onChange={(event) =>
                      navigate({ ...route, sample: event.target.value })
                    }
                  >
                    {report.samples.map((item) => (
                      <option key={item.sample} value={item.sample}>
                        {item.sample} — {item.status}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {detail.analyses?.length > 0 && (
                <label>
                  Avaliação{" "}
                  <select
                    value={route.analysis || ""}
                    onChange={(event) =>
                      navigate({ ...route, analysis: event.target.value })
                    }
                  >
                    <option value="">Sem avaliação selecionada</option>
                    {detail.analyses.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.id}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            {active === "overview" && (
              <Overview
                report={report}
                origin={
                  source === "samples" || source === "embedded"
                    ? "DEMONSTRAÇÃO REGISTRADA"
                    : "EXECUÇÃO"
                }
              />
            )}
            {active === "workflow" && (
              <Workflow key={`${route.id}/${report.sample}`} report={report} />
            )}
            {active === "results" && <Results report={report} />}
            {active === "timeline" && (
              <Timeline key={`${route.id}/${report.sample}`} report={report} />
            )}
            {active === "raw" && <RawData report={report} />}
          </main>
        </div>
      )}
      <Footer />
    </div>
  );
}
