"""Ferramentas de `docs/ferramentas.csv` com efeito nos sistemas simulados e log de ações.

A ferramenta só executa o que recebe: quem decide alçada é `atendimento.politicas`.
Aqui ficam as travas que não dependem de política: papel permitido (HG-02) e
idempotência das ações com dinheiro (HG-12). Toda execução vira uma linha em
`acoes_agente`, com `data_hora = contratos.AGORA`.
"""

from __future__ import annotations

import functools
import json
import re
from dataclasses import asdict, replace
from datetime import date, datetime

from atendimento.contratos import AGORA, AcaoProposta, Papel, RegistroAcao
from atendimento.dados.repositorio import FERRAMENTAS_COM_DINHEIRO, Base
from atendimento.privacidade import mascarar

CENTRAL = "Central de atendimento"
CANAL_DO_TIME = "Canal do time"
OMS = "OMS de trocas e reenvios"
PRODUCAO = "Sistema de produção Gocase"
GATEWAY = "Gateway de pagamentos"
CUPONS = "Plataforma de cupons"
CATALOGO = "Catálogo (PIM)"
QUALIDADE = "Sistema de qualidade (cosmetovigilância)"
INCIDENTES = "Gestão de incidentes"

# Mensagens ao cliente (gravadas em mensagens_enviadas, destino cliente)
_PARA_O_CLIENTE = {
    "responder_cliente",
    "solicitar_foto",
    "informar_status",
    "orientar_suspensao_uso",
    "negar_por_politica",
    "encerrar_conversa",
}
_TIPO_OMS = {
    "reenviar_produto": ("reenvio", OMS),
    "trocar_produto": ("troca", OMS),
    "reimprimir_personalizacao": ("nova_producao", PRODUCAO),
}
# Sigla do chamado por transportadora (o histórico só tem EXJ-AAAA#####).
_SIGLA_CHAMADO = {
    "Expressa Já": "EXJ",
    "ViaLog": "VLG",
    "Correio Ágil": "CAG",
    "Rápido Sul": "RPS",
    "TransNorte": "TRN",
}
FERRAMENTAS_EXECUTAVEIS = (
    *sorted(_PARA_O_CLIENTE),
    "classificar_conversa",
    "abrir_chamado_transportadora",
    *_TIPO_OMS,
    "reembolsar",
    "solicitar_aprovacao",
    "aprovar_acao",
    "rejeitar_acao",
    "sinalizar_suspeita",
    "acionar_pessoa",
    "responder_colaborador",
    "registrar_cosmetovigilancia",
    "abrir_incidente",
    "notificar_clientes",
    "decidir_suspeita",
    "cancelar_pedido",
    "alterar_endereco",
)
DECISOES_SUSPEITA = ("procedente", "improcedente")
# Item reclamado na chave de idempotência (HG-12 + EC-20): quem chama põe `sku=<SKU>` no motivo.
_SKU_NO_MOTIVO = re.compile(r"\bsku=([A-Z]{2,5}-\d{3,6})\b")


def sku_do_motivo(motivo: str | None) -> str | None:
    """SKU do item reclamado, quando o motivo traz `sku=<SKU>` (ex.: `sku=GOC-5043`)."""
    achado = _SKU_NO_MOTIVO.search(motivo or "")
    return achado.group(1) if achado else None


# Máscara única (HG-11): CPF, cartão, telefone e e-mail. Nome mantido para quem já importa.
mascarar_texto = mascarar


class FerramentaNaoPermitida(PermissionError):
    """HG-02: o papel não está em `papeis_permitidos` da ferramenta."""


class FerramentaDesconhecida(ValueError):
    """A ferramenta não existe ou não tem execução neste MVP."""


def _agora_texto(agora: datetime) -> str:
    return agora.strftime("%Y-%m-%d %H:%M:%S")


def _valor_texto(valor: float) -> str:
    return f"{valor:.2f}"


def _com_trava(metodo):
    """HG-12: a conexão é a mesma da `Base`, então todo acesso passa por `base.trava`.

    A API roda rotas síncronas em threads; sem isso, leitura e escrita concorrentes na mesma
    conexão SQLite quebram (IndexError/None no fetch) e `_proximo` pode repetir IDs.
    """

    @functools.wraps(metodo)
    def com_trava(self, *args, **kwargs):
        with self.base.trava:
            return metodo(self, *args, **kwargs)

    return com_trava


