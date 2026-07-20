"""Fase 2 — gera o GOLD do golden set com Test-Suite Execution Accuracy.

1) Reconstrói N variantes de banco (seeds distintas) num diretório PERSISTENTE.
2) Para cada item: compila a spec no MetricFlow (1×, data-independente) e faz o hash do resultado
   em CADA variante. O gold = conjunto de hashes por variante (predito tem de bater em TODAS).
3) Sela o gold (sha256) e carimba proveniência.
"""
import json
from pathlib import Path

from rodoquery.golden import carregar, gerar_respostas, selar
from rodoquery.proveniencia import carimbar
from rodoquery.suite_dbs import construir_suite

REPO = Path.home() / "rodoquery"
DESTINO = Path.home() / "rodoquery_suite"
SEEDS = [1, 2, 3]
ESCALA = 2000

print(f"[1/3] reconstruindo {len(SEEDS)} variantes (escala={ESCALA}) em {DESTINO}...")
suite = construir_suite(SEEDS, ESCALA, DESTINO)
(REPO / "reports" / "fase0" / "suite_dbs.json").write_text(
    json.dumps(suite, ensure_ascii=False, indent=2), encoding="utf-8")
dbs = {f"seed{v['seed']}": Path(v["duckdb"]) for v in suite["variantes"]}
print("  variantes:", {k: str(v) for k, v in dbs.items()})

print("[2/3] gerando gold (compila spec + hash por variante)...")
itens = carregar(REPO / "golden" / "golden.jsonl")
respostas = gerar_respostas(itens, dbs)

# checagem de sanidade: o hash é IGUAL entre variantes? (não deveria — dados diferentes)
distintos = sum(1 for r in respostas if len(set(r["hashes_por_variante"].values())) > 1)
print(f"  itens c/ hash distinto entre variantes: {distintos}/{len(respostas)} "
      f"(esperado alto — variantes têm dados diferentes)")

gold = carimbar({
    "tipo": "gold_golden_set_fase2",
    "metodo": "Test-Suite Execution Accuracy — gold = hashes MetricFlow por variante; "
              "predito precisa bater em TODAS as variantes.",
    "n_itens": len(respostas),
    "variantes": list(dbs.keys()),
    "respostas": respostas,
})
dest = REPO / "reports" / "fase2" / "gold_respostas.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")

print("[3/3] selando golden.jsonl (pré-registro anti-vazamento)...")
sha = selar(REPO / "golden" / "golden.jsonl")
(REPO / "golden" / "golden.sha256").write_text(sha + "\n", encoding="utf-8")

print(f"\nOK  gold -> {dest}")
print(f"    golden.jsonl sha256 = {sha}")
