export const Icon = ({ name, size = 18 }) => {
  const paths = {
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></>,
    play: <path d="m8 5 11 7-11 7Z"/>,
    activity: <><path d="M3 12h4l2-7 4 14 2-7h6"/></>,
    layers: <><path d="m12 3-9 5 9 5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    warning: <><path d="M12 3 2.8 20h18.4Z"/><path d="M12 9v4M12 17h.01"/></>,
    file: <><path d="M6 2h8l4 4v16H6Z"/><path d="M14 2v5h5"/></>,
    arrow: <path d="m9 18 6-6-6-6"/>,
    terminal: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/></>,
    refresh: <><path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M6.1 8A7 7 0 0 1 18 6l2 6M17.9 16A7 7 0 0 1 6 18l-2-6"/></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
};

export const display = input => input == null || input === '' ? 'Não informado' : String(input);
export const formatMs = input => typeof input === 'number' && Number.isFinite(input)
  ? `${input.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ms` : '—';

export function StatusBadge({ status }) {
  const normalized = display(status).toUpperCase();
  const tone = normalized.includes('COMPLETED') ? 'success'
    : normalized.includes('FAIL') || normalized.includes('CANCEL') ? 'danger'
      : normalized.includes('RUN') || normalized.includes('PROGRESS') ? 'active' : 'neutral';
  return <span className={`badge ${tone}`}><span className="badge-dot" />{window.AriadnePresentation?.status(status) || display(status)}</span>;
}

export function JsonDetails({ title, data, open = false }) {
  return <details className="json-details" open={open}>
    <summary>{title}<Icon name="arrow" size={15} /></summary>
    <pre>{JSON.stringify(data, null, 2)}</pre>
  </details>;
}
