import { Icon } from './ui.jsx';

export function TopBar({ onReset }) {
  return <header className="topbar">
    <div className="brand"><span className="brand-mark" aria-hidden="true">A</span><div><strong>Ariadne Inspector</strong><small>evidências de execução</small></div></div>
    {onReset && <button className="new-run" onClick={onReset}><Icon name="layers"/>Todas as execuções</button>}
  </header>;
}

export function Footer() {
  return <footer><span>Ariadne Runtime · protótipo de pesquisa</span><a href="../../docs/presentation.md">Roteiro de apresentação <Icon name="arrow" size={14}/></a></footer>;
}
