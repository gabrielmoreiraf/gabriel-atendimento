import type { ProgressoLeitura, Placar as TPlacar } from "../api/tipos";
import { formatarRs } from "../formato";

interface Props {
  placar: TPlacar | null;
  processando: boolean;
  /** Progresso do leitor (SSE `leitura`) durante a rodada. */
  progresso?: ProgressoLeitura | null;
  /** Mensagem da API quando a rodada não começa (ex.: 409, rodada já em andamento). */
  aviso?: string | null;
  onProcessar: () => void;
}

function rotuloBotao(processando: boolean, progresso?: ProgressoLeitura | null): string {
  if (!processando) return "Processar fila";
  if (!progresso) return "Processando…";
  return progresso.lidas < progresso.total
    ? `Lendo ${progresso.lidas}/${progresso.total}…`
    : "Decidindo…";
}

export function Placar({ placar, processando, progresso, aviso, onProcessar }: Props) {
  const itens: { rotulo: string; valor: string; tom?: string }[] = [
    {
      rotulo: "Resolvidas sozinho",
      valor: String(placar?.resolvidas_sozinho ?? "—"),
      tom: "resolvida",
    },
    {
      rotulo: "Aguardando aprovação",
      valor: String(placar?.aguardando_aprovacao ?? "—"),
      tom: "aprovacao",
    },
    ...(placar?.aguardando_cliente != null
      ? [{ rotulo: "Aguardando cliente", valor: String(placar.aguardando_cliente), tom: "cliente" }]
      : []),
    { rotulo: "Suspeitas", valor: String(placar?.suspeitas ?? "—"), tom: "suspeita" },
    { rotulo: "Escaladas", valor: String(placar?.escaladas ?? "—"), tom: "escalada" },
    { rotulo: "Valor executado", valor: formatarRs(placar?.valor_executado_rs) },
    { rotulo: "Custo evitado", valor: formatarRs(placar?.custo_evitado_rs) },
  ];
  return (
    <div className="placar">
      <dl className="placar__numeros" data-testid="placar">
        {itens.map((i) => (
          <div key={i.rotulo} className="placar__item" data-tom={i.tom}>
            <dt>{i.rotulo}</dt>
            <dd>{i.valor}</dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        className="botao botao--primario botao--grande"
        data-testid="btn-processar"
        disabled={processando}
        onClick={onProcessar}
      >
        {rotuloBotao(processando, progresso)}
      </button>
      {aviso ? (
        <output className="placar__aviso" data-testid="aviso-processar">
          {aviso}
        </output>
      ) : null}
    </div>
  );
}
