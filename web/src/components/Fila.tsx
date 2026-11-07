import type { ItemFila } from "../api/tipos";
import { formatarDataHora } from "../formato";
import { EstadoSelo } from "./EstadoSelo";

interface Props {
  itens: ItemFila[];
  selecionado: string | null;
  onAbrir: (conversationId: string) => void;
}

export function Fila({ itens, selecionado, onAbrir }: Props) {
  return (
    <section className="painel fila" aria-labelledby="fila-titulo">
      <header className="painel__cabeca">
        <h2 id="fila-titulo">Fila</h2>
        <span className="painel__meta">{itens.length} conversas</span>
      </header>
      {itens.length === 0 ? (
        <p className="vazio">Fila vazia.</p>
      ) : (
        <ul className="fila__lista">
          {itens.map((c) => (
            <li key={c.conversation_id}>
              <button
                type="button"
                className="fila__item"
                data-testid="fila-item"
                data-estado={c.estado}
                aria-current={c.conversation_id === selecionado ? "true" : undefined}
                onClick={() => onAbrir(c.conversation_id)}
              >
                <span className="fila__linha">
                  <span className="mono">{c.conversation_id}</span>
                  <EstadoSelo estado={c.estado} />
                </span>
                <span className="fila__assunto">{c.assunto || "(sem assunto)"}</span>
                <span className="fila__meta">
                  {c.marca} · {c.canal.replace("_", " ")} · {formatarDataHora(c.data_abertura)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
