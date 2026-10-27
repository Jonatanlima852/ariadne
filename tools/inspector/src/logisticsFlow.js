// The controller records calls in submission order. These frames explain that
// order; they do not invent network events or a wall-clock trace.
export const FLOW_AGENTS = [
  {id:'OrderInterpreter', name:'OrderInterpreter', type:'LLM', label:'Interpreta os pedidos', x:70, y:210, w:330, h:78},
  {id:'MissionDecomposer', name:'MissionDecomposer', type:'LLM', label:'Ordena a missão', x:70, y:315, w:330, h:78},
  {id:'IncidentAnalyst', name:'IncidentAnalyst', type:'LLM', label:'Analisa a necessidade de revisão', x:70, y:420, w:330, h:78},
  {id:'OperationsReporter', name:'OperationsReporter', type:'LLM', label:'Redige o relato final', x:70, y:525, w:330, h:78},
  {id:'InventoryManager', name:'InventoryManager', type:'BDI', label:'Estoque ou carga já carregada', x:1080, y:199, w:450, h:62},
  {id:'ResourceAllocator', name:'ResourceAllocator', type:'BDI', label:'Veículo, capacidade e origem', x:1080, y:270, w:450, h:62},
  {id:'RoutePlanner', name:'RoutePlanner', type:'BDI', label:'Conexões e rota aberta', x:1080, y:341, w:450, h:62},
  {id:'EnergyManager', name:'EnergyManager', type:'BDI', label:'Bateria, desvios e recarga', x:1080, y:412, w:450, h:62},
  {id:'ConstraintSupervisor', name:'ConstraintSupervisor', type:'BDI', label:'Valida a sequência concreta', x:1080, y:483, w:450, h:62},
  {id:'MissionExecutor', name:'MissionExecutor', type:'BDI', label:'Aplica ações ao mundo simulado', x:1080, y:554, w:450, h:62},
];
const number = (n, digits=1) => Number.isFinite(n) ? n.toLocaleString('pt-BR',{maximumFractionDigits:digits}) : 'indisponível';
const esc = text => String(text ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const short = (s, n=105) => String(s || '').length > n ? `${String(s).slice(0,n-1)}…` : String(s || '');
const sameAction = (a,b) => ['type','vehicle','order','from','to','depot','source_vehicle'].every(k => a?.[k] == null || b?.[k] == null || a[k] === b[k]);
const roleText = call => {
  const out=call.output || {}, choice=out.choice || {};
  const assignment=[choice.order,choice.vehicle,choice.source_vehicle ? `recuperar de ${choice.source_vehicle}` : choice.depot].filter(Boolean).join(' · ');
  if(call.error) return `Falha registrada: ${typeof call.error === 'string' ? call.error : JSON.stringify(call.error)}`;
  switch(call.role){
    case 'OrderInterpreter':return `${out.orders?.length ?? '?'} pedidos estruturados retornados para conferência do controlador.`;
    case 'MissionDecomposer':return `Ordem registrada: ${(out.order_ids || []).join(' → ')}.`;
    case 'MissionCoordinator':return `${out.revision_reason ? `Revisão: ${out.revision_reason}. ` : ''}Missão BDI: ${(out.order_ids || []).join(' → ')}.`;
    case 'InventoryManager':return `${out.options?.length ?? '?'} candidatos de estoque ou carga já carregada.`;
    case 'ResourceAllocator':return assignment || 'Nenhum candidato de veículo retornado.';
    case 'RoutePlanner':return `${out.actions?.length ?? 0} ações propostas${assignment ? ` · ${assignment}` : ''}.`;
    case 'EnergyManager':return `${call.metadata?.selected_plan || 'Plano energético registrado'} · ${out.actions?.length ?? 0} ações.`;
    case 'ConstraintSupervisor':return `${out.approved ? 'Sequência aprovada' : 'Sequência não aprovada'}${Number.isFinite(out.predicted_time) ? ` · término previsto no minuto ${number(out.predicted_time)}` : ''}.`;
    case 'MissionExecutor':return out.reason || 'Resposta do executor registrada; efeitos conferidos no histórico do domínio.';
    case 'IncidentAnalyst':return 'Análise registrada após feedback; o controlador solicita nova decomposição.';
    case 'OperationsReporter':return 'Relato textual retornado. As métricas vêm do estado validado do domínio.';
    case 'SingleLLM':return `${out.actions?.length ?? 0} ações propostas pelo agente único.`;
    default:return 'Resposta de tarefa registrada.';
  }
};

export function createFlowScene(row){
  const history=row.state?.history || [], calls=row.calls || [], workflows=row.workflows || [];
  const agents=(row.configuration === 'single-llm'
    ? [{id:'SingleLLM',name:'SingleLLM',type:'LLM',label:'Planeja e revisa a operação',x:1080,y:341,w:450,h:78}]
    : row.configuration === 'ariadne-lean'
      ? [FLOW_AGENTS[0],{id:'MissionCoordinator',name:'MissionCoordinator',type:'BDI',label:'Coordena a missão e suas revisões',x:70,y:315,w:330,h:78},...FLOW_AGENTS.filter(a=>a.type==='BDI')]
      : FLOW_AGENTS).map(agent => ({...agent,count:calls.filter(c => c.role === agent.id).length}));
  const frames=[{kind:'start',title:'A missão entra no Ariadne',text:`${row.total_orders} pedidos em ${row.case}. Cada chamada e efeito mostrado foi registrado nesta observação.`}];
  const taskWorkflow=new Map();
  workflows.forEach((w,i) => Object.values(w.steps || {}).forEach(s => {if(s.result?.task_id) taskWorkflow.set(s.result.task_id,{id:w.workflow_id,cycle:i+1});}));
  let cycle=0, cursor=0, lastPlan=[];
  function effects(until){
    while(cursor < until && cursor < history.length){
      const item=history[cursor], history_index=cursor++;
      if(item.incident){
        frames.push({kind:'incident',role:'MissionExecutor',title:'Ocorrência registrada no domínio',text:item.incident.description || `${item.incident.type} · ${item.incident.vehicle || `${item.incident.from || ''}–${item.incident.to || ''}`}`,
          history_index,time_simulated:item.time,cycle});
      }else if(item.action && ['TRANSFER','DELIVER','RECHARGE'].includes(item.action.type)){
        const a=item.action;
        frames.push({kind:'effect',role:'MissionExecutor',title:a.type==='TRANSFER' ? 'Carga recuperada por transferência' : a.type==='DELIVER' ? 'Entrega conferida no estado' : 'Recarga aplicada ao veículo',
          text:`${a.type} · ${a.vehicle}${a.order ? ` · ${a.order}` : ''}${a.source_vehicle ? ` · origem ${a.source_vehicle}` : ''} · ${item.accepted ? 'ação aceita' : `rejeitada: ${item.reason}`}.`,
          history_index,time_simulated:item.time_after,cycle});
      }
    }
  }
  calls.forEach((call,i) => {
    if(call.role==='InventoryManager') cycle++;
    const mapped=taskWorkflow.get(call.task_id), wf=mapped?.id || (['InventoryManager','ResourceAllocator','RoutePlanner','EnergyManager','ConstraintSupervisor'].includes(call.role) ? workflows[cycle-1]?.workflow_id : null);
    if(call.role==='ConstraintSupervisor') lastPlan=call.output?.actions || [];
    frames.push({kind:'call',role:call.role,title:`${i+1}. ${call.role}`,text:roleText(call),task_id:call.task_id,workflow_id:wf || undefined,
      cycle:mapped?.cycle || cycle || undefined,call_index:i,status:call.status,selected_plan:call.metadata?.selected_plan,revision:!!call.output?.revision_reason});
    if(call.role==='MissionExecutor' || call.role==='SingleLLM'){
      const snapshot=call.output?.state?.history;
      if(snapshot) effects(snapshot.length);
      else {
        // Archives omit duplicate executor snapshots. Match the supervisor's
        // concrete sequence against actual history, stopping at interruption.
        const proposed=call.role==='SingleLLM' ? call.output?.actions || [] : lastPlan;
        let until=cursor;
        for(const action of proposed){
          const item=history[until];
          if(!item) break;
          if(item.incident){until++;break;}
          if(!item.action || !sameAction(action,item.action)) break;
          until++;
          if(!item.accepted) break;
        }
        effects(until);
      }
    }
  });
  // If compact evidence cannot place an effect in a particular executor call,
  // retain the domain order at the end, without assigning a task identifier.
  effects(history.length);
  frames.push({kind:'finished',title:'Desfecho medido',text:`${row.delivered}/${row.total_orders} pedidos entregues · ${row.on_time} no prazo · ${row.rejected_actions} ações rejeitadas · ${number(row.simulation_minutes)} min simulados.`});
  const incidents=history.filter(h=>h.incident), transfers=history.filter(h=>h.accepted && h.action?.type==='TRANSFER');
  const lean=row.configuration==='ariadne-lean';
  const milestones=[
    {title:'Pedidos e missão',text:`${row.total_orders} pedidos · ${calls.filter(c=>c.role==='OrderInterpreter').length} interpretação · ${calls.filter(c=>c.role===(lean?'MissionCoordinator':'MissionDecomposer')).length} ${lean?'coordenações BDI':'decomposições'}`},
    {title:'Planejar e executar',text:`${workflows.length} workflows · ${calls.filter(c=>c.role==='MissionExecutor').length} chamadas ao executor`},
    {title:'Interromper e recuperar',text:`${incidents.length} ocorrência(s) · ${calls.filter(c=>lean ? c.role==='MissionCoordinator' && c.output?.revision_reason : c.role==='IncidentAnalyst').length} ${lean?'revisões BDI':'análise(s)'} · ${transfers.length} transferência(s)`},
    {title:'Resultado observado',text:`${row.delivered}/${row.total_orders} entregues · ${row.on_time} no prazo · ${number(row.simulation_minutes)} min`},
  ];
  return {row,agents,frames,milestones,incidents,transfers};
}

function svgLines(text,x,y,{size=18,color='#53685e',max=85,lineHeight=25}={}){
  const words=String(text || '').split(/\s+/),lines=[''];
  words.forEach(w=>{const last=lines.length-1;if((lines[last]+' '+w).trim().length>max && lines[last]) lines.push(w);else lines[last]=(lines[last]+' '+w).trim();});
  return `<text x="${x}" y="${y}" font-size="${size}" fill="${color}">${lines.map((line,i)=>`<tspan x="${x}" dy="${i ? lineHeight : 0}">${esc(line)}</tspan>`).join('')}</text>`;
}

export function renderFlowSVG(scene,index,{overview=false,animate=false}={}){
  const {row,agents,frames,milestones}=scene, frame=frames[Math.max(0,Math.min(frames.length-1,index))];
  const completed=frames.slice(0,index+1).filter(f=>f.kind==='call');
  const counts=id => overview ? agents.find(a=>a.id===id)?.count || 0 : completed.filter(f=>f.role===id).length;
  const active=overview ? null : agents.find(a=>a.id===frame.role), hub={x:650,y:350,w:300,h:142};
  const arrow='#94aca0';
  const paths=agents.map(a=>{
    const left=a.x<hub.x, fromX=left ? hub.x : hub.x+hub.w, fromY=421, toX=left ? a.x+a.w : a.x, toY=a.y+a.h/2;
    const d=`M${fromX} ${fromY} C${left?530:1000} ${fromY} ${left?520:1000} ${toY} ${toX} ${toY}`;
    return `<path d="${d}" fill="none" stroke="${a===active?'#c46e24':counts(a.id)?'#80ac99':arrow}" stroke-width="${a===active?4:2}" marker-start="url(#flow-arrow)" marker-end="url(#flow-arrow)"/>${a===active ? `<circle ${animate?'':`cx="${(fromX+toX)/2}" cy="${(fromY+toY)/2}"`} r="9" fill="#c46e24" stroke="#fff" stroke-width="3">${animate ? `<animateMotion dur="1.4s" repeatCount="indefinite" path="${d}"/>` : ''}</circle>` : ''}`;
  }).join('');
  const cards=agents.map(a=>{
    const current=a===active, n=counts(a.id), color=a.type==='LLM'?'#2f65ad':'#19735b';
    return `<g><rect x="${a.x}" y="${a.y}" width="${a.w}" height="${a.h}" rx="15" fill="${current?'#fff2e3':'#fff'}" stroke="${current?'#c46e24':n?'#9cbbaa':'#d5ded8'}" stroke-width="${current?3:1.5}"/>
      <rect x="${a.x+14}" y="${a.y+14}" width="44" height="28" rx="8" fill="${color}"/><text x="${a.x+36}" y="${a.y+33}" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">${a.type}</text>
      <text x="${a.x+70}" y="${a.y+28}" font-size="19" font-weight="650" fill="#203e31">${esc(a.name)}</text><text x="${a.x+70}" y="${a.y+49}" font-size="14" fill="#5a6f63">${esc(a.label)}</text>
      <circle cx="${a.x+a.w-23}" cy="${a.y+19}" r="13" fill="${n ? color:'#e5ece7'}"/><text x="${a.x+a.w-23}" y="${a.y+24}" text-anchor="middle" font-size="12" font-weight="700" fill="${n?'#fff':'#617769'}">${n}</text></g>`;
  }).join('');
  const bottom=overview ? milestones.map((m,i)=>`<g><rect x="${48+i*382}" y="690" width="364" height="120" rx="16" fill="${i===2&&scene.incidents.length?'#fff1df':'#fff'}" stroke="#d9e3dc"/>
    <text x="${68+i*382}" y="723" font-size="18" font-weight="700" fill="#284d3a">${i+1}. ${esc(m.title)}</text>${svgLines(m.text,68+i*382,753,{size:17,max:34,lineHeight:24})}</g>`).join('') : `<rect x="48" y="672" width="1504" height="152" rx="18" fill="${frame.kind==='incident'?'#fff1df':'#fff'}" stroke="#d9e3dc"/>
    <text x="74" y="710" font-size="23" font-weight="700" fill="#203e31">${esc(frame.title)}</text>${svgLines(frame.text,74,747,{size:21,max:125,lineHeight:27})}
    <text x="74" y="802" font-size="14" fill="#64786c">${esc(frame.task_id ? `task_id: ${frame.task_id}` : frame.history_index != null ? `history[${frame.history_index}] · minuto simulado ${number(frame.time_simulated)}` : `Observação: ${row.case}`)}${frame.workflow_id ? esc(` · workflow: ${frame.workflow_id}`) : ''}</text>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-labelledby="flow-title flow-desc"><title id="flow-title">Percurso da missão logística: ${esc(row.case)}</title><desc id="flow-desc">Tarefas coordenadas pelo Ariadne entre agentes LLM e BDI. As conexões representam chamadas e respostas via orquestrador. Ordem dos registros; ritmo didático, sem timestamps inventados.</desc>
    <defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="context-stroke"/></marker></defs>
    <rect width="1600" height="900" fill="#f3f6f2"/><g font-family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif">
    <text x="48" y="42" font-size="15" letter-spacing="2" font-weight="700" fill="#4c7560">ARIADNE · LOGÍSTICA V2 · ${row.execution_kind==='real-llm'?'EVIDÊNCIA COM LLM REAL':'DEMONSTRAÇÃO DETERMINÍSTICA'}</text>
    <text x="48" y="88" font-size="36" font-weight="750" fill="#183b2a">Como a missão atravessou os agentes</text>
    <text x="48" y="123" font-size="20" fill="#526b5c">${esc(row.case)} · ${esc(row.model || 'substitutos determinísticos')} · desfecho final: ${row.delivered}/${row.total_orders} entregues · ${row.on_time} no prazo</text>
    <rect x="48" y="163" width="374" height="475" rx="22" fill="#edf2f7"/><rect x="1058" y="163" width="496" height="475" rx="22" fill="#edf3ed"/>
    <text x="70" y="189" font-size="14" letter-spacing="1" fill="#44668c" font-weight="700">${row.configuration==='ariadne-lean'?'INTERPRETAÇÃO E COORDENAÇÃO':'INTERPRETAÇÃO E REVISÃO'}</text><text x="1080" y="189" font-size="14" letter-spacing="1" fill="#3d755c" font-weight="700">PLANEJAMENTO E AÇÃO</text>
    ${paths}${cards}${row.configuration==='ariadne-lean' ? `<text x="85" y="463" font-size="23" font-weight="700" fill="#315941">1 LLM + 7 agentes BDI</text>${svgLines('O coordenador BDI revisa a missão a partir do estado atual e do feedback registrado.',85,499,{size:18,max:31,lineHeight:27})}`:''}
    <path d="M800 276V342" stroke="#8faa99" stroke-width="2" marker-end="url(#flow-arrow)"/><text x="800" y="237" text-anchor="middle" font-size="27" font-weight="700" fill="#264d37">${row.total_orders} pedidos</text><text x="800" y="264" text-anchor="middle" font-size="16" fill="#647b6a">missão do cenário</text>
    <rect x="650" y="350" width="300" height="142" rx="27" fill="#214e38"/><text x="800" y="396" text-anchor="middle" font-size="32" font-weight="750" fill="#fff">Ariadne</text><text x="800" y="427" text-anchor="middle" font-size="19" fill="#e0eee5">orquestrador do runtime</text><text x="800" y="458" text-anchor="middle" font-size="15" fill="#c7ded0">tarefas · resultados · bindings</text>
    <path d="M800 500V543" stroke="#8faa99" stroke-width="2" marker-end="url(#flow-arrow)"/><text x="800" y="577" text-anchor="middle" font-size="23" font-weight="700" fill="#2a5540">${overview?'Estado final validado':`Passo ${index+1} de ${frames.length}`}</text><text x="800" y="606" text-anchor="middle" font-size="16" fill="#63796b">${overview?`${row.accepted_actions} ações aceitas · ${number(row.simulation_minutes)} min simulados`:'contagem acumulada em cada agente'}</text>
    ${bottom}<text x="48" y="852" font-size="15" fill="#536c5d">Setas: tarefas e respostas via orquestrador. Círculos: número de chamadas. Sem mensagens diretas entre agentes.</text>
    <text x="48" y="878" font-size="13" fill="#6e8175">Fonte: calls, workflows e state.history da observação · trace_id: ${esc(row.trace_id || 'não registrado')} · sequência didática, sem duração inferida.</text></g></svg>`;
}
