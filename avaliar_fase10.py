"""Fase 10 — catálogo de 7 métricas × catálogo LIMPO de 5, pareado.

Hipótese: boa parte do gargalo de "seleção de métrica" (Fases 8 e 9) não é limitação do modelo — é
ambiguidade que o catálogo criou ao expor `revenue` e `revenue_cents` (a mesma grandeza em duas
unidades) como se fossem métricas distintas.

Desenho que isola a variável:
  - itens: o subconjunto do TEST-v3 cujo gold usa APENAS as 5 métricas limpas (+ as abstenções).
    Perguntas com "em centavos" ficam de fora — sob o catálogo limpo elas não teriam resposta, e
    misturá-las mediria outra coisa.
  - braço A: catálogo atual (7) — predições JÁ CONGELADAS da Fase 9, sem nova chamada de LLM.
  - braço B: catálogo limpo (5) — única diferença; o PROMPT é o mesmo byte a byte.
  - os dois braços recebem o normalizador de ordem da Fase 9, para que a comparação seja
    catálogo × catálogo e não catálogo × (catálogo + conserto de ranking).

RESSALVA DECLARADA: o TEST-v3 já foi inspecionado na Fase 9, então isto é um SINAL forte, não a
prova definitiva. A prova sai na migração para os dados reais da ANTT, onde o holdout é novo.
"""
import json
from pathlib import Path

from rodoquery.avaliacao import (
    Predicao,
    avaliar_sistema,
    carregar_hashes_gold,
    coletar_predicoes,
    predicao_de_dict,
    predicao_para_dict,
    vetor_correto,
)
from rodoquery.estat import mcnemar, wilson
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_limpo import tier_a_limpo

REPO = Path(__file__).resolve().parent
D = REPO / "reports" / "fase10"
D.mkdir(parents=True, exist_ok=True)
LIMPAS = {"transactions", "suspect_transactions", "revenue", "revenue_leakage_brl", "suspect_rate"}

todos = carregar(REPO / "golden" / "golden_test_v3.jsonl")
itens = [it for it in todos if it.eh_abstencao or set(it.spec.metrics) <= LIMPAS]
ids = [it.id for it in itens]
print(f"[subconjunto limpo do TEST-v3] {len(itens)} itens "
      f"({sum(1 for i in itens if not i.eh_abstencao)} respondíveis, "
      f"{len(todos) - len(itens)} excluídos por usarem métrica de centavos)", flush=True)

hashes = carregar_hashes_gold(REPO / "reports" / "fase9" / "gold_respostas_v3.json")
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}


def com_normalizador(preds: dict) -> dict:
    """Aplica o normalizador de ordem (Fase 9) — os dois braços recebem o mesmo tratamento."""
    saida = {}
    for id_, d in preds.items():
        p: Predicao = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            ns = normalizar_spec(p.spec)
            if ns != p.spec:
                p = Predicao.com_spec(ns, **p.meta)
        saida[id_] = predicao_para_dict(p)
    return saida


# ---- braço A: catálogo atual (7 métricas) — congelado, sem LLM -------------------------------
_fp_a = REPO / "reports" / "fase9" / "predicoes_tier_a_antigo_test_v3.json"
bruto_a = json.loads(_fp_a.read_text(encoding="utf-8"))
pred_a = com_normalizador({k: v for k, v in bruto_a.items() if k in set(ids)})
print(f"  A (7 métricas): {len(pred_a)} predições congeladas reusadas", flush=True)

# ---- braço B: catálogo limpo (5 métricas) ----------------------------------------------------
fp = D / "predicoes_tier_a_limpo_v3sub.json"
if fp.exists():
    bruto_b = json.loads(fp.read_text(encoding="utf-8"))
    print("  B (5 métricas): predições congeladas reusadas", flush=True)
