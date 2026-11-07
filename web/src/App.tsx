import { useCallback, useEffect, useRef, useState } from "react";
import type { Api } from "./api/cliente";
import type {
  Caso,
  ItemFila,
  ItemReplay,
  MensagemCanal,
  PadraoAnalista,
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
import { VerificacaoEvidencia } from "./components/VerificacaoEvidencia";
import { AGORA_ISO, formatarDataHora } from "./formato";
import { alertasComoMensagens, juntarCanal } from "./vigia";

interface Props {
  api: Api;
  /** Assina eventos ao vivo (SSE). Devolve a função que cancela. */
  assinar: (aoEvento: () => void) => () => void;
  modo?: "api" | "mock";
}

const mensagemDe = (e: unknown) => (e instanceof Error ? e.message : String(e));

export default function App({ api, assinar, modo = "api" }: Props) {
  const [fila, setFila] = useState<ItemFila[]>([]);
  const [acoes, setAcoes] = useState<RegistroAcao[]>([]);
  const [canal, setCanal] = useState<MensagemCanal[]>([]);
  const [placar, setPlacar] = useState<TPlacar | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [caso, setCaso] = useState<Caso | null>(null);
  const [carregandoCaso, setCarregandoCaso] = useState(false);
  const [erroCaso, setErroCaso] = useState<string | null>(null);
  const [processando, setProcessando] = useState(false);
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

  useEffect(() => {
    api
      .casosReplay()
      .then(setReplay)
      .catch(() => setReplay([]));
  }, [api]);

  useEffect(() => {
    recarregar();
    return assinar(() => {
      recarregar();
    });
  }, [recarregar, assinar]);

  function abrir(id: string) {
    selecionadoRef.current = id;
    setSelecionado(id);
    setCaso(null);
    carregarCaso(id);
  }

  async function processar() {
    setProcessando(true);
    try {
      setPlacar(await api.processarFila());
    } catch (e) {
      setErroGeral(mensagemDe(e));
    } finally {
      setProcessando(false);
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

  return (
    <div className="app">
      <div className="primeira-tela">
        <header className="topo">
          <div className="topo__marca">
            <h1>FIO</h1>
            <p>
              o colega de atendimento (Gocase / GoBeauté) · agora:{" "}
              <span className="mono">{formatarDataHora(relogio)}</span>
              {modo === "mock" ? (
                <span className="topo__mock">dados de exemplo · API offline</span>
              ) : null}
            </p>
          </div>
          <a className="topo__link" href="#verificacao">
            Verificação de evidência
          </a>
          <Placar placar={placar} processando={processando} onProcessar={processar} />
        </header>
        {erroGeral ? (
          <output className="erro erro--faixa">Falha ao falar com a API: {erroGeral}</output>
        ) : null}
        <main className="grade">
          <Fila itens={fila} selecionado={selecionado} onAbrir={abrir} />
          <div className="centro">
            <CasoPainel caso={caso} carregando={carregandoCaso} erro={erroCaso} />
            <ConsoleSistemas acoes={acoes} />
          </div>
          <CanalTime
            mensagens={juntarCanal(canal, avisosVigia)}
            onAprovar={aprovar}
            onRejeitar={rejeitar}
            relogio={relogio}
            onRodarVigia={rodarVigia}
            onDecidirSuspeita={decidirSuspeita}
          />
        </main>
      </div>
      <VerificacaoEvidencia
        casos={replay}
        onProcessar={processarReplay}
        suspeitas={suspeitas}
        onDecidirSuspeita={decidirSuspeita}
      />
      <AgenteAnalista padroes={padroes} onTratar={tratarPadrao} />
    </div>
  );
}
