const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const model = require('./model.js');
const presentation = require('./presentation.js');
function sample(name) {
  const directory = path.join(__dirname, 'samples', name);
  return model.parse(fs.readdirSync(directory).filter(name => model.allowed.has(name)).map(name => ({name, content: fs.readFileSync(path.join(directory, name), 'utf8')})));
}
test('recovery story preserves timeout and reassignment without anticipating the final agent', () => {
  const scene = presentation.describe(sample('recovery'));
  const timeout = scene.frames.findIndex(frame => frame.kind === 'timeout');
  const reassigned = scene.frames.findIndex(frame => frame.kind === 'reassigned');
  assert.ok(timeout > 0 && reassigned > timeout);
  assert.equal(presentation.at(scene, timeout).agents['a-slow'].tone, 'warning');
  assert.equal(presentation.at(scene, timeout).agents['b-healthy'].tone, 'waiting');
  assert.equal(presentation.at(scene, reassigned).tasks.step_1.place, 'b-healthy');
  assert.equal(presentation.at(scene, timeout).tasks.step_1.place, 'runtime');
});
test('workflow story preserves separate tasks and returns through the coordinator', () => {
  const scene = presentation.describe(sample('workflow'));
  assert.equal(scene.tasks.length, 2);
  const firstComplete = scene.frames.findIndex(frame => frame.kind === 'completed');
  assert.equal(presentation.at(scene, firstComplete).tasks.first.place, 'runtime');
  assert.equal(presentation.at(scene, firstComplete).tasks.second.place, 'request');
  assert.deepEqual(scene.tasks[1].dependencies, ['first']);
  assert.ok(scene.frames.length < sample('workflow').events.length);
});
test('agent type is never guessed from names; optional labels preserve identity', () => {
  const report = sample('echo');
  report.manifest.agents = [{agent_id: 'llm-looking-name'}];
  report.manifest.metadata = {presentation: {title: 'Título', agents: {'llm-looking-name': {label: 'Intérprete'}}}};
  const scene = presentation.describe(report);
  assert.equal(scene.agents[0].type, 'Agente');
  assert.equal(scene.agents[0].name, 'Intérprete');
  assert.equal(scene.agents[0].id, 'llm-looking-name');
  assert.equal(scene.title, 'Título');
});
test('unknown outputs and incomplete records do not fabricate completion', () => {
  const report = model.parse([{name:'status',content:'FAILED'}]);
  const scene = presentation.describe(report);
  assert.equal(scene.frames.length, 1);
  assert.equal(scene.agents.length, 0);
  assert.equal(presentation.status(report.status), 'Não concluído');
});

test('an agent remains active when a parallel task is still assigned', () => {
  const scene = {agents: [{id: 'worker'}], tasks: [{id: 'a'}, {id: 'b'}], frames: [
    {kind: 'start'}, {kind: 'assigned', task: 'a', agent: 'worker'},
    {kind: 'assigned', task: 'b', agent: 'worker'}, {kind: 'completed', task: 'a', agent: 'worker'}]};
  assert.equal(presentation.at(scene, 3).agents.worker.tone, 'active');
  assert.equal(presentation.at(scene, 3).tasks.a.place, 'runtime');
});
