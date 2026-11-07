import { useState } from "react";
import type { PadraoAnalista, ResultadoTratamento } from "../api/tipos";

interface Props {
  padroes: PadraoAnalista[];
  onTratar: (tipo: string) => Promise<ResultadoTratamento>;
}

const ROTULO_PADRAO: Record<string, string> = {
  cobranca_em_dobro: "Cobrança em dobro",
  contato_repetido: "Contato repetido",
};

const MAX_PEDIDOS_VISIVEIS = 6;

export function AgenteAnalista({ padroes, onTratar }: Props) {
  return (
    <section className="analista" aria-labelledby="analista-titulo">
      <header className="analista__cabeca">
        <h2 id="analista-titulo">Agente analista</h2>
        <p>
          Trabalha em equipe com o FIO: acha a causa comum, abre um incidente e avisa os clientes
          afetados de uma vez.
        </p>
      </header>
      {padroes.length === 0 ? (
        <p className="vazio">Nenhum padrão de causa comum na base agora.</p>
      ) : (
        <ul className="analista__lista">
          {padroes.map((p) => (
            <Padrao key={p.tipo} padrao={p} onTratar={onTratar} />
          ))}
        </ul>
      )}
    </section>
  );
}

function Padrao({ padrao, onTratar }: { padrao: PadraoAnalista } & Pick<Props, "onTratar">) {
  const [resultado, setResultado] = useState<ResultadoTratamento | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function tratar() {
    setEnviando(true);
    setErro(null);
    try {
      setResultado(await onTratar(padrao.tipo));
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  const visiveis = padrao.escopo.slice(0, MAX_PEDIDOS_VISIVEIS);
  const resto = padrao.escopo.length - visiveis.length;

  return (
    <li className="analista__padrao" data-testid="padrao-item" data-tipo={padrao.tipo}>
      <div className="analista__topo">
        <h3>{ROTULO_PADRAO[padrao.tipo] ?? padrao.tipo.replaceAll("_", " ")}</h3>
        <span className="analista__escopo">{padrao.escopo.length} pedidos</span>
      </div>
      <p>{padrao.fator}</p>
      <p className="analista__pedidos mono">
        {visiveis.join(" · ")}
        {resto > 0 ? ` · +${resto}` : ""}
      </p>
      <dl className="analista__evidencia">
        {Object.entries(padrao.evidencia).map(([k, v]) => (
          <div key={k}>
            <dt>{k.replaceAll("_", " ")}</dt>
            <dd className="mono">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
          </div>
        ))}
      </dl>
      {resultado ? (
        <div className="analista__resultado" data-testid="resultado-padrao">
          <p>
            Incidente <strong className="mono">{resultado.incidente?.incidente_id ?? "—"}</strong>
            {resultado.ja_tratado ? " (já tratado antes)" : ""}
          </p>
          <ul>
            <li>{resultado.notificacoes.length} avisos enviados</li>
            <li>{resultado.sem_consentimento.length} sem consentimento (não avisados)</li>
            {resultado.adiados.length > 0 ? <li>{resultado.adiados.length} para amanhã</li> : null}
          </ul>
        </div>
      ) : (
        <button
          type="button"
          className="botao botao--primario"
          data-testid="btn-tratar-padrao"
          disabled={enviando}
          onClick={tratar}
        >
          {enviando ? "Tratando…" : "Tratar"}
        </button>
      )}
      {erro ? (
        <p className="erro" role="alert">
          Não consegui tratar: {erro}
        </p>
      ) : null}
    </li>
  );
}
