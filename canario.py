"""Fase 6 — canário de CORREÇÃO contra o serviço vivo.

Load test mede se o serviço é rápido. Canário mede se ele continua **certo** — é o que pega
"subiu, respondeu 200, e devolveu número errado", que nenhum health check percebe.

**Por que DEV e não TEST:** o TEST é selado e vale como avaliação final única (Fase 4). Um canário
roda de hora em hora; usar o TEST o queimaria. O canário usa itens do **DEV**, e o número dele é um
sinal operacional de saúde — não a métrica científica do sistema.

Correção é medida contra o gold gerado no MESMO banco que o serviço consulta (o canônico), via
MetricFlow a partir da spec do golden — a mesma regra anti-circularidade das fases anteriores.

Uso: python canario.py [n_itens]   (default 8)
"""
import json
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.gold import compilar_spec, executar_gold
from rodoquery.golden import carregar
from rodoquery.proveniencia import carimbar

BASE = "http://127.0.0.1:8077"
REPO = Path(__file__).resolve().parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 8


def consultar(pergunta: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/consulta", data=json.dumps({"pergunta": pergunta}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def _normalizar(linhas):
    """O serviço devolve JSON (datas viram string ISO). Alinha o gold à mesma forma p/ o hash."""
    saida = []
    for linha in linhas:
        saida.append(tuple(
            v.isoformat() if isinstance(v, (datetime, date)) else v for v in linha))
    return saida


dev = carregar(REPO / "golden" / "golden_dev.jsonl")
respondiveis = [it for it in dev if not it.eh_abstencao][:N]
abstencoes = [it for it in dev if it.eh_abstencao][:max(1, N // 4)]

resultados = []
for it in respondiveis:
    d = consultar(it.pergunta_nl)
    if d["tipo"] != "resposta":
        resultados.append({"id": it.id, "ok": False, "motivo": f"servico devolveu {d['tipo']}"})
        continue
    gold = _normalizar(executar_gold(compilar_spec(it.spec), settings.toll_duckdb))
    pred = [tuple(x) for x in d["linhas"]]
    ok = (hash_resultado(pred, ordenado=it.spec.ordenado)
          == hash_resultado(gold, ordenado=it.spec.ordenado))
    resultados.append({"id": it.id, "ok": ok,
                       "motivo": "bate o gold" if ok else "resultado diferente do gold"})

for it in abstencoes:
    d = consultar(it.pergunta_nl)
    ok = d["tipo"] == "abstencao"
    # distingue os dois modos de falha: responder algo (grave) vs errar fechado (menos grave)
    motivo = ("absteve (correto)" if ok
              else "RESPONDEU pergunta fora-de-escopo" if d["tipo"] == "resposta"
              else f"nao absteve: devolveu {d['tipo']}")
    resultados.append({"id": it.id, "ok": ok, "motivo": motivo})

acertos = sum(r["ok"] for r in resultados)
taxa = round(acertos / len(resultados), 4)
rel = carimbar({
    "fase": "6_canario",
    "split_usado": "DEV (o TEST segue selado para a avaliacao final)",
    "banco": settings.toll_duckdb.name,
    "n_respondiveis": len(respondiveis), "n_abstencoes": len(abstencoes),
    "acertos": acertos, "n": len(resultados), "ex_canario": taxa,
    "resultados": resultados,
})
dest = REPO / "reports" / "fase6" / "canario.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

for r in resultados:
    print(f"  {'OK  ' if r['ok'] else 'FALHA'} {r['id']:22s} {r['motivo']}")
print(f"\nEX de canario: {acertos}/{len(resultados)} = {taxa}")
print(f"-> {dest}")
raise SystemExit(0 if taxa >= 0.85 else 1)
