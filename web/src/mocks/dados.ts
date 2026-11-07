// Dados de exemplo para a UI enquanto a API (W4) não sobe.
// Conversas e textos recortados de docs/fila_aberta.csv e docs/historico_mensagens.csv.
// Estados, decisões, valores e ações abaixo são ILUSTRATIVOS (não são saída do motor).
import type {
  Caso,
  ItemFila,
  ItemReplay,
  MensagemCanal,
  PadraoAnalista,
  Placar,
  RegistroAcao,
  RespostaVigia,
  ResultadoTratamento,
} from "../api/tipos";

export const filaMock: ItemFila[] = [
  {
    conversation_id: "AT116160",
    canal: "reclame_aqui",
    marca: "Kokeshi",
    assunto: "Pedido sem atualização",
    order_id: "GBH473217",
    data_abertura: "2026-10-29 13:53:49",
    prioridade: 1,
    estado: "aberta",
  },
  {
    conversation_id: "AT116171",
    canal: "reclame_aqui",
    marca: "Kokeshi",
    assunto: "Pedido sem atualização",
    order_id: "GBH481046",
    data_abertura: "2026-10-29 15:02:16",
    prioridade: 2,
    estado: "aberta",
  },
  {
    conversation_id: "AT116473",
    canal: "reclame_aqui",
    marca: "Auá",
    assunto: "Pedido atrasado e sem resposta",
    order_id: "GBH476745",
    data_abertura: "2026-10-31 15:11:54",
    prioridade: 3,
    estado: "aberta",
  },
  {
    conversation_id: "AT116480",
    canal: "email",
    marca: "Gocase",
    assunto: "Ajuda com o pedido GCH559342",
    order_id: "GCH559342",
    data_abertura: "2026-10-31 15:58:30",
    prioridade: 4,
    estado: "aberta",
  },
  {
    conversation_id: "AT116486",
    canal: "reclame_aqui",
    marca: "Ápice",
    assunto: "Atraso na entrega",
    order_id: "GBH474054",
    data_abertura: "2026-10-31 18:27:33",
    prioridade: 5,
    estado: "aberta",
  },
];

/** Estado ilustrativo de cada conversa depois de "Processar fila" no modo mock. */
export const estadosProcessadosMock: Record<string, ItemFila["estado"]> = {
  AT116160: "resolvida",
  AT116171: "resolvida",
  AT116473: "aguardando_aprovacao",
  AT116480: "suspeita",
  AT116486: "escalada",
};

export const casoMock = (conversa: ItemFila, processado: boolean): Caso => ({
  conversa,
  mensagens: [
    {
      autor: "cliente",
      timestamp: conversa.data_abertura,
      texto:
        conversa.conversation_id === "AT116473"
          ? "[Pedido atrasado e sem resposta] Meu pedido GBH476745 era pra ter chegado até 30/10 e até agora nada. O rastreio diz 'aguardando transferência' na Expressa Já desde 29/10. Meu CPF é ***.***.***-12."
          : `[${conversa.assunto}] O rastreio diz 'aguardando transferência' e não anda. Pedido ${conversa.order_id}.`,
    },
    ...(processado
      ? [
          {
            autor: "agente",
            timestamp: "2026-11-02 08:00:05",
            texto: "Olá! Conferi o rastreio e já tomei providência. Te aviso por aqui. (exemplo)",
          },
        ]
      : []),
  ],
  pedido: {
    order_id: conversa.order_id ?? "",
    marca: conversa.marca,
    status_entrega: "em_transito",
    data_entrega: null,
  },
  anexos:
    conversa.conversation_id === "AT116480"
      ? [
          {
            anexo_id: "IMG000001",
            descricao_visual: "Itens do pedido sobre a mesa; a nota fiscal lista um item a mais.",
            hash_perceptual: "bff98c72083a26e6",
            exif_data_captura: "2026-08-02 12:23:28",
            exif_software: null,
          },
        ]
      : [],
  veredicto: processado
    ? {
        suspeita: estadosProcessadosMock[conversa.conversation_id] === "suspeita",
        sinais:
          estadosProcessadosMock[conversa.conversation_id] === "suspeita"
            ? [
                {
                  tipo: "hash_repetido",
                  descricao: "Mesma imagem (hash perceptual) já enviada em outro pedido. (exemplo)",
                  anexo_id: "IMG000001",
                },
              ]
            : [],
        custo_aceitar_falso_rs: 0,
        custo_sinalizar_verdadeiro_rs: 0,
        justificativa: "Exemplo de justificativa do verificador.",
      }
    : null,
  decisao: processado
    ? {
        resultado:
          estadosProcessadosMock[conversa.conversation_id] === "aguardando_aprovacao"
            ? "pedir_aprovacao"
            : "executar",
        regra: "limites_por_papel.atendente.reenvio_max_rs",
        motivo: "Exemplo: motivo citado pelo motor de políticas.",
      }
    : null,
  acoes: [],
  resposta_ao_cliente: processado
    ? "Olá! Conferi o rastreio e já tomei providência. Te aviso por aqui. (exemplo)"
    : null,
});

