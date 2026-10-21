"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { parse, filterEvents } = require("./model.js");
const sample = require("./sample.js");
const file = (name, value) => ({
  name,
  content: typeof value === "string" ? value : JSON.stringify(value),
});

test("recorded recovery preserves failed attempt and successful agent, separating SDK events", () => {
  const report = parse(sample.files);
  assert.equal(report.status, "COMPLETED");
  assert.equal(report.rows[0].agent_id, "b-healthy");
  assert.equal(report.events.length, 7);
  assert.deepEqual(report.warnings, []);
  assert.deepEqual(
    filterEvents(report.events, "", "events.jsonl").map((event) => event.type),
    [
      "TASK_CREATED",
      "TASK_ASSIGNED",
      "TASK_TIMEOUT",
      "TASK_REASSIGNED",
      "TASK_COMPLETED",
    ],
  );
  assert.equal(filterEvents(report.events, "A-SLOW", "").length, 2);
  assert.equal(
    filterEvents(report.events, "TASK_TIMEOUT", "result.json (SDK)").length,
    0,
  );
});
test("workflow retains pending steps without result and domain evaluation", () => {
  const report = parse([
    file("result.json", {
      workflow_id: "flow",
      steps: {
        first: {
          status: "COMPLETED",
          duration_ms: 10,
          result: { agent_id: "bdi", output: { route: ["A", "D"] } },
        },
        second: { status: "PENDING", result: null },
      },
    }),
    file("result.evaluation.json", { valid: false }),
  ]);
  assert.equal(report.kind, "Workflow");
  assert.equal(report.rows.length, 2);
  assert.equal(report.rows[1].status, "PENDING");
  assert.equal(report.rows[1].agent_id, undefined);
  assert.equal(report.data["result.evaluation.json"].valid, false);
  assert.equal(report.status, "NÃO INFORMADO");
});
test("message preserves correlation and participants", () => {
  const report = parse([
    file("result.json", {
      message_id: "m",
      sender_id: "a",
      receiver_id: "b",
      correlation_id: "c",
    }),
  ]);
  assert.equal(report.kind, "Mensagem");
  assert.equal(report.result.correlation_id, "c");
  assert.deepEqual(report.rows, []);
});
test("failure before result remains visible and does not infer completion", () => {
  const report = parse([
    file("status", "FAILED"),
    file("summary.json", { status: "FAILED", error: "timeout" }),
  ]);
  assert.equal(report.status, "FAILED");
  assert.equal(report.summary.error, "timeout");
  assert.match(report.warnings[0], /result.json ausente/);
  assert.equal(report.kind, "Sem resultado");
});
test("executor cancellation takes precedence over successful client summary", () => {
  const report = parse([
    file("status", "CANCELLED"),
    file("summary.json", { status: "COMPLETED" }),
  ]);
  assert.equal(report.status, "CANCELLED");
  assert.ok(report.warnings.some((value) => value.includes("difere")));
});
test("malformed JSONL preserves valid events and reports skipped lines", () => {
  const report = parse([
    file("events.jsonl", '{"type":"A"}\ninvalid\nnull\n[]\n{"type":"B"}\n'),
  ]);
  assert.deepEqual(
    report.events.map((event) => event.type),
    ["A", "B"],
  );
  assert.deepEqual(
    report.events.map((event) => event.line),
    [1, 5],
  );
  assert.match(report.warnings[0], /3 linha/);
});
test("mixed traces remain visible with warning and timestamps sort stably", () => {
  const report = parse([
    file("result.json", { results: {}, trace_id: "one" }),
    file(
      "events.jsonl",
      [
        { type: "SECOND", timestamp: "2026-10-08T00:00:02Z", trace_id: "two" },
        { type: "UNKNOWN", timestamp: "invalid" },
        { type: "FIRST", timestamp: "2026-10-08T00:00:01Z", trace_id: "one" },
      ]
        .map((value) => JSON.stringify(value))
        .join("\n"),
    ),
  ]);
  assert.deepEqual(
    report.events.map((event) => event.type),
    ["FIRST", "SECOND", "UNKNOWN"],
  );
  assert.ok(report.warnings.some((value) => value.includes("trace diferente")));
});
test("duplicate files and mixed folders cannot silently overwrite an execution", () => {
  assert.throws(
    () => parse([file("status", "FAILED"), file("status", "COMPLETED")]),
    /repetido/,
  );
  assert.throws(
    () =>
      parse([
        { ...file("status", "FAILED"), path: "run-a/status" },
        { ...file("scenario", "demo"), path: "run-b/scenario" },
      ]),
    /pastas diferentes/,
  );
});
test("invalid JSON fails clearly; unsupported structures are not called successful", () => {
  for (const content of ["null", "[]", "{"])
    assert.throws(() => parse([file("result.json", content)]), /objeto JSON/);
  assert.throws(
    () => parse([file("build.log", "log")]),
    /Nenhum arquivo reconhecido/,
  );
  const report = parse([file("result.json", { strategies: {} })]);
  assert.equal(report.status, "NÃO INFORMADO");
  assert.ok(report.warnings.some((value) => value.includes("não reconhecido")));
});
test("imported markup remains plain data", () => {
  const attack = "<img src=x onerror=alert(1)>";
  const report = parse([
    file("scenario", attack),
    file("result.json", { results: { test: { output: attack } } }),
  ]);
  assert.equal(report.scenario, attack);
  assert.equal(report.rows[0].output, attack);
});

