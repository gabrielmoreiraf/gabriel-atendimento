"""Agente analista (P4, HG-17, HG-19, HG-23): age só com as ferramentas do papel analista.

Incidente (`abrir_incidente`, INC-######), avisos (`notificar_clientes`, AVISO-######) e o
aviso ao time (`acionar_pessoa`) saem pelo executor (`atendimento.ferramentas`), que confere
o papel e grava em `acoes_agente`.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import date, datetime

from atendimento.analista.padroes import Padrao, detectar_padroes
from atendimento.contratos import AGORA, AcaoProposta, Papel, RegistroAcao
from atendimento.dados.repositorio import Base
from atendimento.ferramentas import FerramentaNaoPermitida, Ferramentas

PAPEL = Papel.ANALISTA
MIN_PEDIDOS_INCIDENTE = 3  # SPEC.md, Q22
EXECUTADO_POR = "agente_analista"

# Aviso proativo por tipo de padrão. Padrão sem entrada aqui só abre incidente.
AVISOS = {
    "cobranca_em_dobro": (
        "cobranca_duplicada",
        # Q22: descreve o que foi identificado e o próximo passo, sem prometer o estorno,
        # que depende de reembolsar (atendente) e, acima da alçada, de aprovação.
        "Identificamos duas cobranças para o seu pedido {order_id} e abrimos uma análise "
        "com o time de pagamentos. Você recebe o retorno da análise por este canal, sem "
        "precisar entrar em contato.",
    ),
}


@dataclass(frozen=True)
class ResultadoAnalista:
    padrao: Padrao | None
    incidente: dict | None
    notificacoes: tuple[dict, ...] = ()
    sem_consentimento: tuple[str, ...] = ()  # order_ids sem canal com consentimento (HG-23)
    adiados: tuple[str, ...] = ()  # order_ids que passaram do máximo do dia
    aviso_ao_time: RegistroAcao | None = None
    detalhes: dict = field(default_factory=dict)


def canal_com_consentimento(cliente: dict | None) -> str | None:
    """HG-23 / Q13: só avisa em canal com `aceita_comunicacao_<canal>` = sim; prefere o
    `canal_preferido`; sem consentimento em nenhum canal, não avisa."""
    if not cliente:
        return None
    aceitos = [c for c in ("whatsapp", "email") if cliente.get(f"aceita_comunicacao_{c}") == "sim"]
    preferido = cliente.get("canal_preferido")
    if preferido in aceitos:
        return preferido
    return aceitos[0] if aceitos else None


class Analista:
    def __init__(
        self,
        base: Base,
        ferramentas: Ferramentas,
        *,
        agora: datetime = AGORA,
        max_por_dia: int | None = None,
        executado_por: str = EXECUTADO_POR,
    ):
        self.base = base
        self.ferramentas = ferramentas
        self.agora = agora
        self.executado_por = executado_por
        self._catalogo = base.ferramentas()
        limites = json.loads(self._catalogo["notificar_clientes"].get("limites") or "{}")
        self.max_por_dia = max_por_dia if max_por_dia is not None else int(limites["max_por_dia"])
        self._enviados: dict[date, int] = {}
        # Q22: um incidente por (tipo, dia), compartilhado entre o caso e a rota do analista
        self._incidentes: dict[tuple[str, date], dict] = {}
        self._avisados: dict[str, set[str]] = {}  # incidente_id -> order_ids já avisados
        self._trava = threading.RLock()

    def _checar_papel(self, ferramenta: str) -> None:
        permitidos = {p.strip() for p in self._catalogo[ferramenta]["papeis_permitidos"].split(";")}
        if PAPEL.value not in permitidos:
            raise FerramentaNaoPermitida(f"{ferramenta}: papel {PAPEL.value} não permitido")

    def tratar(
        self, padrao: Padrao, *, origem: dict | None = None, agora: datetime | None = None
    ) -> ResultadoAnalista:
        """Abre (ou reaproveita) o incidente do dia e avisa quem ainda não foi avisado (HG-17).

        Q22: um incidente por (tipo, dia); só abre com `MIN_PEDIDOS_INCIDENTE` pedidos ou mais;
        cliente já avisado sobre o mesmo incidente não recebe outro aviso.
        """
        with self._trava:
            return self._tratar(padrao, origem=origem, agora=agora or self.agora)

    def _tratar(self, padrao: Padrao, *, origem: dict | None, agora: datetime) -> ResultadoAnalista:
        if len(padrao.escopo) < MIN_PEDIDOS_INCIDENTE:
            return ResultadoAnalista(
                padrao=padrao,
                incidente=None,
                detalhes={
                    "motivo": f"padrão com {len(padrao.escopo)} pedido(s); o incidente abre "
                    f"com {MIN_PEDIDOS_INCIDENTE} ou mais (Q22)"
                },
            )
        chave = (padrao.tipo, agora.date())
        incidente = self._incidentes.get(chave)
        reaproveitado = incidente is not None
        if incidente is None:
            incidente = self._abrir_incidente(padrao, origem, agora)
            self._incidentes[chave] = incidente
        avisados = self._avisados.setdefault(incidente["incidente_id"], set())
        notificacoes, sem_consentimento, adiados = self._avisar(padrao, incidente, avisados, agora)

        aviso = None
        if not reaproveitado or notificacoes:
            aviso = self.ferramentas.executar(
                AcaoProposta(
                    ferramenta="acionar_pessoa",
                    papel=PAPEL,
                    executado_por=self.executado_por,
                    motivo=(
                        f"{incidente['incidente_id']} ({padrao.tipo}): {len(padrao.escopo)} "
                        f"pedidos. {padrao.fator}. Evidência: {padrao.evidencia['consulta']}. "
                        f"Avisos enviados agora: {len(notificacoes)}; sem consentimento: "
                        f"{len(sem_consentimento)}; para amanhã: {len(adiados)}."
                    ),
                ),
                area="analista",
            )
        return ResultadoAnalista(
            padrao=padrao,
            incidente=incidente,
            notificacoes=tuple(notificacoes),
            sem_consentimento=tuple(sem_consentimento),
            adiados=tuple(adiados),
            aviso_ao_time=aviso,
            detalhes={"reaproveitado": reaproveitado, "avisados_no_incidente": len(avisados)},
        )

    def _abrir_incidente(self, padrao: Padrao, origem: dict | None, agora: datetime) -> dict:
        self._checar_papel("abrir_incidente")
        registro = self.ferramentas.executar(
            AcaoProposta(
                ferramenta="abrir_incidente",
                papel=PAPEL,
                executado_por=self.executado_por,
                order_id=padrao.escopo[0] if len(padrao.escopo) == 1 else None,
                motivo=f"{padrao.tipo}: {len(padrao.escopo)} pedidos. {padrao.fator}. "
                f"Evidência: {padrao.evidencia['consulta']}.",
            )
        )
        return {
            "incidente_id": registro.referencia_sistema,
            "acao_id": registro.acao_id,
            "ferramenta": "abrir_incidente",
            "papel": PAPEL.value,
            "executado_por": self.executado_por,
            "data_hora": agora.isoformat(),
            "tipo": padrao.tipo,
            "fator": padrao.fator,
            "escopo": padrao.escopo,
            "evidencias": padrao.evidencia,
            "origem": origem,
        }

    def _avisar(
        self, padrao: Padrao, incidente: dict, avisados: set[str], agora: datetime
    ) -> tuple[list[dict], list[str], list[str]]:
        notificacoes: list[dict] = []
        sem_consentimento: list[str] = []
        adiados: list[str] = []
        if padrao.tipo in AVISOS:
            self._checar_papel("notificar_clientes")
            tipo_aviso, modelo = AVISOS[padrao.tipo]
            dia = agora.date()
            for order_id in padrao.escopo:
                if order_id in avisados:
                    continue
                canal = canal_com_consentimento(
                    self.base.cliente(padrao.clientes.get(order_id, ""))
                )
                if canal is None:
                    sem_consentimento.append(order_id)
                elif self._enviados.get(dia, 0) >= self.max_por_dia:
                    adiados.append(order_id)
                else:
                    texto = modelo.format(order_id=order_id)
                    try:
                        enviado = self.ferramentas.executar(
                            AcaoProposta(
                                ferramenta="notificar_clientes",
                                papel=PAPEL,
                                executado_por=self.executado_por,
                                order_id=order_id,
                                motivo=texto,
                            )
                        )
                    except FerramentaNaoPermitida:  # máximo do dia já atingido no executor
                        adiados.append(order_id)
                        continue
                    self._enviados[dia] = self._enviados.get(dia, 0) + 1
                    avisados.add(order_id)
                    notificacoes.append(
                        {
                            "ferramenta": "notificar_clientes",
                            "referencia": enviado.referencia_sistema,
                            "papel": PAPEL.value,
                            "incidente_id": incidente["incidente_id"],
                            "order_id": order_id,
                            "canal": canal,
                            "tipo_aviso": tipo_aviso,
                            "texto": texto,
                        }
                    )
        return notificacoes, sem_consentimento, adiados


def chamar_analista(
    base: Base,
    ferramentas: Ferramentas,
    *,
    fator: str,
    order_ids: list[str] | tuple[str, ...],
    conversation_ids: list[str] | tuple[str, ...] = (),
    agora: datetime = AGORA,
    analista: Analista | None = None,
) -> ResultadoAnalista:
    """HG-19: o agente de atendimento passa o caso (conversas, pedidos e fator em comum).

    O analista confere na base se o padrão existe e inclui esses pedidos; só então abre
    incidente. Use um único `Analista` por dia para valer o máximo de avisos diário.
    """
    origem = {
        "conversation_ids": tuple(conversation_ids),
        "order_ids": tuple(order_ids),
        "fator": fator,
    }
    for padrao in detectar_padroes(base, agora):
        if padrao.tipo == fator and set(order_ids) & set(padrao.escopo):
            analista = analista or Analista(base, ferramentas, agora=agora)
            return analista.tratar(padrao, origem=origem)
    return ResultadoAnalista(padrao=None, incidente=None, detalhes={"origem": origem})
