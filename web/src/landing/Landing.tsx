import "./landing.css";

import PillNav from "../vendor/reactbits/PillNav";
import { Mascote, MascoteMarca } from "./Mascote";
import { BotaoBrilho } from "./microkit/BotaoBrilho";
import { type CartaoItem, CartoesDeslizantes } from "./microkit/CartoesDeslizantes";

const icone = (d: string) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
    <path
      d={d}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const PASSOS: CartaoItem[] = [
  {
    nome: "1 · Lê",
    detalhe:
      "A mensagem do cliente, por WhatsApp, e-mail ou Reclame Aqui. Texto do cliente é dado, nunca instrução.",
    marca: icone("M4 5h16v10H8l-4 4V5Z"),
  },
  {
    nome: "2 · Consulta",
    detalhe:
      "Pedido, itens, rastreio, pagamento e anexos, sempre pelo ID, nos sistemas da empresa.",
    marca: icone("M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm9 16-4-4"),
  },
  {
    nome: "3 · Confere",
    detalhe:
      "Se a foto é deste pedido, se foi tirada depois da entrega, se passou por editor ou já apareceu antes.",
    marca: icone("M4 12l5 5L20 6"),
  },
  {
    nome: "4 · Decide",
    detalhe:
      "Pela política e pela alçada, somando o que o pedido já recebeu. A IA lê; quem decide é a regra.",
    marca: icone("M12 3v18M5 8h14M7 8l-3 7h6l-3-7Zm10 0-3 7h6l-3-7Z"),
  },
  {
    nome: "5 · Age",
    detalhe:
      "Reenvia, estorna ou abre chamado com referência no log. Fora da alçada, chama a pessoa certa.",
    marca: icone("M5 12h14M13 6l6 6-6 6"),
  },
];

const PROBLEMA = [
  { numero: "~4.000", texto: "contatos por mês, por WhatsApp, e-mail e Reclame Aqui" },
  { numero: "12,2 min", texto: "de trabalho humano, em média, por contato" },
  { numero: "até 4", texto: "dos 11 sistemas da empresa num único contato" },
  { numero: "32,9%", texto: "dos contatos são o mesmo cliente voltando pelo mesmo pedido" },
];

const RESULTADOS = [
  { numero: "34 de 65", texto: "conversas da fila das 8h resolvidas sem uma pessoa" },
  {
    numero: "64 de 64",
    texto: "casos em que o time passou da alçada somando ações no mesmo pedido, barrados",
  },
  { numero: "R$ 1.356,91", texto: "de custo evitado estimado em reenvios com foto suspeita" },
  { numero: "27 de 27", texto: "relatos de reação adversa reconhecidos e escalados" },
];

const FRENTES = [
  ["Triagem e SLA", false],
  ["Resolução em vários sistemas", false],
  ["Verificação da reclamação", true],
  ["Autonomia e escalação", true],
  ["Prevenção de recontato", false],
] as const;

