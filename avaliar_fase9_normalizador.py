"""Fase 9 — o conserto CERTO: prompt antigo + normalizador de ordem, no TEST-v3.

Este script NÃO chama o LLM. Ele pega as predições **já congeladas** do prompt antigo (as mesmas
que deram EX=66,85% no v3) e aplica o normalizador determinístico de `order_by` antes de pontuar.
Comparação pareada contra o próprio prompt antigo cru → McNemar.

Por que isso é honesto: o normalizador foi motivado pela Fase 8 (v2), antes de o v3 existir; o v3
é o seu holdout. E como ele é uma transformação determinística das specs, não há SUT estocástico
envolvido — o número é exato e reprodutível.
"""
import json
from pathlib import Path

from rodoquery.avaliacao import (
    Predicao,
    avaliar_sistema,
    carregar_hashes_gold,
    predicao_de_dict,
    predicao_para_dict,
    vetor_correto,
)
from rodoquery.estat import mcnemar, wilson
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
itens = carregar(REPO / "golden" / "golden_test_v3.jsonl")
hashes = carregar_hashes_gold(REPO / "reports" / "fase9" / "gold_respostas_v3.json")
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
D = REPO / "reports" / "fase9"

cru = json.loads((D / "predicoes_tier_a_antigo_test_v3.json").read_text(encoding="utf-8"))

# aplica o normalizador determinístico a cada predição congelada (só muda specs [campo, DESC/ASC])
norm, tocadas = {}, 0
for id_, d in cru.items():
    p: Predicao = predicao_de_dict(d)
    if p.tipo == "spec" and p.spec is not None:
        ns = normalizar_spec(p.spec)
        if ns is not p.spec and ns != p.spec:
            tocadas += 1
            p = Predicao.com_spec(ns, **p.meta)
    norm[id_] = predicao_para_dict(p)
(D / "predicoes_tier_a_norm_test_v3.json").write_text(
    json.dumps(norm, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[TEST-v3] {len(itens)} itens; normalizador tocou {tocadas} specs", flush=True)

a_cru = avaliar_sistema(itens, None, hashes, dbs, "tier_a_antigo", predicoes=cru)
a_norm = avaliar_sistema(itens, None, hashes, dbs, "tier_a_norm", predicoes=norm)
ids_resp = [it.id for it in itens if not it.eh_abstencao]
v_cru, v_norm = vetor_correto(a_cru), vetor_correto(a_norm)
mc = mcnemar([v_cru[i] for i in ids_resp], [v_norm[i] for i in ids_resp])


def taxa(v):
    ac = sum(v[i] for i in ids_resp)
    lo, hi = wilson(ac, len(ids_resp))
    return {"n": len(ids_resp), "acertos": ac, "taxa": round(ac / len(ids_resp), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


estratos = sorted({it.estrato for it in itens if not it.eh_abstencao})
por_estrato = {}
for e in estratos:
    ids = [it.id for it in itens if it.estrato == e]
    por_estrato[e] = {"n": len(ids), "cru": sum(v_cru[i] for i in ids),
                      "norm": sum(v_norm[i] for i in ids),
                      "delta": sum(v_norm[i] for i in ids) - sum(v_cru[i] for i in ids)}

rel = carimbar({
    "fase": "9_normalizador_ordem",
    "conserto": ("prompt ANTIGO (byte a byte da Fase 4) + normalizador deterministico de order_by. "
                 "SEM chamada de LLM: reescore de predicoes congeladas."),
    "motivacao_holdout": "normalizador motivado pela Fase 8 (v2); v3 e o holdout que o mede.",
    "specs_tocadas_pelo_normalizador": tocadas,
    "execution_accuracy": {"cru": taxa(v_cru), "com_normalizador": taxa(v_norm), "mcnemar": mc},
    "por_estrato": por_estrato,
    "regressoes": {e: v for e, v in por_estrato.items() if v["delta"] < 0},
})
dest = D / "resultado_normalizador_v3.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

ex = rel["execution_accuracy"]
_c = ex["cru"]
print(f"\nEX  cru={_c['taxa']} IC{_c['wilson_ic95']} ({_c['acertos']}/{_c['n']})")
print(f"EX  norm={ex['com_normalizador']['taxa']} IC{ex['com_normalizador']['wilson_ic95']} "
      f"({ex['com_normalizador']['acertos']}/{ex['com_normalizador']['n']})")
print(f"McNemar: {mc}")
print("\npor estrato (cru -> norm):")
for e, v in por_estrato.items():
    marca = "  <-- REGRESSAO" if v["delta"] < 0 else (f"  (+{v['delta']})" if v["delta"] else "")
    print(f"  {e:20s} {v['cru']:3d} -> {v['norm']:3d}  (n={v['n']}){marca}")
print(f"\n-> {dest}")
