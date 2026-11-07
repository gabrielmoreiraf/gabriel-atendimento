import { useId, useState } from "react";
import type { MensagemCanal } from "../api/tipos";
import { SUPERVISORES } from "../equipe";
import { RELOGIO_0820_ISO } from "../formato";
import { MascoteMarca } from "../landing/Mascote";
import { DecisaoSuspeita, type DecisaoTipo } from "./DecisaoSuspeita";

interface Props {
  mensagens: MensagemCanal[];
  onAprovar: (aprovacaoId: string, supervisorId: string, comentario?: string) => Promise<unknown>;
  onRejeitar: (
    aprovacaoId: string,
    supervisorId: string,
    justificativa: string,
  ) => Promise<unknown>;
  /** Relógio da demo (ISO). O vigia roda nesse horário; quem decide os alertas é o backend. */
  relogio?: string;
  onRodarVigia?: (agoraIso: string) => Promise<unknown>;
  onDecidirSuspeita?: (
    suspeitaId: string,
    supervisorId: string,
    decisao: DecisaoTipo,
    justificativa: string,
  ) => Promise<unknown>;
}

const ROTULO_TIPO: Record<string, string> = {
  aviso: "Aviso",
  aprovacao: "Gabriel pediu aprovação",
  suspeita: "Gabriel sinalizou suspeita",
  escalacao: "Gabriel escalou para uma pessoa",
};

export function CanalTime({
  mensagens,
  onAprovar,
  onRejeitar,
  relogio,
  onRodarVigia,
  onDecidirSuspeita,
}: Props) {
  return (
    <section className="canal" aria-labelledby="canal-titulo">
      <header className="canal__cabeca">
        <h2 id="canal-titulo">Canal do time</h2>
        <span className="canal__sala"># atendimento-ops</span>
        {onRodarVigia && relogio ? <Vigia relogio={relogio} onRodar={onRodarVigia} /> : null}
      </header>
      {mensagens.length === 0 ? (
        <p className="canal__vazio">Sem mensagens. Avisos, suspeitas e aprovações chegam aqui.</p>
      ) : (
        <ol className="canal__lista" aria-label="Mensagens, da mais recente para a mais antiga">
          {[...mensagens].reverse().map((m) => (
            <li key={m.id} className="canal__msg" data-testid="canal-msg" data-tipo={m.tipo}>
              <div className="canal__autor">
                <span className="canal__avatar" aria-hidden="true">
                  <MascoteMarca tamanho={24} />
                </span>
                <span className="canal__quem">
                  <strong>Gabriel</strong>
                  <span className="canal__tipo">{ROTULO_TIPO[m.tipo] ?? m.tipo}</span>
                </span>
              </div>
              <p className="canal__texto">
                {m.para ? <span className="canal__mencao">@{m.para} </span> : null}
                {m.texto}
              </p>
              {m.conversation_id || m.solicitado_por ? (
                <span className="canal__ref">
                  {m.conversation_id ? <span className="mono">{m.conversation_id}</span> : null}
                  {m.conversation_id && m.solicitado_por ? " · " : null}
                  {m.solicitado_por ? (
                    <>
                      Pedido por <span className="mono">{m.solicitado_por}</span>
                    </>
                  ) : null}
                </span>
              ) : null}
              {m.tipo === "aprovacao" && m.aprovacao_id ? (
                <Aprovacao msg={m} onAprovar={onAprovar} onRejeitar={onRejeitar} />
              ) : null}
              {m.tipo === "suspeita" && m.suspeita_id && onDecidirSuspeita ? (
                <DecisaoSuspeita
                  suspeitaId={m.suspeita_id}
                  prazo={m.prazo}
                  estado={m.estado}
                  sinalizadoPor={m.sinalizado_por}
                  onDecidir={onDecidirSuspeita}
                  tema="canal"
                />
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Aprovacao({
  msg,
  onAprovar,
  onRejeitar,
}: { msg: MensagemCanal } & Pick<Props, "onAprovar" | "onRejeitar">) {
  const id = useId();
  const aprovacaoId = msg.aprovacao_id as string;
  // a API recusa autoaprovação; a tela só não oferece quem pediu
  const opcoes = SUPERVISORES.filter((s) => s.id !== msg.solicitado_por);
  const padrao = opcoes.some((s) => s.id === msg.para)
    ? (msg.para as string)
    : (opcoes[0]?.id ?? "");
  const [supervisor, setSupervisor] = useState<string>(padrao);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const pendente = !msg.estado || msg.estado === "pendente";
  if (!pendente) {
    return (
      <p className="canal__decidida" data-estado={msg.estado}>
        Pedido {msg.estado}
      </p>
    );
  }

  async function executar(fn: () => Promise<unknown>) {
    setEnviando(true);
    setErro(null);
    try {
      await fn();
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="canal__aprovacao">
      <div className="canal__campos">
        <label htmlFor={`${id}-sup`}>Supervisor</label>
        <select id={`${id}-sup`} value={supervisor} onChange={(e) => setSupervisor(e.target.value)}>
          {opcoes.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nome} ({s.id})
            </option>
          ))}
        </select>
        <label htmlFor={`${id}-txt`}>Comentário ou justificativa</label>
        <input
          id={`${id}-txt`}
          type="text"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Obrigatória para rejeitar"
        />
      </div>
      <div className="canal__botoes">
        <button
          type="button"
          className="botao botao--aprovar"
          data-testid="btn-aprovar"
          disabled={enviando}
          onClick={() => executar(() => onAprovar(aprovacaoId, supervisor, texto || undefined))}
        >
          Aprovar
        </button>
        <button
          type="button"
          className="botao botao--rejeitar"
          data-testid="btn-rejeitar"
          disabled={enviando || texto.trim() === ""}
          onClick={() => executar(() => onRejeitar(aprovacaoId, supervisor, texto.trim()))}
        >
          Rejeitar
        </button>
      </div>
      {erro ? (
        <p className="canal__erro" role="alert">
          Recusado pela API: {erro}
        </p>
      ) : null}
    </div>
  );
}

function Vigia({
  relogio,
  onRodar,
}: { relogio: string; onRodar: (agoraIso: string) => Promise<unknown> }) {
  const [rodando, setRodando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function rodar(agoraIso: string) {
    setRodando(true);
    setErro(null);
    try {
      await onRodar(agoraIso);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setRodando(false);
    }
  }

  return (
    <div className="canal__vigia">
      <div className="canal__botoes">
        <button
          type="button"
          className="botao botao--rejeitar"
          data-testid="btn-rodar-vigia"
          disabled={rodando}
          onClick={() => rodar(relogio)}
        >
          Rodar vigia
        </button>
        <button
          type="button"
          className="botao botao--rejeitar"
          data-testid="btn-vigia-0820"
          disabled={rodando}
          onClick={() => rodar(RELOGIO_0820_ISO)}
        >
          Avançar o relógio para 08:20
        </button>
      </div>
      {erro ? (
        <p className="canal__erro" role="alert">
          Vigia falhou: {erro}
        </p>
      ) : null}
    </div>
  );
}