function Seta() {
  return (
    <span className="pilula__seta" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
        <path d="M7 17 17 7M9 7h8v8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function Landing() {
  return (
    <div className="landing">
      <header className="lp-nav">
        <PillNav
          ariaLabel="Seções"
          logo={<MascoteMarca tamanho={30} />}
          logoAlt="FIO, início"
          logoHref="/"
          items={[
            { label: "Problema", href: "#problema" },
            { label: "Como funciona", href: "#como" },
            { label: "Slack", href: "#slack" },
            { label: "Resultados", href: "#resultados" },
          ]}
          theme="dark"
          surface="solid"
          barColor="#1d4683"
          textColor="#ffffff"
          highlightColor="#d7d900"
          size="lg"
          itemStyle="plain"
          hoverEffect="fill"
          indicator="dot"
          defaultActiveIndex={-1}
        />
        <a className="pilula pilula--clara" href="/app" data-testid="lp-entrar-topo">
          Entrar no FIO <Seta />
        </a>
      </header>

      <section className="lp-hero">
        <div className="lp-hero__texto">
          <h1>
            O colega de atendimento que <em>confere antes de pagar</em>.
          </h1>
          <p className="lp-hero__sub">
            O FIO pega a fila, consulta pedido, rastreio e pagamento, confere a foto da reclamação e
            age dentro da alçada. Quando não pode decidir, chama a pessoa certa no Slack do time.
          </p>
          <div className="lp-hero__acoes">
            <BotaoBrilho href="/app" testId="lp-entrar">
              Entrar no FIO
            </BotaoBrilho>
            <a className="lp-link" href="#como">
              Ver como funciona
            </a>
          </div>
        </div>
        <div className="lp-hero__arte" aria-hidden="true">
          <span className="lp-bolha lp-bolha--a" />
          <span className="lp-bolha lp-bolha--b" />
          <Mascote tamanho={340} />
          <div className="lp-chat lp-chat--1">
            <b>AT116568 · Reação adversa</b>
            <span>FIO orientou suspender o uso e chamou a qualidade.</span>
          </div>
          <div className="lp-chat lp-chat--2">
            <b>Aprovação · R$ 155,81</b>
            <span>Reembolso acima do limite do atendente.</span>
            <span className="lp-chat__botoes">
              <i>Aprovar</i>
              <i>Rejeitar</i>
            </span>
          </div>
          <div className="lp-chat lp-chat--3">
            <b>AT104936 · Foto suspeita</b>
            <span>Tirada antes da entrega. Cliente recebe "em análise".</span>
          </div>
        </div>
        <svg
          className="lp-onda"
          viewBox="0 0 1440 120"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d="M0 64c240 56 480 56 720 16s480-56 720 8v32H0Z" fill="var(--lp-claro)" />
        </svg>
      </section>

      <div className="lp-canais" aria-label="Onde o FIO trabalha">
        {["WhatsApp", "E-mail", "Reclame Aqui", "Slack", "Claude"].map((c) => (
          <span key={c}>{c}</span>
        ))}
      </div>

      <section id="problema" className="lp-secao">
        <h2>Resolver um contato quase nunca é só responder uma mensagem.</h2>
        <dl className="lp-lista">
          {PROBLEMA.map((p) => (
            <div key={p.numero} className="lp-linha">
              <dt>{p.numero}</dt>
              <dd>{p.texto}</dd>
            </div>
          ))}
        </dl>
        <p className="lp-destaque">
          O Reclame Aqui tem <b>11,6% das conversas</b> e <b>50,4% do custo</b>. E nem toda avaria é
          real: na base há fotos repetidas em pedidos diferentes, tiradas antes da entrega ou
          editadas.
        </p>
      </section>

      <section id="como" className="lp-secao">
        <h2>Cinco passos, com uma pessoa no controle de tudo o que passa da alçada.</h2>
        <CartoesDeslizantes itens={PASSOS} rotulo="Os cinco passos do FIO" />
      </section>

      <section id="slack" className="lp-escura">
        <div className="lp-escura__texto">
          <h2>O supervisor aprova pelo Slack, com um clique.</h2>
          <ul>
            <li>Só vai ao canal o que pede uma pessoa: aprovação, suspeita, escalação e SLA.</li>
            <li>Quem pediu não aprova a própria ação, e quem sinalizou a suspeita não a decide.</li>
            <li>Pedido de colaborador por @FIO passa pela mesma política. A alçada não muda.</li>
          </ul>
        </div>
        <div className="lp-slack" aria-label="Exemplo de mensagem do FIO no Slack">
          <p className="lp-slack__canal"># atendimento-ops</p>
          <div className="lp-slack__msg">
            <Mascote tamanho={40} piscando={false} />
            <div>
              <p>
                <b>FIO</b> <span className="lp-slack__app">APP</span> <time>08:00</time>
              </p>
              <p>
                <b>FIO pediu aprovação</b>: reembolso de R$ 155,81 no pedido GBH469163, acima do
                limite de R$ 100,00 do atendente.
              </p>
              <p className="lp-slack__botoes">
                <span className="lp-slack__aprovar">Aprovar</span>
                <span>Rejeitar</span>
              </p>
              <p className="lp-slack__depois">Aprovado por supervisor_02 pelo Slack · EST000186</p>
            </div>
          </div>
        </div>
      </section>

      <section id="resultados" className="lp-secao">
        <h2>Medido na fila das 8h e reexecutado sobre o histórico da empresa.</h2>
        <dl className="lp-lista lp-lista--resultado">
          {RESULTADOS.map((r) => (
            <div key={r.numero} className="lp-linha">
              <dt>{r.numero}</dt>
              <dd>{r.texto}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="lp-secao">
        <h2>Pensado para a área inteira, provado em uma frente.</h2>
        <ol className="lp-frentes">
          {FRENTES.map(([nome, provado], i) => (
            <li key={nome} data-provado={provado ? "sim" : "nao"}>
              <span className="mono">F{i + 1}</span> {nome}
              {provado ? <em>provado na PoC</em> : null}
            </li>
          ))}
        </ol>
      </section>

      <section className="lp-final">
        <div>
          <h2>Pronto para ver o FIO trabalhar?</h2>
          <p>Processe a fila das 8h, abra um caso suspeito e aprove pelo canal do time.</p>
          <BotaoBrilho href="/app" testId="lp-entrar-final">
            Entrar no FIO
          </BotaoBrilho>
        </div>
        <Mascote tamanho={220} />
      </section>

      <footer className="lp-rodape">
        <span>FIO · GoHacks Talent 2026 · Desafio Atendimento ao Cliente</span>
        <a href="https://github.com/gabrielmoreiraf/fio-atendimento">Código no GitHub</a>
      </footer>
    </div>
  );
}
