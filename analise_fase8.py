"""Fase 8 — análise: replicação no holdout fresco, cobertura nova e ganho de poder estatístico.

Três leituras que NÃO devem ser misturadas:

1. **Replicação** — os 7 estratos originais no TEST-v2. Sistema congelado desde a Fase 4, specs
   inéditas, holdout nunca visto. É a evidência independente de que o resultado da Fase 4 não foi
   sorte de um conjunto pequeno.
2. **Cobertura nova** — o estrato `ranking`, que nenhum item da v1 jamais avaliou apesar de o
   prompt ter uma regra sobre ele. Não faz parte da replicação: é território novo.
3. **Pooled** — v1 ∪ v2, só para o poder máximo. Declarado como pooled, com a ressalva de que o
   TEST-v1 já foi consumido antes.

Também reporta o que o N maior comprou de fato: largura do IC, que é a métrica honesta de poder.
"""
import json
from pathlib import Path

from rodoquery.estat import mcnemar, wilson
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
ORIGINAIS = ("metrica_filtrada", "coalesce_nulo", "join_grao", "metrica_derivada",
             "grao_temporal", "valor_categorico", "controle_trivial")
DEGENERADOS_V1 = {"valor_categorico_02", "valor_categorico_03"}

f4 = json.loads((REPO / "reports" / "fase4" / "resultado_test.json").read_text(encoding="utf-8"))
f8 = json.loads((REPO / "reports" / "fase8" / "resultado_test_v2.json").read_text(encoding="utf-8"))


def linhas(rel):
    """{sistema: {id: registro}} a partir de um relatório de avaliação."""
    return {s: {r["id"]: r for r in itens} for s, itens in rel["resultados_por_item"].items()}


L4, L8 = linhas(f4), linhas(f8)


def taxa(ids, reg):
    ac = sum(reg[i]["correto"] for i in ids)
    lo, hi = wilson(ac, len(ids)) if ids else (0.0, 0.0)
    return {"n": len(ids), "acertos": ac, "taxa": round(ac / len(ids), 4) if ids else None,
            "wilson_ic95": [round(lo, 4), round(hi, 4)],
            "largura_ic_pp": round((hi - lo) * 100, 1)}


def bloco(L, ids_resp, ids_abst, rotulo):
    ta, sc = L["tier_a"], L["sql_cru"]
    mc = mcnemar([sc[i]["correto"] for i in ids_resp], [ta[i]["correto"] for i in ids_resp])
    return {
        "rotulo": rotulo,
        "tier_a": {"execution_accuracy": taxa(ids_resp, ta), "abstencao": taxa(ids_abst, ta)},
        "sql_cru": {"execution_accuracy": taxa(ids_resp, sc), "abstencao": taxa(ids_abst, sc)},
        "mcnemar_sqlcru_vs_tiera": mc,
        "delta_pp": round((sum(ta[i]["correto"] for i in ids_resp)
                           - sum(sc[i]["correto"] for i in ids_resp)) / len(ids_resp) * 100, 2),
    }


def ids_de(L, estratos, abstencao=False):
    ta = L["tier_a"]
    return [i for i, r in ta.items()
            if (r["estrato"] == "abstencao") == abstencao
            and (abstencao or r["estrato"] in estratos)]


# ---------------------------------------------------------------- 1) replicação (7 originais)
r_v1 = ids_de(L4, ORIGINAIS)
r_v2 = ids_de(L8, ORIGINAIS)
a_v1, a_v2 = ids_de(L4, (), True), ids_de(L8, (), True)

fase4_orig = bloco(L4, r_v1, a_v1, "TEST-v1 (Fase 4, ja consumido)")
fase4_sem_deg = bloco(L4, [i for i in r_v1 if i not in DEGENERADOS_V1], a_v1,
                      "TEST-v1 SEM os 2 itens de gold degenerado")
replicacao = bloco(L8, r_v2, a_v2, "TEST-v2 (holdout fresco, specs ineditas)")

# ---------------------------------------------------------------- 2) cobertura nova: ranking
rank = ids_de(L8, ("ranking",))
cobertura_nova = bloco(L8, rank, [], "estrato ranking (nunca avaliado ate aqui)") if rank else None

# ---------------------------------------------------------------- 3) pooled
p_resp = [("v1", i) for i in r_v1] + [("v2", i) for i in r_v2]
p_abst = [("v1", i) for i in a_v1] + [("v2", i) for i in a_v2]
MAP = {"v1": L4, "v2": L8}


def taxa_p(pares, sistema):
    ac = sum(MAP[v][sistema][i]["correto"] for v, i in pares)
    lo, hi = wilson(ac, len(pares))
    return {"n": len(pares), "acertos": ac, "taxa": round(ac / len(pares), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)],
            "largura_ic_pp": round((hi - lo) * 100, 1)}


mc_pool = mcnemar([MAP[v]["sql_cru"][i]["correto"] for v, i in p_resp],
                  [MAP[v]["tier_a"][i]["correto"] for v, i in p_resp])
