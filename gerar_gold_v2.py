"""Fase 8 — gold do golden v2 (expansão de N), com os mesmos mecanismos anti-circularidade da v2.

O gold sai SEMPRE do MetricFlow. Aqui, além disso, aplico dois filtros de qualidade que a v1 não
tinha explicitamente:

1. **Não-vazio em TODAS as variantes.** Um item cujo resultado é vazio é um falso positivo à
   espera: uma spec ERRADA também devolve vazio e "acerta". A v1 checava vazio só no banco
   principal; aqui exijo não-vazio nas 3 seeds.
2. **Aviso de gold constante entre variantes.** Se o hash é igual nas 3 seeds, o resultado não
   depende dos dados — sinal de item degenerado. Não dropo automaticamente (pode ser legítimo,
   ex. contagem de categorias), mas reporto para auditoria.

NÃO reconstrói o test-suite: as variantes já existem e o gold da v1 foi computado nelas. Reconstruir
mudaria os dados sob o gold antigo.
"""
import json
import time
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.gold import compilar_spec, executar_gold
from rodoquery.golden import GOLD_ABSTER, carregar, salvar
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
SUITE = Path.home() / "rodoquery_suite"
DBS = {f"seed{s}": SUITE / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}

for db in DBS.values():
    if not db.exists():
        raise SystemExit(f"variante ausente: {db} — NAO reconstrua (invalidaria o gold da v1)")

itens = carregar(G / "autor_v2.jsonl")
print(f"v2: {len(itens)} itens autorados; gerando gold em {len(DBS)} variantes...")

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
        descartados.append({"id": it.id,
                            "motivo": f"nao compila: {type(e).__name__}: {str(e)[:110]}"})
        continue
    hashes, vazio_em = {}, []
    for nome, db in DBS.items():
        linhas = executar_gold(sql, db)
        if not linhas:
            vazio_em.append(nome)
        hashes[nome] = hash_resultado(linhas, ordenado=it.spec.ordenado)
    if vazio_em:
        descartados.append({"id": it.id,
                            "motivo": f"gold VAZIO em {vazio_em} (risco de falso positivo)"})
        continue
    validos.append(it)
    respostas.append({"id": it.id, "estrato": it.estrato, "sql_metricflow": sql,
                      "n_variantes": len(hashes), "hashes_por_variante": hashes})
    if i % 25 == 0:
        print(f"  {i}/{len(itens)}  ({time.perf_counter() - t0:.0f}s)")

constantes = [r["id"] for r in respostas
              if r["hashes_por_variante"] and len(set(r["hashes_por_variante"].values())) == 1]

salvar(validos, G / "golden_v2.jsonl")
gold = carimbar({
    "tipo": "gold_golden_v2_fase8",
    "metodo": "Test-Suite EX — gold = hashes MetricFlow por variante; predito bate em TODAS.",
    "filtros_de_qualidade": {
        "nao_vazio_em_todas_as_variantes": True,
        "motivo": "gold vazio e falso positivo a espera: spec errada tambem devolve vazio.",
    },
    "n_autorados": len(itens), "n_validos": len(validos), "n_descartados": len(descartados),
    "descartados": descartados,
    "gold_constante_entre_variantes": {
        "n": len(constantes), "ids": constantes,
        "leitura": "hash igual nas 3 seeds = resultado nao depende dos dados; auditar.",
    },
    "variantes": list(DBS),
    "respostas": respostas,
})
dest = REPO / "reports" / "fase8" / "gold_respostas_v2.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")

import collections  # noqa: E402

c = collections.Counter(it.estrato for it in validos)
print(f"\nvalidos: {len(validos)}/{len(itens)}  {dict(sorted(c.items()))}")
print(f"descartados: {len(descartados)}")
for d in descartados[:15]:
    print(f"   {d['id']}: {d['motivo']}")
print(f"gold constante entre variantes: {len(constantes)} {constantes[:8]}")
print(f"-> {dest}")
