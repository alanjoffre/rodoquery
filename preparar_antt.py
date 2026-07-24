"""Fase 12 — gold do golden ANTT via MetricFlow, sobre as 3 variantes REAIS, e selo do TEST.

Anti-circularidade intacta: o gold sai SEMPRE do MetricFlow, nunca de SQL à mão.
Filtros de qualidade (herdados das Fases 8/9), agora como rede de segurança — as guardas de
geração já deveriam ter evitado tudo isto:
  - não compila            → fora
  - gold vazio em qualquer variante → fora (spec errada também devolve vazio e "acerta")
  - gold IDÊNTICO nas 3 variantes   → fora (não depende dos dados; sem proteção de test-suite)

Split 15% DEV / 85% TEST: o sistema está congelado, quase tudo pode ir para o holdout.
"""
import collections
import hashlib
import json
import time
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT, compilar_spec, executar_gold
from rodoquery.golden import GOLD_ABSTER, carregar, dividir_dev_test, resumo_estratos, salvar
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
for db in DBS.values():
    if not db.exists():
        raise SystemExit(f"variante ausente: {db}")

itens = carregar(G / "autor_antt.jsonl")
print(f"golden ANTT: {len(itens)} itens autorados", flush=True)

validos, descartados, respostas = [], [], []
t0 = time.perf_counter()
for i, it in enumerate(itens, 1):
    if it.eh_abstencao:
        validos.append(it)
        respostas.append({"id": it.id, "estrato": it.estrato, "sql_metricflow": None,
                          "n_variantes": 0, "hashes_por_variante": {}, "gold": GOLD_ABSTER})
        continue
    try:
        sql = compilar_spec(it.spec, fundacao=FUNDACAO_ANTT)
    except Exception as e:
        descartados.append({"id": it.id, "motivo": f"nao compila: {str(e)[:90]}"})
        continue
    hashes, vazio = {}, False
    try:
        for nome, db in DBS.items():
            linhas = executar_gold(sql, db)
            if not linhas:
                vazio = True
            hashes[nome] = hash_resultado(linhas, ordenado=it.spec.ordenado)
    except Exception as e:
        descartados.append({"id": it.id, "motivo": f"nao executa: {str(e)[:90]}"})
        continue
    if vazio:
        descartados.append({"id": it.id, "motivo": "gold vazio em alguma variante"})
        continue
    if len(set(hashes.values())) == 1:
        descartados.append({"id": it.id, "motivo": "gold constante entre variantes (degenerado)"})
        continue
    validos.append(it)
    respostas.append({"id": it.id, "estrato": it.estrato, "sql_metricflow": sql,
                      "n_variantes": len(hashes), "hashes_por_variante": hashes})
    if i % 25 == 0:
        print(f"  {i}/{len(itens)} ({time.perf_counter() - t0:.0f}s)", flush=True)

salvar(validos, G / "golden_antt.jsonl")

dev, test = dividir_dev_test(validos, frac_dev=0.15, seed=42)
salvar(dev, G / "golden_dev_antt.jsonl")
salvar(test, G / "golden_test_antt.jsonl")
sha = hashlib.sha256((G / "golden_test_antt.jsonl").read_bytes()).hexdigest()
(G / "golden_test_antt.sha256").write_text(sha + "\n", encoding="utf-8")

rel = carimbar({
    "tipo": "gold_golden_antt_fase12",
    "fundacao": "ANTT real (CC-BY), 3 variantes = partições disjuntas por hash",
    "anti_circularidade": "gold sempre do MetricFlow; nunca SQL escrito à mão",
    "n_autorados": len(itens), "n_validos": len(validos), "n_descartados": len(descartados),
    "descartados": descartados, "variantes": list(DBS), "respostas": respostas,
    "sha256_test": sha,
})
dest = REPO / "reports" / "fase12" / "gold_respostas_antt.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

c = collections.Counter(it.estrato for it in validos)
print(f"\nvalidos: {len(validos)}/{len(itens)}  {dict(sorted(c.items()))}")
print(f"descartados: {len(descartados)}")
for d in descartados[:12]:
    print(f"   {d['id']}: {d['motivo']}")
print(f"\nDEV : {len(dev)}  {resumo_estratos(dev)}")
print(f"TEST: {len(test)}  {resumo_estratos(test)}")
print(f"TEST-ANTT selado sha256 = {sha}")
print(f"-> {dest}")
