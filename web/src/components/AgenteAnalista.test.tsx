import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PadraoAnalista, ResultadoTratamento } from "../api/tipos";
import { AgenteAnalista } from "./AgenteAnalista";

const padroes: PadraoAnalista[] = [
  {
    tipo: "cobranca_em_dobro",
    fator: "Duas transações capturadas no mesmo pedido",
    escopo: ["GBH1", "GBH2", "GBH3"],
    evidencia: { consulta: "pagamentos_gateway", pedidos: 3 },
  },
];

const resultado: ResultadoTratamento = {
  padrao: padroes[0],
  incidente: { incidente_id: "INC-0001" },
  notificacoes: [{ order_id: "GBH1" }, { order_id: "GBH2" }],
  sem_consentimento: ["GBH3"],
  adiados: [],
  aviso_ao_time: null,
  detalhes: {},
  ja_tratado: false,
};

describe("AgenteAnalista", () => {
  it("test_HG_17_lista_padroes_com_escopo_e_evidencia", () => {
    render(<AgenteAnalista padroes={padroes} onTratar={vi.fn()} />);
    const item = screen.getByTestId("padrao-item");
    expect(item).toHaveTextContent("Cobrança em dobro");
    expect(item).toHaveTextContent("3 pedidos");
    expect(item).toHaveTextContent("GBH1");
    expect(item).toHaveTextContent("pagamentos_gateway");
  });

  it("test_HG_19_tratar_mostra_incidente_avisos_e_sem_consentimento", async () => {
    const onTratar = vi.fn().mockResolvedValue(resultado);
    render(<AgenteAnalista padroes={padroes} onTratar={onTratar} />);
    await userEvent.click(screen.getByTestId("btn-tratar-padrao"));
    expect(onTratar).toHaveBeenCalledWith("cobranca_em_dobro");
    await waitFor(() => expect(screen.getByText("INC-0001")).toBeInTheDocument());
    expect(screen.getByTestId("resultado-padrao")).toHaveTextContent("2 avisos enviados");
    expect(screen.getByTestId("resultado-padrao")).toHaveTextContent("1 sem consentimento");
  });

  it("test_HG_19_erro_ao_tratar_aparece", async () => {
    const onTratar = vi.fn().mockRejectedValue(new Error("padrão sumiu"));
    render(<AgenteAnalista padroes={padroes} onTratar={onTratar} />);
    await userEvent.click(screen.getByTestId("btn-tratar-padrao"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("padrão sumiu"));
  });

  it("test_HG_17_sem_padroes_explica", () => {
    render(<AgenteAnalista padroes={[]} onTratar={vi.fn()} />);
    expect(screen.getByText(/nenhum padrão/i)).toBeInTheDocument();
  });
});
