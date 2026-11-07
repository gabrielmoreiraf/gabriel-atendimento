import type { RegistroAcao } from "../api/tipos";
import { formatarDataHora, formatarRs } from "../formato";

export function ConsoleSistemas({ acoes }: { acoes: RegistroAcao[] }) {
  return (
    <section className="painel console" aria-labelledby="console-titulo">
      <header className="painel__cabeca">
        <h2 id="console-titulo">Console dos sistemas</h2>
        <span className="painel__meta">{acoes.length} ações · ao vivo</span>
      </header>
      {acoes.length === 0 ? (
        <p className="vazio">Nenhuma ação executada ainda. Cada ação do agente aparece aqui.</p>
      ) : (
        <div className="console__rolagem">
          <table className="console__tabela">
            <thead>
              <tr>
                <th scope="col">Hora</th>
                <th scope="col">Sistema · ação</th>
                <th scope="col" className="num">
                  Valor
                </th>
                <th scope="col">Executor · aprovador</th>
                <th scope="col">Referência</th>
              </tr>
            </thead>
            <tbody>
              {/* o log chega em ordem de execução; a tela mostra o mais recente no topo */}
              {[...acoes].reverse().map((a) => (
                <tr key={a.acao_id} data-testid="console-acao">
                  <td className="mono">{formatarDataHora(a.data_hora).split(" ").at(-1)}</td>
                  <td>
                    <strong>{a.acao}</strong>
                    <span className="console__sub">
                      {a.sistema}
                      {a.conversation_id ? (
                        <span className="mono"> · {a.conversation_id}</span>
                      ) : null}
                    </span>
                  </td>
                  <td className="num mono">{formatarRs(a.valor_rs)}</td>
                  <td>
                    <span className="mono">{a.executado_por}</span>
                    <span className="console__sub mono">
                      {a.aprovado_por ? `aprov. ${a.aprovado_por}` : "—"}
                    </span>
                  </td>
                  <td className="mono console__ref">{a.referencia_sistema}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
