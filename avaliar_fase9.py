"""Fase 9 — prompt ANTIGO × NOVO no TEST-v3 (holdout que não existia quando o texto foi fechado).

Desenho: comparação **pareada** nos mesmos itens. Os dois sistemas usam o MESMO SUT e o MESMO
pipeline (parse → Spec → MetricFlow); a única variável é o texto do catálogo/prompt. Assim o ganho
é atribuível ao texto, e a dificuldade do conjunto se cancela — o que importa não é o EX absoluto
do v3 (que não é comparável ao do v2, por construção) e sim o delta pareado.

Além do EX global, o relatório checa REGRESSÃO por estrato: um conserto que arruma ranking e quebra
join_grao não é um conserto.
"""
import json
from pathlib import Path

from rodoquery.avaliacao import (
    avaliar_sistema,
    carregar_hashes_gold,
    coletar_predicoes,
    vetor_correto,
)
from rodoquery.estat import mcnemar, wilson
from rodoquery.golden import carregar
from rodoquery.proveniencia import carimbar
from rodoquery.sistema import tier_a
from rodoquery.sistema_v2 import tier_a_v2

REPO = Path(__file__).resolve().parent
itens = carregar(REPO / "golden" / "golden_test_v3.jsonl")
hashes = carregar_hashes_gold(REPO / "reports" / "fase9" / "gold_respostas_v3.json")
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
D = REPO / "reports" / "fase9"
SISTEMAS = {"tier_a_antigo": tier_a, "tier_a_v2": tier_a_v2}

print(f"[TEST-v3] {len(itens)} itens", flush=True)
preds = {}
for nome, fn in SISTEMAS.items():
    fp = D / f"predicoes_{nome}_test_v3.json"
    if fp.exists():
        preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
        print(f"  {nome}: congeladas reusadas", flush=True)
    else:
        print(f"  {nome}: coletando...", flush=True)
        preds[nome] = coletar_predicoes(itens, fn)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {nome}: congeladas", flush=True)

avals = {n: avaliar_sistema(itens, None, hashes, dbs, n, predicoes=preds[n]) for n in SISTEMAS}
ids_resp = [it.id for it in itens if not it.eh_abstencao]
ids_abst = [it.id for it in itens if it.eh_abstencao]
v_old, v_new = vetor_correto(avals["tier_a_antigo"]), vetor_correto(avals["tier_a_v2"])

mc_ex = mcnemar([v_old[i] for i in ids_resp], [v_new[i] for i in ids_resp])
mc_ab = mcnemar([v_old[i] for i in ids_abst], [v_new[i] for i in ids_abst])


def taxa(ids, v):
    ac = sum(v[i] for i in ids)
    lo, hi = wilson(ac, len(ids))
    return {"n": len(ids), "acertos": ac, "taxa": round(ac / len(ids), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


# regressão por estrato: onde o novo perde para o antigo?
estratos = sorted({it.estrato for it in itens if not it.eh_abstencao})
por_estrato = {}
for e in estratos:
    ids = [it.id for it in itens if it.estrato == e]
    a, b = sum(v_old[i] for i in ids), sum(v_new[i] for i in ids)
    por_estrato[e] = {"n": len(ids), "antigo": a, "novo": b, "delta": b - a}

regressoes = {e: v for e, v in por_estrato.items() if v["delta"] < 0}

rel = carimbar({
    "fase": "9_conserto_do_prompt",
    "desenho": ("pareado no TEST-v3; MESMO SUT e MESMO pipeline, so muda o texto do "
                "catalogo/prompt. O v3 foi gerado DEPOIS de o texto estar fechado."),
    "ressalva_comparabilidade": ("o EX absoluto do v3 NAO e comparavel ao do v2 (v3 tem mais itens "
                                 "multidimensionais). O que vale e o delta pareado."),
    "execution_accuracy": {"antigo": taxa(ids_resp, v_old), "novo": taxa(ids_resp, v_new),
                           "mcnemar": mc_ex},
    "abstencao": {"antigo": taxa(ids_abst, v_old), "novo": taxa(ids_abst, v_new),
                  "mcnemar": mc_ab},
    "por_estrato": por_estrato,
    "regressoes_por_estrato": regressoes,
    "resultados_por_item": {n: avals[n]["resultados"] for n in SISTEMAS},
})
dest = D / "resultado_test_v3.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

ex, ab = rel["execution_accuracy"], rel["abstencao"]
print(f"\n== TEST-v3 ({len(itens)} itens) ==")
print(f"  EX        antigo={ex['antigo']['taxa']} IC{ex['antigo']['wilson_ic95']} "
      f"-> novo={ex['novo']['taxa']} IC{ex['novo']['wilson_ic95']}")
print(f"            McNemar: {mc_ex}")
print(f"  abstencao antigo={ab['antigo']['taxa']} -> novo={ab['novo']['taxa']}")
print(f"            McNemar: {mc_ab}")
print("\n  por estrato (antigo -> novo):")
for e, v in por_estrato.items():
    marca = "  <-- REGRESSAO" if v["delta"] < 0 else ""
    print(f"    {e:20s} {v['antigo']:3d} -> {v['novo']:3d}  (n={v['n']}, {v['delta']:+d}){marca}")
print(f"\n-> {dest}")
