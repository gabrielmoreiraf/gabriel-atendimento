"""Orquestração de um caso: o "colega" que pega a conversa e resolve.

Fluxo: mensagens → leitura → pedido → anexos → verificação (só avaria, faltante e
personalização) → AcaoProposta → política → executa, pede aprovação, sinaliza suspeita,
nega ou escala → responde ao cliente → avisa o canal do time.

- HG-01: o leitor só propõe; quem decide é `atendimento.politicas.decidir`.
- HP-09: todo caso termina com ação registrada (com `referencia_sistema`) ou escalação.
- HG-09: instrução embutida no texto do cliente é só dado: sinalizada no canal, sem ação.
- HG-11: texto ao cliente e ao time passa por `mascarar`; o agente nunca ecoa o cliente.
- Q6 (valor da ação): `valor_total` do item reclamado em `itens_pedido` (brinde = valor do
  item brinde, R$ 0,00 na base); sem item identificável, o valor do pedido inteiro
  (o maior, portanto o mais conservador para a alçada). Reembolso usa o valor do pedido.
"""

from __future__ import annotations

import itertools
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from atendimento.agente.aprovacoes import (
    Aprovacao,
    AprovacaoInvalida,
    AprovacaoRecusada,
    aprovar,
    rejeitar,
    validar_aprovacao,
)
from atendimento.agente.leitor import Leitura, ler, mascarar
from atendimento.agente.priorizacao import priorizar
from atendimento.agente.rotulos import (
    acao_feita,
    em_linguagem_do_time,
    nome_da_acao,
    rotulo_categoria,
)
from atendimento.contratos import (
    AGORA,
    FUSO,
    AcaoProposta,
    Decisao,
    Item,
    Papel,
    Pedido,
    RegistroAcao,
    Resultado,
    TipoSinal,
    VeredictoEvidencia,
)
from atendimento.politicas import decidir
from atendimento.verificacao import verificar

EXECUTOR = "agente"
TEXTO_FOTO = (
    "Para seguirmos com a solução, envie por favor uma foto do produto e da embalagem por aqui."
)
TEXTO_NOVA_FOTO = (
    "Para conferirmos direitinho, envie por favor uma nova foto do produto mostrando a "
    "personalização e a embalagem."
)
TEXTO_PEDIR_NUMERO = (
    "Para seguirmos, por favor nos envie o número do pedido (ele começa com GBH ou GCH)."
)
# Categorias do leitor que viram ação com dinheiro: sem pedido, nada com dinheiro (Q20).
COM_DINHEIRO_POSSIVEL = {
    "avaria_vazamento",
    "item_faltante",
    "erro_personalizacao",
    "cobranca_duplicada",
    "arrependimento",
}
COM_EVIDENCIA = {"avaria_vazamento", "item_faltante", "erro_personalizacao"}
COM_DINHEIRO = {
    "reenviar_produto",
    "reimprimir_personalizacao",
    "trocar_produto",
    "reembolsar",
    "cancelar_pedido",  # estorno integral automático (ferramentas.csv)
}
# Gravidade do estado final (o caso fica no estado mais grave entre as demandas).
GRAVIDADE = {
    "resolvida": 0,
    "aguardando_cliente": 1,  # pedimos foto ou número do pedido: nada resolvido ainda
    "aguardando_aprovacao": 2,
    "suspeita": 3,
    "escalada": 4,
}
# HG-16: ações que não se repetem no mesmo pedido quando outra conversa já as fez.
FATOR_ANALISTA = {"cobranca_em_dobro": "cobrança em dobro", "contato_repetido": "contato repetido"}
REPOSICAO = {"reenviar_produto", "reimprimir_personalizacao", "trocar_produto"}
# HG-16 / Q23: só ação SEM dinheiro já feita com o mesmo motivo não se repete (chamado aberto);
# ação com dinheiro sempre passa pela política com o acumulado do pedido (HG-22).
NAO_REPETIR = {"abrir_chamado_transportadora"}
NOME_DA_ACAO = {
    "abrir_chamado_transportadora": "um chamado com a transportadora",
    "reenviar_produto": "o reenvio",
    "reimprimir_personalizacao": "a nova produção da personalização",
    "trocar_produto": "a troca",
    "reembolsar": "o estorno",
    "cancelar_pedido": "o cancelamento",
}
ESTADOS_EFETIVOS = {"paga", "capturada"}  # pagamentos_gateway.status com dinheiro retido


@dataclass
class Caso:
    conversation_id: str
    estado: str = "aberta"
    canal: str | None = None
    replay: bool = False
    categoria: str | None = None
    categoria_secundaria: str | None = None
    order_id: str | None = None
    instrucao_embutida: bool = False
    decisao: Decisao | None = None
    decisoes: list[Decisao] = field(default_factory=list)
    veredicto: VeredictoEvidencia | None = None
    acoes: list[RegistroAcao] = field(default_factory=list)
    resposta_ao_cliente: str = ""
    aprovacao_ids: list[str] = field(default_factory=list)
    analista: list[dict] = field(default_factory=list)
    resposta_por_ferramenta: str = ""  # texto já enviado por responder_duvida
    tag: str | None = None  # tag de encerramento (categorias.<cat>.tag_equivalente), HP-04


PARALELO_LEITURA = 8  # leituras simultâneas do leitor (o do Claude é uma chamada de rede)
_NAO_LIDA = object()  # _processar sem leitura pronta: lê na hora (só o leitor por regras)


class RodadaEmAndamento(RuntimeError):
    """Já há uma rodada de processamento da fila em andamento (a API responde 409)."""


