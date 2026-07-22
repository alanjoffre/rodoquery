"""Fase 7c — volume: como o caminho governado escala com o tamanho dos dados.

**O que este teste PODE e NÃO PODE medir aqui (honestidade de escopo).**
No Tier-A o LLM produz uma *spec*; o SQL vem do MetricFlow. A spec **não depende do volume** — a
mesma pergunta gera a mesma spec com 2 mil ou 20 mil linhas. Logo, aumentar o volume **não testa a
correção do mapeamento** (o EX seria trivialmente igual). O que o volume testa de verdade é o
**custo de execução** do SQL governado: ele escala de forma sadia ou explode?

Então este script mede TEMPO DE EXECUÇÃO do SQL do MetricFlow em duas escalas, para specs
representativas dos estratos — e verifica que os resultados continuam bem-formados.

Uso: python rodar_volume.py [escala_grande]     (default 20000)
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

from rodoquery.gold import compilar_spec, executar_gold
from rodoquery.golden import carregar
from rodoquery.proveniencia import carimbar
from rodoquery.suite_dbs import construir_variante

REPO = Path(__file__).resolve().parent
ESCALA_GRANDE = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000
PEQUENO = Path.home() / "rodoquery_suite" / "toll_seed1.duckdb"     # escala 2.000
DESTINO = Path.home() / "rodoquery_suite"

# specs representativas: agregado simples, série temporal fina, join 2-dim, ratio, filtro
ALVOS = ["controle_trivial_01", "coalesce_nulo_01", "join_grao_02",
         "metrica_derivada_02", "valor_categorico_01"]

itens = {it.id: it for it in carregar(REPO / "golden" / "golden_test.jsonl")}
alvos = [itens[i] for i in ALVOS if i in itens]

print(f"construindo variante de escala {ESCALA_GRANDE} (seed 9)...")
t0 = time.perf_counter()
grande = construir_variante(9, ESCALA_GRANDE, DESTINO)
print(f"  pronta em {time.perf_counter() - t0:.1f}s -> {grande.name}")


def _linhas(db):
    import duckdb
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute("select count(*) from fct_toll_transactions").fetchone()[0]
    finally:
        con.close()


n_peq, n_gra = _linhas(PEQUENO), _linhas(grande)
print(f"  linhas na fato: pequeno={n_peq}  grande={n_gra}  ({n_gra / n_peq:.1f}x)")

medidas = []
for it in alvos:
    sql = compilar_spec(it.spec)                      # compila 1x (data-independente)
    tempos = {}
    linhas_out = {}
    for nome, db in (("pequeno", PEQUENO), ("grande", grande)):
        amostras = []
        for _ in range(3):
            t = time.perf_counter()
            r = executar_gold(sql, db)
            amostras.append(time.perf_counter() - t)
        tempos[nome] = round(st.median(amostras), 4)
        linhas_out[nome] = len(r)
    medidas.append({
        "id": it.id, "estrato": it.estrato,
        "execucao_s": tempos,
        "fator_tempo": (round(tempos["grande"] / tempos["pequeno"], 2)
                        if tempos["pequeno"] else None),
        "linhas_resultado": linhas_out,
        "resultado_bem_formado": linhas_out["grande"] > 0,
    })
    print(f"  {it.id:22s} {tempos['pequeno']:.4f}s -> {tempos['grande']:.4f}s "
          f"({medidas[-1]['fator_tempo']}x)")

fator_dados = round(n_gra / n_peq, 2)
fatores = [m["fator_tempo"] for m in medidas if m["fator_tempo"]]
rel = carimbar({
    "fase": "7c_volume",
    "escopo_honesto": ("No Tier-A a spec NAO depende do volume, entao volume nao testa a correcao "
                       "do mapeamento (o EX seria trivialmente igual). Este teste mede o CUSTO DE "
                       "EXECUCAO do SQL governado e a boa-formacao dos resultados."),
    "linhas_fato": {"pequeno": n_peq, "grande": n_gra, "fator_dados": fator_dados},
    "medidas": medidas,
    "fator_tempo_mediano": round(st.median(fatores), 2) if fatores else None,
    "escala_sublinear": (st.median(fatores) < fator_dados) if fatores else None,
    "todos_bem_formados": all(m["resultado_bem_formado"] for m in medidas),
})
dest = REPO / "reports" / "fase7" / "volume.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\ndados {fator_dados}x -> tempo mediano {rel['fator_tempo_mediano']}x "
      f"(sublinear={rel['escala_sublinear']})")
print(f"-> {dest}")
