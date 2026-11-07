import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { MensagemCanal } from "../api/tipos";
import { CanalTime } from "./CanalTime";

const msgs: MensagemCanal[] = [
  {
    id: "M1",
    tipo: "aprovacao",
    para: "supervisor_02",
    texto: "Aprovar reenvio de R$ 260,00?",
    conversation_id: "AT1",
    aprovacao_id: "APR1",
    estado: "pendente",
    solicitado_por: "supervisor_01",
  },
  { id: "M2", tipo: "aviso", para: null, texto: "Pico de atrasos", conversation_id: null },
];

describe("CanalTime", () => {
  it("test_HG_20_lista_avisos_suspeitas_e_aprovacoes", () => {
    render(<CanalTime mensagens={msgs} onAprovar={vi.fn()} onRejeitar={vi.fn()} />);
    expect(screen.getAllByTestId("canal-msg")).toHaveLength(2);
    expect(screen.getByText("Pico de atrasos")).toBeInTheDocument();
  });

  it("test_HP_10_aprovar_envia_o_supervisor_escolhido", async () => {
    const onAprovar = vi.fn().mockResolvedValue(undefined);
    render(<CanalTime mensagens={msgs} onAprovar={onAprovar} onRejeitar={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText(/supervisor/i), "supervisor_03");
    await userEvent.click(screen.getByTestId("btn-aprovar"));
    expect(onAprovar).toHaveBeenCalledWith("APR1", "supervisor_03", undefined);
  });

  it("test_HG_03_mostra_o_erro_quando_a_api_recusa_autoaprovacao", async () => {
    const onAprovar = vi
      .fn()
      .mockRejectedValue(new Error("Supervisor não pode aprovar a própria ação"));
    render(<CanalTime mensagens={msgs} onAprovar={onAprovar} onRejeitar={vi.fn()} />);
    await userEvent.click(screen.getByTestId("btn-aprovar"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/própria ação/));
  });

  it("test_HP_10_rejeitar_exige_justificativa", async () => {
    const onRejeitar = vi.fn().mockResolvedValue(undefined);
    render(<CanalTime mensagens={msgs} onAprovar={vi.fn()} onRejeitar={onRejeitar} />);
    const btn = screen.getByTestId("btn-rejeitar");
    expect(btn).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/justificativa/i), "Foto não confere");
    await userEvent.click(btn);
    expect(onRejeitar).toHaveBeenCalledWith("APR1", "supervisor_02", "Foto não confere");
  });

  it("test_HP_10_aprovacao_ja_decidida_nao_mostra_botoes", () => {
    render(
      <CanalTime
        mensagens={[{ ...msgs[0], estado: "aprovada" }]}
        onAprovar={vi.fn()}
        onRejeitar={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("btn-aprovar")).toBeNull();
    expect(screen.getByText(/aprovada/i)).toBeInTheDocument();
  });

  it("test_HG_03_mostra_quem_pediu_e_nao_oferece_o_solicitante", () => {
    render(<CanalTime mensagens={msgs} onAprovar={vi.fn()} onRejeitar={vi.fn()} />);
    expect(screen.getAllByTestId("canal-msg")[1]).toHaveTextContent("Pedido por supervisor_01");
    const opcoes = Array.from(
      (screen.getByLabelText(/supervisor/i) as HTMLSelectElement).options,
    ).map((o) => o.value);
    expect(opcoes).not.toContain("supervisor_01");
    expect(opcoes).toContain("supervisor_02");
  });

  it("test_HG_21_botao_rodar_vigia_dispara_no_relogio_atual", async () => {
    const onRodarVigia = vi.fn().mockResolvedValue(undefined);
    render(
      <CanalTime
        mensagens={msgs}
        onAprovar={vi.fn()}
        onRejeitar={vi.fn()}
        relogio="2026-11-02T08:00:00"
        onRodarVigia={onRodarVigia}
      />,
    );
    await userEvent.click(screen.getByTestId("btn-rodar-vigia"));
    expect(onRodarVigia).toHaveBeenCalledWith("2026-11-02T08:00:00");
  });

  it("test_HG_20_avancar_relogio_para_0820_so_passa_o_horario", async () => {
    const onRodarVigia = vi.fn().mockResolvedValue(undefined);
    render(
      <CanalTime
        mensagens={msgs}
        onAprovar={vi.fn()}
        onRejeitar={vi.fn()}
        relogio="2026-11-02T08:00:00"
        onRodarVigia={onRodarVigia}
      />,
    );
    await userEvent.click(screen.getByTestId("btn-vigia-0820"));
    expect(onRodarVigia).toHaveBeenCalledWith("2026-11-02T08:20:00");
  });

  it("test_HG_20_mensagem_mais_recente_aparece_primeiro", () => {
    render(<CanalTime mensagens={msgs} onAprovar={vi.fn()} onRejeitar={vi.fn()} />);
    expect(screen.getAllByTestId("canal-msg")[0]).toHaveTextContent("Pico de atrasos");
  });
});
