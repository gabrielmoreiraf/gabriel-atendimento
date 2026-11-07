import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ItemFila } from "../api/tipos";
import { Fila } from "./Fila";

const itens: ItemFila[] = [
  {
    conversation_id: "AT1",
    canal: "whatsapp",
    marca: "Gocase",
    assunto: "Capinha quebrada",
    order_id: "GCH1",
    data_abertura: "2026-11-01 10:00:00",
    prioridade: 1,
    estado: "suspeita",
  },
  {
    conversation_id: "AT2",
    canal: "email",
    marca: "Auá",
    assunto: "Atraso",
    order_id: "GBH2",
    data_abertura: "2026-11-01 11:00:00",
    prioridade: 2,
    estado: "aguardando_aprovacao",
  },
];

describe("Fila", () => {
  it("test_HP_09_lista_cada_conversa_com_estado_em_texto", () => {
    render(<Fila itens={itens} selecionado={null} onAbrir={() => {}} />);
    const linhas = screen.getAllByTestId("fila-item");
    expect(linhas).toHaveLength(2);
    expect(linhas[0]).toHaveTextContent("AT1");
    expect(linhas[0]).toHaveTextContent("Suspeita");
    expect(linhas[1]).toHaveTextContent("Aguardando aprovação");
  });

  it("test_HP_09_filtra_por_canal", async () => {
    render(<Fila itens={itens} selecionado={null} onAbrir={vi.fn()} />);
    const canais = screen.getByRole("group", { name: "Filtrar por canal" });
    await userEvent.click(within(canais).getByRole("button", { name: /E-mail/ }));
    const ids = screen.getAllByTestId("fila-item").map((b) => b.textContent);
    expect(ids.some((t) => t?.includes("AT2"))).toBe(true);
    expect(ids.some((t) => t?.includes("AT1"))).toBe(false);
  });

  it("test_HP_09_filtra_por_estado", async () => {
    render(<Fila itens={itens} selecionado={null} onAbrir={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Estado"), "suspeita");
    const textos = screen.getAllByTestId("fila-item").map((b) => b.textContent ?? "");
    expect(textos).toHaveLength(1);
    expect(textos[0]).toContain("AT1");
  });

  it("test_HP_09_clicar_abre_o_caso", async () => {
    const onAbrir = vi.fn();
    render(<Fila itens={itens} selecionado={null} onAbrir={onAbrir} />);
    await userEvent.click(screen.getAllByTestId("fila-item")[1]);
    expect(onAbrir).toHaveBeenCalledWith("AT2");
  });

  it("test_HP_09_fila_vazia_mostra_aviso", () => {
    render(<Fila itens={[]} selecionado={null} onAbrir={() => {}} />);
    expect(screen.getByText(/fila vazia/i)).toBeInTheDocument();
  });
});

describe("Fila com dados da API real", () => {
  it("test_HP_09_assunto_vazio_mostra_marcador", () => {
    render(<Fila itens={[{ ...itens[0], assunto: "" }]} selecionado={null} onAbrir={() => {}} />);
    expect(screen.getByTestId("fila-item")).toHaveTextContent("(sem assunto)");
  });
});

describe("Fila: aguardando cliente", () => {
  it("test_HP_09_aguardando_cliente_tem_rotulo_proprio", () => {
    render(
      <Fila
        itens={[{ ...itens[0], estado: "aguardando_cliente" }]}
        selecionado={null}
        onAbrir={() => {}}
      />,
    );
    expect(screen.getByTestId("fila-item")).toHaveTextContent("Aguardando cliente");
  });
});
