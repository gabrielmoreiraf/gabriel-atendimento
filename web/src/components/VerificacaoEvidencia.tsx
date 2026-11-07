import { useState } from "react";
import type { Caso, ItemReplay, SuspeitaPendente } from "../api/tipos";
import { formatarDataHora, formatarRs } from "../formato";
import { DecisaoSuspeita, type DecisaoTipo } from "./DecisaoSuspeita";

interface Props {
  casos: ItemReplay[];
  onProcessar: (conversationId: string) => Promise<Caso>;
  /** Suspeitas pendentes (`GET /api/suspeitas`); a do caso aberto ganha os botões de decisão. */
  suspeitas?: SuspeitaPendente[];
  onDecidirSuspeita?: (
    suspeitaId: string,
    supervisorId: string,
    decisao: DecisaoTipo,
    justificativa: string,
  ) => Promise<Caso>;
}

const ROTULO_SINAL: Record<string, string> = {
  hash_repetido: "Foto repetida de outro pedido",
  captura_antes_da_entrega: "Foto tirada antes da entrega",
  editor_de_imagem: "Editor de imagem",
  personalizacao_divergente: "Personalização divergente",
  produto_divergente: "Produto divergente",
  reenvios_anteriores: "Reenvios anteriores",
  sem_exif: "Foto sem data de captura",
};

export const rotuloSinal = (tipo: string) => ROTULO_SINAL[tipo] ?? tipo.replaceAll("_", " ");

export function VerificacaoEvidencia({
  casos,
  onProcessar,
  suspeitas = [],
  onDecidirSuspeita,
}: Props) {
  const [ativo, setAtivo] = useState<string | null>(null);
  const [resultado, setResultado] = useState<Caso | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function verificar(id: string) {
    setAtivo(id);
    setResultado(null);
    setErro(null);
    setCarregando(true);
    try {
      setResultado(await onProcessar(id));
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setCarregando(false);
    }
  }

  return (
    <section className="verificacao" id="verificacao" aria-labelledby="verificacao-titulo">
      <header className="verificacao__cabeca">
        <h2 id="verificacao-titulo">Verificação de evidência</h2>
        <p>
          Reclamações com foto. Antes de reenviar ou estornar, o FIO confere se a foto é nova,
          quando foi tirada, a data de entrega e a personalização do pedido.
        </p>
      </header>
      <div className="verificacao__grade">
        <ul className="verificacao__lista">
          {casos.length === 0 ? <li className="vazio">Nenhum caso com foto disponível.</li> : null}
          {casos.map((c) => (
            <li
              key={c.conversation_id}
              className="verificacao__item"
              data-testid="replay-item"
              aria-current={c.conversation_id === ativo ? "true" : undefined}
            >
              <span className="verificacao__item-texto">
                <span className="mono fila__linha">{c.conversation_id}</span>
                {c.assunto ? <span className="fila__assunto">{c.assunto}</span> : null}
                <span className="fila__meta">
                  {[
                    c.order_id,
                    c.marca,
                    c.canal?.replace("_", " "),
                    formatarDataHora(c.data_abertura),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </span>
              <button
                type="button"
                className="botao botao--primario"
                data-testid="btn-replay"
                disabled={carregando && c.conversation_id === ativo}
                onClick={() => verificar(c.conversation_id)}
              >
                {carregando && c.conversation_id === ativo ? "Verificando…" : "Verificar"}
              </button>
            </li>
          ))}
        </ul>

        <div className="verificacao__resultado" aria-live="polite" aria-busy={carregando}>
          {erro ? (
            <p className="erro" role="alert">
              Não consegui verificar {ativo}: {erro}
            </p>
          ) : null}
          {!erro && !resultado ? (
            <p className="vazio">
              {carregando ? "Verificando a evidência…" : "Escolha um caso e clique em Verificar."}
            </p>
          ) : null}
          {resultado ? <Resultado caso={resultado} /> : null}
          {resultado && onDecidirSuspeita
            ? suspeitas
                .filter((x) => x.conversation_id === resultado.conversa.conversation_id)
                .map((x) => (
                  <div className="verificacao__suspeita" key={x.suspeita_id}>
                    <DecisaoSuspeita
                      suspeitaId={x.suspeita_id}
                      prazo={x.prazo}
                      estado={x.estado}
                      sinalizadoPor={x.sinalizado_por}
                      onDecidir={async (...args) => setResultado(await onDecidirSuspeita(...args))}
                    />
                  </div>
                ))
            : null}
        </div>
      </div>
    </section>
  );
}

function Resultado({ caso }: { caso: Caso }) {
  const { veredicto, decisao, anexos, resposta_ao_cliente, conversa } = caso;
  const sinais = veredicto?.sinais ?? [];
  return (
    <div className="verificacao__detalhe">
      <div className="verificacao__veredicto" data-suspeita={veredicto?.suspeita ? "sim" : "nao"}>
        <span className="mono">{conversa.conversation_id}</span>
        <strong>
          {veredicto == null
            ? "Sem veredicto"
            : veredicto.suspeita
              ? "Evidência incoerente: supervisor decide"
              : "Evidência confere"}
        </strong>
      </div>

      <div className="verificacao__colunas">
        <div className="caso__bloco">
          <h3>Foto enviada</h3>
          {anexos.length === 0 ? <p className="muted">Sem anexos.</p> : null}
          {anexos.map((a) => (
            <dl key={a.anexo_id} className="anexo">
              <dt>Anexo</dt>
              <dd className="mono">{a.anexo_id}</dd>
              <dt>Descrição</dt>
              <dd>{a.descricao_visual}</dd>
              <dt>Capturada em</dt>
              <dd className="mono">{formatarDataHora(a.exif_data_captura)}</dd>
              {a.exif_software ? (
                <>
                  <dt>Editada com</dt>
                  <dd>{a.exif_software}</dd>
                </>
              ) : null}
            </dl>
          ))}
        </div>

        <div className="caso__bloco">
          <h3>Sinais do verificador</h3>
          {sinais.length === 0 ? (
            <p className="muted">Nenhum sinal de incoerência.</p>
          ) : (
            <ul className="verificacao__sinais">
              {sinais.map((s, i) => (
                <li key={`${s.tipo}-${i}`} data-testid="sinal-evidencia" data-tipo={s.tipo}>
                  <strong>{rotuloSinal(s.tipo)}</strong>
                  <span>{s.descricao}</span>
                </li>
              ))}
            </ul>
          )}
          {veredicto?.justificativa ? <p className="muted">{veredicto.justificativa}</p> : null}
          {veredicto ? (
            <p className="muted">
              Aceitar se for falso: {formatarRs(veredicto.custo_aceitar_falso_rs)} · sinalizar se
              for verdadeiro: {formatarRs(veredicto.custo_sinalizar_verdadeiro_rs)}
            </p>
          ) : null}
        </div>

        <div className="caso__bloco">
          <h3>Decisão da política</h3>
          {decisao ? (
            <>
              <p className="decisao__resultado">{decisao.resultado.replaceAll("_", " ")}</p>
              <p>{decisao.motivo}</p>
            </>
          ) : (
            <p className="muted">Sem decisão.</p>
          )}
          <h3 className="verificacao__subtitulo">Resposta ao cliente</h3>
          {resposta_ao_cliente ? (
            <blockquote className="resposta">{resposta_ao_cliente}</blockquote>
          ) : (
            <p className="muted">Nenhuma resposta.</p>
          )}
        </div>
      </div>
    </div>
  );
}
