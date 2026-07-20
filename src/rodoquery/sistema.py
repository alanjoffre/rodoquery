"""RodoQuery Tier-A — o sistema semântico-primeiro (Fase 4).

**A ideia da tese, em código.** O LLM NUNCA escreve SQL. Ele recebe a pergunta + o **catálogo
governado** (7 métricas, dimensões, valores) e devolve uma **spec** `{metrics, group_by, where,
order_by, ...}` — ou ABSTÉM se nenhuma métrica do catálogo responde. O MetricFlow compila o SQL
correto a partir da spec (join/filtro/grão certos, por construção).

Comparação justa (isola a variável): é o **mesmo SUT** (`qwen2.5-coder:7b`) do baseline `sql_cru`.
Mesma pergunta, mesmo modelo — só muda a **interface**: spec governada vs SQL cru. Se Tier-A ganha,
o mérito é do **Semantic Layer**, não de um modelo melhor.

Segurança de graça: como o LLM só escolhe de um vocabulário fechado (nunca emite SQL), não há
superfície de injeção — o caminho Tier-A dispensa o sandbox (que existe para o SQL cru do Tier-B).
"""
from __future__ import annotations

import json
import re

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.gold import Spec

# Vocabulário do catálogo governado — o MESMO que um anotador teria (não é a resposta de cada item).
CATALOGO = """MÉTRICAS (use o `nome` exato; só existem estas 7):
- transactions           — contagem de transações.
- revenue_cents          — receita em centavos inteiros.
- revenue                — receita/faturamento em BRL.
- revenue_leakage_cents  — vazamento/perda em centavos.
- revenue_leakage_brl    — vazamento/perda/prejuízo de receita em BRL.
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

PROMPT = """Você mapeia uma pergunta de negócio para uma consulta ao dbt Semantic Layer (MetricFlow).

{catalogo}

Responda com UM objeto JSON (e nada mais) com as chaves:
  {{"metrics": [...], "group_by": [...], "where": <string ou null>, "order_by": [...], "limit": <int ou null>, "ordenado": <bool>}}
Regras:
- Use SOMENTE nomes de métricas e tokens listados acima. Não invente.
- NÃO agrupe por nada que a pergunta não peça explicitamente. "receita por método de pagamento"
  → group_by = [transaction__payment_method], e MAIS NADA.
- Filtro por um valor específico é `where`, NÃO group_by: "transações pagas com cartão" →
  where payment_method='CARD' e group_by = [].
- "por dia/semana/mês" → group_by de tempo (order_by opcional, mesmo token).
- Use ordenado=true e limit SÓ se a pergunta pedir ranking explícito (o maior, que mais, top N).
  "por mês", "por método" NÃO são ranking → ordenado=false, limit=null.
- Se NENHUMA métrica acima responde a pergunta (custo, lucro, média/ticket, placa/PII, clima,
  acidentes, satisfação, previsão, etc.), responda EXATAMENTE a palavra: ABSTENHO

Pergunta: {pergunta}
JSON:"""

_JSON = re.compile(r"\{.*\}", re.DOTALL)
_CHAVES = {"metrics", "group_by", "where", "order_by", "limit", "ordenado"}


def _parse_spec(texto: str) -> Spec | None:
    """Extrai o 1º objeto JSON e o converte em Spec. None se não der (→ falha de mapeamento)."""
    m = _JSON.search(texto)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or not d.get("metrics"):
        return None
    return Spec(
        metrics=list(d.get("metrics") or []),
        group_by=list(d.get("group_by") or []),
        where=d.get("where") or None,
        order_by=list(d.get("order_by") or []),
        limit=d.get("limit"),
        ordenado=bool(d.get("ordenado", False)),
    )


def tier_a(pergunta: str, modelo: str | None = None, temperatura: float | None = None) -> Predicao:
    """Sistema semântico: NL → spec (LLM) → MetricFlow. Abstém fora do vocabulário do catálogo."""
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    resp = _chamar_ollama(PROMPT.format(catalogo=CATALOGO, pergunta=pergunta), modelo, temp)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400])
    spec = _parse_spec(resp)
    if spec is None:
        # não produziu spec válida: numa respondível conta erro; numa abstenção não "responde" mesmo.
        return Predicao.abster(modelo=modelo, raw=resp[:400], falha_parse=True)
    return Predicao.com_spec(spec, modelo=modelo, raw=resp[:400])