@dataclass
class Suspeita:
    suspeita_id: str
    acao: AcaoProposta  # ação da política suspensa até a decisão do supervisor
    sinalizado_por: str
    sinalizada_em: datetime
    prazo: datetime  # sinalizada_em + reclamacao_suspeita.prazo_decisao_horas
    sinais: tuple[str, ...] = ()
    estado: str = "pendente"  # pendente, procedente, improcedente
    decidido_por: str | None = None
    justificativa: str = ""


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def _rs(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class Agente:
    def __init__(
        self,
        base,
        ferramentas,
        *,
        agora: datetime = AGORA,
        replay=None,
        analista=None,
        leitor=None,
    ):
        self.base = base
        self.ferramentas = ferramentas
        self.agora = agora
        self.politicas: dict[str, str] = base.politicas()
        self.equipe: list[dict] = base.equipe()
        self.casos: dict[str, Caso] = {}
        # modo replay (F3): conversas do histórico reprocessadas no "agora" em que chegaram
        self.fonte_replay = replay or (ReplaySQL(base) if hasattr(base, "conexao") else None)
        self._conversas_replay: dict[str, dict] = {}
        self._em_replay = False
        # HG-19: agente analista (W2); injetável nos testes
        self.analista = analista or (
            AnalistaReal(base, ferramentas) if hasattr(base, "conexao") else None
        )
        self.canal: list[dict] = []
        self.aprovacoes: dict[str, Aprovacao] = {}
        self.suspeitas: dict[str, Suspeita] = {}
        self._cupons: list[str] | None = None
        # leitor da mensagem: por regras (padrão) ou com Claude (leitor.escolher_leitor)
        self.leitor = leitor
        self.eventos: list[dict] = []
        self._ids_canal = itertools.count(1)
        # mesma trava da base (W1): serializa todo acesso à conexão SQLite compartilhada
        self._trava = getattr(base, "trava", None) or threading.RLock()
        self._rodada = threading.Lock()  # uma rodada da fila por vez

    # ---------- eventos e canal ----------
    def emitir(self, tipo: str, payload: dict) -> None:
        self.eventos.append({"tipo": tipo, "payload": payload})

    def postar_no_canal(
        self, tipo: str, para: str | None, texto: str, cid: str, *, regra=None, **extra
    ) -> dict:
        """Texto em linguagem do time: 'AT… · <Categoria>: …', sem chave de política nem nome
        de ferramenta cru; a chave da regra vai em mensagem['regra'] (auditoria e detalhe)."""
        texto, chaves = em_linguagem_do_time(texto)
        caso = self.casos.get(cid) if cid else None
        if caso is not None and texto.startswith(f"{cid}: "):
            texto = f"{cid} · {rotulo_categoria(caso.categoria)}: " + texto[len(cid) + 2 :]
        mensagem = {
            "id": f"CANAL-{next(self._ids_canal):04d}",
            "tipo": tipo,
            "para": para,
            "texto": mascarar(texto),
            "regra": regra or ("; ".join(chaves) if chaves else None),
            "conversation_id": cid,
            "replay": self._em_replay,
            **extra,
        }
        self.canal.append(mensagem)
        self.emitir("canal", mensagem)
        return mensagem

    def executar(self, caso: Caso, acao: AcaoProposta, **opcoes) -> RegistroAcao:
        if acao.aprovacao_id and acao.ferramenta not in ("aprovar_acao", "rejeitar_acao"):
            # HG-05 / Q21: só executa se a aprovação registrada cobre esta ação.
            consulta = getattr(self.ferramentas, "aprovacao", None)
            aprovacao = consulta(acao.aprovacao_id) if consulta else None
            motivo = validar_aprovacao(aprovacao, acao, self.equipe)
            if motivo:
                raise AprovacaoInvalida(motivo)
        registro = self.ferramentas.executar(acao, **opcoes)
        caso.acoes.append(registro)
        self.emitir("acao", _registro_json(registro))
        return registro

    def _proposta(self, caso: Caso, ferramenta: str, **kw) -> AcaoProposta:
        return AcaoProposta(
            ferramenta=ferramenta,
            papel=kw.pop("papel", Papel.ATENDENTE),
            executado_por=kw.pop("executado_por", EXECUTOR),
            conversation_id=caso.conversation_id,
            order_id=kw.pop("order_id", caso.order_id),
            **kw,
        )

    # ---------- fila ----------
    def fila(self) -> list[dict]:
        with self._trava:
            return self._fila()

    def _fila(self) -> list[dict]:
        ordenada = priorizar(self.base.fila(), self.politicas, agora=self.agora)
        for conversa in ordenada:
            caso = self.casos.get(conversa["conversation_id"])
            conversa["estado"] = caso.estado if caso else "aberta"
        return ordenada

    def processar_fila(self) -> dict:
        """Lê todas as conversas abertas fora da trava (até 8 em paralelo) e só então decide e
        executa, conversa a conversa, com a trava; GET /api/fila e /api/placar seguem respondendo."""
        if not self._rodada.acquire(blocking=False):
            raise RodadaEmAndamento("já há uma rodada da fila em andamento")
        try:
            with self._trava:
                abertas = [c["conversation_id"] for c in self._fila() if c["estado"] == "aberta"]
            leituras = self._pre_ler(abertas)
            for cid in abertas:
                with self._trava:
                    if cid not in self.casos:
                        self._processar(cid, leituras[cid])
            return self.placar()
        finally:
            self._rodada.release()

    # ---------- leitura fora da trava ----------
    def _ler_conversa(self, cid: str, cupons: list[str]):
        leitor = self.leitor or ler
        with self._trava:  # leitura rápida do SQLite; solta antes de chamar o leitor
            textos = [m["texto"] for m in self.base.mensagens(cid) if m.get("autor") == "cliente"]
            nomes = self._nomes_do_cliente(cid) if getattr(leitor, "aceita_nomes", False) else ()
        if not any(t and t.strip() for t in textos):
            return None  # só o bot falou
        if nomes:
            return leitor("\n".join(textos), cupons=cupons, nomes=nomes)
        return leitor("\n".join(textos), cupons=cupons)

    def _nomes_do_cliente(self, cid: str) -> tuple[str, ...]:
        """Nome do cliente da conversa, para o leitor com Claude mascarar antes da API."""
        try:
            customer_id = self._conversa(cid).get("customer_id")
        except KeyError:
            return ()
        cliente = self.base.cliente(customer_id) if customer_id else None
        nome = (cliente or {}).get("nome")
        return (nome,) if nome else ()

    def _pre_ler(self, cids: list[str]) -> dict:
        """Lê as conversas SEM segurar a trava (nunca chame com a trava segura) e emite o
        evento SSE `leitura` com {lidas, total} a cada conversa lida."""
        cupons = self._codigos_cupom()
        total = len(cids)
        contagem = {"lidas": 0}
        trava_contagem = threading.Lock()

        def ler_uma(cid: str):
            leitura = self._ler_conversa(cid, cupons)
            with trava_contagem:
                contagem["lidas"] += 1
                self.emitir("leitura", {"lidas": contagem["lidas"], "total": total})
            return cid, leitura

        if total <= 1:
            return dict(ler_uma(cid) for cid in cids)
        with ThreadPoolExecutor(max_workers=PARALELO_LEITURA) as pool:
            return dict(pool.map(ler_uma, cids))

    def placar(self) -> dict:
        with self._trava:
            placar = self._placar([c for c in self.casos.values() if not c.replay])
            placar["replay"] = self._placar([c for c in self.casos.values() if c.replay])
            return placar

    def _placar(self, casos: list[Caso]) -> dict:
        contagem = {estado: 0 for estado in GRAVIDADE}
        for caso in casos:
            contagem[caso.estado] = contagem.get(caso.estado, 0) + 1
        valor = sum(r.valor_rs for c in casos for r in c.acoes if r.acao in COM_DINHEIRO)
        # custo evitado = custo por conversa do canal (politicas.csv) de cada caso que o
        # agente resolveu sozinho + custo de aceitar uma reclamação que não procede
        # (pedido × 45%, parametros.md) de cada caso sinalizado como suspeito.
        evitado = sum(
            float(self.politicas.get(f"custo_por_conversa_rs.{c.canal}", 0.0))
            for c in casos
            if c.estado == "resolvida" and not c.aprovacao_ids
        ) + sum(
            c.veredicto.custo_aceitar_falso_rs
            for c in casos
            if c.estado == "suspeita" and c.veredicto
        )
        return {
            "resolvidas_sozinho": sum(
                1 for c in casos if c.estado == "resolvida" and not c.aprovacao_ids
            ),
            "aguardando_aprovacao": contagem["aguardando_aprovacao"],
            "aguardando_cliente": contagem["aguardando_cliente"],
            "suspeitas": contagem["suspeita"],
            "escaladas": contagem["escalada"],
            "valor_executado_rs": round(valor, 2),
            "custo_evitado_rs": round(evitado, 2),
        }

    # ---------- caso ----------
    def _conversa(self, cid: str) -> dict:
        for conversa in self.base.fila():
            if conversa["conversation_id"] == cid:
                return conversa
        if cid in self._conversas_replay:
            return self._conversas_replay[cid]
        raise KeyError(cid)

    def obter_analista(self):
        """O único Analista do processo (fluxo do caso e router /api/analista)."""
        obter = getattr(self.analista, "obter", None)
        return obter() if obter else None

    def _chamar_analista(self, caso: Caso, leitura: Leitura) -> None:
        """HG-19 / HG-16: cobrança em dobro ou pedido com conversa anterior vão ao analista."""
        if self.analista is None or not caso.order_id:
            return
        chamadas = []
        if "cobranca_duplicada" in (leitura.categoria, leitura.categoria_secundaria):
            chamadas.append(("cobranca_em_dobro", (caso.conversation_id,)))
        fonte = self.fonte_replay
        anteriores = (
            [
                c["conversation_id"]
                for c in fonte.conversas_do_pedido(caso.order_id)
                if c["conversation_id"] != caso.conversation_id
            ]
            if fonte and hasattr(fonte, "conversas_do_pedido")
            else []
        )
        if anteriores:
            chamadas.append(("contato_repetido", (caso.conversation_id, *anteriores)))
        for fator, conversas in chamadas:
            resultado = self.analista(
                fator=fator, order_ids=(caso.order_id,), conversation_ids=conversas
            )
            caso.analista.append(resultado)
            incidente = (resultado.get("incidente") or {}).get("incidente_id")
            texto = (
                f"{caso.conversation_id}: Gabriel chamou o agente analista: incidente {incidente} "
                f"({FATOR_ANALISTA.get(fator, fator)})."
                if incidente
                else f"{caso.conversation_id}: Gabriel chamou o agente analista "
                f"({FATOR_ANALISTA.get(fator, fator)}): sem padrão de causa comum confirmado na base."
            )
            self.postar_no_canal("aviso", None, texto, caso.conversation_id)

    def _status_do_rastreio(self, caso: Caso, pedido: Pedido) -> str:
        """HP-09: consulta o portal da transportadora antes de informar o status."""
        eventos = self.ferramentas.consultar_rastreio(
            pedido.order_id, conversation_id=caso.conversation_id, executado_por=EXECUTOR
        )
        bruto = (
            self.base.pedido_bruto(pedido.order_id) if hasattr(self.base, "pedido_bruto") else {}
        ) or {}
        ultimo = eventos[-1] if eventos else {}
        transportadora = ultimo.get("portal") or bruto.get("transportadora") or "transportadora"
        previsao = _data_br(bruto.get("data_prometida") or ultimo.get("previsao_entrega"))
        if ultimo:
            situacao = (
                f"Último status no portal da {transportadora}: {ultimo.get('status')}"
                + (f" ({ultimo['local']})" if ultimo.get("local") else "")
                + f" em {_data_br(ultimo.get('data_hora_evento'))}."
            )
        else:
            situacao = f"O portal da {transportadora} ainda não mostra eventos do pedido."
        return f"Pedido {pedido.order_id}: {situacao} Previsão de entrega: {previsao}."

    def _supervisor_do_atendente(self, caso: Caso) -> str | None:
        """EC-22: aprovação vai primeiro ao supervisor do atendente da conversa."""
        try:
            atendente = self._conversa(caso.conversation_id).get("atendente_id")
        except KeyError:
            return None
        for colaborador in self.equipe:
            if colaborador["colaborador_id"] == atendente:
                return colaborador.get("supervisor_id") or None
        return None

    def pedir_coleta_reversa(self, caso: Caso, acao: AcaoProposta) -> None:
        """EC-03 / Q18: reembolso por arrependimento depois do recebimento leva coleta reversa
        (sem ferramenta própria: sai por acionar_pessoa para a logística)."""
        self.executar(
            caso,
            self._proposta(
                caso,
                "acionar_pessoa",
                categoria=acao.categoria,
                motivo=f"Agendar coleta reversa do pedido {acao.order_id} (reembolso de "
                f"{_rs(acao.valor_rs)} por arrependimento).",
            ),
            area="logistica",
        )

    def _codigos_cupom(self) -> list[str]:
        """Códigos de `cupons.csv`, carregados uma vez, para o leitor achar o cupom citado."""
        if self._cupons is None:
            if hasattr(self.base, "codigos_cupom"):
                self._cupons = list(self.base.codigos_cupom())
            elif hasattr(self.base, "conexao"):
                with self._trava:
                    linhas = self.base.conexao.execute("SELECT codigo FROM cupons").fetchall()
                self._cupons = [linha[0] for linha in linhas]
            else:
                self._cupons = []
        return self._cupons

    def _texto_em_analise(self) -> str:
        prazo = self.politicas.get("reclamacao_suspeita.prazo_decisao_horas", "24")
        return (
            "Recebemos sua solicitação e ela está em análise pela nossa equipe. "
            f"Retornamos em até {prazo} horas."
        )

    def _ja_feita(self, caso: Caso, acao: AcaoProposta) -> dict | None:
        """HG-16: a mesma ação já foi executada neste pedido por outra conversa?"""
        fonte = self.fonte_replay
        if acao.ferramenta not in NAO_REPETIR or not acao.order_id or fonte is None:
            return None
        if not hasattr(fonte, "acoes_do_pedido"):
            return None
        for feita in fonte.acoes_do_pedido(acao.order_id, self.agora):
            if feita["acao"] == acao.ferramenta and feita.get("conversation_id") != (
                caso.conversation_id
            ):
                return feita
        return None

    def _informar_ja_feita(self, caso: Caso, acao: AcaoProposta, feita: dict) -> tuple[str, str]:
        quando = _data_br(feita.get("data_hora"))
        ref = feita.get("referencia_sistema") or feita.get("acao_id")
        self.postar_no_canal(
            "aviso",
            None,
            f"{caso.conversation_id}: Gabriel não repetiu o {nome_da_acao(acao.ferramenta)}: já foi "
            f"feito no pedido {acao.order_id} em {quando} (ref. {ref}), na conversa "
            f"{feita.get('conversation_id') or 'anterior'}.",
            caso.conversation_id,
            regra="HG-16 (contato repetido)",
        )
        return (
            "resolvida",
            f"Verificamos que já registramos {NOME_DA_ACAO[acao.ferramenta]} do seu pedido em "
            f"{quando} (protocolo {ref}). Seguimos acompanhando e avisamos por aqui.",
        )

    def _acoes_anteriores(self, order_id: str | None) -> list:
        if not order_id:
            return []
        anteriores = self.base.acoes_com_dinheiro(order_id)
        if self._em_replay and self.fonte_replay:
            # no replay, o que os sistemas fizeram depois da abertura ainda não aconteceu
            futuras = self.fonte_replay.acoes_futuras(order_id, self.agora)
            anteriores = [a for a in anteriores if a.acao_id not in futuras]
        return anteriores

    # ---------- replay (F3) ----------
    def casos_replay(self) -> list[dict]:
        if self.fonte_replay is None:
            return []
        with self._trava:
            saida = []
            for conversa in self.fonte_replay.conversas_com_anexo():
                cid = conversa["conversation_id"]
                pedido = (
                    self.base.pedido(conversa["order_id"]) if conversa.get("order_id") else None
                )
                anexos = self.base.anexos_da_conversa(cid)
                veredicto = None
                if pedido is not None:
                    veredicto = verificar(
                        pedido=pedido,
                        anexos=anexos,
                        anexos_mesmo_hash={
                            a.hash_perceptual: self.base.anexos_por_hash(a.hash_perceptual)
                            for a in anexos
                            if a.hash_perceptual
                        },
                        reenvios_anteriores_cliente=self.base.reenvios_do_cliente(
                            pedido.customer_id
                        ),
                    )
                caso = self.casos.get(cid)
                saida.append(
                    {
                        "conversation_id": cid,
                        "canal": conversa.get("canal"),
                        "marca": conversa.get("marca"),
                        "assunto": conversa.get("assunto"),
                        "tag_agente": conversa.get("tag_agente"),
                        "order_id": conversa.get("order_id"),
                        "data_abertura": conversa.get("data_abertura"),
                        "n_anexos": len(anexos),
                        "suspeita_prevista": bool(veredicto and veredicto.suspeita),
                        "sinais": [s.tipo.value for s in veredicto.sinais] if veredicto else [],
                        "estado": caso.estado if caso else "aberta",
                    }
                )
            return saida

    def processar_replay(self, cid: str) -> Caso:
        with self._trava:
            conversa = self.fonte_replay.conversa(cid) if self.fonte_replay else None
            if conversa is None:
                raise KeyError(cid)
            if cid in self.casos:
                return self.casos[cid]
        leitura = self._pre_ler([cid])[cid]  # fora da trava
        with self._trava:
            if cid in self.casos:
                return self.casos[cid]
            self._conversas_replay[cid] = conversa
            with self._no_momento_da_abertura(cid):
                return self._processar(cid, leitura)

    @contextmanager
    def _no_momento_da_abertura(self, cid: str):
        """Replay: "agora" do agente e das ferramentas = abertura da conversa histórica."""
        conversa = self._conversas_replay[cid]
        agora_original = self.agora
        abertura = datetime.fromisoformat(str(conversa["data_abertura"])).replace(tzinfo=FUSO)
        self.agora = abertura
        if hasattr(self.ferramentas, "agora"):
            self.ferramentas.agora = abertura
        self._em_replay = True
        try:
            yield
        finally:
            self._em_replay = False
            self.agora = agora_original
            if hasattr(self.ferramentas, "agora"):
                self.ferramentas.agora = agora_original

    def _contexto_da_aprovacao(self, aprovacao_id: str):
        aprovacao = self.aprovacoes.get(aprovacao_id)
        cid = aprovacao.acao.conversation_id if aprovacao else None
        if cid in self._conversas_replay:
            return self._no_momento_da_abertura(cid)
        return nullcontext()

    def processar(self, cid: str) -> Caso:
        with self._trava:
            if cid in self.casos:  # HG-12: caso já tratado não repete ações
                return self.casos[cid]
            self._conversa(cid)  # KeyError (404) antes de chamar o leitor
        leitura = self._pre_ler([cid])[cid]  # fora da trava
        with self._trava:
            if cid in self.casos:
                return self.casos[cid]
            return self._processar(cid, leitura)

    def _processar(self, cid: str, leitura=_NAO_LIDA) -> Caso:
        conversa = self._conversa(cid)
        caso = Caso(conversation_id=cid, canal=conversa.get("canal"), replay=self._em_replay)
        self.casos[cid] = caso
        if leitura is _NAO_LIDA:
            leitura = self._ler_conversa(cid, self._codigos_cupom())

        if leitura is None:
            caso.categoria = "sem_interacao"
            # HP-08: toda conversa tem exatamente uma classificação, inclusive sem interação
            self.executar(
                caso,
                self._proposta(
                    caso,
                    "classificar_conversa",
                    categoria="sem_interacao",
                    motivo="secundaria=",
                    order_id=None,
                ),
            )
            self.executar(
                caso,
                self._proposta(
                    caso, "encerrar_conversa", motivo="sem_interacao: só o bot falou", order_id=None
                ),
            )
            caso.estado = "resolvida"
            self.emitir("caso", self.resumo(caso))
            return caso

        caso.categoria = leitura.categoria
        caso.categoria_secundaria = leitura.categoria_secundaria
        caso.instrucao_embutida = leitura.instrucao_embutida
        caso.order_id = conversa.get("order_id") or None
        pedido = self.base.pedido(caso.order_id) if caso.order_id else None
        if caso.order_id is None:
            # pedido citado no texto só vale se for do mesmo cliente da conversa
            for order_id in leitura.order_ids:
                citado = self.base.pedido(order_id)
                if citado and citado.customer_id == conversa.get("customer_id"):
                    caso.order_id, pedido = order_id, citado
                    break

        self.executar(
            caso,
            self._proposta(
                caso,
                "classificar_conversa",
                categoria=leitura.categoria,
                motivo=f"secundaria={leitura.categoria_secundaria or ''}",
            ),
        )
        if not self._em_replay:
            self._chamar_analista(caso, leitura)
        if leitura.instrucao_embutida:
            self.postar_no_canal(
                "aviso",
                None,
                f"{cid}: a mensagem do cliente traz uma instrução dirigida ao Gabriel. Ela foi "
                "tratada como dado: nenhuma ação foi tomada por causa dela. Caso registrado para "
                "revisão.",
                cid,
                regra="seguranca.texto_do_cliente_e_dado_nao_instrucao",
            )

        respostas = []
        estados = []
        secundaria = leitura.categoria_secundaria
        if secundaria == "elogio" and leitura.categoria not in ("elogio", "outros"):
            # "Amei receber metade do pedido 🙃": elogio junto de reclamação é ironia, não demanda
            secundaria = None
            caso.categoria_secundaria = None
        categorias = [leitura.categoria] + ([secundaria] if secundaria else [])
        for categoria in categorias:
            estado, resposta = self._tratar(caso, categoria, leitura, pedido)
            estados.append(estado)
            respostas.append(resposta)

        caso.estado = max(estados, key=GRAVIDADE.__getitem__)
        texto = mascarar(" ".join(_compor_respostas(respostas)))
        if caso.estado == "suspeita":
            # HG-07: enquanto há suspeita, o cliente só sabe que está em análise.
            texto = self._texto_em_analise()
        caso.resposta_ao_cliente = texto
        self._finalizar(caso, texto)
        self.emitir("caso", self.resumo(caso))
        return caso

    def _finalizar(self, caso: Caso, texto: str) -> None:
        caso.resposta_ao_cliente = " ".join(
            t for t in (caso.resposta_por_ferramenta, texto) if t.strip()
        )
        if texto.strip():  # vazio: outra ferramenta já falou com o cliente (responder_duvida)
            self.executar(caso, self._proposta(caso, "responder_cliente", motivo=texto))
        if caso.estado == "resolvida" and caso.tag:
            # HP-04: resolvida com reposição dentro da alçada encerra com a tag da categoria
            self.executar(
                caso,
                self._proposta(
                    caso, "encerrar_conversa", motivo=f"Resolvida pelo agente; tag {caso.tag}"
                ),
            )

    # ---------- suspeitas (HG-04, HG-07, HG-08) ----------
    def _suspeita_pendente(self, order_id: str | None) -> Suspeita | None:
        if not order_id:
            return None
        return next(
            (
                s
                for s in self.suspeitas.values()
                if s.estado == "pendente" and s.acao.order_id == order_id
            ),
            None,
        )

    def suspeitas_pendentes(self) -> list[dict]:
        with self._trava:
            return [
                {
                    "suspeita_id": s.suspeita_id,
                    "conversation_id": s.acao.conversation_id,
                    "order_id": s.acao.order_id,
                    "acao_proposta": s.acao.ferramenta,
                    "valor_rs": s.acao.valor_rs,
                    "sinais": list(s.sinais),
                    "sinalizado_por": s.sinalizado_por,
                    "sinalizada_em": s.sinalizada_em,
                    "prazo": s.prazo,
                    "estado": s.estado,
                }
                for s in self.suspeitas.values()
                if s.estado == "pendente"
            ]

    def decidir_suspeita(
        self, suspeita_id: str, supervisor_id: str, decisao: str, justificativa: str
    ) -> Caso:
        with self._trava:
            suspeita = self.suspeitas[suspeita_id]  # KeyError -> 404
            cid = suspeita.acao.conversation_id
            contexto = (
                self._no_momento_da_abertura(cid)
                if cid in self._conversas_replay
                else nullcontext()
            )
            with contexto:
                return self._decidir_suspeita(suspeita, supervisor_id, decisao, justificativa)

    def _decidir_suspeita(
        self, suspeita: Suspeita, supervisor_id: str, decisao: str, justificativa: str
    ) -> Caso:
        if suspeita.estado != "pendente":
            raise AprovacaoRecusada(f"Suspeita {suspeita.suspeita_id} já está {suspeita.estado}.")
        if decisao not in ("procedente", "improcedente"):
            raise ValueError(f"decisao deve ser procedente ou improcedente: {decisao!r}")
        cargo = {c["colaborador_id"]: c.get("cargo") for c in self.equipe}.get(supervisor_id)
        if cargo != "supervisor":
            raise AprovacaoRecusada(
                f"{supervisor_id} não é supervisor: só o supervisor decide (reclamacao_suspeita."
                "quem_decide)."
            )
        if supervisor_id == suspeita.sinalizado_por:
            raise AprovacaoRecusada("Quem sinalizou a suspeita não a decide (HG-04).")
        acao = suspeita.acao
        caso = self.casos[acao.conversation_id]
        self.executar(
            caso,
            AcaoProposta(
                ferramenta="decidir_suspeita",
                papel=Papel.SUPERVISOR,
                executado_por=supervisor_id,
                conversation_id=acao.conversation_id,
                order_id=acao.order_id,
                motivo=justificativa,
            ),
            decisao=decisao,
        )
        suspeita.estado, suspeita.decidido_por, suspeita.justificativa = (
            decisao,
            supervisor_id,
            justificativa,
        )
        for mensagem in self.canal:
            if mensagem.get("suspeita_id") == suspeita.suspeita_id:
                mensagem["estado"] = decisao
        self.postar_no_canal(
            "aviso",
            supervisor_id,
            f"{caso.conversation_id}: suspeita {suspeita.suspeita_id} decidida como {decisao} por "
            f"{supervisor_id}. Justificativa: {justificativa}",
            caso.conversation_id,
            suspeita_id=suspeita.suspeita_id,
        )
        if decisao == "procedente":
            # libera a ação da política: executa ou pede aprovação, com o acumulado do pedido
            pedido = self.base.pedido(acao.order_id) if acao.order_id else None
            caso.estado, texto = self._decidir_e_agir(caso, acao, pedido, None)
        else:
            caso.estado = "resolvida"
            texto = (
                "Analisamos sua solicitação com as informações do pedido e, desta vez, não "
                "conseguimos seguir com o reenvio, a troca ou o estorno. Se quiser, envie novas "
                "fotos ou mais detalhes por aqui que olhamos de novo."
            )
        self._finalizar(caso, mascarar(texto))
        if decisao == "improcedente":
            self.executar(
                caso,
                self._proposta(
                    caso, "encerrar_conversa", motivo="Reclamação analisada: improcedente."
                ),
            )
        self.emitir("caso", self.resumo(caso))
        return caso

    # ---------- uma demanda ----------
    def _tratar(
        self, caso: Caso, categoria: str, leitura: Leitura, pedido: Pedido | None
    ) -> tuple[str, str]:
        cid = caso.conversation_id
        prazo = self.politicas.get("categorias.reacao_adversa.prazo_registro_horas", "24")
        if categoria == "reacao_adversa":
            acao = self._proposta(
                caso, "orientar_suspensao_uso", categoria=categoria, motivo=_texto_suspensao(prazo)
            )
            return self._decidir_e_agir(caso, acao, pedido, None)

        if pedido is None and categoria in COM_DINHEIRO_POSSIVEL | {"rastreio", "atraso"}:
            # Q20: sem pedido identificado, nada com dinheiro; pede o número ao cliente.
            self._escalar(
                caso,
                f"{rotulo_categoria(categoria)} sem pedido identificado: nada com dinheiro foi "
                "feito e o Gabriel pediu o número do pedido ao cliente.",
                categoria,
                regra="Q20 (ação com dinheiro sem pedido identificado)",
            )
            return "escalada", TEXTO_PEDIR_NUMERO

        if categoria in COM_EVIDENCIA:
            anexos = self.base.anexos_da_conversa(cid)
            if not anexos and self.politicas.get(f"categorias.{categoria}.exige_foto") == "True":
                self.executar(
                    caso,
                    self._proposta(
                        caso,
                        "solicitar_foto",
                        categoria=categoria,
                        motivo=TEXTO_FOTO,
                    ),
                )
                return "aguardando_cliente", TEXTO_FOTO
            mesmo_hash = {
                a.hash_perceptual: self.base.anexos_por_hash(a.hash_perceptual)
                for a in anexos
                if a.hash_perceptual
            }
            veredicto = verificar(
                pedido=pedido,
                anexos=anexos,
                anexos_mesmo_hash=mesmo_hash,
                reenvios_anteriores_cliente=self.base.reenvios_do_cliente(pedido.customer_id),
                agora=self.agora,
            )
            caso.veredicto = veredicto
            divergente = any(
                s.tipo is TipoSinal.PERSONALIZACAO_DIVERGENTE for s in veredicto.sinais
            )
            if divergente and categoria != "erro_personalizacao":
                # EC-18: a foto mostra outra personalização: nova foto antes de decidir.
                self.executar(
                    caso,
                    self._proposta(
                        caso,
                        "solicitar_foto",
                        categoria=categoria,
                        motivo=TEXTO_NOVA_FOTO,
                    ),
                )
                return "aguardando_cliente", TEXTO_NOVA_FOTO
            ferramenta = (
                "reimprimir_personalizacao"
                if categoria == "erro_personalizacao"
                else "reenviar_produto"
            )
            item = _item_reclamado(pedido, categoria, leitura.texto_mascarado)
            acao = self._proposta(
                caso,
                ferramenta,
                categoria=categoria,
                valor_rs=item.valor_total if item else pedido.valor,
                motivo=(
                    f"{categoria}: {item.descricao} sku={item.sku}"
                    if item
                    else f"{categoria}: pedido inteiro"
                ),
            )
            return self._decidir_e_agir(caso, acao, pedido, veredicto)

        if categoria == "cobranca_duplicada" and pedido is not None:
            # regra de dados 4: confere o gateway; reembolsa só a cobrança duplicada em aberto
            transacoes = self.ferramentas.verificar_pagamento(
                pedido.order_id, conversation_id=cid, executado_por=EXECUTOR
            )
            duplicado = valor_duplicado(transacoes)
            if duplicado <= 0:
                self._escalar(
                    caso,
                    f"Cliente relata cobrança em dobro no pedido {pedido.order_id}, mas o gateway "
                    f"mostra {len(transacoes)} transação(ões) sem duplicidade em aberto: "
                    "conferência humana.",
                    categoria,
                )
                return (
                    "escalada",
                    "Conferimos os pagamentos do seu pedido e uma pessoa da nossa equipe vai "
                    "te responder por aqui com o detalhe.",
                )
            acao = self._proposta(
                caso,
                "reembolsar",
                categoria=categoria,
                valor_rs=duplicado,
                motivo="cobrança duplicada confirmada em pagamentos_gateway",
            )
            return self._decidir_e_agir(caso, acao, pedido, None)

        if categoria == "arrependimento" and pedido is not None:
            if pedido.data_separacao is None:
                acao = self._proposta(
                    caso, "cancelar_pedido", categoria="arrependimento_cancelamento"
                )
            else:
                acao = self._proposta(
                    caso,
                    "reembolsar",
                    categoria="arrependimento_cancelamento",
                    valor_rs=pedido.valor,
                    motivo="arrependimento (CDC, art. 49)",
                )
            return self._decidir_e_agir(caso, acao, pedido, None)

        if categoria == "rastreio" and pedido is not None:
            acao = self._proposta(
                caso,
                "informar_status",
                categoria="onde_esta_pedido",
                motivo=self._status_do_rastreio(caso, pedido),
            )
            return self._decidir_e_agir(caso, acao, pedido, None)

        if categoria == "atraso" and pedido is not None:
            acao = self._proposta(
                caso,
                "abrir_chamado_transportadora",
                categoria="atraso_entrega",
                motivo="atraso relatado pelo cliente",
            )
            return self._decidir_e_agir(caso, acao, pedido, None)

        if categoria == "duvida_produto" and hasattr(self.ferramentas, "responder_duvida"):
            vendidos = [i for i in pedido.itens if i.tipo_item != "brinde"] if pedido else []
            sku = vendidos[0].sku if len(vendidos) == 1 else None
            resposta = self.ferramentas.responder_duvida(cid, sku=sku, executado_por=EXECUTOR)
            if not resposta.get("precisa_pessoa"):
                caso.resposta_por_ferramenta = mascarar(resposta.get("resposta") or "")
                return "resolvida", ""  # responder_duvida já enviou a resposta ao cliente
            return self._escalar(
                caso,
                f"Gabriel não achou a resposta na ficha do produto ({resposta.get('motivo')}); uma "
                "pessoa do time responde.",
                categoria,
            )

        codigo = getattr(leitura, "codigo_cupom", None) or _codigo_cupom(leitura.texto_mascarado)
        if categoria == "cupom_promocao" and codigo and hasattr(self.ferramentas, "validar_cupom"):
            cupom = self.ferramentas.validar_cupom(
                codigo, order_id=caso.order_id, conversation_id=cid, executado_por=EXECUTOR
            )
            detalhe = cupom.get("detalhe") or cupom.get("motivo") or ""
            if cupom.get("valido"):
                self._escalar(
                    caso,
                    f"Cupom {codigo} válido mas não aplicado no pedido {caso.order_id}: {detalhe}",
                    categoria,
                    area="comercial",
                )
                return (
                    "escalada",
                    f"Conferimos o cupom {codigo}: {detalhe} Encaminhamos para a nossa equipe "
                    "comercial analisar o desconto do seu pedido, e ela te responde por aqui.",
                )
            return "resolvida", f"Conferimos o cupom {codigo}: {detalhe}"

        return self._escalar(
            caso,
            f"{rotulo_categoria(categoria)}: o Gabriel não tem regra automática para esta demanda"
            + (
                ""
                if pedido or categoria in ("outros", "duvida_produto", "cupom_promocao")
                else " (pedido não identificado)"
            )
            + "; uma pessoa do time responde.",
            categoria,
        )

    def _decidir_e_agir(
        self,
        caso: Caso,
        acao: AcaoProposta,
        pedido: Pedido | None,
        veredicto: VeredictoEvidencia | None,
    ) -> tuple[str, str]:
        feita = self._ja_feita(caso, acao)
        if feita is not None:
            return self._informar_ja_feita(caso, acao, feita)
        pendente = self._suspeita_pendente(acao.order_id)
        if pendente is not None and acao.ferramenta in COM_DINHEIRO:
            # HG-07: reenvio, troca e reembolso do pedido ficam suspensos até a decisão
            self.postar_no_canal(
                "aviso",
                None,
                f"{caso.conversation_id}: Gabriel não fez o {nome_da_acao(acao.ferramenta)} de "
                f"{_rs(acao.valor_rs)}: o pedido {acao.order_id} tem a suspeita "
                f"{pendente.suspeita_id} esperando a decisão do supervisor.",
                caso.conversation_id,
                regra="reclamacao_suspeita.quem_decide",
            )
            return "suspeita", self._texto_em_analise()
        if caso.instrucao_embutida and acao.ferramenta in COM_DINHEIRO:
            # HG-09: texto que tenta mandar no agente tira o caso do automático
            self._escalar(
                caso,
                f"Gabriel não fez o {nome_da_acao(acao.ferramenta)} de {_rs(acao.valor_rs)} sozinho: a "
                "mensagem traz uma instrução dirigida ao Gabriel. Conferência humana.",
                acao.categoria,
            )
            return "escalada", "Uma pessoa da nossa equipe já está cuidando do seu caso."
        decisao = decidir(
            acao,
            pedido=pedido,
            acoes_anteriores=self._acoes_anteriores(acao.order_id),
            politicas=self.politicas,
            equipe=self.equipe,
            agora=self.agora,
            veredicto=veredicto,
            supervisor_preferido=self._supervisor_do_atendente(caso),
        )
        caso.decisoes.append(decisao)
        caso.decisao = caso.decisao or decisao
        cid = caso.conversation_id
        r = decisao.resultado

        if r is Resultado.EXECUTAR:
            registro = self.executar(caso, acao)
            if "coleta_reversa" in decisao.acoes_obrigatorias:
                self.pedir_coleta_reversa(caso, acao)
            self.postar_no_canal(
                "aviso",
                None,
                f"{cid}: Gabriel {acao_feita(acao.ferramenta)}"
                + (f" de {_rs(acao.valor_rs)}" if acao.ferramenta in COM_DINHEIRO else "")
                + f" (ref. {registro.referencia_sistema}).",
                cid,
                regra=decisao.regra,
            )
            texto = _texto_executado(acao, registro)
            if acao.ferramenta in REPOSICAO and pedido is not None:
                bruto = (
                    self.base.pedido_bruto(pedido.order_id)
                    if hasattr(self.base, "pedido_bruto")
                    else None
                )
                prazo = prazo_de_entrega(pedido, bruto or {}, self.politicas, self.agora)
                if prazo:
                    texto += f" Previsão de entrega: {prazo.strftime('%d/%m/%Y')}."
                caso.tag = (
                    self.politicas.get(f"categorias.{acao.categoria}.tag_equivalente") or None
                )
            return "resolvida", texto

        if r is Resultado.PEDIR_APROVACAO:
            registro = self.executar(
                caso,
                self._proposta(
                    caso,
                    "solicitar_aprovacao",
                    categoria=acao.categoria,
                    valor_rs=acao.valor_rs,
                    motivo=f"{acao.ferramenta}: {decisao.motivo}",
                ),
                acao_pendente=acao,
            )
            aprovacao_id = registro.referencia_sistema
            self.aprovacoes[aprovacao_id] = Aprovacao(
                aprovacao_id=aprovacao_id,
                acao=acao,
                solicitado_por=EXECUTOR,
                aprovador_sugerido=decisao.aprovador_sugerido,
            )
            caso.aprovacao_ids.append(aprovacao_id)
            evidencias = (
                "; ".join(s.descricao for s in veredicto.sinais)
                if veredicto and veredicto.sinais
                else (veredicto.justificativa if veredicto else "sem evidência a conferir")
            )
            self.postar_no_canal(
                "aprovacao",
                decisao.aprovador_sugerido,
                f"{cid}: Gabriel pediu aprovação para {nome_da_acao(acao.ferramenta)} de "
                f"{_rs(acao.valor_rs)} no pedido {acao.order_id} ({_por_que_aprovacao(decisao)})."
                + (f" Evidências: {evidencias}" if veredicto else ""),
                cid,
                regra=decisao.regra,
                aprovacao_id=aprovacao_id,
                estado="pendente",
                solicitado_por=EXECUTOR,
            )
            fila_ate = decisao.detalhes.get("fila_ate")
            return (
                "aguardando_aprovacao",
                "Conferimos seu pedido e a solução já foi encaminhada para aprovação. "
                + (
                    f"A supervisão volta a atender a partir das {fila_ate}, e avisamos por aqui "
                    "assim que for liberada."
                    if fila_ate
                    else "Avisamos por aqui assim que for liberada."
                ),
            )

        if r is Resultado.SINALIZAR_SUSPEITA:
            registro = self.executar(
                caso,
                self._proposta(
                    caso,
                    "sinalizar_suspeita",
                    categoria=acao.categoria,
                    valor_rs=0.0,
                    motivo=veredicto.justificativa if veredicto else decisao.motivo,
                ),
            )
            sinais = "; ".join(s.descricao for s in veredicto.sinais) if veredicto else ""
            horas = float(self.politicas.get("reclamacao_suspeita.prazo_decisao_horas", "24"))
            suspeita = Suspeita(
                suspeita_id=registro.referencia_sistema,
                acao=acao,
                sinalizado_por=EXECUTOR,
                sinalizada_em=self.agora,
                prazo=self.agora + timedelta(hours=horas),
                sinais=tuple(s.tipo.value for s in veredicto.sinais) if veredicto else (),
            )
            self.suspeitas[suspeita.suspeita_id] = suspeita
            self.postar_no_canal(
                "suspeita",
                decisao.aprovador_sugerido,
                f"{cid}: Gabriel segurou o {nome_da_acao(acao.ferramenta)} de {_rs(acao.valor_rs)} no "
                f"pedido {acao.order_id} até a decisão do supervisor. Evidências: {sinais} "
                f"Prazo de decisão: {suspeita.prazo.strftime('%d/%m/%Y %H:%M')}.",
                cid,
                regra=decisao.regra,
                estado="pendente",
                suspeita_id=suspeita.suspeita_id,
                prazo=suspeita.prazo.isoformat(),
                solicitado_por=EXECUTOR,
            )
            return "suspeita", self._texto_em_analise()

        if r is Resultado.ESCALAR:
            if acao.ferramenta == "orientar_suspensao_uso":
                return self._reacao_adversa(caso, acao, decisao, pedido)
            self._escalar(
                caso,
                decisao.motivo,
                acao.categoria,
                para=decisao.aprovador_sugerido,
                regra=decisao.regra,
            )
            return "escalada", "Uma pessoa da nossa equipe já está cuidando do seu caso."

        if r is Resultado.NEGAR:
            regra_publica = self.politicas.get(f"categorias.{acao.categoria}.regra", "")
            texto = (
                "Conferimos seu pedido e, pela nossa política, não conseguimos seguir com essa "
                "solicitação." + (f" {regra_publica}" if regra_publica else "")
            )
            self.executar(
                caso,
                self._proposta(caso, "negar_por_politica", categoria=acao.categoria, motivo=texto),
            )
            self.postar_no_canal(
                "aviso",
                None,
                f"{cid}: Gabriel não fez o {nome_da_acao(acao.ferramenta)}, pela política. "
                f"{decisao.motivo}",
                cid,
                regra=decisao.regra,
            )
            return "resolvida", texto

        # BLOQUEAR
        self._escalar(
            caso,
            f"Gabriel não fez o {nome_da_acao(acao.ferramenta)}: bloqueado pela política. "
            f"{decisao.motivo}",
            acao.categoria,
            regra=decisao.regra,
        )
        return "escalada", "Uma pessoa da nossa equipe já está cuidando do seu caso."

    def _escalar(
        self,
        caso: Caso,
        motivo: str,
        categoria: str | None,
        para: str | None = None,
        area: str = "supervisão",
        regra: str | None = None,
    ) -> tuple[str, str]:
        self.executar(
            caso,
            self._proposta(caso, "acionar_pessoa", categoria=categoria, motivo=motivo),
            area=area,
        )
        self.postar_no_canal(
            "escalacao",
            para,
            f"{caso.conversation_id}: {motivo}",
            caso.conversation_id,
            regra=regra,
        )
        return (
            "escalada",
            "Recebemos sua mensagem e uma pessoa da nossa equipe vai te responder por aqui.",
        )

    def _reacao_adversa(
        self, caso: Caso, acao: AcaoProposta, decisao: Decisao, pedido: Pedido | None
    ) -> tuple[str, str]:
        """HG-06: orienta suspender o uso na primeira resposta, aciona a qualidade e pede ao
        supervisor do turno o registrar_cosmetovigilancia (prazo de politicas.csv)."""
        self.executar(caso, acao)
        prazo = decisao.detalhes.get("prazo_registro_horas") or self.politicas.get(
            "categorias.reacao_adversa.prazo_registro_horas", "24"
        )
        produtos = ", ".join(f"{i.sku} {i.descricao}" for i in pedido.itens) if pedido else "?"
        lote = (pedido.lote_produto if pedido else None) or "não informado"
        fotos = ", ".join(a.anexo_id for a in self.base.anexos_da_conversa(caso.conversation_id))
        relato = mascarar(
            " ".join(
                m["texto"]
                for m in self.base.mensagens(caso.conversation_id)
                if m.get("autor") == "cliente" and m.get("texto")
            )
        )
        contexto = (
            f"Reação adversa no pedido {caso.order_id or 'não identificado'}. Produto: {produtos}. "
            f"Lote: {lote}. Descrição do cliente: {relato}. Fotos: {fotos or 'nenhuma'}."
        )
        self.executar(
            caso,
            self._proposta(caso, "acionar_pessoa", categoria=acao.categoria, motivo=contexto),
            area="qualidade",
        )
        self.postar_no_canal(
            "escalacao",
            decisao.aprovador_sugerido,
            f"{caso.conversation_id}: {contexto} Gabriel já orientou o cliente a suspender o uso. "
            f"Pendente para o supervisor do turno: registro de cosmetovigilância em até {prazo} h.",
            caso.conversation_id,
            regra=decisao.regra,
        )
        return "escalada", _texto_suspensao(prazo)

    # ---------- aprovações ----------
    def aprovar(self, aprovacao_id: str, supervisor_id: str, comentario: str = "") -> Caso:
        with self._trava, self._contexto_da_aprovacao(aprovacao_id):
            return aprovar(self, aprovacao_id, supervisor_id, comentario)

    def rejeitar(self, aprovacao_id: str, supervisor_id: str, justificativa: str) -> Caso:
        with self._trava, self._contexto_da_aprovacao(aprovacao_id):
            return rejeitar(self, aprovacao_id, supervisor_id, justificativa)

    # ---------- leitura para a API ----------
    def resumo(self, caso: Caso) -> dict:
        return {
            "conversation_id": caso.conversation_id,
            "estado": caso.estado,
            "categoria": caso.categoria,
            "categoria_secundaria": caso.categoria_secundaria,
            "order_id": caso.order_id,
            "instrucao_embutida": caso.instrucao_embutida,
            "aprovacao_ids": list(caso.aprovacao_ids),
            "replay": caso.replay,
        }

    def acoes(self) -> list[dict]:
        with self._trava:
            if hasattr(self.ferramentas, "acoes_registradas"):
                registros = self.ferramentas.acoes_registradas()
            else:
                registros = [r for c in self.casos.values() for r in c.acoes]
            replay = {c.conversation_id for c in self.casos.values() if c.replay}
            return [{**_registro_json(r), "replay": r.conversation_id in replay} for r in registros]

    def detalhe(self, cid: str) -> dict:
        with self._trava:
            return self._detalhe(cid)

    def _detalhe(self, cid: str) -> dict:
        conversa = self._conversa(cid)
        caso = self.casos.get(cid)
        pedido = self.base.pedido(conversa["order_id"]) if conversa.get("order_id") else None
        if pedido is None and caso and caso.order_id:
            pedido = self.base.pedido(caso.order_id)
        return {
            "conversa": {**conversa, "estado": caso.estado if caso else "aberta"},
            "mensagens": [
                {
                    "autor": m.get("autor"),
                    "timestamp": str(m.get("timestamp", "")),
                    "texto": mascarar(m.get("texto") or ""),
                }
                for m in self.base.mensagens(cid)
            ],
            "pedido": pedido,
            "anexos": self.base.anexos_da_conversa(cid),
            "veredicto": caso.veredicto if caso else None,
            "decisao": caso.decisao if caso else None,
            "acoes": [_registro_json(r) for r in caso.acoes] if caso else [],
            "resposta_ao_cliente": caso.resposta_ao_cliente if caso else "",
            "caso": self.resumo(caso) if caso else None,
        }


# Frases genéricas de encaminhamento: entram uma vez só e somem se outra resposta já encaminha.
ENCAMINHAMENTOS = {
    "Recebemos sua mensagem e uma pessoa da nossa equipe vai te responder por aqui.",
    "Uma pessoa da nossa equipe já está cuidando do seu caso.",
}


def _compor_respostas(respostas: list[str]) -> list[str]:
    especificas = list(dict.fromkeys(r for r in respostas if r and r not in ENCAMINHAMENTOS))
    genericas = [r for r in respostas if r in ENCAMINHAMENTOS]
    ja_encaminha = any("por aqui" in r for r in especificas)
    return especificas + ([] if ja_encaminha or not genericas else genericas[:1])


_CUPOM = re.compile(r"\b(?:cupom|c[oó]digo)\s+([A-Z][A-Z0-9]{3,})\b", re.IGNORECASE)


def _codigo_cupom(texto: str) -> str | None:
    achado = _CUPOM.search(texto)
    return achado.group(1).upper() if achado else None


def _dias_uteis_depois(inicio: date, n: int, feriados: set[date]) -> date:
    dia = inicio
    contados = 0
    while contados < n:
        dia += timedelta(days=1)
        if dia.weekday() < 5 and dia not in feriados:
            contados += 1
    return dia


def prazo_de_entrega(pedido: Pedido, bruto: dict, politicas: dict[str, str], agora: datetime):
    """HP-04: prazo = agora + dias úteis de preparo + SLA da transportadora (dias úteis),
    contando a partir do primeiro dia útil depois (politicas.csv, prazos_entrega.*).
    Sem transportadora ou região conhecida, devolve None (não inventa prazo)."""
    regiao = politicas.get(f"prazos_entrega.regiao_por_uf.{bruto.get('uf')}")
    sla = politicas.get(
        f"prazos_entrega.sla_transportadora_dias_uteis.{bruto.get('transportadora')}.{regiao}"
    )
    if not regiao or not sla:
        return None
    if pedido.marca != "Gocase":
        chave = "gobeaute"
    elif any(i.texto_personalizacao for i in pedido.itens):
        chave = "gocase_personalizado"
    else:
        chave = "gocase_sem_personalizacao"
    preparo = int(politicas.get(f"prazos_entrega.preparo_dias_uteis.{chave}", "1"))
    feriados = {
        date.fromisoformat(d.strip())
        for d in politicas.get("prazos_entrega.feriados_nacionais", "").split(";")
        if d.strip()
    }
    return _dias_uteis_depois(agora.date(), preparo + int(sla), feriados)


def _texto_suspensao(prazo: str) -> str:
    return (
        "Sentimos muito. Por segurança, suspenda o uso do produto agora e, se os sintomas "
        "continuarem, procure atendimento médico. Uma pessoa da nossa equipe já está "
        f"cuidando do seu caso e fala com você em até {prazo} horas."
    )


def _data_br(valor: object) -> str:
    texto = str(valor or "")
    try:
        return datetime.fromisoformat(texto).strftime("%d/%m/%Y")
    except ValueError:
        return texto or "data não registrada"


def _por_que_aprovacao(decisao: Decisao) -> str:
    """'acima do limite de R$ 100,00 do atendente', com o acumulado do pedido quando houver."""
    limite = decisao.detalhes.get("limite_rs")
    if limite is None:
        return "acima da alçada do atendente"
    acumulado = decisao.detalhes.get("acumulado_rs") or 0
    if acumulado:
        return (
            f"somando {_rs(acumulado)} já feitos no pedido, passa do limite de {_rs(limite)} "
            "do atendente"
        )
    return f"acima do limite de {_rs(limite)} do atendente"


def valor_duplicado(transacoes: list[dict]) -> float:
    """Valor cobrado a mais: cobranças efetivas além da primeira, menos o já estornado."""
    efetivas = [t for t in transacoes if t.get("status") in ESTADOS_EFETIVOS]
    return round(
        sum(
            float(t.get("valor") or 0) - float(t.get("valor_estornado") or 0) for t in efetivas[1:]
        ),
        2,
    )


def _item_reclamado(pedido: Pedido, categoria: str, texto: str) -> Item | None:
    """Q6: item citado pelo cliente; brinde quando o cliente fala de brinde."""
    normal = _sem_acento(texto)
    if categoria == "item_faltante" and ("brinde" in normal or "necessaire" in normal):
        brindes = [i for i in pedido.itens if i.tipo_item == "brinde"]
        if brindes:
            return brindes[0]
    if categoria == "erro_personalizacao":
        personalizados = [i for i in pedido.itens if i.texto_personalizacao]
        if personalizados:
            return personalizados[0]
    vendidos = [i for i in pedido.itens if i.tipo_item != "brinde"]
    for item in vendidos:
        palavras = [p for p in _sem_acento(item.descricao).split() if len(p) > 3]
        if any(p in normal for p in palavras):
            return item
    if len(vendidos) == 1:
        return vendidos[0]
    return None


def _texto_executado(acao: AcaoProposta, registro: RegistroAcao) -> str:
    ref = registro.referencia_sistema
    textos = {
        "reenviar_produto": f"Já registramos o reenvio sem custo (protocolo {ref}). "
        "Você recebe o novo código de rastreio por e-mail.",
        "reimprimir_personalizacao": f"Já mandamos produzir de novo a sua peça, sem custo "
        f"(protocolo {ref}).",
        "reembolsar": f"Já registramos o estorno de {_rs(acao.valor_rs)} (protocolo {ref}).",
        "cancelar_pedido": f"Seu pedido foi cancelado e o estorno é integral (protocolo {ref}).",
        "informar_status": f"{acao.motivo} (protocolo {ref})",
        "abrir_chamado_transportadora": f"Abrimos um chamado com a transportadora para "
        f"acelerar a entrega (protocolo {ref}). Avisamos assim que houver retorno.",
    }
    return textos.get(acao.ferramenta, f"Sua solicitação foi registrada (protocolo {ref}).")


def _registro_json(r: RegistroAcao) -> dict:
    return {
        "acao_id": r.acao_id,
        "conversation_id": r.conversation_id,
        "order_id": r.order_id,
        "data_hora": r.data_hora.isoformat() if r.data_hora else None,
        "sistema": r.sistema,
        "acao": r.acao,
        "valor_rs": r.valor_rs,
        "executado_por": r.executado_por,
        "aprovado_por": r.aprovado_por,
        "referencia_sistema": r.referencia_sistema,
    }


class ReplaySQL:
    """Fonte do replay sobre a base do W1 (`historico_conversas`, `anexos_conversas`)."""

    def __init__(self, base):
        self.base = base

    def _linhas(self, sql: str, *parametros) -> list[dict]:
        with self.base.trava:
            return [dict(r) for r in self.base.conexao.execute(sql, parametros).fetchall()]

    def conversas_com_anexo(self) -> list[dict]:
        return self._linhas(
            "SELECT * FROM historico_conversas WHERE conversation_id IN "
            "(SELECT DISTINCT conversation_id FROM anexos_conversas) "
            "ORDER BY data_abertura, conversation_id"
        )

    def conversa(self, cid: str) -> dict | None:
        linhas = self._linhas("SELECT * FROM historico_conversas WHERE conversation_id = ?", cid)
        return linhas[0] if linhas else None

    def acoes_futuras(self, order_id: str, agora: datetime) -> set[str]:
        limite = agora.strftime("%Y-%m-%d %H:%M:%S")
        linhas = self._linhas(
            "SELECT acao_id FROM acoes_executadas_sistemas WHERE order_id = ? AND data_hora >= ?",
            order_id,
            limite,
        )
        return {linha["acao_id"] for linha in linhas}

    def acoes_do_pedido(self, order_id: str, agora: datetime) -> list[dict]:
        """Ações já registradas no pedido (sistemas + agente) antes de `agora`."""
        limite = agora.strftime("%Y-%m-%d %H:%M:%S")
        colunas = "acao_id, order_id, conversation_id, acao, data_hora, referencia_sistema"
        return self._linhas(
            f"SELECT {colunas} FROM acoes_executadas_sistemas WHERE order_id = ? "
            f"AND data_hora < ? UNION ALL SELECT {colunas} FROM acoes_agente "
            "WHERE order_id = ? ORDER BY data_hora",
            order_id,
            limite,
            order_id,
        )

    def conversas_do_pedido(self, order_id: str) -> list[dict]:
        return self._linhas("SELECT * FROM historico_conversas WHERE order_id = ?", order_id)


class AnalistaReal:
    """Adaptador para `atendimento.analista.chamar_analista` com um único Analista por processo
    (o máximo de avisos por dia vale para o processo inteiro)."""

    def __init__(self, base, ferramentas):
        self.base = base
        self.ferramentas = ferramentas
        self._analista = None

    def obter(self):
        from atendimento.analista import Analista

        if self._analista is None:
            self._analista = Analista(self.base, self.ferramentas)
        return self._analista

    def __call__(self, *, fator: str, order_ids, conversation_ids) -> dict:
        from atendimento.analista import chamar_analista

        self.obter()
        resultado = chamar_analista(
            self.base,
            self.ferramentas,
            fator=fator,
            order_ids=list(order_ids),
            conversation_ids=list(conversation_ids),
            analista=self._analista,
        )
        return {
            "fator": fator,
            "incidente": resultado.incidente,
            "notificacoes": len(resultado.notificacoes),
            "sem_consentimento": list(resultado.sem_consentimento),
            "aviso_ao_time": resultado.aviso_ao_time.referencia_sistema
            if resultado.aviso_ao_time
            else None,
        }
