import type { Caso } from "../api/tipos";
import { formatarDataHora, formatarRs } from "../formato";
import { EstadoSelo } from "./EstadoSelo";

interface Props {
  caso: Caso | null;
  carregando: boolean;
  erro: string | null;
}

export function CasoPainel({ caso, carregando, erro }: Props) {
  if (erro) {
    return (
      <section className="painel caso" aria-label="Caso">
        <p className="erro" role="alert">
          Não consegui abrir o caso: {erro}
        </p>
      </section>
    );
  }
  if (!caso) {
    return (
      <section className="painel caso" aria-label="Caso">
        <p className="vazio">
          {carregando ? "Abrindo caso…" : "Escolha uma conversa na fila para ver o caso."}
        </p>
      </section>
    );
  }
  const { conversa, mensagens, anexos, veredicto, decisao, resposta_ao_cliente, pedido } = caso;
  return (
    <section className="painel caso" aria-labelledby="caso-titulo" aria-busy={carregando}>
      <header className="painel__cabeca">
        <h2 id="caso-titulo">
          <span className="mono">{conversa.conversation_id}</span> ·{" "}
          {conversa.assunto || "(sem assunto)"}
        </h2>
        <EstadoSelo estado={conversa.estado} />
      </header>
      <p className="caso__pedido">
        {conversa.marca} · {conversa.canal.replace("_", " ")}
        {pedido?.order_id ? (
          <>
            {" "}
            · pedido <span className="mono">{pedido.order_id}</span>
          </>
        ) : null}
        {pedido?.valor != null ? <> · {formatarRs(pedido.valor)}</> : null}
        {pedido?.status_entrega ? <> · {pedido.status_entrega.replaceAll("_", " ")}</> : null}
      </p>

      <div className="caso__grade">
        <div className="caso__bloco caso__chat">
          <h3>Conversa</h3>
          <ol className="chat">
            {mensagens.map((m, i) => (
              <li
                key={`${m.timestamp}-${i}`}
                className="chat__msg"
                data-autor={m.autor === "cliente" ? "cliente" : "time"}
              >
                <span className="chat__autor">
                  {m.autor} · <span className="mono">{formatarDataHora(m.timestamp)}</span>
                </span>
                <p>{m.texto}</p>
              </li>
            ))}
          </ol>
        </div>

        <div className="caso__lado">
          <div className="caso__bloco">
            <h3>Evidência</h3>
            {anexos.length === 0 && (veredicto?.sinais.length ?? 0) === 0 ? (
              <p className="muted">Sem anexos nem sinais.</p>
            ) : null}
            {anexos.length > 0 ? (
              <ul className="lista-simples">
                {anexos.map((a) => (
                  <li key={a.anexo_id}>
                    <span className="mono">{a.anexo_id}</span>: {a.descricao_visual}
                  </li>
                ))}
              </ul>
            ) : null}
            {veredicto && veredicto.sinais.length > 0 ? (
              <ul className="sinais">
                {veredicto.sinais.map((s, i) => (
                  <li key={`${s.tipo}-${i}`}>
                    <strong>{s.tipo.replaceAll("_", " ")}</strong>: {s.descricao}
                  </li>
                ))}
              </ul>
            ) : null}
            {veredicto?.justificativa ? <p className="muted">{veredicto.justificativa}</p> : null}
          </div>

          <div className="caso__bloco">
            <h3>Decisão da política</h3>
            {decisao ? (
              <>
                <p className="decisao__resultado">{decisao.resultado.replaceAll("_", " ")}</p>
                <p>{decisao.motivo}</p>
                <p className="muted">
                  Regra: <code className="mono">{decisao.regra}</code>
                </p>
                {decisao.aprovador_sugerido ? (
                  <p className="muted">
                    Aprovador: <span className="mono">{decisao.aprovador_sugerido}</span>
                  </p>
                ) : null}
              </>
            ) : (
              <p className="muted">Ainda não processada.</p>
            )}
          </div>

          <div className="caso__bloco">
            <h3>Resposta enviada ao cliente</h3>
            {resposta_ao_cliente ? (
              <blockquote className="resposta">{resposta_ao_cliente}</blockquote>
            ) : (
              <p className="muted">Nenhuma resposta enviada ainda.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
