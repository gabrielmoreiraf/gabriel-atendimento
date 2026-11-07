import type { Placar as TPlacar } from "../api/tipos";
import { formatarRs } from "../formato";

interface Props {
  placar: TPlacar | null;
  processando: boolean;
  onProcessar: () => void;
}

export function Placar({ placar, processando, onProcessar }: Props) {
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
        {processando ? "Processando…" : "Processar fila"}
      </button>
    </div>
  );
}
