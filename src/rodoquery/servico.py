"""RodoQuery — serviço HTTP (Fase 6).

**Só o caminho Tier-A é exposto.** O usuário manda pergunta em linguagem natural; o LLM devolve uma
*spec* do vocabulário fechado e o MetricFlow gera o SQL. O usuário **nunca** injeta SQL — não há
superfície de injeção por construção (o sandbox da Fase 1 existe para o Tier-B, que não é servido).

Endpoints:
  POST /consulta  — pergunta → resposta (ou abstenção honesta)
  GET  /saude     — liveness + modelo carregado
  GET  /metricas  — p50/p95, taxa de abstenção/erro, cache hit (observabilidade da Fase 5 no ar)

**Cache spec→SQL:** a compilação do MetricFlow é *data-independente* (a mesma spec sempre gera o
mesmo SQL — é o que sustenta o Test-Suite EX). Logo dá para cachear com segurança, e isso tira um
subprocess de ~2 s do caminho quente. Invalidação: o cache é por processo e morre no restart; se o
manifesto do dbt mudar, o serviço tem de ser reiniciado (documentado no SLO).
"""
from __future__ import annotations

import json
import statistics as st
import threading
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

import duckdb
from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT, FUNDACAO_SINTETICA, Spec, compilar_spec
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.sistema import tier_a
from rodoquery.sistema_antt import tier_a_antt

# Qual fundação este processo serve (RODOQUERY_FUNDACAO_ATIVA). O default é a sintética, para
# não alterar nada do que já foi medido; o container sobe com "antt" (dado real).
if settings.fundacao_ativa == "antt":
    _SISTEMA, _FUNDACAO, _BANCO = tier_a_antt, FUNDACAO_ANTT, settings.antt_duckdb
else:
    _SISTEMA, _FUNDACAO, _BANCO = tier_a, FUNDACAO_SINTETICA, settings.toll_duckdb

# Qual SUT responde (RODOQUERY_PROVEDOR). Default "ollama" = o caminho de todas as fases; a API
# entra por CONFIGURAÇÃO, nunca por acidente — um serviço que gasta dinheiro a cada request não
# pode virar default sem alguém ter decidido isso. A construção acontece no IMPORT de propósito:
# sem chave, o processo morre no START, não no primeiro request de um usuário.
_PROVEDOR = None
if settings.provedor == "anthropic":
    from rodoquery.provedor import ProvedorAnthropic
    _PROVEDOR = ProvedorAnthropic(modelo_padrao=settings.modelo_api)
elif settings.provedor != "ollama":
    raise ValueError(f"RODOQUERY_PROVEDOR invalido: {settings.provedor!r} "
                     "(use 'ollama' ou 'anthropic')")


def _TIER_A(pergunta: str):  # noqa: N802 — nome mantido: é assim desde a Fase 6
    return _SISTEMA(pergunta, provedor=_PROVEDOR) if _PROVEDOR else _SISTEMA(pergunta)

LIMITE_LINHAS = 1_000
_MAX_AMOSTRAS = 2_000

# CONTROLE DE ADMISSÃO — decidido pela MEDIÇÃO (ver reports/fase6/).
#
# 1) A vazão em 1 GPU de 6 GB NÃO escala: c=2 → 1,11×, c=4 → 0,75×, c=8 → 0,76×, com p95 indo de
#    4,4 s a 43 s. Admitir mais só enfileira e ainda causa contenção.
# 2) O ótimo de VAZÃO (c=2: 0,279 req/s) NÃO é o ótimo de SLO. Em c=2 cada inferência custa ~8,2 s
#    de p95 — não sobra orçamento de fila dentro de um SLO de 10 s. Medido: com limite 2 e espera
#    6 s, o p95 das atendidas ficou em 11,4 s (violando o SLO).
# 3) Em c=1 o p95 é 4,36 s, deixando ~5 s de fila dentro do SLO. Custa 11% de vazão (0,251 vs
#    0,279) e compra previsibilidade. Para um serviço com SLO, previsibilidade vale mais.
# 4) **Esse raciocínio inteiro pressupõe UMA GPU local — e a premissa cai no caminho de API.**
#    Lá o gargalo não é VRAM, é rate limit do provedor, e a inferência paraleliza de verdade.
#    Manter 1 na API não seria conservador: seria aplicar uma medição a um sistema que não foi
#    medido, e estrangular a vazão por um motivo que não existe mais.
#    O SLO da Fase 6 continua valendo só para GPU local, do mesmo jeito que não foi herdado no
#    Docker (Fase 16) nem no Kubernetes (Fase 17b).
# 5) **O 8 da API agora é MEDIDO** (Fase 21, `reports/fase21/concorrencia_api.json`). O critério
#    foi declarado ANTES de olhar — manter 8 só se a vazão em c=8 passasse de 1,5× a de c=1 — e
#    passou com folga. A curva é o oposto exato da GPU local:
#        c=       1      2      4      8
#        API      1,00×  1,94×  3,10×  5,74×   e o p95 fica PLANO (~3,3 s)
#        GPU      1,00×  1,11×  0,75×  0,76×   e o p95 vai a 43 s
#    Escala quase linear e sem penalidade de latência — 8 é conservador, não agressivo.
#    Sobrescrevível por RODOQUERY_MAX_INFERENCIA_SIMULTANEA.
_PADRAO_CONCORRENCIA = {"ollama": 1, "anthropic": 8}
MAX_INFERENCIA_SIMULTANEA = (settings.max_inferencia_simultanea
                             or _PADRAO_CONCORRENCIA[settings.provedor])