else:
    print("  B (5 métricas): coletando...", flush=True)
    bruto_b = coletar_predicoes(itens, tier_a_limpo)
    fp.write_text(json.dumps(bruto_b, ensure_ascii=False, indent=2), encoding="utf-8")
pred_b = com_normalizador(bruto_b)

av_a = avaliar_sistema(itens, None, hashes, dbs, "catalogo_7", predicoes=pred_a)
av_b = avaliar_sistema(itens, None, hashes, dbs, "catalogo_5_limpo", predicoes=pred_b)
va, vb = vetor_correto(av_a), vetor_correto(av_b)

resp = [it.id for it in itens if not it.eh_abstencao]
abst = [it.id for it in itens if it.eh_abstencao]
mc_ex = mcnemar([va[i] for i in resp], [vb[i] for i in resp])
mc_ab = mcnemar([va[i] for i in abst], [vb[i] for i in abst])


def taxa(ids_, v):
    ac = sum(v[i] for i in ids_)
    lo, hi = wilson(ac, len(ids_))
    return {"n": len(ids_), "acertos": ac, "taxa": round(ac / len(ids_), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


estratos = sorted({it.estrato for it in itens if not it.eh_abstencao})
por_estrato = {}
for e in estratos:
    ide = [it.id for it in itens if it.estrato == e]
    a, b = sum(va[i] for i in ide), sum(vb[i] for i in ide)
    por_estrato[e] = {"n": len(ide), "cat7": a, "cat5": b, "delta": b - a}

rel = carimbar({
    "fase": "10_catalogo_limpo",
    "hipotese": ("parte do gargalo de selecao de metrica e ambiguidade CRIADA pelo catalogo: "
                 "revenue e revenue_cents sao a mesma grandeza (derived: cents/100)."),
    "desenho": ("pareado no subconjunto do TEST-v3 que usa so as 5 metricas limpas; PROMPT "
                "identico byte a byte nos dois bracos; normalizador de ordem nos DOIS."),
    "ressalva": ("TEST-v3 ja foi inspecionado na Fase 9 -> SINAL, nao prova final. A prova sai no "
                 "holdout novo da migracao para dados reais da ANTT."),
    "n_itens": len(itens), "n_excluidos_centavos": len(todos) - len(itens),
    "execution_accuracy": {"catalogo_7": taxa(resp, va), "catalogo_5_limpo": taxa(resp, vb),
                           "mcnemar": mc_ex},
    "abstencao": {"catalogo_7": taxa(abst, va), "catalogo_5_limpo": taxa(abst, vb),
                  "mcnemar": mc_ab},
    "por_estrato": por_estrato,
    "regressoes": {e: v for e, v in por_estrato.items() if v["delta"] < 0},
    "resultados_por_item": {"catalogo_7": av_a["resultados"],
                            "catalogo_5_limpo": av_b["resultados"]},
})
(D / "resultado_catalogo_limpo.json").write_text(
    json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

ex, ab = rel["execution_accuracy"], rel["abstencao"]
print(f"\n== catálogo 7 × 5 (n={len(itens)}) ==")
print(f"  EX        7={ex['catalogo_7']['taxa']} IC{ex['catalogo_7']['wilson_ic95']}"
      f"  ->  5={ex['catalogo_5_limpo']['taxa']} IC{ex['catalogo_5_limpo']['wilson_ic95']}")
print(f"            McNemar: {mc_ex}")
print(f"  abstenção 7={ab['catalogo_7']['taxa']}  ->  5={ab['catalogo_5_limpo']['taxa']}")
print("\n  por estrato (cat7 -> cat5):")
for e, v in por_estrato.items():
    marca = "  <-- REGRESSAO" if v["delta"] < 0 else (f"  (+{v['delta']})" if v["delta"] else "")
    print(f"    {e:20s} {v['cat7']:3d} -> {v['cat5']:3d}  (n={v['n']}){marca}")
print(f"\n-> {D / 'resultado_catalogo_limpo.json'}")
