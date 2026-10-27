import {useEffect, useMemo, useState} from 'react';
import {createFlowScene, renderFlowSVG} from '../logisticsFlow.js';
import {JsonDetails} from './ui.jsx';

export default function LogisticsFlow({row}){
  const scene=useMemo(()=>createFlowScene(row),[row]);
  const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false),[speed,setSpeed]=useState(1),[overview,setOverview]=useState(false);
  const last=scene.frames.length-1, current=scene.frames[Math.min(index,last)];
  useEffect(()=>{
    if(!playing || index>=last){if(playing)setPlaying(false);return;}
    const timer=setTimeout(()=>setIndex(i=>Math.min(i+1,last)),2000/speed);
    return ()=>clearTimeout(timer);
  },[playing,index,last,speed]);
  const jump=i=>{setPlaying(false);setOverview(false);setIndex(Math.max(0,Math.min(last,i)));};
  const svg=renderFlowSVG(scene,index,{overview,animate:playing});
  const download=()=>{
    const url=URL.createObjectURL(new Blob([renderFlowSVG(scene,index,{overview})],{type:'image/svg+xml;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download=`${row.case}-${row.configuration}-${overview?'panorama':`passo-${index+1}`}.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  const revisions=scene.frames.map((f,i)=>({frame:f,index:i})).filter(f=>f.frame.kind==='incident' || f.frame.role==='IncidentAnalyst' || f.frame.revision || f.frame.kind==='effect' && f.frame.text.startsWith('TRANSFER'));
  return <section className="theatre logistics-flow" aria-label="Percurso registrado pelos agentes logísticos">
    <div className="theatre-heading"><h2>O caminho da missão pelos agentes</h2><span>Reprodução das chamadas e dos efeitos registrados</span></div>
    <div className="logistics-flow-diagram" dangerouslySetInnerHTML={{__html:svg}}/>
    <div className="story-controls">
      <button className="play-story" onClick={()=>{setOverview(false);if(index===last)setIndex(0);setPlaying(!playing);}}>{playing?'Ⅱ Pausar percurso':'▶ Reproduzir percurso'}</button>
      <button aria-label="Passo anterior do percurso" disabled={index===0} onClick={()=>jump(index-1)}>←</button><span>{index+1} de {last+1}</span><button aria-label="Próximo passo do percurso" disabled={index===last} onClick={()=>jump(index+1)}>→</button>
      <label>Ritmo <select value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value="0.5">Lento</option><option value="1">Normal</option><option value="2">Rápido</option></select></label>
      <button aria-pressed={overview} onClick={()=>{setPlaying(false);setOverview(!overview);}}>Panorama para apresentação</button><button onClick={download}>Baixar figura SVG</button>
    </div>
    <div className="logistics-flow-seek"><label>Passo da reprodução <input aria-label="Passo da reprodução" type="range" min="0" max={last} value={index} onChange={e=>jump(Number(e.target.value))}/></label><small>Ritmo didático; a animação não representa a duração real das chamadas.</small></div>
    {revisions.length>0 && <div className="logistics-flow-chapters"><strong>Ir direto à revisão:</strong>{revisions.map(({frame,index:i})=><button key={i} onClick={()=>jump(i)}>{frame.kind==='incident'?'Ocorrência':frame.kind==='effect'?'Transferência da carga':frame.revision?'Revisão BDI':'Análise do incidente'} · passo {i+1}</button>)}</div>}
    <div className="logistics-flow-evidence"><JsonDetails title="Evidência do passo selecionado" data={{...current,call:current.call_index!=null?row.calls[current.call_index]:undefined,domain_event:current.history_index!=null?row.state.history[current.history_index]:undefined}}/></div>
  </section>;
}
