"""Tier-A com CATÁLOGO LIMPO (Fase 10) — uma métrica por conceito.

**O diagnóstico.** Olhando o semantic model da fundação, as métricas de centavos e as de BRL não
são conceitos diferentes — são a MESMA grandeza em unidades diferentes:

    revenue:             type: derived   expr: revenue_cents / 100.0
    revenue_leakage_brl: type: derived   expr: revenue_leakage_cents / 100.0

As de centavos são o bloco interno (`type: simple` sobre a measure); as de BRL são a apresentação.
Expor as duas a uma interface de linguagem natural é **erro de governança**: "qual a receita?"
passa a ter duas respostas certas, e o modelo é punido por uma ambiguidade que o catálogo criou.
Isso explica boa parte dos erros de "seleção de métrica" que a Fase 8 e a 9 apontaram como gargalo.

**O conserto** é de desenho, não de modelo: o catálogo de usuário expõe 5 métricas (uma por
conceito), com a unidade declarada. As de centavos continuam existindo no semantic layer como base
de cálculo — só deixam de ser oferecidas como escolha.

**Isolamento da variável.** O PROMPT é importado byte a byte de `sistema.py`. A ÚNICA diferença
para o sistema congelado é a lista de métricas. Sem isso a medição não diria nada — foi a lição da
Fase 9, onde mexer no catálogo e na prosa ao mesmo tempo produziu um empate ininterpretável.
"""
from __future__ import annotations

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.sistema import PROMPT, _parse_spec

# Mesmo formato do CATALOGO original; só saem `revenue_cents` e `revenue_leakage_cents`.
CATALOGO_LIMPO = """MÉTRICAS (use o `nome` exato; só existem estas 5):
- transactions           — contagem de transações.
- revenue                — receita/faturamento, em BRL.
- revenue_leakage_brl    — vazamento/perda/prejuízo de receita, em BRL.
- suspect_transactions   — contagem de transações suspeitas.
- suspect_rate           — taxa/proporção de transações suspeitas (suspeitas/total).
(NÃO existe métrica de custo, lucro, margem, média/ticket, satisfação, tempo, velocidade, previsão.)

TOKENS de group_by (use exatamente estes):
- tempo:       metric_time__day, metric_time__week, metric_time__month
- categóricos: transaction__status, transaction__payment_method, transaction__audit_flag
- entidades:   transaction__plaza (praça), transaction__vehicle (veículo)

VALORES p/ filtro `where`:
- status: COMPLETED, FAILED, REVERSED
- payment_method: AUTOMATIC_TAG, CARD, CASH
- audit_flag: OK, COBRANCA_EM_FALHA, TARIFA_DIVERGENTE, POSSIVEL_DUPLICIDADE, VALOR_INVALIDO
Sintaxe de where: {{ Dimension('transaction__status') }} = 'COMPLETED'"""


def tier_a_limpo(pergunta: str, modelo: str | None = None,
                 temperatura: float | None = None) -> Predicao:
    """Idêntico ao `tier_a` da Fase 4, exceto pela lista de métricas do catálogo."""
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    resp, tel = _chamar_ollama(PROMPT.format(catalogo=CATALOGO_LIMPO, pergunta=pergunta),
                               modelo, temp)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400], **tel)
    spec = _parse_spec(resp)
    if spec is None:
        return Predicao.abster(modelo=modelo, raw=resp[:400], falha_parse=True, **tel)
    return Predicao.com_spec(spec, modelo=modelo, raw=resp[:400], **tel)
