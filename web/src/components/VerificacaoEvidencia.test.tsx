import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Caso, ItemReplay } from "../api/tipos";
import { VerificacaoEvidencia } from "./VerificacaoEvidencia";

const casos: ItemReplay[] = [
  {
    conversation_id: "AT106191",
    order_id: "GBH367665",
    marca: "Kokeshi",
    canal: "reclame_aqui",
    assunto: "Item faltante",
    data_abertura: "2026-08-17 19:14:53",
  },
];

const resultado: Caso = {
  conversa: {
    conversation_id: "AT106191",
    order_id: "GBH367665",
    marca: "Kokeshi",
    canal: "reclame_aqui",
    assunto: "Item faltante",
    data_abertura: "2026-08-17 19:14:53",
    prioridade: null,
    estado: "suspeita",
  },
  mensagens: [{ autor: "cliente", timestamp: "2026-08-17 19:14:53", texto: "Veio só um item" }],
  pedido: { order_id: "GBH367665" },
  anexos: [
    {
      anexo_id: "IMG000053",
      descricao_visual: "Caixa aberta com Co-wash",
      hash_perceptual: "c299e0aaf1507c96",
      exif_data_captura: "2026-08-16 02:40:13",
      exif_software: "Editor de Fotos do Galaxy",
    },
  ],
  veredicto: {
    suspeita: true,
    sinais: [
      { tipo: "editor_de_imagem", descricao: "Foto passou por editor", anexo_id: "IMG000053" },
      { tipo: "hash_repetido", descricao: "Mesma foto em outro pedido", anexo_id: "IMG000053" },
    ],
    custo_aceitar_falso_rs: 40.5,
    custo_sinalizar_verdadeiro_rs: 6,
    justificativa: "Dois sinais incoerentes",
  },
  decisao: {
    resultado: "sinalizar_suspeita",
    regra: "suspeita.supervisor_decide",
    motivo: "Evidência incoerente",
  },
  acoes: [],
  resposta_ao_cliente: "Recebemos sua foto e um especialista vai conferir.",
};

describe("VerificacaoEvidencia", () => {
  it("test_EC_16_lista_casos_reais_do_historico", () => {
    render(<VerificacaoEvidencia casos={casos} onProcessar={vi.fn()} />);
    expect(screen.getAllByTestId("replay-item")).toHaveLength(1);
    expect(screen.getByTestId("replay-item")).toHaveTextContent("AT106191");
  });

  it("test_EC_16_processar_mostra_sinais_decisao_e_resposta_neutra", async () => {
    const onProcessar = vi.fn().mockResolvedValue(resultado);
    render(<VerificacaoEvidencia casos={casos} onProcessar={onProcessar} />);
    await userEvent.click(screen.getByTestId("btn-replay"));
    expect(onProcessar).toHaveBeenCalledWith("AT106191");
    await waitFor(() => expect(screen.getAllByTestId("sinal-evidencia")).toHaveLength(2));
    expect(screen.getByText(/Editor de imagem/)).toBeInTheDocument();
    expect(screen.getByText(/Foto repetida de outro pedido/)).toBeInTheDocument();
    expect(screen.getByText("Evidência incoerente")).toBeInTheDocument();
    // O código interno da regra fica no log, não na tela do atendente.
    expect(screen.queryByText("suspeita.supervisor_decide")).not.toBeInTheDocument();
    expect(
      screen.getByText("Recebemos sua foto e um especialista vai conferir."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Editor de Fotos do Galaxy/)).toBeInTheDocument();
  });

  it("test_EC_15_sem_sinais_diz_que_a_evidencia_confere", async () => {
    const limpo = {
      ...resultado,
      veredicto: {
        ...(resultado.veredicto as NonNullable<Caso["veredicto"]>),
        suspeita: false,
        sinais: [],
      },
    };
    render(<VerificacaoEvidencia casos={casos} onProcessar={vi.fn().mockResolvedValue(limpo)} />);
    await userEvent.click(screen.getByTestId("btn-replay"));
    await waitFor(() => expect(screen.getByText(/nenhum sinal/i)).toBeInTheDocument());
  });

  it("test_EC_16_erro_da_api_aparece", async () => {
    render(
      <VerificacaoEvidencia
        casos={casos}
        onProcessar={vi.fn().mockRejectedValue(new Error("rota fora"))}
      />,
    );
    await userEvent.click(screen.getByTestId("btn-replay"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("rota fora"));
  });
});
