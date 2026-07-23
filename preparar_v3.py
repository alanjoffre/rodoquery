"""Fase 9 — gold do v3, regra anti-degenerado e selo. TODO o v3 é holdout (não há split de DEV).

Mesmos filtros de qualidade da Fase 8, aplicados ANTES de qualquer sistema rodar:
  - gold vazio em qualquer variante → fora (spec errada também devolve vazio e "acerta");
  - gold idêntico nas 3 variantes → fora (não depende dos dados, mesma armadilha).
"""
import collections
import hashlib
import json
import time
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.gold import compilar_spec, executar_gold
from rodoquery.golden import GOLD_ABSTER, carregar, salvar
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
DBS = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}

itens = carregar(G / "autor_v3.jsonl")
print(f"v3: {len(itens)} itens autorados", flush=True)

validos, descartados, respostas = [], [], []
t0 = time.perf_counter()
for i, it in enumerate(itens, 1):
    if it.eh_abstencao:
        validos.append(it)
        respostas.append({"id": it.id, "estrato": it.estrato, "sql_metricflow": None,
                          "n_variantes": 0, "hashes_por_variante": {}, "gold": GOLD_ABSTER})
        continue
    try:
        sql = compilar_spec(it.spec)
    except Exception as e:
        descartados.append({"id": it.id, "motivo": f"nao compila: {str(e)[:90]}"})
        continue
    hashes, vazio = {}, False
    for nome, db in DBS.items():
        linhas = executar_gold(sql, db)
        if not linhas:
            vazio = True
        hashes[nome] = hash_resultado(linhas, ordenado=it.spec.ordenado)
    if vazio:
        descartados.append({"id": it.id, "motivo": "gold vazio em alguma variante"})
        continue
    if len(set(hashes.values())) == 1:
        descartados.append({"id": it.id, "motivo": "gold constante entre variantes (degenerado)"})
        continue
    validos.append(it)
    respostas.append({"id": it.id, "estrato": it.estrato, "sql_metricflow": sql,
                      "n_variantes": len(hashes), "hashes_por_variante": hashes})
    if i % 30 == 0:
        print(f"  {i}/{len(itens)} ({time.perf_counter() - t0:.0f}s)", flush=True)

salvar(validos, G / "golden_test_v3.jsonl")
sha = hashlib.sha256((G / "golden_test_v3.jsonl").read_bytes()).hexdigest()
(G / "golden_test_v3.sha256").write_text(sha + "\n", encoding="utf-8")

rel = carimbar({
    "tipo": "gold_golden_v3_fase9",
    "papel": "holdout INTEGRAL p/ medir o conserto do prompt; gerado apos o texto estar fechado.",
    "n_autorados": len(itens), "n_validos": len(validos), "n_descartados": len(descartados),
    "descartados": descartados, "variantes": list(DBS), "respostas": respostas,
})
dest = REPO / "reports" / "fase9" / "gold_respostas_v3.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

c = collections.Counter(it.estrato for it in validos)
print(f"\nvalidos: {len(validos)}/{len(itens)}  {dict(sorted(c.items()))}")
print(f"descartados: {len(descartados)}")
for d in descartados[:10]:
    print(f"   {d['id']}: {d['motivo']}")
print(f"\nTEST-v3 selado sha256 = {sha}")
print(f"-> {dest}")
