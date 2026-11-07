"""Redator: o Claude reescreve a resposta da política em tom de WhatsApp, sem mudar os fatos.

A trava (guardrail) é determinística: todo protocolo, valor, data e pedido da resposta oficial
precisa estar na versão nova, e nada desse tipo pode aparecer do nada. Se falhar, vai a oficial.
"""

from types import SimpleNamespace

from atendimento.agente.redator import RedatorClaude, eh_conversa_social, reescrita_segura

BASE = (
    "Pedido GBH473217: Último status no portal da Expressa Já: em transferencia em 25/10/2026. "
    "Previsão de entrega: 29/10/2026. (protocolo MSG-000001)"
)


class ClienteFalso:
    def __init__(self, texto=None, erro=None):
        self.texto, self.erro, self.chamadas = texto, erro, []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.chamadas.append(kw)
        if self.erro:
            raise self.erro
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.texto)])


def test_HG_reescrita_que_mantem_todos_os_fatos_passa():
    nova = (
        "Oi, Bruna! Seu pedido GBH473217 está em transferência desde 25/10/2026 e a previsão "
        "é 29/10/2026. Qualquer coisa, o protocolo é MSG-000001."
    )
    assert reescrita_segura(BASE, nova) == nova


def test_HG_reescrita_que_perde_o_pedido_ou_a_data_volta_para_a_oficial():
    sem_pedido = "Oi, Bruna! Seu pedido chega em 29/10/2026, desde 25/10/2026. MSG-000001"
    sem_data = "Oi, Bruna! O pedido GBH473217 está em transferência desde 25/10/2026."
    assert reescrita_segura(BASE, sem_pedido) == BASE
    assert reescrita_segura(BASE, sem_data) == BASE


def test_HG_reescrita_que_perde_protocolo_de_acao_volta_para_a_oficial():
    oficial = "Já registramos o estorno de R$ 72,17 (protocolo EST000186)."
    assert reescrita_segura(oficial, "Pronto, Bruna! Estornamos R$ 72,17.") == oficial


def test_HG_referencia_interna_da_mensagem_pode_ficar_de_fora():
    # MSG-xxxxxx é o registro da própria mensagem no sistema, não um protocolo para o cliente
    nova = "Oi, Bruna! O pedido GBH473217 está em transferência (25/10/2026), previsão 29/10/2026."
    assert reescrita_segura(BASE, nova) == nova


def test_HG_reescrita_que_inventa_valor_volta_para_a_oficial():
    nova = BASE + " Vamos te dar R$ 50,00 de desconto."
    assert reescrita_segura(BASE, nova) == BASE


def test_HG_redator_usa_o_claude_e_cai_na_oficial_se_a_api_falhar():
    boa = (
        "Oi, Bruna! O pedido GBH473217 está em transferência (25/10/2026), previsão "
        "29/10/2026. Protocolo MSG-000001."
    )
    assert RedatorClaude(ClienteFalso(texto=boa))("cadê?", BASE, "Bruna") == boa
    assert RedatorClaude(ClienteFalso(erro=RuntimeError("fora")))("cadê?", BASE, "Bruna") == BASE


def test_HG_11_redator_nao_manda_cpf_para_a_api():
    cliente = ClienteFalso(texto=BASE)
    RedatorClaude(cliente)("meu cpf é 123.456.789-12, cadê?", BASE, "Bruna")
    assert "123.456.789" not in str(cliente.chamadas[0]["messages"])


def test_conversa_social_nao_abre_caso():
    for texto in ("oi", "Olá!", "bom dia", "boa tarde, tudo bem?", "obrigado", "valeu!!"):
        assert eh_conversa_social(texto), texto
    for texto in ("oi, cadê meu pedido?", "quero cancelar", "chegou quebrado"):
        assert not eh_conversa_social(texto), texto