test("samples isolate traces without foreign warnings and preserve original lines and raw files", () => {
  const files = [
    file("manifest.json", {
      repeat: 3,
      steps: [{ step_id: "a", depends_on: [] }],
    }),
    file(
      "results.jsonl",
      [
        { sample: 1, trace_id: "one", workflow_id: "w1", steps: {} },
        { sample: 2, trace_id: "two", workflow_id: "w2", steps: {} },
      ]
        .map(JSON.stringify)
        .join("\n"),
    ),
    file(
      "events.jsonl",
      '{"type":"TASK_ASSIGNED","trace_id":"one"}\n{"type":"TASK_COMPLETED","trace_id":"two"}\n',
    ),
  ];
  const report = parse(files, 2);
  assert.equal(report.sample, 2);
  assert.equal(report.events.length, 1);
  assert.equal(report.events[0].line, 2);
  assert.equal(report.trace, "two");
  assert.ok(
    !report.warnings.some((value) => value.includes("trace diferente")),
  );
  assert.ok(report.warnings.some((value) => value.includes("2 de 3")));
  assert.equal(
    report.rawFiles.find((item) => item.name === "events.jsonl").content,
    files[2].content,
  );
});

test("graph uses declarations and replay never reveals future agent assignments", () => {
  const model = require("./model.js");
  const report = parse([
    file("manifest.json", {
      steps: [
        { step_id: "a", depends_on: [] },
        { step_id: "b", depends_on: ["a"] },
        { step_id: "c", depends_on: [] },
      ],
    }),
    file("result.json", {
      workflow_id: "w",
      steps: { a: { result: { task_id: "task-a", agent_id: "healthy" } } },
    }),
    file(
      "events.jsonl",
      [
        { type: "TASK_ASSIGNED", task_id: "task-a", agent_id: "slow" },
        { type: "TASK_TIMEOUT", task_id: "task-a", agent_id: "slow" },
        { type: "TASK_REASSIGNED", task_id: "task-a", agent_id: "healthy" },
      ]
        .map(JSON.stringify)
        .join("\n"),
    ),
  ]);
  assert.deepEqual(
    model.graph(report).nodes.map((node) => node.level),
    [0, 1, 0],
  );
  assert.equal(model.replay(report, 0).states.a.agent, null);
  assert.equal(model.replay(report, 2).states.a.agent, "slow");
  assert.equal(model.replay(report, 3).states.a.agent, "healthy");
  const old = parse(sample.files);
  assert.equal(model.graph(old).declared, false);
  assert.deepEqual(model.graph(old).nodes[0].depends_on, []);
});

test("cycle and missing dependency cannot invent a graph", () => {
  const { graph } = require("./model.js");
  for (const dependencies of [["a"], ["missing"]]) {
    const report = parse([
      file("manifest.json", {
        steps: [{ step_id: "a", depends_on: dependencies }],
      }),
    ]);
    assert.throws(() => graph(report), /Dependência/);
  }
});

test("completed execution does not imply domain validity", () => {
  const { domainOutcome } = require("./model.js");
  const report = parse([
    file("status", "COMPLETED"),
    file("result.json", {
      workflow_id: "w",
      steps: {},
      output: { feasible: false },
    }),
  ]);
  assert.equal(domainOutcome(report).mission, "Missão recusada");
  assert.match(domainOutcome(report).validity, /não disponível/);
  report.evaluation = { valid: true, correct_rejection: true };
  assert.match(domainOutcome(report).validity, /Rejeição correta/);
});

test('recorded local demonstrations expose real graph and replay without malformed evidence', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const model = require('./model.js');
  for (const name of ['echo', 'workflow', 'recovery']) {
    const directory = path.join(__dirname, 'samples', name);
    const files = fs.readdirSync(directory).filter(name => model.allowed.has(name))
      .map(name => ({name, content: fs.readFileSync(path.join(directory, name), 'utf8')}));
    const report = model.parse(files);
    assert.deepEqual(report.warnings, [], name);
    assert.ok(model.graph(report).nodes.length > 0);
    if (name === 'workflow') assert.equal(report.samples.length, 2);
    if (name === 'recovery') assert.ok(model.replay(report, 100).events.some(event => event.type === 'TASK_REASSIGNED'));
  }
});