class Ferramentas:
    def __init__(self, base: Base, agora: datetime = AGORA):
        self.base = base
        self.agora = agora
        self._banco = base.banco
        self._con = base.conexao  # compatibilidade: código antigo que lê a conexão crua
        self._catalogo = base.ferramentas()

    # ---------- API pública ----------

    @_com_trava
    def executar(
        self,
        acao: AcaoProposta,
        *,
        acao_pendente: AcaoProposta | None = None,
        area: str | None = None,
        decisao: str | None = None,
    ) -> RegistroAcao:
        """Executa `acao` e devolve o registro gravado em `acoes_agente`.

        `acao.motivo` é o texto da mensagem (responder_cliente e afins), o motivo do
        reenvio/estorno/chamado ou o comentário da aprovação. `solicitar_aprovacao`
        exige `acao_pendente` (a ação que espera o supervisor). `acionar_pessoa`
        aceita `area` (supervisão, logística, qualidade...). `decidir_suspeita` exige
        `decisao` (procedente ou improcedente).

        Ordem (HG-02): ferramenta existe no catálogo → papel (bloqueia e grava a tentativa)
        → tem execução neste MVP. Checagem de idempotência e gravação ficam sob a mesma
        trava (`_com_trava`), então são atômicas (HG-12).
        """
        if acao.ferramenta not in self._catalogo:
            raise FerramentaDesconhecida(acao.ferramenta)
        self._checar_papel(acao)
        if acao.ferramenta not in FERRAMENTAS_EXECUTAVEIS:
            raise FerramentaDesconhecida(acao.ferramenta)
        if acao.ferramenta in FERRAMENTAS_COM_DINHEIRO:
            existente = self._registro_existente(acao)
            if existente is not None:
                return existente
        suspeita_id = None
        if acao.ferramenta == "decidir_suspeita":
            suspeita_id = self._suspeita_decidivel(acao, decisao)
        if acao.ferramenta in ("cancelar_pedido", "alterar_endereco"):
            self._antes_da_separacao(acao)
        with self._banco.transacao():
            if suspeita_id:
                return self._decidir_suspeita(acao, suspeita_id, decisao)
            return self._executar(acao, acao_pendente, area)

    @_com_trava
    def consultar_rastreio(
        self,
        order_id: str,
        *,
        conversation_id: str | None = None,
        executado_por: str = "agente",
    ) -> list[dict]:
        """Eventos do portal da transportadora para o pedido, do mais antigo ao mais recente."""
        eventos = [
            dict(linha)
            for linha in self._banco.executar(
                "SELECT * FROM rastreio_portais_transportadoras WHERE pedido_ref = ? "
                "ORDER BY data_hora_evento",
                (order_id,),
            )
        ]
        pedido = self.base.pedido_bruto(order_id)
        portal = eventos[-1]["portal"] if eventos else (pedido or {}).get("transportadora", "")
        with self._banco.transacao():
            self._registrar(
                "consultar_rastreio",
                f"Portal {portal}".strip(),
                conversation_id,
                order_id,
                executado_por,
                referencia="",
            )
        return eventos

    @_com_trava
    def verificar_pagamento(
        self,
        order_id: str,
        *,
        conversation_id: str | None = None,
        executado_por: str = "agente",
        papel: Papel = Papel.ATENDENTE,
    ) -> list[dict]:
        """Tentativas de cobrança do pedido no gateway (o final do cartão é ocultado)."""
        self._checar_papel(
            AcaoProposta(
                ferramenta="verificar_pagamento",
                papel=papel,
                executado_por=executado_por,
                conversation_id=conversation_id,
                order_id=order_id,
            )
        )
        transacoes = []
        for linha in self._banco.executar(
            "SELECT * FROM pagamentos_gateway WHERE order_id = ? ORDER BY data_hora_criacao",
            (order_id,),
        ):
            transacao = dict(linha)
            if transacao.get("cartao_final"):
                transacao["cartao_final"] = "****"
            transacoes.append(transacao)
        referencia = transacoes[-1]["transacao_id"] if transacoes else ""
        with self._banco.transacao():
            self._registrar(
                "verificar_pagamento",
                GATEWAY,
                conversation_id,
                order_id,
                executado_por,
                referencia=referencia,
            )
        return transacoes

    @_com_trava
    def responder_duvida(
        self,
        conversation_id: str,
        *,
        sku: str | None = None,
        executado_por: str = "agente",
        papel: Papel = Papel.ATENDENTE,
    ) -> dict:
        """Responde dúvida de produto só com a ficha de `produtos.csv` (sem inventar nada).

        Usa nome, composição, modo de uso e advertências, só os campos preenchidos. Sem `sku`,
        sem ficha ou com ficha vazia, não responde: devolve `precisa_pessoa=True` e o motivo,
        para o agente escalar. Quando responde, grava a mensagem ao cliente e a ação.
        """
        self._checar_papel(
            AcaoProposta(
                ferramenta="responder_duvida",
                papel=papel,
                executado_por=executado_por,
                conversation_id=conversation_id,
            )
        )
        sem_resposta = {"sku": sku or None, "resposta": None, "precisa_pessoa": True}
        if not sku:
            return {**sem_resposta, "motivo": "sem SKU identificado na conversa"}
        ficha = self._banco.executar_um("SELECT * FROM produtos WHERE sku = ?", (sku,))
        if ficha is None:
            return {**sem_resposta, "motivo": f"SKU {sku} sem ficha no catálogo"}
        partes = [
            f"{rotulo}: {ficha[campo].strip()}"
            for rotulo, campo in (
                ("Composição", "composicao"),
                ("Modo de uso", "modo_de_uso"),
                ("Advertências", "advertencias"),
            )
            if (ficha[campo] or "").strip()
        ]
        if not partes:
            return {**sem_resposta, "motivo": f"ficha do SKU {sku} sem composição nem modo de uso"}
        texto = mascarar(f"Sobre o {ficha['nome']}. " + " ".join(partes))
        acao = AcaoProposta(
            ferramenta="responder_duvida",
            papel=papel,
            executado_por=executado_por,
            conversation_id=conversation_id,
            motivo=texto,
        )
        with self._banco.transacao():
            referencia = self._mensagem(acao, "cliente", texto)
            self._registrar("responder_duvida", CATALOGO, acao=acao, referencia=referencia)
        return {"sku": sku, "resposta": texto, "precisa_pessoa": False, "motivo": None}

    @_com_trava
    def validar_cupom(
        self,
        codigo: str,
        *,
        order_id: str | None = None,
        conversation_id: str | None = None,
        executado_por: str = "agente",
        papel: Papel = Papel.ATENDENTE,
    ) -> dict:
        """Confere um cupom nas regras de `cupons.csv` e nos usos de `uso_cupons.csv`.

        Sem pedido: existe, está ativo e vigente no `agora`. Com pedido: vigência na data do
        pedido, marca, valor mínimo dos produtos, primeira compra, limites por cliente e total
        (sem contar o uso no próprio pedido) e, por último, a recusa registrada pela
        plataforma para esse pedido. `motivo` usa os nomes de `uso_cupons.motivo_recusa`.
        """
        self._checar_papel(
            AcaoProposta(
                ferramenta="validar_cupom",
                papel=papel,
                executado_por=executado_por,
                conversation_id=conversation_id,
                order_id=order_id,
            )
        )
        codigo = (codigo or "").strip().upper()
        motivo, detalhe, referencia = self._regras_do_cupom(codigo, order_id)
        acao = AcaoProposta(
            ferramenta="validar_cupom",
            papel=papel,
            executado_por=executado_por,
            conversation_id=conversation_id,
            order_id=order_id,
        )
        with self._banco.transacao():
            self._registrar("validar_cupom", CUPONS, acao=acao, referencia=referencia or codigo)
        return {
            "codigo": codigo,
            "order_id": order_id,
            "valido": motivo is None,
            "motivo": motivo,
            "detalhe": detalhe,
            "referencia": referencia,
        }

    def _regras_do_cupom(self, codigo: str, order_id: str | None):
        cupom = self._banco.executar_um("SELECT * FROM cupons WHERE codigo = ?", (codigo,))
        if cupom is None:
            return "cupom_inexistente", f"O cupom {codigo} não existe na plataforma.", None
        inicio = date.fromisoformat(cupom["inicio_vigencia"])
        fim = date.fromisoformat(cupom["fim_vigencia"])
        vigencia = f"vigência de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
        pedido = self.base.pedido_bruto(order_id) if order_id else None
        if pedido is None:
            hoje = self.agora.date()
            if cupom["status"] != "ativo" or not inicio <= hoje <= fim:
                return "fora_da_vigencia", f"Cupom {codigo} fora da {vigencia}.", None
            return None, f"Cupom {codigo} ativo ({cupom['descricao']}; {vigencia}).", None

        uso_aqui = self._banco.executar_um(
            "SELECT * FROM uso_cupons WHERE codigo = ? AND order_id = ? ORDER BY data_hora DESC",
            (codigo, order_id),
        )
        referencia = uso_aqui["uso_id"] if uso_aqui else None
        data_pedido = date.fromisoformat(pedido["data_pedido"][:10])
        if not inicio <= data_pedido <= fim:
            return (
                "fora_da_vigencia",
                f"Pedido de {data_pedido:%d/%m/%Y} fora da {vigencia}.",
                referencia,
            )
        marcas = cupom["marcas_validas"].strip()
        if marcas.lower() != "todas" and pedido["marca"] not in {
            m.strip() for m in re.split(r"[;,|]", marcas)
        }:
            return "marca_nao_valida", f"Cupom vale só para {marcas}.", referencia
        minimo = float(cupom["valor_minimo_pedido"] or 0)
        if float(pedido["valor_produtos"] or 0) < minimo:
            return (
                "valor_minimo_nao_atingido",
                f"Produtos somam R$ {float(pedido['valor_produtos']):.2f}; mínimo R$ {minimo:.2f}.",
                referencia,
            )
        cliente = pedido["customer_id"]
        if cupom["primeira_compra"] == "sim":
            anteriores = self._banco.executar_um(
                "SELECT COUNT(*) AS n FROM pedidos WHERE customer_id = ? AND order_id != ? "
                "AND substr(data_pedido, 1, 10) < ?",
                (cliente, order_id, data_pedido.isoformat()),
            )["n"]
            if anteriores:
                return (
                    "exclusivo_primeira_compra",
                    f"Cupom de primeira compra; o cliente tem {anteriores} pedido(s) anterior(es).",
                    referencia,
                )
        for coluna, filtro, nome in (
            ("limite_uso_por_cliente", "AND customer_id = ?", "limite_por_cliente_atingido"),
            ("limite_uso_total", "", "limite_total_atingido"),
        ):
            limite = cupom[coluna]
            if not limite:
                continue
            parametros = (codigo, order_id, cliente) if filtro else (codigo, order_id)
            usos = self._banco.executar_um(
                "SELECT COUNT(*) AS n FROM uso_cupons WHERE codigo = ? AND status = 'aplicado' "
                f"AND order_id != ? {filtro}",
                parametros,
            )["n"]
            if usos >= int(limite):
                return nome, f"{usos} uso(s) já aplicados; limite {int(limite)}.", referencia
        if uso_aqui is not None and uso_aqui["status"] == "recusado":
            return (
                uso_aqui["motivo_recusa"] or "recusado_pela_plataforma",
                f"A plataforma recusou o cupom neste pedido ({uso_aqui['motivo_recusa']}).",
                referencia,
            )
        return None, f"Cupom {codigo} válido para o pedido {order_id}.", referencia

    @_com_trava
    def aprovacao(self, aprovacao_id: str) -> dict | None:
        linha = self._banco.executar_um(
            "SELECT * FROM aprovacoes WHERE aprovacao_id = ?", (aprovacao_id,)
        )
        if linha is None:
            return None
        aprovacao = dict(linha)
        dados = json.loads(aprovacao["acao"])
        dados["papel"] = Papel(dados["papel"])
        aprovacao["acao"] = AcaoProposta(**dados)
        return aprovacao

    @_com_trava
    def acoes_registradas(self) -> list[RegistroAcao]:
        linhas = self._banco.executar("SELECT * FROM acoes_agente ORDER BY acao_id")
        return [self._registro(linha) for linha in linhas]

    # ---------- travas ----------

    def _checar_papel(self, acao: AcaoProposta) -> None:
        permitidos = {
            p.strip() for p in self._catalogo[acao.ferramenta]["papeis_permitidos"].split(";")
        }
        if acao.papel.value in permitidos:
            return
        self._bloquear(acao, f"papel {acao.papel.value} não está em {sorted(permitidos)}")

    def _bloquear(self, acao: AcaoProposta, motivo: str) -> None:
        """Grava a tentativa em `tentativas_bloqueadas` (fora da transação da ação) e recusa."""
        with self._banco.transacao():
            self._banco.executar(
                "INSERT INTO tentativas_bloqueadas VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    acao.ferramenta,
                    acao.papel.value,
                    acao.executado_por,
                    acao.conversation_id,
                    acao.order_id,
                    motivo,
                    _agora_texto(self.agora),
                ),
            )
        raise FerramentaNaoPermitida(f"{acao.ferramenta}: {motivo}")

    def _registro_existente(self, acao: AcaoProposta) -> RegistroAcao | None:
        """REQUISITOS.md @HG-12: chave = conversation_id + order_id + ação (sem o valor).

        Nas ferramentas do OMS, quando o motivo traz `sku=<SKU>`, o item entra na chave:
        dois itens diferentes da mesma conversa são dois reenvios legítimos (EC-20).
        """
        sku = sku_do_motivo(acao.motivo) if acao.ferramenta in _TIPO_OMS else None
        if sku:
            linha = self._banco.executar_um(
                "SELECT a.* FROM acoes_agente a JOIN trocas_reenvios t ON t.acao_id = a.acao_id "
                "WHERE a.acao = ? AND a.order_id IS NOT DISTINCT FROM ? AND a.conversation_id IS NOT DISTINCT FROM ? "
                "AND t.sku_enviado = ? ORDER BY a.acao_id LIMIT 1",
                (acao.ferramenta, acao.order_id, acao.conversation_id, sku),
            )
            return self._registro(linha) if linha else None
        linha = self._banco.executar_um(
            "SELECT * FROM acoes_agente WHERE acao = ? AND order_id IS NOT DISTINCT FROM ? "
            "AND conversation_id IS NOT DISTINCT FROM ? ORDER BY acao_id LIMIT 1",
            (acao.ferramenta, acao.order_id, acao.conversation_id),
        )
        return self._registro(linha) if linha else None

    # ---------- execução ----------

    def _executar(
        self, acao: AcaoProposta, acao_pendente: AcaoProposta | None, area: str | None
    ) -> RegistroAcao:
        ferramenta = acao.ferramenta
        texto = mascarar_texto(acao.motivo)
        agora = _agora_texto(self.agora)
        acao_id = self._proximo("AG", 6, [("acoes_agente", "acao_id")])

        if ferramenta in _PARA_O_CLIENTE:
            referencia = self._mensagem(acao, "cliente", texto)
            return self._registrar(
                ferramenta, CENTRAL, acao=acao, referencia=referencia, acao_id=acao_id
            )

        if ferramenta == "responder_colaborador":  # HG-10: resposta a pedido no canal do time
            referencia = self._mensagem(acao, "time", texto)
            return self._registrar(
                ferramenta, CANAL_DO_TIME, acao=acao, referencia=referencia, acao_id=acao_id
            )

        if ferramenta == "acionar_pessoa":
            conteudo = f"[{area}] {texto}" if area else texto
            referencia = self._mensagem(acao, "time", conteudo)
            return self._registrar(
                ferramenta, CANAL_DO_TIME, acao=acao, referencia=referencia, acao_id=acao_id
            )

        if ferramenta == "classificar_conversa":
            self._banco.executar(
                "INSERT INTO classificacoes VALUES (?, ?, ?, ?)",
                (acao.conversation_id, acao.categoria, acao.executado_por, agora),
            )
            return self._registrar(
                ferramenta,
                CENTRAL,
                acao=acao,
                referencia=f"CLS-{acao.conversation_id}",
                acao_id=acao_id,
            )

        if ferramenta == "sinalizar_suspeita":
            referencia = self._proximo("SUS-", 6, [("suspeitas", "suspeita_id")])
            self._banco.executar(
                "INSERT INTO suspeitas VALUES (?, ?, ?, ?, ?, 'pendente', ?)",
                (referencia, acao.conversation_id, acao.order_id, acao.executado_por, texto, agora),
            )
            return self._registrar(
                ferramenta, CENTRAL, acao=acao, referencia=referencia, acao_id=acao_id
            )

        if ferramenta == "abrir_chamado_transportadora":
            return self._abrir_chamado(acao, texto, acao_id)

        if ferramenta in _TIPO_OMS:
            return self._oms(acao, texto, acao_id)

        if ferramenta == "reembolsar":
            return self._reembolsar(acao, texto, acao_id)

        if ferramenta == "solicitar_aprovacao":
            return self._solicitar_aprovacao(acao, acao_pendente, texto, acao_id)

        if ferramenta in ("aprovar_acao", "rejeitar_acao"):
            return self._decidir_aprovacao(acao, texto, acao_id)

        if ferramenta == "abrir_incidente":
            referencia = self._proximo("INC-", 6, [])
            return self._registrar(
                ferramenta, INCIDENTES, acao=acao, referencia=referencia, acao_id=acao_id
            )

        if ferramenta == "notificar_clientes":
            self._checar_max_por_dia(acao)
            referencia = self._proximo("AVISO-", 6, [])
            return self._registrar(
                ferramenta, CENTRAL, acao=acao, referencia=referencia, acao_id=acao_id
            )

        if ferramenta == "cancelar_pedido":
            # estorno integral automático (ferramentas.csv); exige não separado (checado antes)
            pedido = self._pedido_obrigatorio(acao)
            return self._reembolsar(replace(acao, valor_rs=float(pedido["valor"])), texto, acao_id)

        if ferramenta == "alterar_endereco":
            self._pedido_obrigatorio(acao)
            referencia = self._mensagem(acao, "time", f"Novo endereço: {texto}")
            return self._registrar(
                ferramenta, CENTRAL, acao=acao, referencia=referencia, acao_id=acao_id
            )

        # registrar_cosmetovigilancia
        referencia = self._proximo("CVG-", 6, [])
        return self._registrar(
            ferramenta, QUALIDADE, acao=acao, referencia=referencia, acao_id=acao_id
        )

    def _checar_max_por_dia(self, acao: AcaoProposta) -> None:
        """HG-17: `notificar_clientes` respeita `max_por_dia` de `ferramentas.csv`."""
        limites = json.loads(self._catalogo[acao.ferramenta].get("limites") or "{}")
        maximo = limites.get("max_por_dia")
        if maximo is None:
            return
        enviados = self._banco.executar_um(
            "SELECT COUNT(*) AS n FROM acoes_agente WHERE acao = ? AND data_hora LIKE ?",
            (acao.ferramenta, _agora_texto(self.agora)[:10] + "%"),
        )["n"]
        if enviados >= int(maximo):
            raise FerramentaNaoPermitida(f"{acao.ferramenta}: máximo de {maximo} por dia atingido")

    def _mensagem(self, acao: AcaoProposta, destino: str, texto: str) -> str:
        mensagem_id = self._proximo("MSG-", 6, [("mensagens_enviadas", "mensagem_id")])
        self._banco.executar(
            "INSERT INTO mensagens_enviadas VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                mensagem_id,
                acao.conversation_id,
                destino,
                acao.ferramenta,
                texto,
                acao.executado_por,
                _agora_texto(self.agora),
            ),
        )
        return mensagem_id

    def _pedido_obrigatorio(self, acao: AcaoProposta) -> dict:
        pedido = self.base.pedido_bruto(acao.order_id) if acao.order_id else None
        if pedido is None:
            raise ValueError(f"{acao.ferramenta} exige order_id existente: {acao.order_id!r}")
        return pedido

    def _antes_da_separacao(self, acao: AcaoProposta) -> None:
        """`ferramentas.csv`: cancelar_pedido e alterar_endereco só antes da separação."""
        pedido = self._pedido_obrigatorio(acao)
        if pedido.get("data_separacao"):
            raise ValueError(
                f"{acao.ferramenta}: pedido {acao.order_id} já foi separado em "
                f"{pedido['data_separacao'][:10]} (somente_antes_da_separacao)"
            )

    def _suspeita_decidivel(self, acao: AcaoProposta, decisao: str | None) -> str:
        """HG-04: suspeita pendente da conversa, decidida por quem não a sinalizou."""
        if decisao not in DECISOES_SUSPEITA:
            raise ValueError(f"decidir_suspeita exige decisao em {DECISOES_SUSPEITA}: {decisao!r}")
        linha = self._banco.executar_um(
            "SELECT suspeita_id, sinalizado_por FROM suspeitas WHERE conversation_id IS NOT DISTINCT FROM ? "
            "AND estado = 'pendente' ORDER BY suspeita_id DESC LIMIT 1",
            (acao.conversation_id,),
        )
        if linha is None:
            raise ValueError(f"sem suspeita pendente em {acao.conversation_id}")
        if linha["sinalizado_por"] == acao.executado_por:
            self._bloquear(
                acao, "quem sinalizou não decide a suspeita (nao_decide_o_que_ele_mesmo_sinalizou)"
            )
        return linha["suspeita_id"]

    def _decidir_suspeita(self, acao: AcaoProposta, suspeita_id: str, decisao: str) -> RegistroAcao:
        self._banco.executar(
            "UPDATE suspeitas SET estado = ? WHERE suspeita_id = ?", (decisao, suspeita_id)
        )
        return self._registrar(
            acao.ferramenta,
            CENTRAL,
            acao=acao,
            referencia=suspeita_id,
            acao_id=self._proximo("AG", 6, [("acoes_agente", "acao_id")]),
        )

    def _abrir_chamado(self, acao: AcaoProposta, texto: str, acao_id: str) -> RegistroAcao:
        pedido = self._pedido_obrigatorio(acao)
        transportadora = pedido["transportadora"]
        sigla = _SIGLA_CHAMADO.get(transportadora, transportadora[:3].upper())
        prefixo = f"{sigla}-{self.agora.year}"
        referencia = self._proximo(prefixo, 5, [("chamados_transportadora", "chamado_id")])
        self._banco.executar(
            "INSERT INTO chamados_transportadora (chamado_id, transportadora, order_id, "
            "codigo_rastreio, conversation_id, acao_id, aberto_por, data_abertura, motivo, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'aberto')",
            (
                referencia,
                transportadora,
                acao.order_id,
                pedido["codigo_rastreio"],
                acao.conversation_id,
                acao_id,
                acao.executado_por,
                _agora_texto(self.agora),
                texto,
            ),
        )
        return self._registrar(
            acao.ferramenta,
            f"Portal {transportadora}",
            acao=acao,
            referencia=referencia,
            acao_id=acao_id,
        )

    def _aprovador(self, acao: AcaoProposta) -> str | None:
        if acao.aprovado_por or not acao.aprovacao_id:
            return acao.aprovado_por
        aprovacao = self.aprovacao(acao.aprovacao_id)
        return aprovacao["decidido_por"] if aprovacao else None

    def _oms(self, acao: AcaoProposta, texto: str, acao_id: str) -> RegistroAcao:
        pedido = self._pedido_obrigatorio(acao)
        tipo, sistema = _TIPO_OMS[acao.ferramenta]
        aprovado_por = self._aprovador(acao)
        referencia = self._proximo("OMS", 6, [("trocas_reenvios", "solicitacao_id")])
        self._banco.executar(
            "INSERT INTO trocas_reenvios (solicitacao_id, acao_id, conversation_id, customer_id, "
            "order_id_original, tipo, motivo_registrado, data_solicitacao, solicitado_por, "
            "aprovado_por, sku_enviado, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'solicitado')",
            (
                referencia,
                acao_id,
                acao.conversation_id,
                pedido["customer_id"],
                acao.order_id,
                tipo,
                acao.categoria or texto,
                _agora_texto(self.agora),
                acao.executado_por,
                aprovado_por,
                sku_do_motivo(acao.motivo),
            ),
        )
        return self._registrar(
            acao.ferramenta,
            sistema,
            acao=acao,
            referencia=referencia,
            acao_id=acao_id,
            aprovado_por=aprovado_por,
        )

    def _reembolsar(self, acao: AcaoProposta, texto: str, acao_id: str) -> RegistroAcao:
        pedido = self._pedido_obrigatorio(acao)
        transacao = self._banco.executar_um(
            "SELECT transacao_id FROM pagamentos_gateway WHERE order_id = ? "
            "AND status IN ('paga', 'capturada') ORDER BY data_hora_criacao DESC LIMIT 1",
            (acao.order_id,),
        )
        aprovado_por = self._aprovador(acao)
        referencia = self._proximo("EST", 6, [("estornos", "estorno_id")])
        tipo = "parcial" if acao.valor_rs < float(pedido["valor"]) else "total"
        self._banco.executar(
            "INSERT INTO estornos (estorno_id, transacao_id, order_id, conversation_id, acao_id, "
            "tipo, valor, motivo, solicitado_por, aprovado_por, data_hora_solicitacao, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'em_processamento')",
            (
                referencia,
                transacao["transacao_id"] if transacao else None,
                acao.order_id,
                acao.conversation_id,
                acao_id,
                tipo,
                _valor_texto(acao.valor_rs),
                texto,
                acao.executado_por,
                aprovado_por,
                _agora_texto(self.agora),
            ),
        )
        return self._registrar(
            acao.ferramenta,
            GATEWAY,
            acao=acao,
            referencia=referencia,
            acao_id=acao_id,
            aprovado_por=aprovado_por,
        )

    def _solicitar_aprovacao(
        self, acao: AcaoProposta, pendente: AcaoProposta | None, texto: str, acao_id: str
    ) -> RegistroAcao:
        if pendente is None:
            raise ValueError("solicitar_aprovacao exige acao_pendente")
        referencia = self._proximo("APR-", 6, [("aprovacoes", "aprovacao_id")])
        serializada = {**asdict(pendente), "papel": pendente.papel.value}
        self._banco.executar(
            "INSERT INTO aprovacoes VALUES (?, ?, ?, 'pendente', NULL, ?, ?, NULL)",
            (
                referencia,
                json.dumps(serializada, ensure_ascii=False),
                acao.executado_por,
                texto,
                _agora_texto(self.agora),
            ),
        )
        resumo = (
            f"Aprovação {referencia}: {pendente.ferramenta} de R$ {pendente.valor_rs:.2f} "
            f"no pedido {pendente.order_id}. {texto}"
        )
        self._mensagem(acao, "time", resumo)
        return self._registrar(
            acao.ferramenta, CANAL_DO_TIME, acao=acao, referencia=referencia, acao_id=acao_id
        )

    def _decidir_aprovacao(self, acao: AcaoProposta, texto: str, acao_id: str) -> RegistroAcao:
        aprovacao = self.aprovacao(acao.aprovacao_id) if acao.aprovacao_id else None
        if aprovacao is None:
            raise ValueError(f"aprovação inexistente: {acao.aprovacao_id!r}")
        if aprovacao["estado"] != "pendente":
            raise ValueError(f"aprovação {acao.aprovacao_id} já está {aprovacao['estado']}")
        estado = "aprovada" if acao.ferramenta == "aprovar_acao" else "rejeitada"
        self._banco.executar(
            "UPDATE aprovacoes SET estado = ?, decidido_por = ?, comentario = ?, decidido_em = ? "
            "WHERE aprovacao_id = ?",
            (estado, acao.executado_por, texto, _agora_texto(self.agora), acao.aprovacao_id),
        )
        pendente = aprovacao["acao"]
        return self._registrar(
            acao.ferramenta,
            CANAL_DO_TIME,
            conversation_id=acao.conversation_id or pendente.conversation_id,
            order_id=acao.order_id or pendente.order_id,
            executado_por=acao.executado_por,
            valor_rs=pendente.valor_rs,
            aprovado_por=acao.executado_por if estado == "aprovada" else None,
            referencia=acao.aprovacao_id,
            acao_id=acao_id,
        )

    # ---------- log ----------

    def _proximo(self, prefixo: str, largura: int, fontes: list[tuple[str, str]]) -> str:
        """Próximo identificador sequencial com `prefixo`, sem colidir com o histórico."""
        fontes = [
            *fontes,
            ("acoes_executadas_sistemas", "referencia_sistema"),
            ("acoes_agente", "referencia_sistema"),
        ]
        maior = 0
        for tabela, coluna in fontes:
            for linha in self._banco.executar(
                f"SELECT {coluna} AS valor FROM {tabela} WHERE {coluna} LIKE ?", (prefixo + "%",)
            ):
                valor = linha["valor"]
                sufixo = valor[len(prefixo) :]
                if sufixo.isdigit():
                    maior = max(maior, int(sufixo))
        return f"{prefixo}{maior + 1:0{largura}d}"

    def _registrar(
        self,
        ferramenta: str,
        sistema: str,
        conversation_id: str | None = None,
        order_id: str | None = None,
        executado_por: str = "agente",
        *,
        referencia: str,
        acao: AcaoProposta | None = None,
        acao_id: str | None = None,
        valor_rs: float | None = None,
        aprovado_por: str | None = None,
    ) -> RegistroAcao:
        if acao is not None:
            conversation_id, order_id = acao.conversation_id, acao.order_id
            executado_por = acao.executado_por
            valor_rs = acao.valor_rs if valor_rs is None else valor_rs
            aprovado_por = aprovado_por or acao.aprovado_por
        valor_rs = valor_rs or 0.0
        acao_id = acao_id or self._proximo("AG", 6, [("acoes_agente", "acao_id")])
        self._banco.executar(
            "INSERT INTO acoes_agente VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                acao_id,
                conversation_id,
                order_id,
                _agora_texto(self.agora),
                sistema,
                ferramenta,
                _valor_texto(valor_rs) if valor_rs else "",
                executado_por,
                aprovado_por,
                referencia,
            ),
        )
        return RegistroAcao(
            acao_id=acao_id,
            conversation_id=conversation_id,
            order_id=order_id,
            data_hora=self.agora,
            sistema=sistema,
            acao=ferramenta,
            valor_rs=valor_rs,
            executado_por=executado_por,
            aprovado_por=aprovado_por,
            referencia_sistema=referencia,
        )

    def _registro(self, linha) -> RegistroAcao:
        return RegistroAcao(
            acao_id=linha["acao_id"],
            conversation_id=linha["conversation_id"],
            order_id=linha["order_id"],
            data_hora=datetime.fromisoformat(linha["data_hora"]).replace(tzinfo=self.agora.tzinfo),
            sistema=linha["sistema"],
            acao=linha["acao"],
            valor_rs=float(linha["valor_rs"]) if linha["valor_rs"] else 0.0,
            executado_por=linha["executado_por"],
            aprovado_por=linha["aprovado_por"],
            referencia_sistema=linha["referencia_sistema"],
        )
