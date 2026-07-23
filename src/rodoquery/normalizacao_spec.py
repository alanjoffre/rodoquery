"""Normalização determinística de spec — o conserto CERTO para a falha de ranking (Fase 9).

A Fase 8 mostrou e a Fase 9 confirmou: a única falha de ranking do sistema é **mecânica**. O
modelo, treinado em SQL, serializa a direção da ordenação como um token separado —
`["revenue", "DESC"]` — em vez do prefixo do MetricFlow — `["-revenue"]`. A métrica está certa e a
intenção de direção está certa; só a sintaxe diverge, e a spec não compila.

Consertar isto reescrevendo o prompt foi testado (sistema_v2) e **fracassou como estratégia**: no
holdout v3 o prompt mais prescritivo empatou (McNemar p=0,89), porque a prosa extra sobre seleção
de métrica introduziu 18 erros de métrica que anularam o ganho de ranking. A lição: uma falha
**mecânica** se conserta em **código**, não com mais texto que o modelo tem de interpretar.

Este normalizador só age quando o `order_by` tem exatamente a forma `[campo, "DESC"|"ASC"]`. Fora
disso devolve a spec intacta. Como não toca em `metrics`, `group_by` nem `where`, é impossível ele
regredir a seleção de métrica — que era o custo do prompt reescrito.

Ele é motivado inteiramente pela Fase 8 (v2); o v3 é o holdout que o mede pela primeira vez.
"""
from __future__ import annotations

from dataclasses import replace

from rodoquery.gold import Spec

_DIRECOES = ("DESC", "ASC")


def normalizar_ordem(order_by: list[str]) -> list[str]:
    """`["revenue", "DESC"]` → `["-revenue"]`; `["revenue", "ASC"]` → `["revenue"]`. Idempotente."""
    if (len(order_by) == 2 and isinstance(order_by[1], str)
            and order_by[1].strip().upper() in _DIRECOES):
        campo = str(order_by[0]).lstrip("-")
        return [f"-{campo}"] if order_by[1].strip().upper() == "DESC" else [campo]
    return order_by


def normalizar_spec(spec: Spec) -> Spec:
    """Aplica `normalizar_ordem` ao `order_by` da spec, preservando todo o resto."""
    novo = normalizar_ordem(spec.order_by)
    return spec if novo == spec.order_by else replace(spec, order_by=novo)
