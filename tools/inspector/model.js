/* Shared by the offline browser UI and dependency-free Node tests. */
(function (root) {
  "use strict";
  const allowed = new Set([
    "summary.json",
    "result.json",
    "result.evaluation.json",
    "events.jsonl",
    "message-events.jsonl",
    "execution.jsonl",
    "manifest.json",
    "demo.json",
    "results.jsonl",
    "status",
    "environment",
    "scenario",
  ]);
  const object = (value) =>
    value !== null && typeof value === "object" && !Array.isArray(value);
  const text = (value) => (value == null ? "" : String(value));

  function parseBase(files) {
    const data = {},
      warnings = [],
      events = [],
      names = new Set(),
      folders = new Set();
    for (const file of files) {
      if (!allowed.has(file.name)) continue;
      if (names.has(file.name))
        throw new Error(
          "Arquivo repetido: " + file.name + ". Selecione apenas uma execução.",
        );
      names.add(file.name);
      if (file.path && file.path.includes("/"))
        folders.add(file.path.slice(0, file.path.lastIndexOf("/")));
      if (folders.size > 1)
        throw new Error(
          "Os arquivos pertencem a pastas diferentes. Selecione apenas uma execução.",
        );
      if (file.name.endsWith(".jsonl")) {
        let invalid = 0;
        file.content.split(/\r?\n/).forEach((line, index) => {
          if (!line.trim()) return;
          try {
            const event = JSON.parse(line);
            if (!object(event) || typeof event.type !== "string")
              throw new Error();
            events.push({ ...event, source: file.name, line: index + 1 });
          } catch {
            invalid++;
          }
        });
        if (invalid)
          warnings.push(
            file.name + ": " + invalid + " linha(s) inválida(s) ignorada(s).",
          );
      } else if (file.name.endsWith(".json")) {
        try {
          data[file.name] = JSON.parse(file.content);
          if (!object(data[file.name])) throw new Error();
        } catch {
          throw new Error(file.name + ": esperado um objeto JSON válido.");
        }
      } else data[file.name] = file.content.trim();
    }
    if (!names.size)
      throw new Error(
        "Nenhum arquivo reconhecido. Selecione os arquivos de .ariadne/runs/ID/.",
      );
    const result = data["result.json"] || {},
      summary = data["summary.json"] || {};
    const rows = [];
    let kind = "Sem resultado";
    if ("workflow_id" in result && object(result.steps)) {
      kind = "Workflow";
      for (const [name, step] of Object.entries(result.steps)) {
        if (!object(step)) {
          warnings.push("Etapa inválida: " + name);
          continue;
        }
        const task = object(step.result) ? step.result : {};
        rows.push({
          name,
          status: step.status,
          task_id: task.task_id,
          agent_id: task.agent_id,
          agent_kind: task.agent_kind,
          duration_ms: step.duration_ms,
          output: task.output,
          error: task.error,
        });
      }
    } else if (object(result.results)) {
      kind = "Tarefas";
      for (const [name, task] of Object.entries(result.results)) {
        if (object(task)) rows.push({ ...task, name });
        else warnings.push("Tarefa inválida: " + name);
      }
    } else if (typeof result.message_id === "string") kind = "Mensagem";
    else if (data["result.json"])
      warnings.push(
        "Formato de resultado não reconhecido. Consulte os dados brutos; este visualizador aceita relatórios de cenários ./ariadne.",
      );
    if (!data["result.json"])
      warnings.push(
        "result.json ausente: a execução pode ter falhado antes de produzir um resultado.",
      );
    if (!data["summary.json"])
      warnings.push(
        "summary.json ausente: o resultado não informa se todas as verificações do cenário passaram.",
      );
    // SDK events describe client actions; do not merge them with runtime events.
    if (Array.isArray(result.events)) {
      result.events.forEach((event, index) => {
        if (object(event) && typeof event.type === "string")
          events.push({
            ...event,
            source: "result.json (SDK)",
            line: index + 1,
          });
      });
    }
    const trace = text(result.trace_id);
    const foreign = events.filter(
      (event) => trace && event.trace_id && event.trace_id !== trace,
    );
    if (foreign.length)
      warnings.push(
        foreign.length +
          " evento(s) têm trace diferente do resultado. Confira a origem dos arquivos; eles continuam visíveis.",
      );
    events.sort((a, b) => {
      const left = Date.parse(a.timestamp),
        right = Date.parse(b.timestamp);
      if (!Number.isFinite(left)) return Number.isFinite(right) ? 1 : 0;
      if (!Number.isFinite(right)) return -1;
      return left - right;
    });
    const status = text(data.status || summary.status || "NÃO INFORMADO");
    if (data.status && summary.status && data.status !== summary.status)
      warnings.push(
        "O estado do executor difere do resumo do cliente. O estado do executor é exibido; confira os arquivos brutos.",
      );
    return {
      data,
      warnings,
      events,
      rows,
      kind,
      result,
      summary,
      trace,
      status,
      scenario: text(
        data.scenario ||
          summary.scenario ||
          result.scenario ||
          result.workflow_id ||
          "Não informado",
      ),
      environment: text(data.environment || "Não informado"),
      names: [...names],
    };
  }

  function parse(files, selectedSample) {
    if (new Set(files.map((file) => file.name)).size !== files.length)
      throw new Error("Arquivo repetido na execução.");
    const resultFile = files.find((file) => file.name === "results.jsonl");
    let samples = [],
      sampleWarnings = [];
    if (resultFile) {
      resultFile.content.split(/\r?\n/).forEach((line, index) => {
        if (!line.trim()) return;
        try {
          const value = JSON.parse(line);
          if (
            !object(value) ||
            !Number.isInteger(value.sample) ||
            value.sample < 1
          )
            throw new Error();
          if (samples.some((row) => row.sample === value.sample))
            throw new Error();
          samples.push(value);
        } catch {
          sampleWarnings.push(
            `results.jsonl: linha ${index + 1} inválida ou amostra duplicada.`,
          );
        }
      });
    }
    const selected =
      samples.find((row) => row.sample === Number(selectedSample)) ||
      samples.at(-1);
    let input = files.filter((file) => file.name !== "results.jsonl");
    if (selected) {
      const previous = files.find((file) => file.name === "result.json");
      input = input.filter((file) => file.name !== "result.json");
      input.push({
        name: "result.json",
        path: previous?.path,
        content: JSON.stringify(selected),
      });
      // Events belonging to other repetitions are expected, not foreign evidence.
      input = input.map((file) => {
        if (
          !["events.jsonl", "message-events.jsonl", "execution.jsonl"].includes(
            file.name,
          )
        )
          return file;
        return {
          ...file,
          content: file.content
            .split(/\r?\n/)
            .map((line) => {
              try {
                const event = JSON.parse(line);
                return (
                  selected.trace_id
                    ? event.trace_id === selected.trace_id
                    : event.sample === selected.sample
                )
                  ? line
                  : "";
              } catch {
                return line;
              }
            })
            .join("\n"),
        };
      });
    }
    const report = parseBase(input);
    report.samples = samples;
    report.sample = selected?.sample;
    report.manifest = report.data["manifest.json"] || {};
    report.demo = report.data["demo.json"];
    report.warnings.push(...sampleWarnings);
    if (
      selectedSample &&
      !samples.some((row) => row.sample === Number(selectedSample))
    )
      report.warnings.push(
        "Amostra solicitada indisponível; exibindo a última registrada.",
      );
    report.rawFiles = files.filter((file) => allowed.has(file.name));
    report.names = report.rawFiles.map((file) => file.name);
    if (samples.length) report.data["results.jsonl"] = samples;
    if (report.manifest.repeat > samples.length && resultFile)
      report.warnings.push(
        `${samples.length} de ${report.manifest.repeat} amostras registradas.`,
      );
    return report;
  }

  function graph(report) {
    const declarations = report.manifest.steps;
    const declared = Array.isArray(declarations) && declarations.length > 0;
    const nodes = declared
      ? declarations.map((step) => ({ ...step, id: step.step_id }))
      : report.rows.map((row) => ({
          id: row.name,
          depends_on: [],
          input_bindings: [],
        }));
    const ids = new Set(nodes.map((node) => node.id));
    const depth = new Map(),
      visiting = new Set();
    function level(id) {
      if (visiting.has(id))
        throw new Error("Dependências cíclicas no manifesto.");
      if (depth.has(id)) return depth.get(id);
      visiting.add(id);
      const node = nodes.find((item) => item.id === id);
      const dependencies = node.depends_on || [];
      if (dependencies.some((parent) => !ids.has(parent)))
        throw new Error("Dependência ausente no manifesto.");
      const value = dependencies.length
        ? 1 + Math.max(...dependencies.map(level))
        : 0;
      visiting.delete(id);
      depth.set(id, value);
      return value;
    }
    for (const node of nodes) node.level = level(node.id);
    return { declared, nodes };
  }

  function replay(report, count) {
    const states = Object.fromEntries(
      graph(report).nodes.map((node) => [
        node.id,
        { status: "Aguardando evento", agent: null },
      ]),
    );
    const events = report.events.filter(
      (event) => event.source === "events.jsonl",
    );
    for (const event of events.slice(0, count)) {
      const id =
        event.step_id ||
        report.rows.find((row) => row.task_id && row.task_id === event.task_id)
          ?.name;
      if (!states[id]) continue;
      states[id] = {
        status: event.type,
        agent: event.agent_id || states[id].agent,
        event,
      };
    }
    return { states, events, current: events[count - 1] };
  }

  function domainOutcome(report) {
    const output =
      report.result.output ||
      (report.kind !== "Workflow" && report.rows.length === 1
        ? report.rows[0].output
        : undefined);
    const recorded = report.evaluation || report.data["result.evaluation.json"];
    const evaluation =
      report.evaluation ||
      (report.samples.length > 1 && recorded?.sample !== report.sample
        ? undefined
        : recorded);
    const mission =
      output?.feasible === false
        ? "Missão recusada"
        : output?.feasible === true
          ? "Plano proposto"
          : "Sem decisão de viabilidade";
    const validity =
      evaluation?.correct_rejection === true
        ? "Rejeição correta segundo o avaliador"
        : evaluation?.valid === true
          ? "Resposta válida segundo o avaliador"
          : evaluation?.valid === false
            ? "Resposta inválida segundo o avaliador"
            : "Avaliação de domínio não disponível";
    return { mission, validity, evaluation };
  }

  function filterEvents(events, query, source) {
    const needle = query.trim().toLocaleLowerCase();
    return events.filter(
      (event) =>
        (!source || event.source === source) &&
        (!needle || JSON.stringify(event).toLocaleLowerCase().includes(needle)),
    );
  }

  const api = { parse, filterEvents, allowed, graph, replay, domainOutcome };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TGInspector = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