export const acoesProcessadasMock: RegistroAcao[] = [
  {
    acao_id: "AC-MOCK-0001",
    conversation_id: "AT116160",
    order_id: "GBH473217",
    data_hora: "2026-11-02 08:00:03",
    sistema: "portal_transportadora",
    acao: "abrir_chamado_transportadora",
    valor_rs: 0,
    executado_por: "agente_ia",
    aprovado_por: null,
    referencia_sistema: "CH-MOCK-01",
  },
  {
    acao_id: "AC-MOCK-0002",
    conversation_id: "AT116171",
    order_id: "GBH481046",
    data_hora: "2026-11-02 08:00:04",
    sistema: "oms",
    acao: "reenviar_produto",
    valor_rs: 89.9,
    executado_por: "agente_ia",
    aprovado_por: null,
    referencia_sistema: "RE-MOCK-02",
  },
];

export const canalProcessadoMock: MensagemCanal[] = [
  {
    id: "CN-MOCK-1",
    tipo: "aprovacao",
    para: "supervisor_01",
    texto:
      "Pedido de aprovação: reenvio do pedido GBH476745 (AT116473) acima da alçada do atendente. (exemplo)",
    conversation_id: "AT116473",
    aprovacao_id: "APR-MOCK-1",
    estado: "pendente",
    solicitado_por: "agente",
  },
  {
    id: "CN-MOCK-2",
    tipo: "suspeita",
    para: "supervisor_01",
    texto: "Evidência incoerente em AT116480: imagem repetida de outro pedido. (exemplo)",
    conversation_id: "AT116480",
    aprovacao_id: null,
    estado: null,
  },
  {
    id: "CN-MOCK-3",
    tipo: "escalacao",
    para: "analista_01",
    texto: "AT116486 escalada para uma pessoa: caso sem regra automática. (exemplo)",
    conversation_id: "AT116486",
  },
  {
    id: "CN-MOCK-4",
    tipo: "aviso",
    para: null,
    texto: "Aviso ao time: vários atrasos na Expressa Já com 'aguardando transferência'. (exemplo)",
    conversation_id: null,
  },
];

export const placarZeroMock: Placar = {
  resolvidas_sozinho: 0,
  aguardando_aprovacao: 0,
  suspeitas: 0,
  escaladas: 0,
  valor_executado_rs: 0,
  custo_evitado_rs: 0,
};

// Replay: conversas do histórico com foto (docs/anexos_conversas.csv). Os anexos são reais;
// sinais, decisão e resposta são ILUSTRATIVOS até a rota /api/replay existir.
export const replayMock: ItemReplay[] = [
  {
    conversation_id: "AT106191",
    order_id: "GBH367665",
    canal: "reclame_aqui",
    assunto: "Foto de item faltante",
    data_abertura: "2026-08-17 19:14:53",
  },
  {
    conversation_id: "AT106397",
    order_id: "GBH375448",
    canal: "reclame_aqui",
    assunto: "Foto de produto avariado",
    data_abertura: "2026-08-19 08:43:40",
  },
  {
    conversation_id: "AT104618",
    order_id: "GBH361471",
    canal: "reclame_aqui",
    assunto: "Foto de item faltante",
    data_abertura: "2026-08-05 08:14:22",
  },
];

