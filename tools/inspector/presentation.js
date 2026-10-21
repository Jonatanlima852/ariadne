/* Presentation derived from recorded facts; no inferred reasoning architectures. */
(function (root) {
  const roles = {echo: 'Devolve o texto recebido', uppercase: 'Transforma texto em maiúsculas',
    'logistics-interpret': 'Interpreta a missão', 'logistics-execution': 'Planeja a missão',
    'logistics-plan': 'Propõe um plano', 'route': 'Escolhe uma rota', 'meeting': 'Propõe um horário'};
  const titles = {echo: 'Uma tarefa, um agente', workflow: 'Dois agentes, uma resposta', recovery: 'Uma nova chance para a tarefa',
    'failure-reassignment': 'Recuperação após uma demora', 'sequential-echo': 'Cooperação em duas etapas'};
  const plain = value => String(value || '').replace(/[_-]+/g, ' ').replace(/^./, char => char.toUpperCase());
  const opaque = value => !value || /^[a-f\d-]{25,}$/i.test(value) || /^(ariadne|tg)-[a-f\d-]{20,}$/i.test(value);
  const status = value => {
    const text = String(value || '');
    if (/COMPLETED/.test(text)) return 'Concluído';
    if (/CANCEL/.test(text)) return 'Interrompido';
    if (/FAIL|ERROR/.test(text)) return 'Não concluído';
    if (/RUN|PROGRESS/.test(text)) return 'Em andamento';
    if (/PENDING|READY/.test(text)) return 'Aguardando';
    if (text === 'AVALIADA') return 'Avaliação disponível';
    return 'Estado não informado';
  };
  const title = (name, fallback = 'Execução de agentes') => titles[name] || (opaque(name) ? fallback : plain(name));

  function describe(report) {
    const presentation = {...report.demo?.presentation, ...report.manifest?.metadata?.presentation};
    const declared = report.manifest?.agents || [];
    const events = report.events.filter(event => event.source === 'events.jsonl' && (!report.trace || !event.trace_id || event.trace_id === report.trace));
    const ids = [...new Set([...declared.map(agent => agent.agent_id), ...events.map(event => event.agent_id), ...report.rows.map(row => row.agent_id)].filter(Boolean))];
    const agents = ids.map((id, index) => {
      const agent = declared.find(value => value.agent_id === id) || {};
      const custom = presentation.agents?.[id] || {};
      const kind = agent.agent_kind || report.rows.find(row => row.agent_id === id)?.agent_kind;
      const type = /^(bdi|agent_kind_bdi)$/i.test(kind) ? 'BDI' : /^(llm|agent_kind_llm)$/i.test(kind) ? 'LLM' : 'Agente';
      return {id, name: custom.label || agent.name || `Agente ${index + 1}`,
        role: custom.role || agent.capabilities?.map(cap => roles[cap]).filter(Boolean).join(' · ') || 'Executa tarefas atribuídas', type};
    });
    const steps = report.manifest?.steps || report.rows.map(row => ({step_id: row.name}));
    const tasks = steps.map((step, index) => ({id: step.step_id, number: index + 1,
      name: presentation.steps?.[step.step_id]?.label || step.goal || `Etapa ${index + 1}`,
      dependencies: step.depends_on || [], bindings: step.input_bindings || [],
      output: report.rows.find(row => row.name === step.step_id)?.output}));
    const taskIds = new Map(report.rows.filter(row => row.task_id).map(row => [row.task_id, row.name]));
    // Root events can also name a step. Only STEP_STARTED associates the concrete task.
    for (const event of events) if (event.type === 'STEP_STARTED' && event.step_id && event.task_id) taskIds.set(event.task_id, event.step_id);
    const nameOf = id => agents.find(agent => agent.id === id)?.name || 'um agente';
    const frames = [{kind: 'start', text: 'Um pedido chega ao Ariadne. Os agentes participantes aparecem abaixo.', event: null}];
    for (const event of events) {
      const task = taskIds.get(event.task_id);
      const agent = nameOf(event.agent_id);
      const number = tasks.find(value => value.id === task)?.number;
      const unit = number ? `a tarefa ${number}` : 'a tarefa';
      const labels = {
        TASK_ASSIGNED: ['assigned', `Ariadne atribui ${unit} a ${agent}.`],
        TASK_REASSIGNED: ['reassigned', `Após uma tentativa anterior, Ariadne atribui ${unit} a ${agent}.`],
        TASK_TIMEOUT: ['timeout', `${agent} não respondeu dentro do prazo desta tentativa.`],
        TASK_FAILED: ['failed', `A tentativa de executar ${unit} falhou.`],
        TASK_COMPLETED: ['completed', `${agent} concluiu ${unit} e devolveu o resultado ao Ariadne.`],
        WORKFLOW_COMPLETED: ['finished', 'As etapas terminaram. Ariadne reúne a resposta para o pedido.'],
        WORKFLOW_FAILED: ['stopped', 'A execução terminou sem concluir todas as etapas.'],
        WORKFLOW_CANCELLED: ['stopped', 'A execução foi interrompida.'],
        WORKFLOW_TIMEOUT: ['stopped', 'O prazo da execução terminou.'],
      };
      if (!labels[event.type]) continue;
      if (event.type.startsWith('TASK_') && report.result.root_task_id === event.task_id) continue;
      const [kind, text] = labels[event.type];
      frames.push({kind, text, task, agent: event.agent_id, event});
    }
    const firstTime = events.map(event => Date.parse(event.timestamp)).find(Number.isFinite);
    for (const frame of frames) {
      const time = Date.parse(frame.event?.timestamp);
      frame.elapsed = Number.isFinite(time) && Number.isFinite(firstTime) ? Math.max(0, (time - firstTime) / 1000) : null;
    }
    return {agents, tasks, frames, presentation,
      title: presentation.title || report.demo?.title || title(report.scenario),
      request: presentation.request || report.manifest?.metadata?.case?.request || steps[0]?.goal || 'O texto original do pedido não foi registrado.',
      description: presentation.description || report.demo?.description || 'Acompanhe como o Ariadne distribui o trabalho e recebe as respostas.'};
  }

  function at(scene, index) {
    const agents = Object.fromEntries(scene.agents.map(agent => [agent.id, {label: 'Participante', tone: 'waiting'}]));
    const tasks = Object.fromEntries(scene.tasks.map(task => [task.id, {place: 'request', tone: 'waiting'}]));
    for (const frame of scene.frames.slice(1, index + 1)) {
      const active = ['assigned', 'reassigned'].includes(frame.kind);
      if (frame.agent && agents[frame.agent]) agents[frame.agent] = {label: active ? 'Executando' : frame.kind === 'timeout' ? 'Prazo esgotado' : frame.kind === 'completed' ? 'Concluiu a tarefa' : 'Tentativa falhou', tone: active ? 'active' : frame.kind === 'completed' ? 'done' : 'warning'};
      if (frame.task && tasks[frame.task]) tasks[frame.task] = {place: active ? frame.agent : 'runtime', tone: active ? 'active' : frame.kind === 'completed' ? 'done' : 'warning'};
      if (frame.kind === 'finished') for (const task of Object.values(tasks)) task.place = 'response';
    }
    // A completed task does not make an agent idle while another is still assigned.
    for (const task of Object.values(tasks)) if (agents[task.place]) agents[task.place] = {label: 'Executando', tone: 'active'};
    return {agents, tasks, frame: scene.frames[index] || scene.frames[0]};
  }
  const api = {describe, at, title, status};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AriadnePresentation = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
