"""Fase 3b — roda os baselines no split DEV e gera o relatório com estatística honesta.

Sistemas avaliados:
  - sql_cru       : LLM escreve SQL direto sobre o schema cru (o baseline que a tese precisa bater)
  - sempre_abster : piso trivial (abstém sempre) — prova que o scorer não dá acerto de graça

Referência (NÃO é sistema): o "oráculo semântico" acerta 100% dos respondíveis por CONSTRUÇÃO
(o gold É a saída do Semantic Layer) e sabe abster no fora-de-escopo (vocabulário fechado). É o
teto; o sistema REAL Tier-A (NL→spec via LLM) é a Fase 4, e é lá que entra o McNemar pareado
Tier-A × sql_cru. Aqui estabelecemos só os baselines, com IC de Wilson e ressalva de N.
"""
import json
from pathlib import Path

from rodoquery.avaliacao import avaliar_sistema, carregar_hashes_gold, vetor_correto
from rodoquery.baselines import sempre_abster, sql_cru
from rodoquery.estat import mcnemar
from rodoquery.golden import carregar
from rodoquery.proveniencia import carimbar

REPO = Path.home() / "rodoquery"
DEV = carregar(REPO / "golden" / "golden_dev.jsonl")
hashes_gold = carregar_hashes_gold()
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}

print(f"avaliando {len(DEV)} itens do DEV em {len(dbs)} variantes...")

aval_cru = avaliar_sistema(DEV, sql_cru, hashes_gold, dbs, "sql_cru")
print(f"  sql_cru: EX={aval_cru['execution_accuracy_respondiveis']['taxa']} "
      f"abst={aval_cru['acuracia_abstencao']['taxa']}")
aval_triv = avaliar_sistema(DEV, sempre_abster, hashes_gold, dbs, "sempre_abster")
print(f"  sempre_abster: EX={aval_triv['execution_accuracy_respondiveis']['taxa']} "
      f"abst={aval_triv['acuracia_abstencao']['taxa']}")

# McNemar pareado no eixo RESPONDÍVEL (sql_cru vs piso): sanidade do scorer.
va, vt = vetor_correto(aval_cru), vetor_correto(aval_triv)
ids_resp = [r["id"] for r in aval_cru["resultados"] if not r["abstencao"]]
mc = mcnemar([va[i] for i in ids_resp], [vt[i] for i in ids_resp])

relatorio = carimbar({
    "fase": "3b_baselines",
    "split": "DEV",
    "n_dev": len(DEV),
    "n_variantes_test_suite": len(dbs),
    "ressalva_N": ("N por estrato abaixo da meta pré-registrada (>=25). ICs largos de propósito; "
                   "expandir o golden é backlog. TEST (53) segue selado p/ a avaliação final."),
    "referencia_oraculo_semantico": ("teto por construção: EX=1.0 nos respondíveis (o gold É a "
                                     "saída do Semantic Layer). Tier-A × sql_cru real = Fase 4."),
    "sistemas": {
        "sql_cru": {k: v for k, v in aval_cru.items() if k != "resultados"},
        "sempre_abster": {k: v for k, v in aval_triv.items() if k != "resultados"},
    },
    "mcnemar_respondiveis_sqlcru_vs_piso": mc,
    "resultados_por_item": {
        "sql_cru": aval_cru["resultados"],
        "sempre_abster": aval_triv["resultados"],
    },
})

dest = REPO / "reports" / "fase3" / "baselines.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n-> {dest}")
print("\nEX por estrato (sql_cru):")
for e, m in aval_cru["ex_por_estrato"].items():
    print(f"  {e:20s} {m['acertos']}/{m['n']}  ({m['taxa']:.0%})  IC95 {m['wilson_ic95']}")
