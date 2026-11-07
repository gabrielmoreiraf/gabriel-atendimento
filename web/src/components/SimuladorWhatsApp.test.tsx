import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Api } from "../api/cliente";
import { SimuladorWhatsApp } from "./SimuladorWhatsApp";

const cliente = {
  customer_id: "CH1",
  nome: "Bruna S.",
  pedidos: [
    {
      order_id: "GBH1",
      marca: "Kokeshi",
      status_entrega: "em_transito",
      valor: 99.9,
      descricao_produto: "Sérum",
    },
  ],
};

describe("SimuladorWhatsApp", () => {
  it("test_HP_cliente_escreve_e_o_gabriel_responde_com_o_pedido", async () => {
    const simuladorMensagem = vi.fn().mockResolvedValue({
      conversation_id: "WPP-0001",
      resposta: "Seu pedido GBH1 está em trânsito.",
      estado: "resolvida",
      mensagens: [],
    });
    const onVerCaso = vi.fn();
    const api = {
      simuladorClientes: vi.fn().mockResolvedValue([cliente]),
      simuladorMensagem,
    } as unknown as Api;
    render(<SimuladorWhatsApp api={api} onVerCaso={onVerCaso} />);

    await waitFor(() => expect(screen.getAllByText("Bruna S.").length).toBeGreaterThan(0));
    await userEvent.type(screen.getByLabelText("Mensagem do cliente"), "Cadê meu pedido?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() =>
      expect(screen.getByText("Seu pedido GBH1 está em trânsito.")).toBeInTheDocument(),
    );
    expect(simuladorMensagem).toHaveBeenCalledWith({
      customer_id: "CH1",
      order_id: "GBH1",
      texto: "Cadê meu pedido?",
      anterior: undefined,
    });
    await userEvent.click(screen.getByRole("button", { name: "Ver o que o Gabriel fez" }));
    expect(onVerCaso).toHaveBeenCalledWith("WPP-0001");
  });
});
