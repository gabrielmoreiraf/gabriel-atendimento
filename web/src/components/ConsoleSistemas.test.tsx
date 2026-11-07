import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RegistroAcao } from "../api/tipos";
import { ConsoleSistemas } from "./ConsoleSistemas";

const acoes: RegistroAcao[] = [
  {
    acao_id: "AC1",
    conversation_id: "AT1",
    order_id: "GCH1",
    data_hora: "2026-11-02T08:00:03-03:00",
    sistema: "oms",
    acao: "reenviar_produto",
    valor_rs: 260,
    executado_por: "agente_ia",
    aprovado_por: "supervisor_01",
    referencia_sistema: "RE-77",
  },
];

describe("ConsoleSistemas", () => {
  it("test_HP_10_cada_acao_mostra_sistema_valor_executor_aprovador_e_referencia", () => {
    render(<ConsoleSistemas acoes={acoes} />);
    const linha = screen.getByTestId("console-acao");
    for (const t of [
      "oms",
      "reenviar_produto",
      "R$ 260,00",
      "agente_ia",
      "supervisor_01",
      "RE-77",
    ]) {
      expect(linha).toHaveTextContent(t);
    }
  });

  it("test_HP_09_console_vazio_explica_o_que_vai_aparecer", () => {
    render(<ConsoleSistemas acoes={[]} />);
    expect(screen.getByText(/nenhuma ação/i)).toBeInTheDocument();
  });

  it("test_HP_09_acao_mais_recente_aparece_primeiro", () => {
    const segunda = { ...acoes[0], acao_id: "AC2", acao: "abrir_chamado_transportadora" };
    render(<ConsoleSistemas acoes={[acoes[0], segunda]} />);
    const linhas = screen.getAllByTestId("console-acao");
    expect(linhas[0]).toHaveTextContent("abrir_chamado_transportadora");
  });
});
