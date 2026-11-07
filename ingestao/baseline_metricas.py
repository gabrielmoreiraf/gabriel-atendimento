"""Linha de base da dor de negócio (Atendimento ao Cliente).

Lê os CSVs de docs/ em modo somente leitura (UTF-8, separador conferido no
cabeçalho) e imprime em Markdown as métricas citadas em REQUISITOS.md.

Uso: python3 -I ingestao/baseline_metricas.py > ingestao/baseline_metricas.md
"Agora" fixo em 2026-11-02 08:00 (America/Sao_Paulo), nunca o relógio do sistema.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
AGORA = datetime(2026, 11, 2, 8, 0, 0)
FMT = "%Y-%m-%d %H:%M:%S"


def ler(nome: str) -> list[dict]:
    caminho = DOCS / nome
    with caminho.open(encoding="utf-8", newline="") as fh:
        cab = fh.readline()
        sep = ";" if cab.count(";") > cab.count(",") else ","
        fh.seek(0)
        return list(csv.DictReader(fh, delimiter=sep))


def politica() -> dict[tuple[str, str], str]:
    return {(p["secao"], p["regra"]): p["valor"] for p in ler("politicas.csv")}


def minutos_comerciais(inicio: datetime, fim: datetime, h_ini=8, h_fim=20) -> float:
    """Minutos entre inicio e fim contando só a janela 08h-20h (todos os dias)."""
    total, cursor = 0.0, inicio
    while cursor < fim:
        j_ini = cursor.replace(hour=h_ini, minute=0, second=0)
        j_fim = cursor.replace(hour=h_fim, minute=0, second=0)
        a, b = max(cursor, j_ini), min(fim, j_fim)
        if b > a:
            total += (b - a).total_seconds() / 60
        cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    return total


def mascara(txt: str) -> str:
    return re.sub(r"\d", "#", txt)


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "n/a"


def main() -> None:
    pol = politica()
    conv = ler("historico_conversas.csv")
    fila = ler("fila_aberta.csv")
    msgs = ler("historico_mensagens.csv")
    tempo = ler("tempo_por_conversa.csv")
    pedidos = {p["order_id"]: p for p in ler("pedidos.csv")}
    anexos = ler("anexos_conversas.csv")
    pagto = ler("pagamentos_gateway.csv")
    acoes = ler("acoes_executadas_sistemas.csv")
    trocas = ler("trocas_reenvios.csv")
    csat = ler("avaliacoes_csat.csv")
    ra = ler("reclame_aqui.csv")

    print("# Linha de base: métricas da dor de negócio\n")
    print(f"Gerado por `ingestao/baseline_metricas.py`. Agora fixo: {AGORA:%Y-%m-%d %H:%M}.\n")

    # M1 volume e custo por canal
    print(
        "## M1. Volume e custo por canal (`historico_conversas.canal` × `politicas.custo_por_conversa_rs`)\n"
    )
    print("| Canal | Conversas | Custo unitário (R$) | Custo na amostra (R$) |")
    print("| --- | ---: | ---: | ---: |")
    por_canal = Counter(c["canal"] for c in conv)
    custo_total = 0.0
    for canal, n in por_canal.most_common():
        cu = float(pol[("custo_por_conversa_rs", canal)])
        custo_total += cu * n
        print(f"| {canal} | {n} | {cu:.2f} | {cu * n:,.2f} |")
    print(f"| **Total** | **{len(conv)}** | | **{custo_total:,.2f}** |\n")
    print("Amostra de 1 em cada 4 clientes (`parametros.md`).\n")

    # M2 tags
    print("## M2. Motivos de contato (`historico_conversas.tag_agente`)\n")
    print("| Tag | Conversas | % |")
    print("| --- | ---: | ---: |")
    for tag, n in Counter(c["tag_agente"] or "(sem tag: só bot)" for c in conv).most_common():
        print(f"| {tag} | {n} | {pct(n, len(conv))} |")
    print()

    # M3 status e esforço
    st = Counter(c["status"] for c in conv)
    mins = [float(t["minutos_trabalhados"]) for t in tempo if t["minutos_trabalhados"]]
    sist = [int(t["sistemas_acessados"]) for t in tempo if t["sistemas_acessados"]]
    print("## M3. Status e esforço (`historico_conversas.status`, `tempo_por_conversa`)\n")
    for k, v in st.most_common():
        print(f"- status `{k}`: {v} ({pct(v, len(conv))})")
    print(
        f"- minutos trabalhados: média {sum(mins) / len(mins):.1f}, total {sum(mins):,.0f} min em {len(mins)} conversas"
    )
    print(
        f"- sistemas acessados por conversa: média {sum(sist) / len(sist):.2f}, máximo {max(sist)}"
    )
    acessos = Counter(a["sistema"] for a in acoes)
    print(
        f"- sistemas distintos no log de ações (`acoes_executadas_sistemas.sistema`): {len(acessos)}\n"
    )

    # M4 contatos repetidos
    por_par = Counter((c["customer_id"], c["order_id"]) for c in conv if c["order_id"])
    rep = {k: n for k, n in por_par.items() if n > 1}
    pedidos_hist = {c["order_id"] for c in conv if c["order_id"]}
    fila_rep = [f for f in fila if f["order_id"] and f["order_id"] in pedidos_hist]
    print("## M4. Contatos repetidos (`historico_conversas` por `customer_id` + `order_id`)\n")
    print(f"- pares cliente+pedido com 2+ conversas: {len(rep)}")
    print(
        f"- conversas nesses pares: {sum(rep.values())} ({pct(sum(rep.values()), len(conv))} do histórico)"
    )
    print(
        f"- conversas da fila sobre pedido que já teve conversa no histórico: {len(fila_rep)} de {len(fila)}\n"
    )

    # M5 fila e SLA
    print("## M5. Fila de agora (`fila_aberta`, SLA de `politicas.sla_primeira_resposta`)\n")
    sla_wa = float(pol[("sla_primeira_resposta", "whatsapp.minutos")])
    sla_em = float(pol[("sla_primeira_resposta", "email.horas")]) * 60
    sla_ra = float(pol[("sla_primeira_resposta", "reclame_aqui.horas")]) * 60
    print("| Canal | Na fila | Sem 1ª resposta humana | Já fora do SLA |")
    print("| --- | ---: | ---: | ---: |")
    for canal in ("whatsapp", "email", "reclame_aqui"):
        itens = [f for f in fila if f["canal"] == canal]
        sem = [f for f in itens if not f["data_primeira_resposta"]]
        fora = 0
        for f in sem:
            ab = datetime.strptime(f["data_abertura"], FMT)
            if canal == "whatsapp":
                fora += minutos_comerciais(ab, AGORA) > sla_wa
            else:
                lim = sla_em if canal == "email" else sla_ra
                fora += (AGORA - ab).total_seconds() / 60 > lim
        print(f"| {canal} | {len(itens)} | {len(sem)} | {fora} |")
    print()

    # M6 anexos / reclamação suspeita
    hash_pedidos = defaultdict(set)
    for a in anexos:
        hash_pedidos[a["hash_perceptual"]].add(a["order_id"])
    hash_reuso = {h for h, ps in hash_pedidos.items() if len(ps) > 1}
    anexo_reuso = [a for a in anexos if a["hash_perceptual"] in hash_reuso]
    sem_exif = [a for a in anexos if not a["exif_data_captura"]]
    antes_entrega = []
    for a in anexos:
        p = pedidos.get(a["order_id"])
        if a["exif_data_captura"] and p and p["data_entrega"]:
            if a["exif_data_captura"][:10] < p["data_entrega"][:10]:
                antes_entrega.append(a)
    editados = [a for a in anexos if a["exif_software"]]
    print("## M6. Evidência das reclamações (`anexos_conversas` × `pedidos.data_entrega`)\n")
    print(
        f"- anexos: {len(anexos)}; sem EXIF de captura: {len(sem_exif)} ({pct(len(sem_exif), len(anexos))})"
    )
    print(
        f"- anexos com mesmo `hash_perceptual` em pedidos diferentes: {len(anexo_reuso)} ({len(hash_reuso)} hashes)"
    )
    print(f"- anexos com EXIF de captura anterior à entrega do pedido: {len(antes_entrega)}")
    print(f"- anexos com `exif_software` preenchido (passaram por editor): {len(editados)}\n")

    # M7 cobrança em dobro
    tx = defaultdict(list)
    for t in pagto:
        tx[t["order_id"]].append(t)
    dup_aberta = [
        o for o, ts in tx.items() if sum(t["status"] in ("capturada", "paga") for t in ts) > 1
    ]
    dup_total = [
        o
        for o, ts in tx.items()
        if sum(t["status"] in ("capturada", "paga", "estornada") for t in ts) > 1
    ]
    print("## M7. Cobrança em dobro (`pagamentos_gateway` por `order_id`)\n")
    print(f"- pedidos com 2+ transações capturadas/pagas/estornadas: {len(dup_total)}")
    print(f"- pedidos com 2+ transações capturadas/pagas ainda sem estorno: {len(dup_aberta)}\n")

    # M8 alçadas no histórico
    lim_ree = float(pol[("limites_por_papel", "atendente.reembolso_max_rs")])
    lim_env = float(pol[("limites_por_papel", "atendente.reenvio_ou_reimpressao_max_rs")])
    lim_trc = float(pol[("limites_por_papel", "atendente.troca_max_rs")])
    limite = {
        "reembolsar": lim_ree,
        "reenviar_produto": lim_env,
        "reimprimir_personalizacao": lim_env,
        "trocar_produto": lim_trc,
    }
    acima = [
        a
        for a in acoes
        if a["acao"] in limite and a["valor_rs"] and float(a["valor_rs"]) > limite[a["acao"]]
    ]
    acima_sem = [a for a in acima if not a["aprovado_por"]]
    auto = [a for a in acoes if a["aprovado_por"] and a["aprovado_por"] == a["executado_por"]]
    print(
        "## M8. Alçadas no histórico (`acoes_executadas_sistemas` × `politicas.limites_por_papel`)\n"
    )
    print(
        f"- ações com dinheiro acima do limite do atendente: {len(acima)}; sem `aprovado_por`: {len(acima_sem)}"
    )
    print(f"- ações aprovadas pelo próprio executor: {len(auto)}")
    custo_reenv = sum(float(t["custo_total"]) for t in trocas if t["custo_total"])
    print(
        f"- trocas/reenvios/novas produções: {len(trocas)}, custo total R$ {custo_reenv:,.2f} (`trocas_reenvios.custo_total`)\n"
    )

    # M9 satisfação e Reclame Aqui
    notas = [int(c["nota"]) for c in csat if c["nota"]]
    print("## M9. Satisfação (`avaliacoes_csat`, `reclame_aqui`)\n")
    print(
        f"- pesquisas enviadas: {len(csat)}; respondidas: {len(notas)} ({pct(len(notas), len(csat))}); nota média {sum(notas) / len(notas):.2f} de 5"
    )
    print(
        f"- notas 1-2: {sum(n <= 2 for n in notas)} ({pct(sum(n <= 2 for n in notas), len(notas))})"
    )
    res = Counter(r["resolvido"] for r in ra)
    print(f"- reclamações no Reclame Aqui: {len(ra)}; `resolvido`: {dict(res)}\n")

    # M10 sinais nos textos dos clientes (harness)
    fila_ids = {f["conversation_id"] for f in fila}
    txt_cli = [m for m in msgs if m["autor"] == "cliente"]
    re_reacao = re.compile(
        r"alerg|rea[çc][ãa]o|irrita|coceira|vermelh|ard[eê]n|ardor|bolinha|incha", re.I
    )
    re_inj = re.compile(
        r"ignor[ea] (todas )?(as )?instru|instru[çc][ãa]o para o (assistente|agente|rob)|para o rob[ôo]",
        re.I,
    )
    re_multi = re.compile(r"aproveitando|outra coisa", re.I)
    re_pii = re.compile(
        r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}|\b\d{4}[ .]?\d{4}[ .]?\d{4}[ .]?\d{4}\b|\(?\d{2}\)?\s?9?\d{4}-?\d{4}"
    )

    def contar(rx):
        hits = [m for m in txt_cli if rx.search(m["texto"])]
        return hits, {m["conversation_id"] for m in hits}

    print("## M10. Sinais nos textos dos clientes (`historico_mensagens`, autor = cliente)\n")
    sinais = (
        ("possível reação adversa", re_reacao, True),
        ("instrução embutida dirigida ao agente (prompt injection)", re_inj, False),
        ("dado pessoal (CPF, cartão, telefone)", re_pii, False),
        ("mais de um pedido na mesma mensagem", re_multi, False),
    )
    for nome, rx, exemplos in sinais:
        hits, convs = contar(rx)
        na_fila = sorted(convs & fila_ids)
        print(
            f"- {nome}: {len(hits)} mensagens em {len(convs)} conversas ({len(na_fila)} na fila: {', '.join(na_fila) or '-'})"
        )
        if rx is re_inj:
            print(f"  - conversas: {', '.join(sorted(convs))} (texto omitido de propósito)")
        for m in hits[:3] if exemplos else []:
            print(f'  - `{m["conversation_id"]}`: "{mascara(m["texto"][:140])}"')
    cosmeto = [a for a in acoes if a["acao"] == "registrar_cosmetovigilancia"]
    print(f"- registros de cosmetovigilância no log (`acoes_executadas_sistemas`): {len(cosmeto)}")
    print()

    # M11 lacunas de requisito (análise com requirements-analysis)
    print(
        "## M11. Lacunas de requisito (`acoes_executadas_sistemas`, `pagamentos_gateway`, `clientes`, `historico_conversas`)\n"
    )
    for acao in ("reenviar_produto", "trocar_produto", "reembolsar", "reimprimir_personalizacao"):
        c = Counter(a["order_id"] for a in acoes if a["acao"] == acao)
        print(
            f"- `{acao}`: {sum(v > 1 for v in c.values())} de {len(c)} pedidos receberam a ação 2+ vezes"
        )
    grupos = defaultdict(list)
    for a in acoes:
        if a["acao"] in limite and a["valor_rs"]:
            grupos[(a["order_id"], a["acao"])].append(a)
    frac = [
        v
        for (o, ac), v in grupos.items()
        if len(v) > 1
        and all(float(x["valor_rs"]) <= limite[ac] and not x["aprovado_por"] for x in v)
        and sum(float(x["valor_rs"]) for x in v) > limite[ac]
    ]
    print(
        f"- pedido+ação repetidos em que cada execução cabe na alçada mas a soma passa do limite, sem aprovação: {len(frac)} "
        f"(em conversas diferentes: {sum(len({x['conversation_id'] for x in v}) > 1 for v in frac)})"
    )
    valores_dup = [
        float(next(t for t in tx[o] if t["status"] in ("capturada", "paga"))["valor"])
        for o in dup_aberta
    ]
    print(
        f"- cobranças em dobro sem estorno: {sum(v <= lim_ree for v in valores_dup)} com valor ≤ R$ {lim_ree:.0f}, "
        f"{sum(v > lim_ree for v in valores_dup)} acima (exigem aprovação)"
    )
    cli = ler("clientes.csv")
    print(
        f"- clientes sem consentimento: WhatsApp {sum(c['aceita_comunicacao_whatsapp'] == 'não' for c in cli)}, "
        f"e-mail {sum(c['aceita_comunicacao_email'] == 'não' for c in cli)} de {len(cli)}"
    )
    fora_h = sum(1 for c in conv if not 8 <= int(c["data_abertura"][11:13]) < 20)
    print(
        f"- conversas abertas fora do horário humano (antes das 08h ou a partir das 20h): {fora_h} de {len(conv)} ({pct(fora_h, len(conv))})"
    )
    print()

    # M12 cortes temporais e percentuais derivados citados em REQUISITOS.md
    print("## M12. Cortes temporais e percentuais derivados (revisão do REQUISITOS.md v3)\n")
    agora_txt = AGORA.strftime(FMT)
    futuros = [p for p in pedidos.values() if p["data_hora_pedido"] >= agora_txt]
    so_data = [p for p in pedidos.values() if p["data_pedido"] > agora_txt[:10]]
    print(
        f"- pedidos criados em ou depois de agora (`pedidos.data_hora_pedido` ≥ {agora_txt}): {len(futuros)}; "
        f"pelo campo só de data (`data_pedido` > {agora_txt[:10]}): {len(so_data)} "
        f"(diferença de {len(futuros) - len(so_data)} pedidos de 02/11 depois das 08h)"
    )
    print(f"- conversas da fila sem `order_id`: {sum(1 for f in fila if not f['order_id'])}")
    n_ra = por_canal["reclame_aqui"]
    custo_ra = n_ra * float(pol[("custo_por_conversa_rs", "reclame_aqui")])
    print(
        f"- Reclame Aqui: {pct(n_ra, len(conv))} das conversas e {pct(custo_ra, custo_total)} do custo"
    )
    tags = Counter(c["tag_agente"] for c in conv)
    print(f"- Rastreio + Atraso: {pct(tags['Rastreio'] + tags['Atraso'], len(conv))} das conversas")
    print()


if __name__ == "__main__":
    main()
