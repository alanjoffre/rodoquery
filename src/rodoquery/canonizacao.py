"""Canonicalização de result-set — o oráculo do Execution Accuracy (Fase 0).

Comparar "o resultado da query predita bate com o da gold?" parece trivial e não é. Este módulo
fixa as decisões, **explicitamente e de forma conservadora** (na dúvida, mais estrito → o número
de acurácia sai menor, nunca inflado):

- **Nome/alias de coluna: IGNORADO** — `sum(x) as receita` vs `as total` é a mesma resposta.
- **Ordem das COLUNAS: importa** — faz parte da forma da resposta (relaxar exigiria permutar).
- **Ordem das LINHAS: ignorada** (multiset), salvo `ordenado=True` (ranking/top-N: a ordem
  É a resposta).
- **Dinheiro em centavos (int): exato** — a plataforma guarda centavos inteiros.
- **Float/Decimal (BRL, ratios):** arredondado a `casas` (6) — mata ruído de ponto flutuante.
- **NULL vs 0: DIFERENTES por padrão.** O Semantic Layer coalesce para 0; o SQL cru pode
  devolver NULL. Tratar como iguais **mascararia erro** — a flag `nulo_igual_zero` existe,
  mas o default é estrito.

`hash_resultado` dá uma forma estável para versionar o resultado esperado do golden set.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

Linha = Sequence[object]
Canon = tuple[tuple[object, ...], ...]

_SENTINELA_NULO = "\x00NULL"


def _norm_valor(v: object, casas: int, nulo_igual_zero: bool) -> object:
    if v is None:
        return 0 if nulo_igual_zero else _SENTINELA_NULO
    if isinstance(v, bool):          # antes de int: bool é subclasse de int
        return bool(v)
    if isinstance(v, int):           # centavos e contagens: exato
        return v
    if isinstance(v, (float, Decimal)):
        f = float(v)
        if f != f:                   # NaN
            return "\x00NAN"
        arred = round(f, casas)
        # 2.0 e 2 devem casar (SUM pode vir int ou float conforme o motor)
        return int(arred) if arred == int(arred) else arred
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).hex()
    return str(v)


def canonicalizar(
    linhas: Sequence[Linha],
    ordenado: bool = False,
    casas: int = 6,
    nulo_igual_zero: bool = False,
) -> Canon:
    """Forma canônica e hashável de um result-set.

    `ordenado=True` preserva a ordem das linhas (use quando a pergunta pede ranking/top-N).
    """
    norm = tuple(
        tuple(_norm_valor(v, casas, nulo_igual_zero) for v in linha) for linha in linhas
    )
    if ordenado:
        return norm
    # multiset estável: ordena por repr (ordem total mesmo com tipos mistos)
    return tuple(sorted(norm, key=repr))


def resultados_batem(
    pred: Sequence[Linha],
    gold: Sequence[Linha],
    ordenado: bool = False,
    casas: int = 6,
    nulo_igual_zero: bool = False,
) -> bool:
    """Execution match: os result-sets são equivalentes sob as regras acima?"""
    a = canonicalizar(pred, ordenado, casas, nulo_igual_zero)
    b = canonicalizar(gold, ordenado, casas, nulo_igual_zero)
    return a == b


def hash_resultado(
    linhas: Sequence[Linha],
    ordenado: bool = False,
    casas: int = 6,
    nulo_igual_zero: bool = False,
) -> str:
    """Hash estável do result-set canônico — para versionar o esperado do golden set."""
    canon = canonicalizar(linhas, ordenado, casas, nulo_igual_zero)
    return hashlib.sha256(repr(canon).encode("utf-8")).hexdigest()[:16]