# Os DOIS caminhos agora vêm de medição (Fase 6 para o local, Fase 21 para a API).
CONCORRENCIA_MEDIDA = True
ESPERA_MAX_S = 5.0          # 4,36 s (p95 da inferência) + 5 s de fila <= 10 s do SLO
_vagas = threading.Semaphore(MAX_INFERENCIA_SIMULTANEA)

app = FastAPI(title="RodoQuery", version="0.1.0",
              description="Agente de Analytics sobre lakehouse governado (Semantic Layer).")

_cache_sql: dict[str, str] = {}
_trava = threading.Lock()
_amostras: deque[dict] = deque(maxlen=_MAX_AMOSTRAS)
_contadores = {"total": 0, "respostas": 0, "abstencoes": 0, "erros": 0,
               "rejeitadas": 0, "cache_hit": 0, "cache_miss": 0}


class Consulta(BaseModel):
    pergunta: str = Field(min_length=3, max_length=500,
                          description="Pergunta de negócio em português.")


class Resposta(BaseModel):
    tipo: str                      # "resposta" | "abstencao" | "erro"
    pergunta: str
    spec: dict | None = None       # o que o sistema entendeu (auditável pelo usuário)
    colunas: list[str] | None = None
    linhas: list[list] | None = None
    truncado: bool = False
    motivo: str | None = None
    latencia_s: dict | None = None  # breakdown: llm / compilacao / execucao / total


def _chave(spec: Spec) -> str:
    return json.dumps(asdict(spec), sort_keys=True, ensure_ascii=False)


def compilar_cacheado(spec: Spec) -> tuple[str, bool]:
    """(sql, veio_do_cache). Compilação é data-independente → cachear é seguro."""
    k = _chave(spec)
    with _trava:
        if k in _cache_sql:
            _contadores["cache_hit"] += 1
            return _cache_sql[k], True
    sql = compilar_spec(spec, fundacao=_FUNDACAO)
    with _trava:
        _cache_sql[k] = sql
        _contadores["cache_miss"] += 1
    return sql, False


def _executar(sql: str, db: Path, limite: int = LIMITE_LINHAS) -> tuple[list[str], list[tuple]]:
    """Read-only + teto de linhas. O SQL vem do MetricFlow, não do usuário."""
    con = duckdb.connect(str(db), read_only=True,
                         config={"enable_external_access": "false", "memory_limit": "2GB"})
    try:
        cur = con.execute(f"select * from ({sql.rstrip().rstrip(';')}) as _rq limit {limite + 1}")
        colunas = [d[0] for d in cur.description]
        return colunas, cur.fetchall()
    finally:
        con.close()


@app.post("/consulta", response_model=Resposta)
def consulta(req: Consulta, resposta_http: Response) -> Resposta:
    t0 = time.perf_counter()
    lat = {}
    # Admissão: se não há vaga de inferência dentro da espera máxima, rejeita rápido (503).
    # Degradar com honestidade é melhor que aceitar e devolver 43 s depois.
    if not _vagas.acquire(timeout=ESPERA_MAX_S):
        with _trava:
            _contadores["rejeitadas"] += 1
        resposta_http.status_code = 503
        return Resposta(tipo="erro", pergunta=req.pergunta,
                        latencia_s={"total": round(time.perf_counter() - t0, 3)},
                        motivo="Serviço saturado (1 GPU não paraleliza). Tente novamente.")
    try:
        pred = _TIER_A(req.pergunta)
        lat["llm"] = round(pred.meta.get("latencia_s", 0.0), 3)

        if pred.tipo == "abster":
            lat["total"] = round(time.perf_counter() - t0, 3)
            _registrar("abstencao", lat, False)
            return Resposta(
                tipo="abstencao", pergunta=req.pergunta, latencia_s=lat,
                motivo="Fora do catálogo governado — não há métrica que responda a pergunta.")

        # Normaliza a ordenação estilo-SQL (`["x","DESC"]` → `["-x"]`) ANTES de compilar. É o
        # conserto de ranking da Fase 9: um endurecimento determinístico do SERVIÇO que provou
        # +5pp / p=0,004 / zero regressões no holdout v3. O `tier_a` congelado não muda; isto age
        # sobre a spec que ele devolve, no mesmo ponto onde o `compilar` falharia.
        spec = normalizar_spec(pred.spec)
        t1 = time.perf_counter()
        try:
            sql, do_cache = compilar_cacheado(spec)
        except Exception:                                    # noqa: BLE001 — falha fechada
            # Spec que não compila = o modelo não conseguiu mapear a pergunta ao catálogo.
            # Em produção isso vira ABSTENÇÃO honesta, não 500: falhar fechado é a postura certa
            # (descoberto pelo canário, em `abstencao_07`). A avaliação da Fase 4 usa o `tier_a`
            # direto e segue congelada — este é endurecimento de SERVIÇO, não mudança do sistema.
            lat["compilacao"] = round(time.perf_counter() - t1, 3)
            lat["total"] = round(time.perf_counter() - t0, 3)
            _registrar("abstencao", lat, False)
            return Resposta(
                tipo="abstencao", pergunta=req.pergunta, spec=asdict(spec), latencia_s=lat,
                motivo="Não consegui mapear a pergunta ao catálogo governado com segurança.")
        lat["compilacao"] = round(time.perf_counter() - t1, 3)

        t2 = time.perf_counter()
        colunas, linhas = _executar(sql, _BANCO)
        lat["execucao"] = round(time.perf_counter() - t2, 3)
        lat["total"] = round(time.perf_counter() - t0, 3)

        truncado = len(linhas) > LIMITE_LINHAS
        _registrar("resposta", lat, do_cache)
        return Resposta(tipo="resposta", pergunta=req.pergunta, spec=asdict(spec),
                        colunas=colunas, linhas=[list(x) for x in linhas[:LIMITE_LINHAS]],
                        truncado=truncado, latencia_s=lat)
    except Exception as e:                                   # noqa: BLE001 (fronteira do serviço)
        lat["total"] = round(time.perf_counter() - t0, 3)
        _registrar("erro", lat, False)
        resposta_http.status_code = 500
        return Resposta(tipo="erro", pergunta=req.pergunta, latencia_s=lat,
                        motivo=f"{type(e).__name__}: {str(e)[:200]}")
    finally:
        _vagas.release()


