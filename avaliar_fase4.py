"""Fase 4 — o sistema RodoQuery Tier-A vs o baseline sql_cru, no split escolhido.

Uso:  python avaliar_fase4.py [dev|test]   (default: test)

**Protocolo anti-vazamento:** desenvolve-se no DEV; a avaliação FINAL roda no TEST **uma vez**. As
predições de cada sistema são CONGELADAS em disco (`reports/fase4/predicoes_<sistema>_<split>.json`)
na 1ª execução — o SUT é estocástico (não-determinismo de GPU do llama.cpp mesmo com greedy+seed),
então congelar torna o número **reprodutível e auditável**. Reexecuções reusam o congelado.

Compara o MESMO SUT (qwen2.5-coder:7b) nas duas interfaces — spec governada (Tier-A) vs SQL cru
(baseline). Se Tier-A ganha, o mérito é do Semantic Layer, não de um modelo melhor. McNemar pareado
nos itens respondíveis dá o teste de significância.
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
REPO = Path.home() / "rodoquery"
itens = carregar(REPO / "golden" / f"golden_{split}.jsonl")
hashes = carregar_hashes_gold()
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
SISTEMAS = {"tier_a": tier_a, "sql_cru": sql_cru}

pred_dir = REPO / "reports" / "fase4"
pred_dir.mkdir(parents=True, exist_ok=True)
print(f"[{split}] {len(itens)} itens, {len(dbs)} variantes")

preds: dict[str, dict] = {}
for nome, fn in SISTEMAS.items():
    fp = pred_dir / f"predicoes_{nome}_{split}.json"
    if fp.exists():
        preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
        print(f"  {nome}: predições CONGELADAS reusadas ({fp.name})")
    else:
        print(f"  {nome}: coletando predições (1×)...")
        preds[nome] = coletar_predicoes(itens, fn)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")

avals = {n: avaliar_sistema(itens, None, hashes, dbs, n, predicoes=preds[n]) for n in SISTEMAS}

# McNemar pareado nos RESPONDÍVEIS (o head-to-head real da tese)
ids_resp = [it.id for it in itens if not it.eh_abstencao]
va, vb = vetor_correto(avals["tier_a"]), vetor_correto(avals["sql_cru"])
mc = mcnemar([va[i] for i in ids_resp], [vb[i] for i in ids_resp])

relatorio = carimbar({
    "fase": "4_sistema_tier_a",
    "split": split,
    "n": len(itens),
    "n_variantes_test_suite": len(dbs),
    "comparacao": "MESMO SUT (qwen2.5-coder:7b); só muda a interface: spec governada vs SQL cru.",
    "ressalva": ("SUT estocástico → predições congeladas (reprodutível). N por estrato < 25 (ICs "
                 "largos). Predições auditáveis em reports/fase4/predicoes_*.json."),
    "sistemas": {n: {k: v for k, v in avals[n].items() if k != "resultados"} for n in SISTEMAS},
    "mcnemar_tier_a_vs_sql_cru_respondiveis": mc,
    "resultados_por_item": {n: avals[n]["resultados"] for n in SISTEMAS},
})
dest = pred_dir / f"resultado_{split}.json"
dest.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n== {split.upper()} ==")
for n in SISTEMAS:
    ex = avals[n]["execution_accuracy_respondiveis"]
    ab = avals[n]["acuracia_abstencao"]
    print(f"  {n:9s} EX={ex['taxa']} IC{ex['wilson_ic95']}  | abstenção={ab['taxa']}")
print(f"  McNemar (respondíveis): {mc}")
print(f"\n-> {dest}")
