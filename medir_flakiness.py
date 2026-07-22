"""Fase 5 — QUANTIFICA a estabilidade do SUT (o roadmap previa "flakiness desestabiliza o gate").

Por que isto existe: na Fase 4 vi um item de fronteira mudar de veredito entre execuções e SUPUS
não-determinismo de GPU. Suposição não é medição — então aqui eu meço.

**Resultado (ver reports/fase5/flakiness.json): a hipótese NÃO se confirmou.** Com greedy
(temp 0 + top_k 1), seed fixa e modelo quente, K runs deram EX idêntico. O achado esperado do
roadmap não apareceu nesta configuração — e isso vai reportado como está, não escondido.

O gate continua com margem (piso de 1 item): K runs pequenos mostram que a variância é baixa,
não que é zero. Este script roda o sistema K vezes no DEV e reporta:
  - distribuição do EX por run (média, desvio, min–max);
  - quais ITENS são instáveis (mudam de veredito entre runs) — o "conjunto de fronteira";
  - latência (p50/p95) e tokens, para observabilidade e custo.

Uso: python medir_flakiness.py [K]      (default K=5)
"""
import json
import statistics as st
import sys
from pathlib import Path

from rodoquery.avaliacao import (
    avaliar_sistema,
    carregar_hashes_gold,
    coletar_predicoes,
    vetor_correto,
)
from rodoquery.golden import carregar
from rodoquery.proveniencia import carimbar
from rodoquery.sistema import tier_a

K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
REPO = Path.home() / "rodoquery"
DEV = carregar(REPO / "golden" / "golden_dev.jsonl")
hashes = carregar_hashes_gold()
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}

print(f"medindo flakiness: {K} runs x {len(DEV)} itens (DEV)...")
runs = []
for k in range(K):
    preds = coletar_predicoes(DEV, tier_a)
    av = avaliar_sistema(DEV, None, hashes, dbs, "tier_a", predicoes=preds)
    lat = [p["meta"].get("latencia_s") for p in preds.values() if p["meta"].get("latencia_s")]
    tok = [p["meta"].get("tokens_saida") or 0 for p in preds.values()]
    tok_in = [p["meta"].get("tokens_prompt") or 0 for p in preds.values()]
    runs.append({
        "run": k,
        "ex": av["execution_accuracy_respondiveis"]["taxa"],
        "abstencao": av["acuracia_abstencao"]["taxa"],
        "vetor": vetor_correto(av),
        "latencias": lat,
        "tokens_saida_total": sum(tok),
        "tokens_prompt_total": sum(tok_in),
    })
    print(f"  run {k}: EX={runs[-1]['ex']}  abst={runs[-1]['abstencao']}")

ex = [r["ex"] for r in runs]
lat_todas = sorted(x for r in runs for x in r["latencias"])


def _pct(v, p):
    return round(v[min(len(v) - 1, int(len(v) * p))], 3) if v else None


# itens instáveis: veredito não é o mesmo em todos os runs
ids = list(runs[0]["vetor"])
instaveis = {i: [r["vetor"][i] for r in runs] for i in ids
             if len({r["vetor"][i] for r in runs}) > 1}

rel = carimbar({
    "fase": "5_flakiness",
    "K_runs": K,
    "n_itens_dev": len(DEV),
    "ex_por_run": ex,
    "ex_media": round(st.mean(ex), 4),
    "ex_desvio": round(st.pstdev(ex), 4) if K > 1 else 0.0,
    "ex_min": min(ex), "ex_max": max(ex),
    "amplitude_pp": round((max(ex) - min(ex)) * 100, 2),
    "itens_instaveis": {i: v for i, v in instaveis.items()},
    "n_itens_instaveis": len(instaveis),
    "latencia_s": {"p50": _pct(lat_todas, 0.50), "p95": _pct(lat_todas, 0.95),
                   "media": round(st.mean(lat_todas), 3) if lat_todas else None},
    "tokens_por_run": {"prompt": runs[0]["tokens_prompt_total"],
                       "saida_media": round(st.mean([r["tokens_saida_total"] for r in runs]), 1)},
    "n_respondiveis": sum(1 for it in DEV if not it.eh_abstencao),
    "leitura": ("amplitude_pp == 0 => nesta configuracao (greedy+top_k=1, modelo quente) o SUT foi "
                "ESTAVEL; o 'flakiness desestabiliza o gate' previsto no roadmap NAO se confirmou. "
                "O gate live mantem margem com piso de 1 item: K runs pequenos mostram variancia "
                "baixa, nao nula. Ver src/rodoquery/regressao.py:carregar_margem_medida."),
})
dest = REPO / "reports" / "fase5" / "flakiness.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nEX: media={rel['ex_media']} desvio={rel['ex_desvio']} "
      f"min={rel['ex_min']} max={rel['ex_max']} amplitude={rel['amplitude_pp']}pp")
print(f"itens instaveis: {rel['n_itens_instaveis']} -> {list(instaveis)}")
print(f"latencia p50={rel['latencia_s']['p50']}s p95={rel['latencia_s']['p95']}s")
print(f"-> {dest}")
