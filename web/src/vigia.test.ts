import { describe, expect, it } from "vitest";
import type { MensagemCanal } from "./api/tipos";
import { alertasComoMensagens, juntarCanal } from "./vigia";

describe("vigia", () => {
  it("test_HG_20_alertas_de_sla_e_lembretes_viram_avisos_no_canal", () => {
    const msgs = alertasComoMensagens({
      sla: [
        {
          conversation_id: "AT1",
          situacao: "estourado",
          para: "atendente_01",
          texto: "SLA de AT1 estourou",
        },
      ],
      aprovacoes: [
        { aprovacao_id: "APR-1", nivel: 1, para: "supervisor_01", texto: "APR-1 parada há 2h" },
      ],
    });
    expect(msgs).toHaveLength(2);
    expect(msgs.every((m) => m.tipo === "aviso")).toBe(true);
    expect(msgs[0]).toMatchObject({
      para: "atendente_01",
      texto: "SLA de AT1 estourou",
      conversation_id: "AT1",
    });
    expect(msgs[1].texto).toBe("APR-1 parada há 2h");
  });

  it("test_HG_21_aceita_lista_simples", () => {
    const msgs = alertasComoMensagens([{ texto: "lembrete", para: null }]);
    expect(msgs).toHaveLength(1);
    expect(msgs[0].tipo).toBe("aviso");
  });

  it("test_HG_20_nao_duplica_aviso_que_o_canal_ja_tem", () => {
    const canal: MensagemCanal[] = [
      { id: "C1", tipo: "aviso", para: null, texto: "SLA de AT1 estourou", conversation_id: "AT1" },
    ];
    const vigia = alertasComoMensagens([{ texto: "SLA de AT1 estourou" }, { texto: "novo" }]);
    expect(juntarCanal(canal, vigia).map((m) => m.texto)).toEqual(["SLA de AT1 estourou", "novo"]);
  });
});
