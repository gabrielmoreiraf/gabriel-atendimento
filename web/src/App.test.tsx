import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "./App";
import { criarApiMock } from "./mocks/apiMock";

describe("App (com API mock)", () => {
  it("test_HP_09_processar_fila_atualiza_placar_console_e_canal", async () => {
    render(<App api={criarApiMock()} assinar={() => () => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("fila-item").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByTestId("btn-processar"));
    await waitFor(() => expect(screen.getAllByTestId("console-acao").length).toBeGreaterThan(0));
    expect(screen.getAllByTestId("canal-msg").length).toBeGreaterThan(0);
    expect(within(screen.getByTestId("placar")).getByText("2")).toBeInTheDocument();
  });

  it("test_EC_16_verificacao_de_evidencia_processa_caso_do_historico", async () => {
    render(<App api={criarApiMock()} assinar={() => () => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("replay-item").length).toBeGreaterThan(0));
    await userEvent.click(screen.getAllByTestId("btn-replay")[0]);
    await waitFor(() => expect(screen.getAllByTestId("sinal-evidencia").length).toBeGreaterThan(0));
  });

  it("test_HP_09_abrir_caso_mostra_o_chat", async () => {
    render(<App api={criarApiMock()} assinar={() => () => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("fila-item").length).toBeGreaterThan(0));
    await userEvent.click(screen.getAllByTestId("fila-item")[2]);
    await waitFor(() => expect(screen.getByText(/\*\*\*\.\*\*\*\.\*\*\*-12/)).toBeInTheDocument());
  });

  it("test_HG_19_painel_do_analista_trata_padrao_no_mock", async () => {
    render(<App api={criarApiMock()} assinar={() => () => {}} />);
    await waitFor(() =>
      expect(screen.getAllByTestId("btn-tratar-padrao").length).toBeGreaterThan(0),
    );
    await userEvent.click(screen.getAllByTestId("btn-tratar-padrao")[0]);
    await waitFor(() => expect(screen.getByTestId("resultado-padrao")).toHaveTextContent(/INC-/));
  });

  it("test_HG_20_alertas_do_vigia_aparecem_no_canal", async () => {
    render(<App api={criarApiMock()} assinar={() => () => {}} />);
    await waitFor(() =>
      expect(screen.getAllByTestId("canal-msg").some((m) => /SLA/.test(m.textContent ?? ""))).toBe(
        true,
      ),
    );
  });

  it("test_HG_04_replay_gera_suspeita_que_o_supervisor_decide", async () => {
    render(<App api={criarApiMock()} assinar={() => () => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("btn-replay").length).toBeGreaterThan(0));
    await userEvent.click(screen.getAllByTestId("btn-replay")[0]);
    await waitFor(() =>
      expect(screen.getAllByTestId("btn-suspeita-procedente").length).toBeGreaterThan(0),
    );
    const campo = screen.getAllByLabelText(/justificativa da decisão/i)[0];
    await userEvent.type(campo, "Hash repetido confirmado");
    await userEvent.click(screen.getAllByTestId("btn-suspeita-procedente")[0]);
    await waitFor(() => expect(screen.queryAllByTestId("btn-suspeita-procedente")).toHaveLength(0));
  });
});
