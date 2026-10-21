import { useState } from "react";
export default function RawData({ report }) {
  const [name, setName] = useState("");
  const file = report.rawFiles.find((item) => item.name === name);
  return (
    <section className="content-card">
      <h2>Arquivos originais</h2>
      <p>
        Conteúdo integral da execução, incluindo outras amostras. A seleção de
        amostra não altera estes arquivos.
      </p>
      <select
        aria-label="Arquivo de evidências"
        value={name}
        onChange={(event) => setName(event.target.value)}
      >
        <option value="">Selecione um arquivo</option>
        {report.rawFiles.map((item) => (
          <option key={item.name}>{item.name}</option>
        ))}
      </select>
      {file && <pre className="raw-file">{file.content}</pre>}
    </section>
  );
}
