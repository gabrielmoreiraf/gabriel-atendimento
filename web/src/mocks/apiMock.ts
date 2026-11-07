// Implementação em memória de `Api`, com o mesmo formato da API real.
import { type Api, ErroApi } from "../api/cliente";
import type { ItemFila, MensagemCanal, Placar, RegistroAcao, SuspeitaPendente } from "../api/tipos";
import {
  acoesProcessadasMock,
  alertasVigiaMock,
  canalProcessadoMock,
  casoMock,
  estadosProcessadosMock,
  filaMock,
  padroesMock,
  placarZeroMock,
  replayMock,
  resultadoReplayMock,
  resultadoTratamentoMock,
} from "./dados";

export function criarApiMock(): Api {
  let fila: ItemFila[] = filaMock.map((c) => ({ ...c }));
  let acoes: RegistroAcao[] = [];
  let canal: MensagemCanal[] = [];
  let placar: Placar = { ...placarZeroMock };
  let suspeitas: SuspeitaPendente[] = [];
  const copia = <T>(v: T): T => structuredClone(v);
  const zerar = () => {
    fila = filaMock.map((c) => ({ ...c }));
    acoes = [];
    canal = [];
    placar = { ...placarZeroMock };
    suspeitas = [];
  };

  return {
    fila: async () => copia(fila),
    processarFila: async () => {
      fila = fila.map((c) => ({
        ...c,
        estado: estadosProcessadosMock[c.conversation_id] ?? c.estado,
      }));
      acoes = copia(acoesProcessadasMock);
      canal = copia(canalProcessadoMock);
      placar = {
        resolvidas_sozinho: 2,
        aguardando_aprovacao: 1,
        suspeitas: 1,
        escaladas: 1,
        valor_executado_rs: 89.9,
        custo_evitado_rs: 0,
      };
      return copia(placar);
    },
    processarConversa: async (id) => {
      const c = fila.find((x) => x.conversation_id === id);
      if (!c) throw new ErroApi(404, `Conversa ${id} não encontrada`);
      return casoMock(c, true);
    },
    caso: async (id) => {
      const c = fila.find((x) => x.conversation_id === id);
      if (!c) throw new ErroApi(404, `Conversa ${id} não encontrada`);
      return casoMock(c, c.estado !== "aberta");
    },
    acoes: async () => copia(acoes),
    canal: async () => copia(canal),
    placar: async () => copia(placar),
    aprovar: async (aprovacaoId, supervisorId) => {
      const msg = canal.find((m) => m.aprovacao_id === aprovacaoId);
      if (msg?.solicitado_por === supervisorId) {
        throw new ErroApi(403, "Supervisor não pode aprovar a própria ação (autoaprovação).");
      }
      canal = canal.map((m) => (m.aprovacao_id === aprovacaoId ? { ...m, estado: "aprovada" } : m));
      return { ok: true };
    },
    rejeitar: async (aprovacaoId) => {
      canal = canal.map((m) =>
        m.aprovacao_id === aprovacaoId ? { ...m, estado: "rejeitada" } : m,
      );
      return { ok: true };
    },
    padroes: async () => copia(padroesMock),
    tratarPadrao: async (tipo) => {
      const padrao = padroesMock.find((p) => p.tipo === tipo);
      if (!padrao) throw new ErroApi(404, `padrão ${tipo} não encontrado na base`);
      return resultadoTratamentoMock(padrao);
    },
    alertasVigia: async (agoraIso) => alertasVigiaMock(agoraIso),
    rodarVigia: async (agoraIso) => {
      const resp = alertasVigiaMock(agoraIso) as { sla: MensagemCanal[] };
      const vistos = new Set(canal.map((m) => m.texto));
      for (const [i, a] of resp.sla.entries()) {
        if (vistos.has(a.texto)) continue;
        canal = [
          ...canal,
          {
            id: `CN-VIGIA-${i}`,
            tipo: "aviso",
            para: a.para,
            texto: a.texto,
            conversation_id: a.conversation_id,
          },
        ];
      }
      return { agora: agoraIso, postados: resp.sla };
    },
    suspeitas: async () => copia(suspeitas.filter((x) => x.estado === "pendente")),
    decidirSuspeita: async (suspeitaId, supervisorId, decisao, justificativa) => {
      const suspeita = suspeitas.find((x) => x.suspeita_id === suspeitaId);
      if (!suspeita) throw new ErroApi(404, `suspeita ${suspeitaId} não existe`);
      if (supervisorId === suspeita.sinalizado_por)
        throw new ErroApi(403, "Quem sinalizou a suspeita não pode decidi-la.");
      if (suspeita.estado !== "pendente")
        throw new ErroApi(409, `Suspeita ${suspeitaId} já está ${suspeita.estado}.`);
      if (!justificativa.trim()) throw new ErroApi(422, "justificativa obrigatória");
      suspeitas = suspeitas.map((x) => (x === suspeita ? { ...x, estado: decisao } : x));
      canal = canal.map((m) => (m.suspeita_id === suspeitaId ? { ...m, estado: decisao } : m));
      const item = replayMock.find((c) => c.conversation_id === suspeita.conversation_id);
      if (!item) throw new ErroApi(404, "conversa da suspeita não encontrada");
      return resultadoReplayMock(item);
    },
    reiniciarDemo: async () => {
      zerar();
      return { ok: true };
    },
    casosReplay: async () => copia(replayMock),
    processarReplay: async (id) => {
      const item = replayMock.find((c) => c.conversation_id === id);
      if (!item) throw new ErroApi(404, `Caso ${id} não está no replay`);
      const caso = resultadoReplayMock(item);
      if (caso.veredicto?.suspeita && !suspeitas.some((x) => x.conversation_id === id)) {
        const suspeita_id = `SUS-MOCK-${suspeitas.length + 1}`;
        const prazo = "2026-11-03T08:00:00-03:00";
        suspeitas = [
          ...suspeitas,
          {
            suspeita_id,
            conversation_id: id,
            order_id: item.order_id,
            acao_proposta: "reenviar_produto",
            valor_rs: 0,
            sinais: caso.veredicto.sinais,
            sinalizado_por: "agente",
            sinalizada_em: "2026-11-02T08:00:00-03:00",
            prazo,
            estado: "pendente",
          },
        ];
        canal = [
          ...canal,
          {
            id: `CN-${suspeita_id}`,
            tipo: "suspeita",
            para: "supervisor_01",
            texto: `${id}: FIO sinalizou evidência incoerente. (exemplo)`,
            conversation_id: id,
            suspeita_id,
            prazo,
            estado: "pendente",
            sinalizado_por: "agente",
          },
        ];
      }
      return caso;
    },
  };
}
