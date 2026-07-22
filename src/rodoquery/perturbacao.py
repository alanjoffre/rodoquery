"""Fase 7b — perturbação de schema por ALIAS OPACO.

**A pergunta:** o Tier-A acerta porque *entende* a descrição da métrica, ou porque casa a palavra
"receita" com o identificador `revenue`? Se for casamento lexical, o sistema é frágil a qualquer
catálogo cujos nomes não sejam em inglês transparente — o que é a regra em warehouses reais.

**Como testar sem tocar na fundação:** o dbt/MetricFlow continua com os nomes reais. Trocamos só a
*apresentação*: o prompt mostra `m01`, `d03`… com as MESMAS descrições, o modelo responde em alias,
e traduzimos de volta antes de compilar. O gabarito não muda.

Se o EX segurar → a competência está na descrição (semântica). Se cair → era pistas lexicais.
"""
from __future__ import annotations

import json
import re

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.gold import Spec
from rodoquery.sistema import _parse_spec

# alias opaco -> nome real (o modelo só vê a esquerda; nós traduzimos)
ALIAS_METRICA = {
    "m01": "transactions", "m02": "revenue_cents", "m03": "revenue",
    "m04": "revenue_leakage_cents", "m05": "revenue_leakage_brl",
    "m06": "suspect_transactions", "m07": "suspect_rate",
}
ALIAS_DIM = {
    "t_dia": "metric_time__day", "t_sem": "metric_time__week", "t_mes": "metric_time__month",
    "d01": "transaction__status", "d02": "transaction__payment_method",
    "d03": "transaction__audit_flag", "d04": "transaction__plaza", "d05": "transaction__vehicle",
}
_REAL_METRICA = {v: k for k, v in ALIAS_METRICA.items()}
_REAL_DIM = {v: k for k, v in ALIAS_DIM.items()}

# MESMAS descrições do catálogo real — só os identificadores foram ofuscados.
CATALOGO_OPACO = """MÉTRICAS (use o código exato; só existem estas 7):
- m01 — contagem de transações.
- m02 — receita em centavos inteiros.
- m03 — receita/faturamento em BRL.
- m04 — vazamento/perda em centavos.
- m05 — vazamento/perda/prejuízo de receita em BRL.
- m06 — contagem de transações suspeitas.
- m07 — taxa/proporção de transações suspeitas (suspeitas/total).
(NÃO existe métrica de custo, lucro, margem, média/ticket, satisfação, tempo, velocidade, previsão.)

TOKENS de group_by (use exatamente estes códigos):
- tempo:       t_dia (dia), t_sem (semana), t_mes (mês)
- categóricos: d01 (status), d02 (método de pagamento), d03 (marcação de auditoria)
- entidades:   d04 (praça), d05 (veículo)

VALORES p/ filtro `where`:
- d01: COMPLETED, FAILED, REVERSED
- d02: AUTOMATIC_TAG, CARD, CASH
- d03: OK, COBRANCA_EM_FALHA, TARIFA_DIVERGENTE, POSSIVEL_DUPLICIDADE, VALOR_INVALIDO
Sintaxe de where: {{ Dimension('d01') }} = 'COMPLETED'"""

PROMPT_OPACO = """Você mapeia uma pergunta de negócio para uma consulta a um Semantic Layer.

{catalogo}

Responda com UM objeto JSON (e nada mais) com as chaves:
  {{"metrics": [...], "group_by": [...], "where": <string ou null>, "order_by": [...], "limit": <int ou null>, "ordenado": <bool>}}
Regras:
- Use SOMENTE os códigos listados acima. Não invente.
- NÃO agrupe por nada que a pergunta não peça explicitamente.
- Filtro por um valor específico é `where`, NÃO group_by.
- "por dia/semana/mês" → group_by de tempo correspondente.
- Use ordenado=true e limit SÓ se a pergunta pedir ranking explícito (o maior, top N).
- Se NENHUMA métrica acima responde a pergunta (custo, lucro, média/ticket, placa/PII, clima,
  acidentes, satisfação, previsão, etc.), responda EXATAMENTE a palavra: ABSTENHO

Pergunta: {pergunta}
JSON:"""


def _traduzir(spec: Spec) -> Spec | None:
    """alias → nome real. Devolve None se o modelo inventou um código (falha de mapeamento)."""
    metrics = []
    for m in spec.metrics:
        real = ALIAS_METRICA.get(m.strip())
        if real is None:
            return None
        metrics.append(real)
    grupos = []
    for g in spec.group_by:
        real = ALIAS_DIM.get(g.strip())
        if real is None:
            return None
        grupos.append(real)
    onde = spec.where
    if onde:
        for alias, real in ALIAS_DIM.items():          # troca dentro do Dimension('...')
            onde = re.sub(rf"Dimension\(\s*'{alias}'\s*\)", f"Dimension('{real}')", onde)
    ordem = [ALIAS_DIM.get(o, ALIAS_METRICA.get(o, o)) for o in spec.order_by]
    return Spec(metrics=metrics, group_by=grupos, where=onde, order_by=ordem,
                limit=spec.limit, ordenado=spec.ordenado)


def tier_a_opaco(pergunta: str, modelo: str | None = None,
                 temperatura: float | None = None) -> Predicao:
    """Tier-A com o catálogo ofuscado: mesmas descrições, identificadores sem pista lexical."""
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    resp, tel = _chamar_ollama(
        PROMPT_OPACO.format(catalogo=CATALOGO_OPACO, pergunta=pergunta), modelo, temp)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400], **tel)
    bruta = _parse_spec(resp)
    if bruta is None:
        return Predicao.abster(modelo=modelo, raw=resp[:400], falha_parse=True, **tel)
    traduzida = _traduzir(bruta)
    if traduzida is None:
        return Predicao.abster(modelo=modelo, raw=resp[:400], alias_invalido=True,
                               spec_bruta=json.dumps(bruta.metrics + bruta.group_by), **tel)
    return Predicao.com_spec(traduzida, modelo=modelo, raw=resp[:400], **tel)
