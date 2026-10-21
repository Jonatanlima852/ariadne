import {Icon} from './ui.jsx';
const tabs = [{id: 'demonstration', label: 'Demonstração', icon: 'play'}, {id: 'analysis', label: 'Análise', icon: 'activity'}, {id: 'details', label: 'Detalhes técnicos', icon: 'terminal'}];
export default function Sidebar({active, onChange}) {
  return <aside className="story-navigation" aria-label="Explorar execução">{tabs.map(tab => <button key={tab.id} className={active === tab.id ? 'active' : ''} aria-current={active === tab.id ? 'page' : undefined} onClick={() => onChange(tab.id)}><Icon name={tab.icon}/>{tab.label}</button>)}</aside>;
}
