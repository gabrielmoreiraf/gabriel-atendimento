"""Máscara única de dados pessoais (HG-11, AGENTS.md regra 6).

CPF, cartão, telefone e e-mail nunca saem sem máscara em resposta, log, canal ou API.
Formatos: CPF `***.***.***-12`, cartão `**** **** **** 1234`, telefone `(**) *****-1234`,
e-mail `m***@dominio.com`. Onze dígitos sem pontuação são ambíguos (CPF ou celular) e
recebem a máscara de CPF, a que expõe menos dígitos.
"""

from __future__ import annotations

import re

# Ordem importa: cartão (mais longo) → CPF pontuado → telefone → CPF sem pontuação → e-mail.
_CARTAO = re.compile(r"\b(?:\d[ .-]?){12,15}(\d{4})\b")
_CPF_PONTUADO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-(\d{2})\b")
_CPF_CORRIDO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}(\d{2})\b")
_TELEFONE = re.compile(r"(?:\+?55\s?)?(?:\(\d{2}\)|\b\d{2})\s?(?:9\d{4}|[2-5]\d{3})[-\s]?(\d{4})\b")
_EMAIL = re.compile(r"\b([\w+-])[\w.+-]*@([\w-]+(?:\.[\w-]+)+)")


def mascarar(texto: str) -> str:
    """Mascara CPF, cartão, telefone e e-mail num texto livre."""
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
