import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DecisaoSuspeita } from "./DecisaoSuspeita";

const base = {
  suspeitaId: "SUS-000001",
  prazo: "2026-11-03T08:00:00-03:00",
  estado: "pendente",
  sinalizadoPor: "supervisor_01",
};

describe("DecisaoSuspeita", () => {
  it("test_HG_04_mostra_prazo_e_nao_oferece_quem_sinalizou", () => {
    render(<DecisaoSuspeita {...base} onDecidir={vi.fn()} />);
    expect(screen.getByText(/03\/11 08:00/)).toBeInTheDocument();
    const opcoes = Array.from(
      (screen.getByLabelText(/supervisor/i) as HTMLSelectElement).options,
    ).map((o) => o.value);
    expect(opcoes).not.toContain("supervisor_01");
  });

  it("test_HG_04_procedente_envia_supervisor_decisao_e_justificativa", async () => {
    const onDecidir = vi.fn().mockResolvedValue(undefined);
    render(<DecisaoSuspeita {...base} onDecidir={onDecidir} />);
    const btn = screen.getByTestId("btn-suspeita-procedente");
    expect(btn).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/justificativa/i), "Foto repetida confirmada");
    await userEvent.click(btn);
    expect(onDecidir).toHaveBeenCalledWith(
      "SUS-000001",
      "supervisor_02",
      "procedente",
      "Foto repetida confirmada",
    );
  });

  it("test_HG_04_improcedente_e_erro_da_api_aparece", async () => {
    const onDecidir = vi.fn().mockRejectedValue(new Error("Suspeita SUS-000001 já está decidida."));
    render(<DecisaoSuspeita {...base} onDecidir={onDecidir} />);
    await userEvent.type(screen.getByLabelText(/justificativa/i), "Cliente tem histórico limpo");
    await userEvent.click(screen.getByTestId("btn-suspeita-improcedente"));
    expect(onDecidir).toHaveBeenCalledWith(
      "SUS-000001",
      "supervisor_02",
      "improcedente",
      "Cliente tem histórico limpo",
    );
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/já está decidida/));
  });

  it("test_HG_04_suspeita_decidida_nao_mostra_botoes", () => {
    render(<DecisaoSuspeita {...base} estado="procedente" onDecidir={vi.fn()} />);
    expect(screen.queryByTestId("btn-suspeita-procedente")).toBeNull();
    expect(screen.getByText(/procedente/i)).toBeInTheDocument();
  });
});
