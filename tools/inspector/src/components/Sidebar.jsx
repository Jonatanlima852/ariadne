import { Icon, StatusBadge } from "./ui.jsx";

const tabs = [
  { id: "overview", label: "Visão geral", icon: "activity" },
  { id: "workflow", label: "Workflow e replay", icon: "play" },
  { id: "results", label: "Etapas", icon: "layers" },
  { id: "timeline", label: "Timeline", icon: "clock" },
  { id: "raw", label: "Dados brutos", icon: "terminal" },
];

export default function Sidebar({ active, onChange, report }) {
  return (
    <aside>
      <span className="aside-label">NAVEGAÇÃO</span>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={active === tab.id ? "active" : ""}
          onClick={() => onChange(tab.id)}
        >
          <Icon name={tab.icon} />
          {tab.label}
        </button>
      ))}
      <div className="aside-run">
        <small>EXECUÇÃO ATUAL</small>
        <strong>{report.scenario}</strong>
        <StatusBadge status={report.status} />
      </div>
    </aside>
  );
}
