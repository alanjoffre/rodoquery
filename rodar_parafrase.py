"""Fase 7a — held-out de PARÁFRASE: o teste que derruba memorização.

As perguntas do golden foram geradas por TEMPLATE (fraqueza que declarei nas fases 2/3). Se o
sistema aprendeu o *fraseado* em vez da *semântica*, reescrever as mesmas perguntas como um analista
real falaria derruba o EX. Se o EX segurar, a competência é semântica.

Protocolo (anti-viés):
  1. Paráfrases escritas por um LLM DIFERENTE (Claude), rotuladas como geradas por máquina.
  2. Um 2º LLM revisor, **cego ao desempenho**, validou equivalência; as 3 SUSPEITAS foram
     excluídas ANTES de rodar o sistema (golden/parafrases_veredito.json). Sem isso, uma queda
     mediria "paráfrase ruim", não fragilidade.
  3. Comparação PAREADA (mesmos ids) contra as predições CONGELADAS da Fase 4 → McNemar.
  4. O gabarito NÃO muda: a paráfrase tem a mesma resposta certa.
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
from rodoquery.golden import ItemGolden, carregar
from rodoquery.proveniencia import carimbar
from rodoquery.sistema import tier_a

REPO = Path(__file__).resolve().parent
F7 = REPO / "reports" / "fase7"
F7.mkdir(parents=True, exist_ok=True)

veredito = json.loads((REPO / "golden" / "parafrases_veredito.json").read_text(encoding="utf-8"))
excluidas = set(veredito["excluidas"])
_linhas_para = (REPO / "golden" / "parafrases_raw.jsonl").read_text(encoding="utf-8").splitlines()
paras = {d["id"]: d["parafrase"]
         for d in (json.loads(x) for x in _linhas_para if x.strip())}

orig = carregar(REPO / "golden" / "golden_test.jsonl")
# mesmos itens, MESMO gabarito, só a pergunta é reescrita
itens = [ItemGolden(id=it.id, pergunta_nl=paras[it.id], estrato=it.estrato, spec=it.spec)
         for it in orig if it.id not in excluidas]
ids = [it.id for it in itens]
print(f"held-out de parafrase: {len(itens)} itens ({len(excluidas)} excluidos por equivalencia)")

hashes = carregar_hashes_gold()
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}

fp = F7 / "predicoes_tier_a_parafrase.json"
if fp.exists():
    preds = json.loads(fp.read_text(encoding="utf-8"))
    print("  predicoes CONGELADAS reusadas")
else:
    preds = coletar_predicoes(itens, tier_a)
    fp.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")

av = avaliar_sistema(itens, None, hashes, dbs, "tier_a_parafrase", predicoes=preds)

# ---- baseline pareado: as predicoes ORIGINAIS congeladas da Fase 4, nos MESMOS ids -------------
f4 = json.loads((REPO / "reports" / "fase4" / "resultado_test.json").read_text(encoding="utf-8"))
orig_correto = {r["id"]: r["correto"] for r in f4["resultados_por_item"]["tier_a"]}
orig_abst = {r["id"]: r["abstencao"] for r in f4["resultados_por_item"]["tier_a"]}
novo_correto = vetor_correto(av)

resp = [i for i in ids if not orig_abst[i]]
abst = [i for i in ids if orig_abst[i]]


def _taxa(ids_, vetor):
    ac = sum(vetor[i] for i in ids_)
    lo, hi = wilson(ac, len(ids_))
    return {"n": len(ids_), "acertos": ac, "taxa": round(ac / len(ids_), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


ex_orig, ex_para = _taxa(resp, orig_correto), _taxa(resp, novo_correto)
ab_orig, ab_para = _taxa(abst, orig_correto), _taxa(abst, novo_correto)
mc = mcnemar([orig_correto[i] for i in resp], [novo_correto[i] for i in resp])
quebrou = [i for i in resp if orig_correto[i] and not novo_correto[i]]
consertou = [i for i in resp if not orig_correto[i] and novo_correto[i]]

rel = carimbar({
    "fase": "7a_heldout_parafrase",
    "protocolo": ("parafrases por LLM diferente; equivalencia validada por revisor CEGO ao "
                  "desempenho; 3 suspeitas excluidas ANTES de rodar; comparacao pareada nos "
                  "mesmos ids contra as predicoes congeladas da Fase 4."),
    "n_itens": len(itens), "excluidas_por_equivalencia": veredito["excluidas"],
    "execution_accuracy": {"original": ex_orig, "parafrase": ex_para,
                           "delta_pp": round((ex_para["taxa"] - ex_orig["taxa"]) * 100, 2)},
    "abstencao": {"original": ab_orig, "parafrase": ab_para,
                  "delta_pp": round((ab_para["taxa"] - ab_orig["taxa"]) * 100, 2)},
    "mcnemar_original_vs_parafrase": mc,
    "quebrou_com_parafrase": quebrou,
    "consertou_com_parafrase": consertou,
    "resultados": av["resultados"],
})
(F7 / "heldout_parafrase.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2),
                                           encoding="utf-8")

print(f"\nEX respondiveis  original={ex_orig['taxa']} IC{ex_orig['wilson_ic95']}")
print(f"EX respondiveis  parafrase={ex_para['taxa']} IC{ex_para['wilson_ic95']}  "
      f"delta={rel['execution_accuracy']['delta_pp']}pp")
print(f"Abstencao        original={ab_orig['taxa']}  parafrase={ab_para['taxa']}")
print(f"McNemar: {mc}")
print(f"quebrou: {quebrou}\nconsertou: {consertou}")
print(f"-> {F7 / 'heldout_parafrase.json'}")
