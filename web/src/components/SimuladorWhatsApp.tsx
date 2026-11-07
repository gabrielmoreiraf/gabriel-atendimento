import { useEffect, useRef, useState } from "react";
import type { Api, ClienteSimulado } from "../api/cliente";
import { formatarRs } from "../formato";
import { MascoteMarca } from "../landing/Mascote";

interface Props {
  api: Api;
  /** Abre o caso no painel de operação, para ver o que o Gabriel conferiu e fez. */
  onVerCaso: (conversationId: string) => void;
}

interface Bolha {
  autor: "cliente" | "gabriel";
  texto: string;
}

/**
 * Demo do canal do cliente: a mensagem entra na fila como uma conversa nova e o Gabriel responde
 * pelo mesmo fluxo da operação. O WhatsApp real fica para integração futura; nenhuma regra
 * de negócio aqui, só envia e mostra o que a API devolveu.
 */
export function SimuladorWhatsApp({ api, onVerCaso }: Props) {
  const [clientes, setClientes] = useState<ClienteSimulado[]>([]);
  const [ativo, setAtivo] = useState<ClienteSimulado | null>(null);
  const [pedido, setPedido] = useState<string>("");
  const [conversas, setConversas] = useState<Record<string, Bolha[]>>({});
  const [ultima, setUltima] = useState<Record<string, string>>({});
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLLIElement>(null);

  useEffect(() => {
    api
      .simuladorClientes?.()
      .then((lista) => {
        setClientes(lista);
        if (lista[0]) {
          setAtivo(lista[0]);
          setPedido(lista[0].pedidos[0]?.order_id ?? "");
        }
      })
      .catch(() => setErro("Não consegui carregar os clientes da base."));
  }, [api]);

  const bolhas = ativo ? (conversas[ativo.customer_id] ?? []) : [];

  useEffect(() => {
    if (bolhas.length > 0) fim.current?.scrollIntoView?.({ block: "end", behavior: "smooth" });
  }, [bolhas.length]);

  if (!api.simuladorMensagem) {
    return (
      <section className="wpp" aria-labelledby="wpp-titulo">
        <h2 id="wpp-titulo">WhatsApp do cliente</h2>
        <p className="vazio">Disponível só com o backend ligado.</p>
      </section>
    );
  }

  function escolher(c: ClienteSimulado) {
    setAtivo(c);
    setPedido(c.pedidos[0]?.order_id ?? "");
    setErro(null);
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    const mensagem = texto.trim();
    if (!ativo || !mensagem || enviando || !api.simuladorMensagem) return;
    const id = ativo.customer_id;
    setTexto("");
    setErro(null);
    setConversas((atual) => ({
      ...atual,
      [id]: [...(atual[id] ?? []), { autor: "cliente", texto: mensagem }],
    }));
    setEnviando(true);
    try {
      const r = await api.simuladorMensagem({
        customer_id: id,
        order_id: pedido || undefined,
        texto: mensagem,
        anterior: ultima[id],
      });
      // cumprimento não abre caso: o botão continua apontando para o último atendimento
      if (r.conversation_id)
        setUltima((atual) => ({ ...atual, [id]: r.conversation_id as string }));
      setConversas((atual) => ({
        ...atual,
        [id]: [
          ...(atual[id] ?? []),
          {
            autor: "gabriel",
            texto: r.resposta || "Recebi sua mensagem e já passei para o time.",
          },
        ],
      }));
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  const pedidoAtivo = ativo?.pedidos.find((p) => p.order_id === pedido);

  return (
    <section className="wpp" aria-labelledby="wpp-titulo">
      <header className="wpp__cabeca">
        <h2 id="wpp-titulo">WhatsApp do cliente</h2>
        <p>
          Escreva como se fosse o cliente. A mensagem entra na fila e o Gabriel responde com os
          dados do cadastro e do pedido. Aqui é uma simulação do canal: a integração com o WhatsApp
          de verdade fica para depois.
        </p>
      </header>
      <div className="wpp__grade">
        <ul className="wpp__clientes" aria-label="Clientes da base">
          {clientes.map((c) => (
            <li key={c.customer_id}>
              <button
                type="button"
                className="wpp__cliente"
                aria-current={ativo?.customer_id === c.customer_id ? "true" : undefined}
                onClick={() => escolher(c)}
              >
                <span className="wpp__avatar" aria-hidden="true">
                  {c.nome.charAt(0)}
                </span>
                <span className="wpp__cliente-texto">
                  <strong>{c.nome}</strong>
                  <span className="muted">
                    {c.pedidos[0]
                      ? `${c.pedidos[0].marca} · ${(c.pedidos[0].status_entrega ?? "").replaceAll("_", " ")}`
                      : "sem pedido"}
                  </span>
                </span>
                {conversas[c.customer_id]?.length ? (
                  <span className="wpp__badge">{conversas[c.customer_id].length}</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>

        <div className="wpp__chat">
          {ativo ? (
            <>
              <div className="wpp__topo">
                <span className="wpp__avatar" aria-hidden="true">
                  {ativo.nome.charAt(0)}
                </span>
                <div className="wpp__quem">
                  <strong>{ativo.nome}</strong>
                  <label className="muted">
                    Pedido{" "}
                    <select value={pedido} onChange={(e) => setPedido(e.target.value)}>
                      {ativo.pedidos.map((p) => (
                        <option key={p.order_id} value={p.order_id}>
                          {p.order_id} · {p.marca}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {pedidoAtivo ? (
                  <span className="wpp__pedido muted">
                    {pedidoAtivo.descricao_produto}
                    {pedidoAtivo.valor != null ? ` · ${formatarRs(pedidoAtivo.valor)}` : ""}
                  </span>
                ) : null}
              </div>

              <ol className="wpp__mensagens" aria-live="polite">
                {bolhas.length === 0 ? (
                  <li className="wpp__dica">
                    Experimente: “Cadê meu pedido?”, “Chegou quebrado, quero reenvio” ou “Fui
                    cobrado duas vezes”.
                  </li>
                ) : null}
                {bolhas.map((b, i) => (
                  <li key={`${b.autor}-${i}`} className="wpp__bolha" data-autor={b.autor}>
                    {b.autor === "gabriel" ? (
                      <span className="wpp__autor">
                        <MascoteMarca tamanho={16} /> Gabriel
                      </span>
                    ) : null}
                    <p>{b.texto}</p>
                  </li>
                ))}
                {enviando ? (
                  <li className="wpp__bolha wpp__digitando" data-autor="gabriel">
                    Gabriel está conferindo o pedido…
                  </li>
                ) : null}
                <li ref={fim} aria-hidden="true" />
              </ol>

              {erro ? (
                <p className="erro" role="alert">
                  {erro}
                </p>
              ) : null}

              <form className="wpp__envio" onSubmit={enviar}>
                <label htmlFor="wpp-texto" className="sr-only">
                  Mensagem do cliente
                </label>
                <input
                  id="wpp-texto"
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  placeholder="Escreva como o cliente…"
                  autoComplete="off"
                  disabled={enviando}
                />
                <button
                  type="submit"
                  className="botao botao--primario"
                  disabled={enviando || !texto.trim()}
                >
                  Enviar
                </button>
                {ultima[ativo.customer_id] ? (
                  <button
                    type="button"
                    className="botao botao--suave"
                    onClick={() => onVerCaso(ultima[ativo.customer_id])}
                  >
                    Ver o que o Gabriel fez
                  </button>
                ) : null}
              </form>
            </>
          ) : (
            <p className="vazio">Carregando clientes…</p>
          )}
        </div>
      </div>
    </section>
  );
}
