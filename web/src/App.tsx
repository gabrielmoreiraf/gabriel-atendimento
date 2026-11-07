import { useCallback, useEffect, useRef, useState } from "react";
import { type Api, ErroApi } from "./api/cliente";
import type {
  Caso,
  EventoApi,
  ItemFila,
  ItemReplay,
  MensagemCanal,
  PadraoAnalista,
  ProgressoLeitura,
  RegistroAcao,
  SuspeitaPendente,
  Placar as TPlacar,
} from "./api/tipos";
import { AgenteAnalista } from "./components/AgenteAnalista";
import { CanalTime } from "./components/CanalTime";
import { CasoPainel } from "./components/CasoPainel";
import { ConsoleSistemas } from "./components/ConsoleSistemas";
import { Fila } from "./components/Fila";
import { Placar } from "./components/Placar";
import { SimuladorWhatsApp } from "./components/SimuladorWhatsApp";
import { VerificacaoEvidencia } from "./components/VerificacaoEvidencia";
import { AGORA_ISO, formatarDataHora } from "./formato";
import { MascoteMarca } from "./landing/Mascote";
import PillNav from "./vendor/reactbits/PillNav";
import { alertasComoMensagens, juntarCanal } from "./vigia";

type Tela = "operacao" | "whatsapp" | "evidencia" | "analista";

interface Props {
  api: Api;
  /** Assina eventos ao vivo (SSE). Devolve a função que cancela. */
  assinar: (aoEvento: (evento?: EventoApi) => void) => () => void;
  modo?: "api" | "mock";
}

