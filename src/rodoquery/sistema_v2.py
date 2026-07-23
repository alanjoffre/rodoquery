"""RodoQuery Tier-A **v2** (Fase 9) — o mesmo sistema, com o catálogo e o prompt corrigidos.

**Por que um módulo novo em vez de editar `sistema.py`.** O `sistema.py` é o SUT congelado que
produziu as Fases 4 a 8. Editá-lo tornaria aqueles resultados irreproduzíveis. Aqui só muda o
TEXTO do catálogo/prompt; o pipeline (parse → Spec → MetricFlow) é o mesmo, importado de lá.

**O que a Fase 8 mostrou e este arquivo conserta** — três modos de falha, todos por *omissão* no
texto, nenhum por limitação do modelo:

1. `ranking` 17,2%: o prompt mandava usar `ordenado`/`limit` mas **nunca documentou a sintaxe de
   ordenação**. O modelo caía no hábito de SQL (`["revenue","DESC"]`) e a spec não compilava.
2. `coalesce_nulo` 14,8%: a regra "filtro é `where`, não `group_by`" **não compunha** — quando a
   pergunta pedia filtro *e* agrupamento, o modelo agrupava pelos dois.
3. abstenção 55,6%: o catálogo dizia o que cada métrica É, nunca o que ela **não é**, nem que não
   existem operadores derivados. O modelo trocava a métrica pedida por uma vizinha plausível.

**Disciplina anti-overfitting.** Eu vi as falhas do TEST-v2 antes de escrever isto, então havia o
risco real de enumerar os casos que falharam. As regras abaixo são **gerais** (sintaxe de ordem,
composição de filtro+agrupamento, inexistência de operadores derivados) e nenhuma cita uma pergunta
específica do conjunto. A medição vale no TEST-v3, que não existia quando este texto foi escrito.
"""
from __future__ import annotations

import json

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.sistema import _JSON, _parse_spec

CATALOGO_V2 = """MÉTRICAS (use o `nome` exato; só existem estas 7):
- transactions           — contagem de transações.
- revenue_cents          — receita em centavos inteiros.
- revenue                — receita/faturamento em BRL.
- revenue_leakage_cents  — vazamento/perda em centavos.
- revenue_leakage_brl    — vazamento/perda/prejuízo de receita em BRL.
- suspect_transactions   — contagem de transações suspeitas.
- suspect_rate           — taxa/proporção de transações suspeitas (suspeitas/total).

Esta lista é COMPLETA e cada métrica significa EXATAMENTE o que está escrito.
- NÃO existe métrica de custo, lucro, margem, ticket, satisfação, tempo, velocidade, previsão.
- NÃO existem OPERADORES sobre as métricas: média, mediana, máximo/mínimo, contagem de valores
  distintos, acumulado, crescimento ou variação entre períodos, participação no total, desvio
  padrão. Não dá para derivar nada a partir das métricas acima — só é possível o que está listado.
- Uma métrica cujo nome SOA parecido com o que a pergunta pede não é substituta dela. Se a
  definição acima não descreve exatamente o que foi pedido, nenhuma métrica serve.

TOKENS de group_by (use exatamente estes):
- tempo:       metric_time__day, metric_time__week, metric_time__month
- categóricos: transaction__status, transaction__payment_method, transaction__audit_flag
- entidades:   transaction__plaza (praça), transaction__vehicle (veículo)

VALORES p/ filtro `where`:
- status: COMPLETED, FAILED, REVERSED
- payment_method: AUTOMATIC_TAG, CARD, CASH
- audit_flag: OK, COBRANCA_EM_FALHA, TARIFA_DIVERGENTE, POSSIVEL_DUPLICIDADE, VALOR_INVALIDO
Sintaxe de where: {{ Dimension('transaction__status') }} = 'COMPLETED'

Sintaxe de order_by: um token de group_by (ex.: "metric_time__day") ou um nome de métrica.
Prefixe com '-' para ordem DECRESCENTE: "-revenue" é do maior para o menor; "revenue" é do menor
para o maior. NUNCA escreva "DESC" nem "ASC" — não existem aqui."""