pooled = {
    "rotulo": "POOLED v1+v2 (7 estratos originais) — poder maximo",
    "ressalva": "o TEST-v1 ja havia sido consumido na Fase 4 e nos deltas da Fase 7.",
    "tier_a": {"execution_accuracy": taxa_p(p_resp, "tier_a"),
               "abstencao": taxa_p(p_abst, "tier_a")},
    "sql_cru": {"execution_accuracy": taxa_p(p_resp, "sql_cru"),
                "abstencao": taxa_p(p_abst, "sql_cru")},
    "mcnemar_sqlcru_vs_tiera": mc_pool,
}

# ---------------------------------------------------------------- 4) o que o N comprou
def por_estrato(L, estratos):
    ta = L["tier_a"]
    out = {}
    for e in estratos:
        ids = [i for i, r in ta.items() if r["estrato"] == e]
        if ids:
            out[e] = taxa(ids, ta)
    return out


pe_v1, pe_v2 = por_estrato(L4, ORIGINAIS), por_estrato(L8, ORIGINAIS + ("ranking",))
larg_v1 = sorted(v["largura_ic_pp"] for v in pe_v1.values())
larg_v2 = sorted(v["largura_ic_pp"] for v in pe_v2.values())
med = lambda xs: xs[len(xs) // 2] if xs else None  # noqa: E731

poder = {
    "o_que_o_N_comprou": ("O ganho honesto de aumentar N nao e um EX mais alto — e um IC mais "
                          "estreito. Abaixo, a largura do IC de Wilson (em pontos percentuais)."),
    "ex_global_largura_ic_pp": {
        "v1": fase4_orig["tier_a"]["execution_accuracy"]["largura_ic_pp"],
        "v2": replicacao["tier_a"]["execution_accuracy"]["largura_ic_pp"],
        "pooled": pooled["tier_a"]["execution_accuracy"]["largura_ic_pp"],
    },
    "largura_ic_por_estrato_pp": {"v1_mediana": med(larg_v1), "v2_mediana": med(larg_v2),
                                  "v1": pe_v1 and {k: v["largura_ic_pp"] for k, v in pe_v1.items()},
                                  "v2": {k: v["largura_ic_pp"] for k, v in pe_v2.items()}},
}

rel = carimbar({
    "fase": "8_analise",
    "auditoria_gold_degenerado_v1": {
        "ids": sorted(DEGENERADOS_V1),
        "achado": ("2 itens do TEST-v1 tem gold constante entre as 3 variantes (receita de "
                   "transacoes FAILED/REVERSED = sempre 0), entao o Test-Suite EX nao protegia "
                   "contra falso positivo neles."),
        "sensibilidade": "comparar 'TEST-v1' com 'TEST-v1 SEM degenerados' abaixo.",
    },
    "replicacao_7_estratos_originais": {"fase4_v1": fase4_orig, "fase4_v1_sem_degenerados":
                                        fase4_sem_deg, "fase8_v2": replicacao},
    "cobertura_nova_ranking": cobertura_nova,
    "pooled": pooled,
    "poder_estatistico": poder,
    "ex_por_estrato": {"v1": pe_v1, "v2": pe_v2},
})
dest = REPO / "reports" / "fase8" / "analise.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------------- saída legível
def p(b):
    ex, ab = b["tier_a"]["execution_accuracy"], b["tier_a"]["abstencao"]
    sc = b["sql_cru"]["execution_accuracy"]
    print(f"\n{b['rotulo']}")
    print(f"  tier_a  EX={ex['taxa']} IC{ex['wilson_ic95']} (largura {ex['largura_ic_pp']}pp, "
          f"n={ex['n']})")
    print(f"  sql_cru EX={sc['taxa']} n={sc['n']}   | delta={b.get('delta_pp')}pp")
    if ab["n"]:
        print(f"  abstencao tier_a={ab['taxa']} (n={ab['n']})")
    print(f"  McNemar: {b['mcnemar_sqlcru_vs_tiera']}")


p(fase4_orig)
p(fase4_sem_deg)
p(replicacao)
if cobertura_nova:
    p(cobertura_nova)
print(f"\n{pooled['rotulo']}")
print(f"  tier_a  EX={pooled['tier_a']['execution_accuracy']}")
print(f"  sql_cru EX={pooled['sql_cru']['execution_accuracy']['taxa']}")
print(f"  McNemar: {pooled['mcnemar_sqlcru_vs_tiera']}")
print(f"\nlargura do IC (pp)  global: {poder['ex_global_largura_ic_pp']}")
print(f"                    por estrato (mediana): v1={med(larg_v1)}  v2={med(larg_v2)}")
print("\nEX do tier_a por estrato (v2):")
for k, v in sorted(pe_v2.items()):
    print(f"  {k:20s} {v['acertos']:3d}/{v['n']:3d} = {str(v['taxa']):6s} IC{v['wilson_ic95']} "
          f"(largura {v['largura_ic_pp']}pp)")
print(f"\n-> {dest}")
