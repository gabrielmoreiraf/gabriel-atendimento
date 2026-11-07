import { useEffect, useId, useRef, useState } from "react";
import type { ItemFila } from "../api/tipos";
import { formatarDataHora, rotuloEstado } from "../formato";
import { EstadoSelo } from "./EstadoSelo";

interface Props {
  itens: ItemFila[];
  selecionado: string | null;
  onAbrir: (conversationId: string) => void;
}

const ORDEM_ESTADOS = [
  "aberta",
  "resolvida",
  "aguardando_aprovacao",
  "aguardando_cliente",
  "suspeita",
  "escalada",
];

const CANAL = {
  whatsapp: { sigla: "W", nome: "WhatsApp" },
  email: { sigla: "@", nome: "E-mail" },
  reclame_aqui: { sigla: "RA", nome: "Reclame Aqui" },
} as const;

export function Fila({ itens, selecionado, onAbrir }: Props) {
  const [filtro, setFiltro] = useState<string>("todas");
  const [canalFiltro, setCanalFiltro] = useState<string>("todos");
  const porCanal = (canal: string) => itens.filter((c) => c.canal === canal).length;
  // o filtro de canal vem primeiro: as contagens por estado já respeitam o canal escolhido
  const doCanal = canalFiltro === "todos" ? itens : itens.filter((c) => c.canal === canalFiltro);
  const contagem = (estado: string) => doCanal.filter((c) => c.estado === estado).length;
  const visiveis = filtro === "todas" ? doCanal : doCanal.filter((c) => c.estado === filtro);
  const estados = ORDEM_ESTADOS.filter((e) => e === "aberta" || contagem(e) > 0);

  return (
    <section className="painel fila" aria-labelledby="fila-titulo">
      <header className="painel__cabeca fila__cabeca">
        <h2 id="fila-titulo">Fila</h2>
        <span className="painel__meta mono">{itens.length} conversas</span>
        <fieldset className="canais" aria-label="Filtrar por canal">
          <button
            type="button"
            className="canais__opcao"
            aria-pressed={canalFiltro === "todos"}
            onClick={() => setCanalFiltro("todos")}
          >
            Todos
          </button>
          {(Object.keys(CANAL) as (keyof typeof CANAL)[]).map((id) => (
            <button
              key={id}
              type="button"
              className="canais__opcao"
              aria-pressed={canalFiltro === id}
              onClick={() => setCanalFiltro(id)}
            >
              {CANAL[id].nome} <span className="mono">{porCanal(id)}</span>
            </button>
          ))}
        </fieldset>
        <FiltroEstado
          valor={filtro}
          onEscolher={setFiltro}
          opcoes={[
            { valor: "todas", rotulo: "Todas", total: doCanal.length },
            ...estados.map((e) => ({ valor: e, rotulo: rotuloEstado(e), total: contagem(e) })),
          ]}
        />
      </header>
      {visiveis.length === 0 ? (
        <p className="vazio">
          {itens.length === 0 ? "Fila vazia." : "Nenhuma conversa neste filtro."}
        </p>
      ) : (
        <ul className="fila__lista">
          {visiveis.map((c) => {
            const canal = CANAL[c.canal as keyof typeof CANAL];
            return (
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
                    <span className="mono fila__id">{c.conversation_id}</span>
                    <span className="mono fila__hora">{formatarDataHora(c.data_abertura)}</span>
                  </span>
                  <span className="fila__assunto">{c.assunto || "(sem assunto)"}</span>
                  <span className="fila__rodape">
                    <span className="fila__meta">
                      <span className="canal-sigla mono" aria-hidden="true">
                        {canal?.sigla ?? "?"}
                      </span>
                      {canal?.nome ?? c.canal} · {c.marca}
                    </span>
                    <EstadoSelo estado={c.estado} />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

interface OpcaoEstado {
  valor: string;
  rotulo: string;
  total: number;
}

/** Menu de estado com a cor de cada estado; fecha com Esc ou clique fora. */
function FiltroEstado({
  valor,
  opcoes,
  onEscolher,
}: {
  valor: string;
  opcoes: OpcaoEstado[];
  onEscolher: (valor: string) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const id = useId();
  const atual = opcoes.find((o) => o.valor === valor) ?? opcoes[0];

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => {
      if (!raiz.current?.contains(e.target as Node)) setAberto(false);
    };
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAberto(false);
    };
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", tecla);
    };
  }, [aberto]);

  return (
    <div className="estado-filtro" ref={raiz}>
      <button
        type="button"
        className="estado-filtro__botao"
        aria-expanded={aberto}
        aria-controls={id}
        onClick={() => setAberto((a) => !a)}
      >
        <span className="estado-filtro__rotulo">Estado</span>
        <span className="estado-filtro__valor" data-estado={atual?.valor}>
          <span className="ponto" aria-hidden="true" />
          {atual?.rotulo} <span className="mono">{atual?.total}</span>
        </span>
        <span className="estado-filtro__seta" aria-hidden="true">
          ▾
        </span>
      </button>
      {aberto ? (
        <ul className="estado-filtro__menu" id={id}>
          {opcoes.map((o) => (
            <li key={o.valor} data-estado={o.valor}>
              <button
                type="button"
                aria-pressed={o.valor === valor}
                onClick={() => {
                  onEscolher(o.valor);
                  setAberto(false);
                }}
              >
                <span className="ponto" aria-hidden="true" />
                {o.rotulo}
                <span className="mono">{o.total}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