PROMPT_V2 = """Você mapeia uma pergunta de negócio para uma consulta ao dbt Semantic Layer (MetricFlow).

{catalogo}

Responda com UM objeto JSON (e nada mais) com as chaves:
  {{"metrics": [...], "group_by": [...], "where": <string ou null>, "order_by": [...], "limit": <int ou null>, "ordenado": <bool>}}

COMO ABSTER (leia antes das outras regras): quando o catálogo não puder responder, devolva o mesmo
JSON com "metrics": [] — lista vazia. É a resposta CERTA sempre que: nenhuma métrica descreve o que
foi pedido; a pergunta exige um operador inexistente (média, acumulado, variação, distintos,
máximo...); ou pede agrupamento por algo fora dos tokens. Responder com a métrica mais parecida é
PIOR do que abster — devolve um número errado com aparência de certo.
Não descarte parte da pergunta para fazê-la caber: se QUALQUER pedaço do pedido (um recorte, um
agrupamento, um operador, uma comparação) não puder ser expresso com o catálogo, abstenha — em vez
de responder só a parte que cabe.

Regras:
- Use SOMENTE nomes de métricas e tokens listados acima. Não invente.
- `metrics` só aceita NOMES DE MÉTRICA. Um token de group_by nunca vai em `metrics`.
- NÃO agrupe por nada que a pergunta não peça explicitamente. "receita por método de pagamento"
  → group_by = [transaction__payment_method], e MAIS NADA.
- Filtro por um valor específico é `where`, NÃO group_by: "transações pagas com cartão" →
  where payment_method='CARD' e group_by = [].
- Uma pergunta pode pedir filtro E agrupamento ao mesmo tempo; eles vão em campos DIFERENTES.
  "receita das transações que falharam em cada dia" → where status='FAILED' E
  group_by = [metric_time__day]. A dimensão usada no `where` NÃO entra no group_by — nem quando a
  pergunta também pede um agrupamento por outra coisa.
- "por dia/semana/mês" → group_by de tempo (order_by opcional, mesmo token).
- Ranking ("as 3 praças com maior X", "top 5", "os 3 com menor X"): group_by = [a dimensão que
  está sendo ranqueada], order_by = ["-<metrica>"] para MAIOR ou ["<metrica>"] para MENOR,
  limit = N, ordenado = true. Esquecer o '-' inverte a resposta; esquecer o group_by faz a
  pergunta perder o sentido.
- Fora de ranking: order_by sem métrica, ordenado=false e limit=null. "por mês", "por método",
  "por praça" NÃO são ranking.

Pergunta: {pergunta}
JSON:"""


def _metrics_vazio(texto: str) -> bool:
    """A resposta é um JSON bem-formado com `metrics` vazio? (= abstenção deliberada)"""
    m = _JSON.search(texto)
    if not m:
        return False
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return False
    return isinstance(d, dict) and "metrics" in d and not d.get("metrics")


def tier_a_v2(pergunta: str, modelo: str | None = None,
              temperatura: float | None = None) -> Predicao:
    """Idêntico ao `tier_a` da Fase 4, exceto pelo texto do catálogo/prompt."""
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    resp, tel = _chamar_ollama(PROMPT_V2.format(catalogo=CATALOGO_V2, pergunta=pergunta),
                               modelo, temp)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400], via="palavra", **tel)
    spec = _parse_spec(resp)
    if spec is None:
        # `_parse_spec` devolve None tanto para "JSON com metrics vazio" (abstenção deliberada,
        # que é o contrato documentado no prompt) quanto para "não veio JSON nenhum" (falha real).
        # Separar os dois importa: um é o sistema funcionando, o outro é o modelo se perdendo.
        deliberada = _metrics_vazio(resp)
        return Predicao.abster(modelo=modelo, raw=resp[:400],
                               via="metrics_vazio" if deliberada else "falha_parse",
                               falha_parse=not deliberada, **tel)
    return Predicao.com_spec(spec, modelo=modelo, raw=resp[:400], **tel)
