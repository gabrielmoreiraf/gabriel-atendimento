"""HG-12 no Vercel: cada instância começa de uma cópia limpa da base pré-gerada.

No Vercel não há `docs/` (ADR-002) e só `/tmp` aceita escrita. Com
`ATENDIMENTO_BASE_PRONTA`, a subida copia a base pronta para `ATENDIMENTO_DB` em vez
de gerar a partir dos CSVs, e cada subida começa limpa, como no modo local.
"""

from pathlib import Path

from atendimento.api.app import agente_real
from atendimento.dados.carga import carregar
from atendimento.dados.repositorio import Base

FIXTURES = Path(__file__).parent / "fixtures" / "dados"


def test_HG_12_subida_copia_a_base_pronta_sem_ler_docs(tmp_path, monkeypatch):
    pronta = tmp_path / "pronta.db"
    carregar(FIXTURES, pronta)
    trabalho = tmp_path / "tmp" / "atendimento.db"
    monkeypatch.setenv("ATENDIMENTO_BASE_PRONTA", str(pronta))
    monkeypatch.setenv("ATENDIMENTO_DB", str(trabalho))
    monkeypatch.setenv("ATENDIMENTO_DOCS", str(tmp_path / "nao_existe"))
    monkeypatch.setenv("ATENDIMENTO_LLM", "0")

    agente = agente_real()

    assert trabalho.exists()
    assert agente.base.fila()


def test_HG_12_cada_subida_comeca_da_base_pronta_limpa(tmp_path, monkeypatch):
    pronta = tmp_path / "pronta.db"
    carregar(FIXTURES, pronta)
    trabalho = tmp_path / "atendimento.db"
    monkeypatch.setenv("ATENDIMENTO_BASE_PRONTA", str(pronta))
    monkeypatch.setenv("ATENDIMENTO_DB", str(trabalho))
    monkeypatch.setenv("ATENDIMENTO_DOCS", str(tmp_path / "nao_existe"))
    monkeypatch.setenv("ATENDIMENTO_LLM", "0")

    agente_real()
    Base(trabalho).banco.executar("DELETE FROM fila_aberta")
    agente = agente_real()

    assert agente.base.fila(), "a segunda subida deve voltar à base pronta"
