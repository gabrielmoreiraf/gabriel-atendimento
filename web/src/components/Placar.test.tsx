import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Placar } from "./Placar";

const placar = {
  resolvidas_sozinho: 12,
  aguardando_aprovacao: 3,
  suspeitas: 2,
  escaladas: 4,
  valor_executado_rs: 1234.5,
  custo_evitado_rs: 678.9,
};

describe("Placar", () => {
  it("test_HP_09_placar_mostra_os_numeros_da_api_sem_recalcular", () => {
    render(<Placar placar={placar} processando={false} onProcessar={() => {}} />);
    const el = screen.getByTestId("placar");
    expect(el).toHaveTextContent("12");
    expect(el).toHaveTextContent("Resolvidas sozinho");
    expect(el).toHaveTextContent("R$ 1.234,50");
    expect(el).toHaveTextContent("R$ 678,90");
  });

  it("test_HP_09_botao_processar_dispara_a_acao", async () => {
    const onProcessar = vi.fn();
    render(<Placar placar={placar} processando={false} onProcessar={onProcessar} />);
    await userEvent.click(screen.getByTestId("btn-processar"));
    expect(onProcessar).toHaveBeenCalledOnce();
  });

  it("test_HP_09_botao_fica_desabilitado_enquanto_processa", () => {
    render(<Placar placar={placar} processando onProcessar={() => {}} />);
    expect(screen.getByTestId("btn-processar")).toBeDisabled();
  });

  it("test_HP_09_placar_mostra_aguardando_cliente_separado_de_resolvidas", () => {
    render(
      <Placar
        placar={{ ...placar, aguardando_cliente: 5 }}
        processando={false}
        onProcessar={() => {}}
      />,
    );
    expect(screen.getByTestId("placar")).toHaveTextContent("Aguardando cliente");
    expect(screen.getByTestId("placar")).toHaveTextContent("5");
  });
});
