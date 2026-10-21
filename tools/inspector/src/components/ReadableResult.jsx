// Only known fields get domain-specific summaries; unknown outputs stay inspectable.
export default function ReadableResult({ value, onDetails }) {
  if (value == null)
    return <p>A resposta não está disponível neste registro.</p>;
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  )
    return <blockquote className="answer-text">{String(value)}</blockquote>;
  if (typeof value !== "object" || Array.isArray(value))
    return (
      <p>
        Uma resposta estruturada está disponível.{" "}
        <button onClick={onDetails}>Ver detalhes</button>
      </p>
    );
  const text = value.text ?? value.echo ?? value.message;
  if (typeof text === "string")
    return <blockquote className="answer-text">{text}</blockquote>;
  if (value.feasible === false)
    return (
      <>
        <h3>O agente recusou a missão</h3>
        <p>
          {value.rejection_reason || "O agente não informou uma justificativa."}
        </p>
      </>
    );
  if (value.feasible === true)
    return (
      <>
        <h3>O agente propôs um plano</h3>
        <p>
          {Array.isArray(value.actions)
            ? `${value.actions.length} ações registradas.`
            : ""}{" "}
          {value.final_state?.elapsed_minutes != null
            ? `Duração prevista: ${value.final_state.elapsed_minutes} minutos.`
            : ""}
        </p>
        <button onClick={onDetails}>Consultar as ações</button>
      </>
    );
  if (
    Array.isArray(value.route) &&
    value.route.every((item) => typeof item === "string")
  )
    return (
      <>
        <h3>Rota proposta</h3>
        <p className="answer-text">{value.route.join(" → ")}</p>
      </>
    );
  if (typeof value.start === "number" && typeof value.end === "number")
    return (
      <p className="answer-text">
        Horário proposto: {value.start}h às {value.end}h.
      </p>
    );
  return (
    <>
      <p>
        O agente devolveu uma resposta estruturada com{" "}
        {Object.keys(value).length} campos.
      </p>
      <button onClick={onDetails}>Consultar a resposta</button>
    </>
  );
}
