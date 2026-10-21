import { Icon } from "./ui.jsx";

export function TopBar({ onReset }) {
  return (
    <header className="topbar">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          A
        </span>
        <div>
          <strong>Ariadne Inspector</strong>
          <small>evidências de execução</small>
        </div>
      </div>
      {onReset && (
        <button className="new-run" onClick={onReset}>
          <Icon name="layers" />
          Todas as execuções
        </button>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer>
      <span>Ariadne Runtime · protótipo de pesquisa</span>
      <span>Reprodução de evidências · sem controle de agentes</span>
    </footer>
  );
}
