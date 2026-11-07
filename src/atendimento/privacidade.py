"""Máscara única de dados pessoais (HG-11, AGENTS.md regra 6).

CPF, cartão, telefone e e-mail nunca saem sem máscara em resposta, log, canal ou API.
Formatos: CPF `***.***.***-12`, cartão `**** **** **** 1234`, telefone `(**) *****-1234`,
e-mail `m***@dominio.com`. Onze dígitos sem pontuação são ambíguos (CPF ou celular) e
recebem a máscara de CPF, a que expõe menos dígitos.

Nome do cliente (`nomes=`): o nome completo vira `Primeiro S.` (primeiro nome + inicial do
último sobrenome). Vale para o nome inteiro, para o primeiro nome com o último sobrenome e
para qualquer trecho de dois ou mais nomes que termine no último sobrenome, sem diferenciar
caixa nem acento. O primeiro nome sozinho fica: sem sobrenome, não identifica o cliente.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Ordem importa: cartão (mais longo) → CPF pontuado → telefone → CPF sem pontuação → e-mail.
_CARTAO = re.compile(r"\b(?:\d[ .-]?){12,15}(\d{4})\b")
_CPF_PONTUADO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-(\d{2})\b")
_CPF_CORRIDO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}(\d{2})\b")
_TELEFONE = re.compile(r"(?:\+?55\s?)?(?:\(\d{2}\)|\b\d{2})\s?(?:9\d{4}|[2-5]\d{3})[-\s]?(\d{4})\b")
_EMAIL = re.compile(r"\b([\w+-])[\w.+-]*@([\w-]+(?:\.[\w-]+)+)")


def mascarar(texto: str, *, nomes: Iterable[str | None] = ()) -> str:
    """Mascara CPF, cartão, telefone e e-mail e, se informados, os nomes completos."""
    for nome in nomes:
        texto = _mascarar_nome(texto, nome)
    texto = _CARTAO.sub(r"**** **** **** \1", texto)
    texto = _CPF_PONTUADO.sub(r"***.***.***-\1", texto)
    texto = _CPF_CORRIDO.sub(r"***.***.***-\1", texto)
    texto = _TELEFONE.sub(r"(**) *****-\1", texto)
    return _EMAIL.sub(r"\1***@\2", texto)


def _digitos(valor: str) -> str:
    return "".join(c for c in valor if c.isdigit())


def mascarar_cpf(cpf: str) -> str:
    return "***.***.***-" + _digitos(cpf)[-2:]


def mascarar_telefone(telefone: str) -> str:
    return "(**) *****-" + _digitos(telefone)[-4:]


def mascarar_email(email: str) -> str:
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:1]}***@{dominio}"


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _padrao_da_palavra(palavra: str) -> str:
    """Casa a palavra com ou sem acento (cada letra aceita as variantes acentuadas)."""
    partes = []
    for letra in _sem_acento(palavra).lower():
        if letra.isalpha():
            variantes = {letra, letra.upper()} | _ACENTUADAS.get(letra, set())
            partes.append("[" + "".join(sorted(re.escape(v) for v in variantes)) + "]")
        else:
            partes.append(re.escape(letra))
    return "".join(partes)


_ACENTUADAS = {
    base: {c for c in todas + todas.upper()}
    for base, todas in {
        "a": "áàâãä",
        "e": "éèêë",
        "i": "íìîï",
        "o": "óòôõö",
        "u": "úùûü",
        "c": "ç",
        "n": "ñ",
    }.items()
}


def _mascarar_nome(texto: str, nome: str | None) -> str:
    partes = (nome or "").split()
    if len(partes) < 2:
        return texto
    trocar_por = f"{partes[0]} {_sem_acento(partes[-1])[:1].upper()}."
    trechos = {(partes[0], partes[-1])} | {
        tuple(partes[i:]) for i in range(len(partes) - 1)
    }  # primeiro + último, e todo trecho de 2+ nomes que termina no último sobrenome
    alternativas = sorted(
        (r"\s+".join(_padrao_da_palavra(p) for p in trecho) for trecho in trechos),
        key=len,
        reverse=True,
    )
    padrao = re.compile(r"(?<!\w)(?:" + "|".join(alternativas) + r")(?!\w)")
    return padrao.sub(trocar_por, texto)
