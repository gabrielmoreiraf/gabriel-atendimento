import type { Caso, RegistroAcao } from "../api/tipos";
import { formatarDataHora, formatarRs } from "../formato";
import { EstadoSelo } from "./EstadoSelo";
import { rotuloDecisao, rotuloSinal } from "./VerificacaoEvidencia";

interface Props {
  caso: Caso | null;
  carregando: boolean;
  erro: string | null;
  /** Ações registradas nos sistemas; o painel mostra só as desta conversa. */
  acoes?: RegistroAcao[];
  /** Falso enquanto a fila não foi processada: o painel explica o primeiro passo. */
  filaProcessada?: boolean;
}

const nomeDaAcao = (acao: string) => {
  const texto = acao.replaceAll("_", " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
};

export function CasoPainel({ caso, carregando, erro, acoes = [], filaProcessada = true }: Props) {
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
        {carregando ? (
          <p className="vazio">Abrindo caso…</p>
        ) : filaProcessada ? (
          <p className="vazio">Escolha uma conversa na fila para ver o que o Gabriel fez.</p>
        ) : (
          <div className="caso__inicio">
            <h2>Como usar</h2>
            <ol>
              <li>
                Clique em <strong>Processar fila</strong>. O Gabriel lê cada conversa, confere
                pedido e foto e resolve o que está dentro da alçada.
              </li>
              <li>
                O que passa do limite ou parece suspeito vai para o <strong>canal do time</strong>,
                à direita, onde o supervisor aprova ou rejeita.
              </li>
              <li>Clique numa conversa da fila para ver, passo a passo, o que ele fez.</li>
            </ol>
          </div>
        )}
      </section>
    );
  }
  const { conversa, mensagens, anexos, veredicto, decisao, resposta_ao_cliente, pedido } = caso;
  const sinais = veredicto?.sinais ?? [];
  const feitas =
    caso.acoes && caso.acoes.length > 0
      ? caso.acoes
      : acoes.filter((a) => a.conversation_id === conversa.conversation_id);
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
          <h3>
            <span className="caso__passo">1</span> O que o cliente pediu
          </h3>
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
            <h3>
              <span className="caso__passo">2</span> O que o Gabriel conferiu
            </h3>
            {anexos.length === 0 && sinais.length === 0 ? (
              <p className="muted">Sem foto anexada e nenhum sinal de problema.</p>
            ) : null}
            {anexos.length > 0 ? (
              <ul className="lista-simples">
                {anexos.map((a) => (
                  <li key={a.anexo_id}>
                    Foto <span className="mono">{a.anexo_id}</span>: {a.descricao_visual}
                  </li>
                ))}
              </ul>
            ) : null}
            {sinais.length > 0 ? (
              <ul className="sinais">
                {sinais.map((s, i) => (
                  <li key={`${s.tipo}-${i}`}>
                    <strong>{rotuloSinal(s.tipo)}</strong>: {s.descricao}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          <div className="caso__bloco">
            <h3>
              <span className="caso__passo">3</span> O que decidiu
            </h3>
            {decisao ? (
              <>
                <p className="decisao__resultado">{rotuloDecisao(decisao.resultado)}</p>
                <p>{decisao.motivo}</p>
                {decisao.aprovador_sugerido ? (
                  <p className="muted">
                    Quem aprova: <span className="mono">{decisao.aprovador_sugerido}</span>
                  </p>
                ) : null}
              </>
            ) : (
              <p className="muted">Ainda não processada. Clique em Processar fila.</p>
            )}
          </div>

          <div className="caso__bloco">
            <h3>
              <span className="caso__passo">4</span> O que fez
            </h3>
            {feitas.length > 0 ? (
              <ul className="caso__feitas">
                {feitas.map((a) => (
                  <li key={a.acao_id}>
                    <strong>{nomeDaAcao(a.acao)}</strong>
                    {a.valor_rs > 0 ? <> · {formatarRs(a.valor_rs)}</> : null}
                    <span className="muted">
                      {" "}
                      no {a.sistema} · ref. <span className="mono">{a.referencia_sistema}</span>
                      {a.aprovado_por ? <> · aprovado por {a.aprovado_por}</> : null}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Nenhuma ação nos sistemas ainda.</p>
            )}
            <p className="caso__subtitulo">Resposta ao cliente</p>
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
