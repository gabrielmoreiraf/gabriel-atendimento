import { useId, useState } from "react";
import { SUPERVISORES } from "../equipe";
import { formatarDataHora } from "../formato";

export type DecisaoTipo = "procedente" | "improcedente";

interface Props {
  suspeitaId: string;
  prazo?: string | null;
  estado?: string | null;
  sinalizadoPor?: string | null;
  onDecidir: (
    suspeitaId: string,
    supervisorId: string,
    decisao: DecisaoTipo,
    justificativa: string,
  ) => Promise<unknown>;
  /** Visual do canal (fundo escuro) ou do painel claro. */
  tema?: "canal" | "painel";
}

/** Supervisor decide a suspeita. Quem pode decidir é o backend (403 se for quem sinalizou). */
export function DecisaoSuspeita({
  suspeitaId,
  prazo,
  estado,
  sinalizadoPor,
  onDecidir,
  tema = "painel",
}: Props) {
  const id = useId();
  const opcoes = SUPERVISORES.filter((s) => s.id !== sinalizadoPor);
  const [supervisor, setSupervisor] = useState<string>(opcoes[0]?.id ?? "");
  const [justificativa, setJustificativa] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const pendente = !estado || estado === "pendente";
  if (!pendente) {
    return (
      <p className="suspeita__decidida" data-estado={estado} data-tema={tema}>
        Suspeita <span className="mono">{suspeitaId}</span> decidida: {estado}
      </p>
    );
  }

  async function decidir(decisao: DecisaoTipo) {
    setEnviando(true);
    setErro(null);
    try {
      await onDecidir(suspeitaId, supervisor, decisao, justificativa.trim());
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  const bloqueado = enviando || justificativa.trim() === "" || supervisor === "";

  return (
    <div className="suspeita" data-tema={tema}>
      <p className="suspeita__prazo">
        Suspeita <span className="mono">{suspeitaId}</span> · decidir até{" "}
        <strong className="mono">{formatarDataHora(prazo)}</strong>
        {sinalizadoPor ? (
          <>
            {" "}
            · sinalizada por <span className="mono">{sinalizadoPor}</span>
          </>
        ) : null}
      </p>
      <div className="canal__campos">
        <label htmlFor={`${id}-sup`}>Supervisor que decide</label>
        <select id={`${id}-sup`} value={supervisor} onChange={(e) => setSupervisor(e.target.value)}>
          {opcoes.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nome} ({s.id})
            </option>
          ))}
        </select>
        <label htmlFor={`${id}-just`}>Justificativa da decisão</label>
        <input
          id={`${id}-just`}
          type="text"
          value={justificativa}
          onChange={(e) => setJustificativa(e.target.value)}
          placeholder="Obrigatória"
        />
      </div>
      <div className="canal__botoes">
        <button
          type="button"
          className="botao botao--suspeita"
          data-testid="btn-suspeita-procedente"
          disabled={bloqueado}
          onClick={() => decidir("procedente")}
        >
          Procedente
        </button>
        <button
          type="button"
          className="botao botao--aprovar"
          data-testid="btn-suspeita-improcedente"
          disabled={bloqueado}
          onClick={() => decidir("improcedente")}
        >
          Improcedente
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
