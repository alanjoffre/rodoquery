"""Sistemas-baseline da Fase 3.

`sql_cru` é o baseline que a tese precisa bater: um LLM competente (o mesmo SUT, qwen2.5-coder:7b)
recebe o **schema real** das tabelas analíticas + um **prompt justo** e escreve SQL DuckDB direto.

Justiça (para não ser espantalho): o prompt é generoso no COSMÉTICO (contrato de saída: ordem das
colunas, colunas de código, `date_trunc`, unidade em reais) — mas NÃO entrega a REGRA DE NEGÓCIO
que é justamente o que o Semantic Layer governa e o SQL cru precisa redescobrir sozinho:
  - `revenue` só conta transações COMPLETED (o schema não diz isso);
  - `suspect` = `audit_flag != 'OK'`;
  - o denominador de `suspect_rate`; o sinal/So filtro do leakage.
Se o baseline erra ISSO mesmo com todo o resto facilitado, o erro é semântico — a tese.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

from rodoquery.avaliacao import Predicao
from rodoquery.config import settings

OLLAMA_URL = "http://localhost:11434/api/generate"

# Schema HONESTO das tabelas que o sandbox permite (dicionário de dados que um analista teria).
# Descrições neutras — NÃO revelam as regras das métricas.
SCHEMA_DOC = """Tabelas disponíveis (DuckDB, schema `main`). SÓ estas podem ser consultadas:

fct_toll_transactions  — uma linha por transação de pedágio (tabela fato)
  transaction_id VARCHAR
  event_date DATE                 — data do evento
  event_ts TIMESTAMP
  vehicle_id VARCHAR              — FK p/ dim_vehicle
  plaza_id VARCHAR                — FK p/ dim_plaza (código da praça, ex. 'P001')
  payment_method VARCHAR          — valores: AUTOMATIC_TAG, CARD, CASH
  status VARCHAR                  — valores: COMPLETED, FAILED, REVERSED
  audit_flag VARCHAR              — valores: OK, COBRANCA_EM_FALHA, TARIFA_DIVERGENTE, POSSIVEL_DUPLICIDADE, VALOR_INVALIDO
  amount_cents INTEGER            — valor cobrado, em centavos inteiros
  amount_brl DOUBLE               — valor cobrado, em reais (= amount_cents/100)
  expected_amount_cents INTEGER   — valor esperado (tarifa correta), em centavos
  amount_diff_cents INTEGER       — (cobrado - esperado), em centavos
  is_duplicate BOOLEAN

dim_plaza   (plaza_id VARCHAR, plaza_name VARCHAR, highway VARCHAR, uf VARCHAR)
dim_vehicle (vehicle_id VARCHAR, category INTEGER, category_description VARCHAR, fare_multiplier DOUBLE, account_id VARCHAR)
dim_date    (date_day DATE, year INTEGER, month INTEGER, day INTEGER, day_of_week INTEGER, is_weekend BOOLEAN)"""

PROMPT = """Você é um analista de dados sênior, especialista em SQL DuckDB, numa concessionária de pedágio.

{schema}

Regras de SAÍDA (obrigatórias):
- Responda com UMA única query SELECT em DuckDB e MAIS NADA (sem explicação, sem ```).
- Ao agrupar, ponha a(s) coluna(s) de agrupamento PRIMEIRO (use as colunas de código: plaza_id, status, payment_method, audit_flag, vehicle_id) e o valor agregado por ÚLTIMO.
- Para agrupar por tempo use date_trunc('day'|'week'|'month', event_date).
- Valores monetários: responda em REAIS (coluna amount_brl).
- Se a pergunta NÃO puder ser respondida com estas tabelas/colunas, responda EXATAMENTE a palavra: ABSTENHO

Pergunta: {pergunta}
SQL:"""

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _chamar_ollama(
    prompt: str, modelo: str, temperatura: float, timeout: float = 120.0,
) -> tuple[str, dict]:
    """Devolve (texto, telemetria). A telemetria alimenta observabilidade e custo (Fase 5)."""
    corpo = json.dumps({
        "model": modelo, "prompt": prompt, "stream": False,
        # determinismo: greedy (temp 0 + top_k 1) e seed fixa. MEDIDO na Fase 5: com estas opções e
        # o modelo quente, 5 runs deram EX idêntico (amplitude 0,0pp, 0 itens instáveis) — ver
        # reports/fase5/flakiness.json. As predições ainda são CONGELADAS em disco como seguro
        # barato (5 runs não provam variância zero, e houve uma anomalia não explicada antes do
        # top_k=1); isso torna o número reportado reprodutível independentemente disso.
        "options": {"temperature": temperatura, "seed": 42, "top_k": 1, "top_p": 1.0},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=corpo,
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 (localhost)
        d = json.loads(r.read())
    telemetria = {
        "latencia_s": round(time.perf_counter() - t0, 3),
        "tokens_prompt": d.get("prompt_eval_count"),
        "tokens_saida": d.get("eval_count"),
        # nanosegundos → segundos (o Ollama reporta assim)
        "eval_s": round((d.get("eval_duration") or 0) / 1e9, 3),
        "carga_modelo_s": round((d.get("load_duration") or 0) / 1e9, 3),
    }
    return d["response"], telemetria


def _extrair_sql(texto: str) -> str:
    m = _FENCE.search(texto)
    return (m.group(1) if m else texto).strip()


def sql_cru(pergunta: str, modelo: str | None = None, temperatura: float | None = None) -> Predicao:
    """Baseline: LLM escreve SQL direto sobre o schema cru (sem Semantic Layer)."""
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    resp, tel = _chamar_ollama(PROMPT.format(schema=SCHEMA_DOC, pergunta=pergunta), modelo, temp)
    sql = _extrair_sql(resp)
    if sql.strip().upper().rstrip(".") == "ABSTENHO" or sql.strip().upper().startswith("ABSTENHO"):
        return Predicao.abster(modelo=modelo, raw=resp[:400], **tel)
    return Predicao.com_sql(sql, modelo=modelo, raw=resp[:400], **tel)


def sempre_abster(pergunta: str) -> Predicao:
    """Piso trivial (sanity anchor): abstém sempre. Acerta 100% da abstenção, 0% do respondível.
    Serve para provar que o scorer não é viciado (não dá acerto de graça no eixo respondível)."""
    return Predicao.abster(modelo="trivial")
