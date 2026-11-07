import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Caso } from "../api/tipos";
import { CasoPainel } from "./CasoPainel";

const caso: Caso = {
  conversa: {
    conversation_id: "AT9",
    canal: "whatsapp",
    marca: "Gocase",
    assunto: "Item faltante",
    order_id: "GCH9",
    data_abertura: "2026-11-01 09:00:00",
    prioridade: 1,
    estado: "suspeita",
  },
  mensagens: [
    { autor: "cliente", timestamp: "2026-11-01 09:00:00", texto: "Meu CPF é ***.***.***-12" },
  ],
  pedido: { order_id: "GCH9", valor: 120 },
  anexos: [{ anexo_id: "IMG9", descricao_visual: "Foto da caixa aberta" }],
  veredicto: {
    suspeita: true,
    sinais: [
      { tipo: "hash_repetido", descricao: "Imagem repetida de outro pedido", anexo_id: "IMG9" },
    ],
    custo_aceitar_falso_rs: 54,
    custo_sinalizar_verdadeiro_rs: 6,
    justificativa: "Sinais incoerentes",
  },
  decisao: {
    resultado: "sinalizar_suspeita",
    regra: "suspeita.supervisor_decide",
    motivo: "Evidência incoerente",
  },
  acoes: [],
  resposta_ao_cliente: "Recebemos sua foto e estamos conferindo.",
};

describe("CasoPainel", () => {
  it("test_HP_09_mostra_chat_evidencia_decisao_e_resposta", () => {
    render(<CasoPainel caso={caso} carregando={false} erro={null} />);
    expect(screen.getByText("Meu CPF é ***.***.***-12")).toBeInTheDocument();
    expect(screen.getByText(/Foto da caixa aberta/)).toBeInTheDocument();
    expect(screen.getByText(/Imagem repetida de outro pedido/)).toBeInTheDocument();
    expect(screen.getByText("Evidência incoerente")).toBeInTheDocument();
    // O código interno da regra fica no log, não na tela do atendente.
    expect(screen.queryByText("suspeita.supervisor_decide")).not.toBeInTheDocument();
    expect(screen.getByText("Recebemos sua foto e estamos conferindo.")).toBeInTheDocument();
  });

  it("test_HG_11_texto_mascarado_e_exibido_como_veio", () => {
    render(<CasoPainel caso={caso} carregando={false} erro={null} />);
    expect(screen.queryByText(/\d{3}\.\d{3}\.\d{3}-\d{2}/)).toBeNull();
  });

  it("test_HP_09_passo_4_mostra_so_as_acoes_desta_conversa", () => {
    const acao = (id: string, conversa: string, acaoNome: string) => ({
      acao_id: id,
      conversation_id: conversa,
      order_id: null,
      data_hora: "2026-11-02T08:01:00",
      sistema: "OMS de trocas e reenvios",
      acao: acaoNome,
      valor_rs: 90,
      executado_por: "agente",
      aprovado_por: null,
      referencia_sistema: `REF-${id}`,
    });
    render(
      <CasoPainel
        caso={caso}
        carregando={false}
        erro={null}
        acoes={[acao("1", "AT9", "reenviar_produto"), acao("2", "AT8", "estornar_pagamento")]}
      />,
    );
    expect(screen.getByText("Reenviar produto")).toBeInTheDocument();
    expect(screen.queryByText("Estornar pagamento")).not.toBeInTheDocument();
  });

  it("test_HP_09_antes_de_processar_explica_o_primeiro_passo", () => {
    render(<CasoPainel caso={null} carregando={false} erro={null} filaProcessada={false} />);
    expect(screen.getByRole("heading", { name: "Como usar" })).toBeInTheDocument();
    expect(screen.getByText("Processar fila")).toBeInTheDocument();
  });

  it("test_HP_09_sem_caso_pede_para_escolher_na_fila", () => {
    render(<CasoPainel caso={null} carregando={false} erro={null} />);
    expect(screen.getByText(/escolha uma conversa/i)).toBeInTheDocument();
  });
});
