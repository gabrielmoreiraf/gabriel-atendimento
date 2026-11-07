import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { ErroApi } from "./api/cliente";
import type { EventoApi } from "./api/tipos";
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
    await userEvent.click(
      within(screen.getByRole("navigation", { name: "Telas" })).getByRole("link", {
        name: "Evidência",
      }),
    );
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
    await userEvent.click(
      within(screen.getByRole("navigation", { name: "Telas" })).getByRole("link", {
        name: "Analista",
      }),
    );
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
    await userEvent.click(
      within(screen.getByRole("navigation", { name: "Telas" })).getByRole("link", {
        name: "Evidência",
      }),
    );
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

  it("test_HP_09_botao_acompanha_leitura_e_decisao_pelo_sse", async () => {
    const api = criarApiMock();
    let terminar: (v: Awaited<ReturnType<typeof api.processarFila>>) => void = () => {};
    api.processarFila = () =>
      new Promise((r) => {
        terminar = r;
      });
    let emitir: (e?: EventoApi) => void = () => {};
    render(
      <App
        api={api}
        assinar={(cb) => {
          emitir = cb;
          return () => {};
        }}
      />,
    );
    await waitFor(() => expect(screen.getAllByTestId("fila-item").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByTestId("btn-processar"));
    act(() => emitir({ tipo: "leitura", payload: { lidas: 23, total: 65 } }));
    expect(screen.getByTestId("btn-processar")).toHaveTextContent("Lendo 23/65…");
    act(() => emitir({ tipo: "leitura", payload: { lidas: 65, total: 65 } }));
    expect(screen.getByTestId("btn-processar")).toHaveTextContent("Decidindo…");
    await act(async () => terminar({ ...(await api.placar()) }));
    await waitFor(() =>
      expect(screen.getByTestId("btn-processar")).toHaveTextContent("Processar fila"),
    );
  });

  it("test_HG_12_rodada_em_andamento_409_mostra_aviso_sem_quebrar", async () => {
    const api = criarApiMock();
    api.processarFila = vi
      .fn()
      .mockRejectedValue(new ErroApi(409, "já há uma rodada da fila em andamento"));
    render(<App api={api} assinar={() => () => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("fila-item").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByTestId("btn-processar"));
    await waitFor(() =>
      expect(screen.getByTestId("aviso-processar")).toHaveTextContent(
        "já há uma rodada da fila em andamento",
      ),
    );
    expect(screen.getAllByTestId("fila-item").length).toBeGreaterThan(0);
    expect(screen.getByTestId("btn-processar")).toBeEnabled();
  });

  it("test_HG_13_reiniciar_demo_limpa_o_estado_e_recarrega", async () => {
    render(<App api={criarApiMock()} assinar={() => () => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("fila-item").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByTestId("btn-processar"));
    await waitFor(() => expect(screen.getAllByTestId("console-acao").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByTestId("btn-reiniciar"));
    await waitFor(() => expect(screen.queryAllByTestId("console-acao")).toHaveLength(0));
    expect(screen.getAllByTestId("fila-item")[0]).toHaveTextContent("Aberta");
  });

  it("test_HG_13_falha_ao_reiniciar_aparece_sem_quebrar", async () => {
    const api = criarApiMock();
    api.reiniciarDemo = vi.fn().mockRejectedValue(new ErroApi(500, "banco fora do ar"));
    render(<App api={api} assinar={() => () => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("fila-item").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByTestId("btn-reiniciar"));
    await waitFor(() => expect(screen.getByText(/banco fora do ar/)).toBeInTheDocument());
    expect(screen.getByTestId("btn-reiniciar")).toBeEnabled();
  });
});