const mensagemDe = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function App({ api, assinar, modo = "api" }: Props) {
  const [tela, setTela] = useState<Tela>("operacao");
  const [foco, setFoco] = useState<"fila" | "canal">("fila");
  const irPara = (t: Tela) => {
    setTela(t);
    window.scrollTo?.(0, 0);
  };
  const [fila, setFila] = useState<ItemFila[]>([]);
  const [acoes, setAcoes] = useState<RegistroAcao[]>([]);
  const [canal, setCanal] = useState<MensagemCanal[]>([]);
  const [placar, setPlacar] = useState<TPlacar | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [caso, setCaso] = useState<Caso | null>(null);
  const [carregandoCaso, setCarregandoCaso] = useState(false);
  const [erroCaso, setErroCaso] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);
  const processandoRef = useRef(false);
  const [progresso, setProgresso] = useState<ProgressoLeitura | null>(null);
  const [avisoProcessar, setAvisoProcessar] = useState<string | null>(null);
  const [reiniciando, setReiniciando] = useState(false);
  // muda a cada reinício: remonta os painéis que guardam resultado local (replay, analista)
  const [rodadaDemo, setRodadaDemo] = useState(0);
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [replay, setReplay] = useState<ItemReplay[]>([]);
  const [padroes, setPadroes] = useState<PadraoAnalista[]>([]);
  const [suspeitas, setSuspeitas] = useState<SuspeitaPendente[]>([]);
  const [avisosVigia, setAvisosVigia] = useState<MensagemCanal[]>([]);
  const [relogio, setRelogio] = useState(AGORA_ISO);
  const relogioRef = useRef(AGORA_ISO);
  const selecionadoRef = useRef<string | null>(null);

  const carregarCaso = useCallback(
    async (id: string) => {
      setCarregandoCaso(true);
      setErroCaso(null);
      try {
        const c = await api.caso(id);
        if (selecionadoRef.current === id) setCaso(c);
      } catch (e) {
        if (selecionadoRef.current === id) setErroCaso(mensagemDe(e));
      } finally {
        setCarregandoCaso(false);
      }
    },
    [api],
  );

  const recarregar = useCallback(async () => {
    try {
      const [f, a, c, p] = await Promise.all([api.fila(), api.acoes(), api.canal(), api.placar()]);
      setFila(f);
      setAcoes(a);
      setCanal(c);
      setPlacar(p);
      setErroGeral(null);
    } catch (e) {
      setErroGeral(mensagemDe(e));
    }
    // painéis extras: se a rota falhar, o resto da tela continua
    api
      .suspeitas()
      .then(setSuspeitas)
      .catch(() => setSuspeitas([]));
    api
      .padroes()
      .then(setPadroes)
      .catch(() => setPadroes([]));
    api
      .alertasVigia(relogioRef.current)
      .then((r) => setAvisosVigia(alertasComoMensagens(r)))
      .catch(() => setAvisosVigia([]));
    if (selecionadoRef.current) await carregarCaso(selecionadoRef.current);
  }, [api, carregarCaso]);

  // O canal diz de onde vem: espelhado no Slack quando o backend tem o Slack ligado.
  const [noSlack, setNoSlack] = useState(false);
  useEffect(() => {
    api
      .saude?.()
      .then((s) => setNoSlack(Boolean(s.slack)))
      .catch(() => setNoSlack(false));
  }, [api]);

  useEffect(() => {
    api
      .casosReplay()
      .then(setReplay)
      .catch(() => setReplay([]));
  }, [api]);

  useEffect(() => {
    recarregar();
    return assinar((evento) => {
      // progresso do leitor: só interessa durante a rodada disparada nesta tela
      if (evento?.tipo === "leitura") {
        if (processandoRef.current) setProgresso(evento.payload as ProgressoLeitura);
        return;
      }
      recarregar();
    });
  }, [recarregar, assinar]);

  function abrir(id: string) {
    selecionadoRef.current = id;
    setSelecionado(id);
    setCaso(null);
    carregarCaso(id);
  }

  async function reiniciarDemo() {
    setReiniciando(true);
    setAvisoProcessar(null);
    try {
      await api.reiniciarDemo();
      selecionadoRef.current = null;
      setSelecionado(null);
      setCaso(null);
      setErroCaso(null);
      setProgresso(null);
      relogioRef.current = AGORA_ISO;
      setRelogio(AGORA_ISO);
      setRodadaDemo((n) => n + 1);
      setErroGeral(null);
    } catch (e) {
      setAvisoProcessar(`Não consegui reiniciar a demo: ${mensagemDe(e)}`);
    } finally {
      setReiniciando(false);
    }
    await recarregar();
  }

  async function processar() {
    processandoRef.current = true;
    setProcessando(true);
    setProgresso(null);
    setAvisoProcessar(null);
    try {
      setPlacar(await api.processarFila());
    } catch (e) {
      // 409: já há uma rodada em andamento; a tela segue viva e mostra o motivo
      if (e instanceof ErroApi && e.status === 409) setAvisoProcessar(e.message);
      else setErroGeral(mensagemDe(e));
    } finally {
      processandoRef.current = false;
      setProcessando(false);
      setProgresso(null);
    }
    await recarregar();
  }

  async function aprovar(id: string, supervisor: string, comentario?: string) {
    await api.aprovar(id, supervisor, comentario);
    await recarregar();
  }

  async function rodarVigia(agoraIso: string) {
    await api.rodarVigia(agoraIso);
    relogioRef.current = agoraIso;
    setRelogio(agoraIso);
    await recarregar();
  }

  async function decidirSuspeita(
    id: string,
    supervisor: string,
    decisao: "procedente" | "improcedente",
    justificativa: string,
  ) {
    const caso = await api.decidirSuspeita(id, supervisor, decisao, justificativa);
    await recarregar();
    return caso;
  }

  async function tratarPadrao(tipo: string) {
    const resultado = await api.tratarPadrao(tipo);
    recarregar();
    return resultado;
  }

  async function processarReplay(id: string) {
    const caso = await api.processarReplay(id);
    await recarregar();
    return caso;
  }

  async function rejeitar(id: string, supervisor: string, justificativa: string) {
    await api.rejeitar(id, supervisor, justificativa);
    await recarregar();
  }

  const telas: { id: Tela; rotulo: string }[] = [
    { id: "operacao", rotulo: "Operação" },
    { id: "whatsapp", rotulo: "WhatsApp" },
    { id: "evidencia", rotulo: "Conferir fotos" },
    { id: "analista", rotulo: "Padrões" },
  ];

  return (
    <div className="app" data-tela={tela} data-foco={foco}>
      <header className="barra">
        <div className="barra__marca">
          <a className="logo" href="/" aria-label="Gabriel, voltar ao início">
            <MascoteMarca tamanho={36} />
            <span>Gabriel</span>
          </a>
        </div>
        <div className="barra__nav">
          <PillNav
            ariaLabel="Telas"
            items={telas.map((t) => ({ label: t.rotulo, href: `#${t.id}` }))}
            activeHref={`#${tela}`}
            onItemClick={(item, _indice, evento) => {
              evento.preventDefault();
              const alvo = telas.find((t) => `#${t.id}` === item.href);
              if (alvo) irPara(alvo.id);
            }}
            theme="light"
            surface="solid"
            barColor="#e6ebf3"
            textColor="#13213a"
            highlightColor="#2659a5"
            itemStyle="plain"
            hoverEffect="fill"
            indicator="pill"
            collapse="never"
          />
        </div>
        <div className="barra__agora">
          <span>Agora</span>
          <span className="mono">{formatarDataHora(relogio)}</span>
          {modo === "mock" ? (
            <span className="topo__mock">dados de exemplo · API offline</span>
          ) : null}
        </div>
        <button
          type="button"
          className="botao botao--suave"
          data-testid="btn-reiniciar"
          disabled={reiniciando || processando}
          onClick={reiniciarDemo}
        >
          {reiniciando ? "Reiniciando…" : "Reiniciar"}
        </button>
      </header>
      {erroGeral ? (
        <output className="erro erro--faixa">Falha ao falar com a API: {erroGeral}</output>
      ) : null}

      {tela === "operacao" ? (
        <div className="operacao">
          <Placar
            placar={placar}
            processando={processando}
            progresso={progresso}
            aviso={avisoProcessar}
            onProcessar={processar}
          />
          <main className="grade">
            <Fila itens={fila} selecionado={selecionado} onAbrir={abrir} />
            <div className="centro">
              <CasoPainel
                caso={caso}
                carregando={carregandoCaso}
                erro={erroCaso}
                acoes={acoes}
                filaProcessada={fila.some((c) => c.estado !== "aberta")}
              />
              <ConsoleSistemas acoes={acoes} />
            </div>
            <CanalTime
              mensagens={juntarCanal(canal, avisosVigia)}
              onAprovar={aprovar}
              onRejeitar={rejeitar}
              relogio={relogio}
              onRodarVigia={rodarVigia}
              onDecidirSuspeita={decidirSuspeita}
              noSlack={noSlack}
            />
          </main>
        </div>
      ) : null}
      {tela === "whatsapp" ? (
        <SimuladorWhatsApp
          api={api}
          onVerCaso={(cid) => {
            irPara("operacao");
            recarregar().then(() => abrir(cid));
          }}
        />
      ) : null}
      {tela === "evidencia" ? (
        <VerificacaoEvidencia
          key={`verificacao-${rodadaDemo}`}
          casos={replay}
          onProcessar={processarReplay}
          suspeitas={suspeitas}
          onDecidirSuspeita={decidirSuspeita}
        />
      ) : null}
      {tela === "analista" ? (
        <AgenteAnalista key={`analista-${rodadaDemo}`} padroes={padroes} onTratar={tratarPadrao} />
      ) : null}

      <nav className="barra-inferior" aria-label="Telas no celular">
        {(
          [
            ["fila", "Fila"],
            ["canal", "Canal"],
            ["whatsapp", "WhatsApp"],
            ["evidencia", "Fotos"],
            ["analista", "Padrões"],
          ] as const
        ).map(([id, rotulo]) => {
          const atual =
            id === "fila" || id === "canal" ? tela === "operacao" && foco === id : tela === id;
          return (
            <button
              key={id}
              type="button"
              aria-current={atual ? "page" : undefined}
              onClick={() => {
                if (id === "fila" || id === "canal") {
                  irPara("operacao");
                  setFoco(id);
                } else {
                  irPara(id);
                }
              }}
            >
              {rotulo}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
