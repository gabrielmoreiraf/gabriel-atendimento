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
    expect(screen.getByText("suspeita.supervisor_decide")).toBeInTheDocument();
    expect(screen.getByText("Recebemos sua foto e estamos conferindo.")).toBeInTheDocument();
  });

  it("test_HG_11_texto_mascarado_e_exibido_como_veio", () => {
    render(<CasoPainel caso={caso} carregando={false} erro={null} />);
    expect(screen.queryByText(/\d{3}\.\d{3}\.\d{3}-\d{2}/)).toBeNull();
  });

  it("test_HP_09_sem_caso_pede_para_escolher_na_fila", () => {
    render(<CasoPainel caso={null} carregando={false} erro={null} />);
    expect(screen.getByText(/escolha uma conversa/i)).toBeInTheDocument();
  });
});
