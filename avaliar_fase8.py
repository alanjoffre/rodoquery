"""Fase 8 — os mesmos dois sistemas da Fase 4, agora no TEST-v2 (holdout fresco, N maior).

**O sistema NÃO foi tocado.** Prompt, catálogo e SUT são byte a byte os da Fase 4. Isto é uma
REPLICAÇÃO, não um novo desenvolvimento — por isso vale como evidência independente, e por isso o
estrato `ranking` é um teste honesto: o prompt tem uma regra sobre ranking que nenhum item da v1
jamais avaliou. Se ele falhar ali, o achado é "regra de prompt não avaliada não funciona", não um
bug que eu conserto depois de ver o resultado.

Uso: python avaliar_fase8.py [dev|test]   (default: test)
"""
import json
import sys
from pathlib import Path

from rodoquery.avaliacao import (
    avaliar_sistema,
    carregar_hashes_gold,
    coletar_predicoes,
    vetor_correto,
)
from rodoquery.baselines import sql_cru
from rodoquery.estat import mcnemar
from rodoquery.golden import carregar
from rodoquery.proveniencia import carimbar
from rodoquery.sistema import tier_a

split = (sys.argv[1] if len(sys.argv) > 1 else "test").lower()
assert split in ("dev", "test")
REPO = Path(__file__).resolve().parent
itens = carregar(REPO / "golden" / f"golden_{split}_v2.jsonl")
hashes = carregar_hashes_gold(REPO / "reports" / "fase8" / "gold_respostas_v2.json")
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
SISTEMAS = {"tier_a": tier_a, "sql_cru": sql_cru}

pred_dir = REPO / "reports" / "fase8"
pred_dir.mkdir(parents=True, exist_ok=True)
print(f"[{split}-v2] {len(itens)} itens, {len(dbs)} variantes", flush=True)

preds: dict[str, dict] = {}
for nome, fn in SISTEMAS.items():
    fp = pred_dir / f"predicoes_{nome}_{split}_v2.json"
    if fp.exists():
        preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
        print(f"  {nome}: predicoes CONGELADAS reusadas ({fp.name})", flush=True)
    else:
        print(f"  {nome}: coletando predicoes (1x)...", flush=True)
        preds[nome] = coletar_predicoes(itens, fn)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {nome}: congeladas em {fp.name}", flush=True)

avals = {n: avaliar_sistema(itens, None, hashes, dbs, n, predicoes=preds[n]) for n in SISTEMAS}

ids_resp = [it.id for it in itens if not it.eh_abstencao]
va, vb = vetor_correto(avals["tier_a"]), vetor_correto(avals["sql_cru"])
mc = mcnemar([va[i] for i in ids_resp], [vb[i] for i in ids_resp])

relatorio = carimbar({
    "fase": "8_replicacao_N_maior",
    "split": f"{split}_v2",
    "n": len(itens),
    "n_variantes_test_suite": len(dbs),
    "sistema_inalterado": ("prompt/catalogo/SUT identicos aos da Fase 4 — replicacao, nao "
                           "desenvolvimento. Nenhum ajuste foi feito com base no TEST-v2."),
    "golden_v2": ("specs INEDITAS (nenhuma repete a v1); regra anti-degenerado aplicada (gold "
                  "constante entre variantes = fora); estrato `ranking` novo."),
    "sistemas": {n: {k: v for k, v in avals[n].items() if k != "resultados"} for n in SISTEMAS},
    "mcnemar_tier_a_vs_sql_cru_respondiveis": mc,
    "resultados_por_item": {n: avals[n]["resultados"] for n in SISTEMAS},
})
dest = pred_dir / f"resultado_{split}_v2.json"
dest.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n== {split.upper()}-v2 ==")
for n in SISTEMAS:
    ex = avals[n]["execution_accuracy_respondiveis"]
    ab = avals[n]["acuracia_abstencao"]
    print(f"  {n:9s} EX={ex['taxa']} IC{ex['wilson_ic95']}  | abstencao={ab['taxa']}")
print(f"  McNemar (respondiveis): {mc}")
print("\n  EX do tier_a por estrato:")
for e, v in sorted(avals["tier_a"]["ex_por_estrato"].items()):
    print(f"    {e:20s} {v['acertos']:3d}/{v['n']:3d} = {v['taxa']:.3f} IC{v['wilson_ic95']}")
print(f"\n-> {dest}")
