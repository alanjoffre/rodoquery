"""Fase 7b — roda o Tier-A com o catálogo de identificadores OFUSCADOS e mede a queda.

Mesmas perguntas do TEST, mesmo gabarito, mesma pipeline — só os identificadores do catálogo
viraram códigos opacos (revenue→m03, transaction__plaza→d04...), com as MESMAS descrições.
Comparação PAREADA contra as predições congeladas da Fase 4.
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
from rodoquery.perturbacao import tier_a_opaco
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
F7 = REPO / "reports" / "fase7"
F7.mkdir(parents=True, exist_ok=True)

itens = carregar(REPO / "golden" / "golden_test.jsonl")
hashes = carregar_hashes_gold()
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
print(f"perturbacao de schema (alias opaco): {len(itens)} itens do TEST")

fp = F7 / "predicoes_tier_a_opaco.json"
if fp.exists():
    preds = json.loads(fp.read_text(encoding="utf-8"))
    print("  predicoes CONGELADAS reusadas")
else:
    preds = coletar_predicoes(itens, tier_a_opaco)
    fp.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")

av = avaliar_sistema(itens, None, hashes, dbs, "tier_a_opaco", predicoes=preds)

f4 = json.loads((REPO / "reports" / "fase4" / "resultado_test.json").read_text(encoding="utf-8"))
orig = {r["id"]: r["correto"] for r in f4["resultados_por_item"]["tier_a"]}
abst = {r["id"]: r["abstencao"] for r in f4["resultados_por_item"]["tier_a"]}
novo = vetor_correto(av)

resp = [it.id for it in itens if not abst[it.id]]
absten = [it.id for it in itens if abst[it.id]]


def _taxa(ids_, vetor):
    ac = sum(vetor[i] for i in ids_)
    lo, hi = wilson(ac, len(ids_))
    return {"n": len(ids_), "acertos": ac, "taxa": round(ac / len(ids_), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


ex_o, ex_p = _taxa(resp, orig), _taxa(resp, novo)
ab_o, ab_p = _taxa(absten, orig), _taxa(absten, novo)
mc = mcnemar([orig[i] for i in resp], [novo[i] for i in resp])
alias_invalido = [i for i, p in preds.items() if p["meta"].get("alias_invalido")]

rel = carimbar({
    "fase": "7b_perturbacao_schema",
    "perturbacao": ("identificadores do catalogo trocados por codigos opacos (m01..m07, d01..d05, "
                    "t_dia/t_sem/t_mes), MESMAS descricoes. O gabarito nao muda; traduzimos o "
                    "alias de volta antes de compilar no MetricFlow."),
    "execution_accuracy": {"nomes_reais": ex_o, "alias_opaco": ex_p,
                           "delta_pp": round((ex_p["taxa"] - ex_o["taxa"]) * 100, 2)},
    "abstencao": {"nomes_reais": ab_o, "alias_opaco": ab_p,
                  "delta_pp": round((ab_p["taxa"] - ab_o["taxa"]) * 100, 2)},
    "mcnemar_reais_vs_opaco": mc,
    "quebrou": [i for i in resp if orig[i] and not novo[i]],
    "codigos_inventados_pelo_modelo": alias_invalido,
    "resultados": av["resultados"],
})
(F7 / "perturbacao_schema.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2),
                                            encoding="utf-8")

print(f"\nEX respondiveis  nomes reais={ex_o['taxa']} IC{ex_o['wilson_ic95']}")
print(f"EX respondiveis  alias opaco={ex_p['taxa']} IC{ex_p['wilson_ic95']}  "
      f"delta={rel['execution_accuracy']['delta_pp']}pp")
print(f"Abstencao        reais={ab_o['taxa']}  opaco={ab_p['taxa']}")
print(f"McNemar: {mc}")
print(f"codigos inventados: {alias_invalido}")
print(f"-> {F7 / 'perturbacao_schema.json'}")
