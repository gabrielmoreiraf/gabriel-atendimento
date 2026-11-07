/** Visão 360°: as frentes que o Gabriel assume e onde a pessoa decide (REQUISITOS.md §1.2). */
const FRENTES = [
  {
    id: "F1",
    nome: "Triagem e SLA da fila",
    faz: "Classifica, prioriza pelo risco de SLA e pelo custo do canal e dá a primeira resposta.",
    pessoa: "—",
  },
  {
    id: "F2",
    nome: "Resolução em vários sistemas",
    faz: "Consulta pedido, portal e pagamento; abre chamado; reenvia, troca e reembolsa dentro da alçada.",
    pessoa: "Aprova acima de R$ 100 (reembolso) e R$ 200 (reenvio e troca).",
  },
  {
    id: "F3",
    nome: "Verificação da reclamação",
    faz: "Cruza foto, data da captura, pedido, personalização e histórico; sinaliza suspeita com evidência.",
    pessoa: "Supervisor decide a suspeita em até 24 h.",
  },
  {
    id: "F4",
    nome: "Autonomia e escalação",
    faz: "Aplica a política, pede aprovação e chama a pessoa certa no canal do time.",
    pessoa: "Supervisor, qualidade (cosmetovigilância) e jurídico.",
  },
  {
    id: "F5",
    nome: "Prevenção de recontato",
    faz: "O agente analista detecta padrões, abre um incidente por padrão e avisa clientes com consentimento.",
    pessoa: "Analista valida o escopo; até 300 avisos por dia.",
  },
];

export function Mapa360() {
  return (
    <section className="mapa" aria-labelledby="mapa-titulo">
      <h2 id="mapa-titulo">Mapa 360°</h2>
      <p className="mapa__sub">
        O que o Gabriel assume na área de atendimento e onde a pessoa continua no controle.
      </p>
      <ol className="mapa__frentes">
        {FRENTES.map((f) => (
          <li key={f.id} className="mapa__frente">
            <div className="mapa__cabeca">
              <h3>{f.nome}</h3>
            </div>
            <p>{f.faz}</p>
            {f.pessoa !== "—" ? (
              <p className="mapa__pessoa">
                <b>Onde a pessoa decide:</b> {f.pessoa}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