const anexosReplay: Record<string, Caso["anexos"]> = {
  AT106191: [
    {
      anexo_id: "IMG000053",
      descricao_visual:
        "Caixa aberta com Co-wash Hidratante 300ml; não há outro item nem brinde dentro da caixa.",
      hash_perceptual: "c299e0aaf1507c96",
      exif_data_captura: "2026-08-16 02:40:13",
      exif_software: "Editor de Fotos do Galaxy",
    },
  ],
  AT106397: [
    {
      anexo_id: "IMG000058",
      descricao_visual:
        "Kit Barba Completo (Óleo + Balm + Shampoo) com a tampa quebrada e produto espalhado na caixa.",
      hash_perceptual: "f4bcc63d80f9be0a",
      exif_data_captura: "2026-08-15 12:34:48",
      exif_software: "Editor de Fotos do Galaxy",
    },
  ],
  AT104618: [
    {
      anexo_id: "IMG000001",
      descricao_visual:
        "Itens do pedido sobre a mesa: Gelatina Fixadora 300g; a nota fiscal lista um item a mais.",
      hash_perceptual: "bff98c72083a26e6",
      exif_data_captura: "2026-08-02 12:23:28",
      exif_software: null,
    },
  ],
};

export function resultadoReplayMock(item: ItemReplay): Caso {
  const anexos = anexosReplay[item.conversation_id] ?? [];
  const sinais = anexos.flatMap((a) => [
    ...(a.exif_software
      ? [
          {
            tipo: "editor_de_imagem",
            descricao: `Metadado indica edição (${a.exif_software}). (exemplo)`,
            anexo_id: a.anexo_id,
          },
        ]
      : []),
    {
      tipo: "hash_repetido",
      descricao: "Mesma imagem (hash perceptual) aparece em outro pedido. (exemplo)",
      anexo_id: a.anexo_id,
    },
  ]);
  return {
    conversa: {
      conversation_id: item.conversation_id,
      canal: item.canal ?? "",
      marca: item.marca ?? "",
      assunto: item.assunto ?? "",
      order_id: item.order_id,
      data_abertura: item.data_abertura ?? "",
      prioridade: null,
      estado: "suspeita",
    },
    mensagens: [],
    pedido: item.order_id ? { order_id: item.order_id } : null,
    anexos,
    veredicto: {
      suspeita: sinais.length > 0,
      sinais,
      custo_aceitar_falso_rs: 0,
      custo_sinalizar_verdadeiro_rs: 0,
      justificativa: "Exemplo: o verificador cruza hash, EXIF e data de entrega.",
    },
    decisao: {
      resultado: "sinalizar_suspeita",
      regra: "exemplo.regra_de_suspeita",
      motivo: "Exemplo: evidência incoerente vai para o supervisor decidir.",
    },
    acoes: [],
    resposta_ao_cliente:
      "Recebemos sua foto, obrigado. Uma pessoa do nosso time vai conferir e te responde por aqui. (exemplo)",
  };
}

// Agente analista e vigia: formato de src/atendimento/api/analista.py e api/vigia.py.
// Conteúdo ILUSTRATIVO até as rotas responderem no :8000.
export const padroesMock: PadraoAnalista[] = [
  {
    tipo: "cobranca_em_dobro",
    fator: "Pedidos com duas transações capturadas no gateway e sem estorno. (exemplo)",
    escopo: ["GBH473217", "GBH481046", "GCH559342"],
    evidencia: { consulta: "pagamentos_gateway", pedidos: 3 },
  },
  {
    tipo: "contato_repetido",
    fator: "Clientes que voltaram a falar do mesmo pedido sem solução. (exemplo)",
    escopo: ["GBH476745", "GBH474054"],
    evidencia: { consulta: "historico_conversas", pedidos: 2 },
  },
];

export const resultadoTratamentoMock = (padrao: PadraoAnalista): ResultadoTratamento => ({
  padrao,
  incidente: { incidente_id: `INC-MOCK-${padrao.tipo === "cobranca_em_dobro" ? 1 : 2}` },
  notificacoes: padrao.escopo.slice(0, -1).map((order_id) => ({ order_id })),
  sem_consentimento: padrao.escopo.slice(-1),
  adiados: [],
  aviso_ao_time: null,
  detalhes: {},
  ja_tratado: false,
});

export const alertasVigiaMock = (agoraIso: string): RespostaVigia => ({
  agora: agoraIso,
  sla: [
    {
      conversation_id: "AT116480",
      situacao: "estourado",
      para: null,
      texto: "SLA de primeira resposta de AT116480 estourou. (exemplo)",
    },
    ...(agoraIso >= "2026-11-02T08:20"
      ? [
          {
            conversation_id: "AT116664",
            situacao: "vai_estourar",
            para: null,
            texto: "SLA do WhatsApp de AT116664 vence às 08:30. (exemplo)",
          },
        ]
      : []),
  ],
  aprovacoes: [],
});