def _registrar(tipo: str, lat: dict, do_cache: bool) -> None:
    with _trava:
        _contadores["total"] += 1
        chave = {"resposta": "respostas", "abstencao": "abstencoes", "erro": "erros"}[tipo]
        _contadores[chave] += 1
        _amostras.append({"tipo": tipo, "total": lat.get("total"), "llm": lat.get("llm"),
                          "compilacao": lat.get("compilacao"), "execucao": lat.get("execucao"),
                          "cache": do_cache})


def _pct(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    v = sorted(vals)
    return round(v[min(len(v) - 1, int(len(v) * p))], 3)


@app.get("/saude")
def saude() -> dict:
    return {"status": "ok",
            "provedor": settings.provedor,
            # o modelo que de fato responde — não `settings.modelo_sut`, que no caminho de API
            # seria o nome do modelo LOCAL. Foi exatamente esse descuido que fez as predições
            # da Fase 18 nascerem rotuladas como qwen2.5-coder:7b.
            "modelo": settings.modelo_api if _PROVEDOR else settings.modelo_sut,
            "temperatura": settings.temperatura if not _PROVEDOR else None,
            "fundacao": settings.fundacao_ativa, "banco": _BANCO.name,
            "specs_em_cache": len(_cache_sql),
            "max_inferencia_simultanea": MAX_INFERENCIA_SIMULTANEA,
            # se o limite acima veio de medição ou é só um default plausível
            "concorrencia_medida": CONCORRENCIA_MEDIDA,
            "espera_max_s": ESPERA_MAX_S}


@app.get("/metricas")
def metricas() -> dict:
    with _trava:
        amostras = list(_amostras)
        cont = dict(_contadores)
    tot = [a["total"] for a in amostras if a["total"] is not None]
    hits = cont["cache_hit"] + cont["cache_miss"]
    # Custo é métrica de PRODUÇÃO quando o SUT é pago. Sem isto, a única forma de descobrir que
    # o serviço está queimando crédito é a fatura no fim do mês — que é tarde demais.
    custo = None
    if _PROVEDOR is not None:
        custo = {"usd_acumulado": round(_PROVEDOR.custo_usd, 4),
                 "chamadas": _PROVEDOR.chamadas,
                 "usd_por_chamada": round(_PROVEDOR.custo_usd / _PROVEDOR.chamadas, 6)
                 if _PROVEDOR.chamadas else None,
                 "tokens_cache_leitura": _PROVEDOR.tokens_cache_leitura}
    return {
        "contadores": cont,
        "custo": custo,
        "taxa_abstencao": round(cont["abstencoes"] / cont["total"], 4) if cont["total"] else None,
        "taxa_erro": round(cont["erros"] / cont["total"], 4) if cont["total"] else None,
        "cache_hit_rate": round(cont["cache_hit"] / hits, 4) if hits else None,
        "latencia_total_s": {"p50": _pct(tot, 0.50), "p95": _pct(tot, 0.95),
                             "media": round(st.mean(tot), 3) if tot else None},
        "latencia_por_etapa_media_s": {
            etapa: round(st.mean(v), 3) if (v := [a[etapa] for a in amostras
                                                  if a.get(etapa) is not None]) else None
            for etapa in ("llm", "compilacao", "execucao")
        },
    }
