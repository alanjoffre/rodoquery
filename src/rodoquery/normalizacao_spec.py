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

import re
from dataclasses import replace

from rodoquery.gold import Spec

_DIRECOES = ("DESC", "ASC")
# Captura a dimensão de um filtro de IGUALDADE: {{ Dimension('X') }} = 'V'
# Só igualdade: em `!=` ou `IN (...)` com vários valores o agrupamento continua informativo.
_EQ = re.compile(r"Dimension\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}\s*=\s*['\"]")


def normalizar_ordem(order_by: list[str]) -> list[str]:
    """`["revenue", "DESC"]` → `["-revenue"]`; `["revenue", "ASC"]` → `["revenue"]`. Idempotente."""
    if (len(order_by) == 2 and isinstance(order_by[1], str)
            and order_by[1].strip().upper() in _DIRECOES):
        campo = str(order_by[0]).lstrip("-")
        return [f"-{campo}"] if order_by[1].strip().upper() == "DESC" else [campo]
    return order_by


def dimensoes_filtradas_por_igualdade(where: str | None) -> set[str]:
    """Dimensões presas a UM valor por `=` no where."""
    return set(_EQ.findall(where or ""))


def normalizar_group_by(group_by: list[str], where: str | None) -> list[str]:
    """Remove do `group_by` toda dimensão já presa a um único valor por igualdade no `where`.

    Motivação (Fase 10): este é o modo de falha DOMINANTE do sistema — 22 dos 29 erros de
    estrutura. Quando a pergunta pede filtro E agrupamento ("receita das transações estornadas em
    cada dia"), o modelo põe a dimensão filtrada TAMBÉM no group_by.

    Por que é seguro corrigir em código: agrupar por uma coluna restrita a um único valor produz
    exatamente um grupo — acrescenta uma coluna constante e nenhuma informação. Nas 26 predições do
    TEST-v3 com esse padrão, o gold NUNCA agrupa pela dimensão filtrada (0 quebras possíveis).

    Ressalva honesta: quando a pergunta é do tipo "entre as transações estornadas, por status", as
    duas leituras se defendem. Esses itens são AMBÍGUOS e foram removidos do v3 pelos anotadores
    cegos antes de qualquer medição — não é a regra que os resolve, é o golden que não deve tê-los.
    """
    presas = dimensoes_filtradas_por_igualdade(where)
    if not presas:
        return group_by
    limpo = [d for d in group_by if d not in presas]
    # nunca esvaziar o group_by por completo: sem dimensão nenhuma a pergunta muda de sentido
    return limpo if limpo else group_by


def normalizar_spec(spec: Spec) -> Spec:
    """Aplica as normalizações determinísticas, preservando todo o resto da spec."""
    ordem = normalizar_ordem(spec.order_by)
    gb = normalizar_group_by(spec.group_by, spec.where)
    if ordem == spec.order_by and gb == spec.group_by:
        return spec
    return replace(spec, order_by=ordem, group_by=gb)
