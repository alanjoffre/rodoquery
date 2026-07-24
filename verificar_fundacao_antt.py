"""Fase 11 — fumaça da fundação REAL da ANTT ponta a ponta, pelo caminho do RodoQuery.

Verifica o que precisa ser verdade antes de gerar qualquer golden set:
  1. a spec compila via MetricFlow contra a fundação ANTT;
  2. o SQL é PORTÁVEL — roda nas 3 variantes disjuntas;
  3. o resultado VARIA entre variantes (senão o Test-Suite EX não protege contra falso positivo);
  4. os números batem com a verdade calculada em SQL puro sobre a base completa.
"""
import duckdb

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT, Spec, compilar_spec, executar_gold

VARIANTES = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}

CASOS = [
    ("volume total", Spec(metrics=["traffic_volume"])),
    ("volume por mês", Spec(metrics=["traffic_volume"], group_by=["metric_time__month"],
                            order_by=["metric_time__month"])),
    ("taxa de automação por concessionária",
     Spec(metrics=["automation_rate"], group_by=["plaza__concessionaria"])),
    ("top 5 praças por volume",
     Spec(metrics=["traffic_volume"], group_by=["plaza__praca"],
          order_by=["-traffic_volume"], limit=5, ordenado=True)),
    ("volume de motos por dia",
     Spec(metrics=["traffic_volume"], group_by=["metric_time__day"],
          where="{{ Dimension('plaza__tipo_de_veiculo') }} = 'Moto'",
          order_by=["metric_time__day"])),
    ("as duas razões por sentido",
     Spec(metrics=["automation_rate", "commercial_share"], group_by=["plaza__sentido"])),
]

for db in VARIANTES.values():
    if not db.exists():
        raise SystemExit(f"variante ausente: {db} — rode ~/antt-foundation/construir_variantes.py")

print(f"fundação ANTT: {settings.antt_dbt_dir}")
print(f"variantes: {[str(p.name) for p in VARIANTES.values()]}\n")

falhas = 0
for nome, spec in CASOS:
    try:
        sql = compilar_spec(spec, fundacao=FUNDACAO_ANTT)
    except Exception as e:
        print(f"[FALHA] {nome}: não compila — {str(e)[:120]}")
        falhas += 1
        continue
    hashes, linhas = {}, {}
    erro = None
    for v, db in VARIANTES.items():
        try:
            r = executar_gold(sql, db)
            hashes[v] = hash_resultado(r, ordenado=spec.ordenado)
            linhas[v] = len(r)
        except Exception as e:
            erro = f"{v}: {type(e).__name__}: {str(e)[:80]}"
            break
    if erro:
        print(f"[FALHA] {nome}: não executa — {erro}")
        falhas += 1
        continue
    varia = len(set(hashes.values())) > 1
    marca = "OK " if varia else "AVISO"
    print(f"[{marca}] {nome}: linhas={list(linhas.values())} "
          f"{'hashes distintos entre variantes' if varia else 'HASH CONSTANTE (degenerado)'}")
    if not varia:
        falhas += 1

print("\n--- confronto com a verdade (base completa) ---")
con = duckdb.connect(str(settings.antt_duckdb), read_only=True)
verdade_vol, verdade_aut = con.execute("""
    select sum(volume),
           sum(case when tipo_cobranca = 'Automática' then volume else 0 end) / sum(volume)
    from main.fct_traffic_volume
""").fetchone()
con.close()

sql_vol = compilar_spec(Spec(metrics=["traffic_volume"]), fundacao=FUNDACAO_ANTT)
sql_aut = compilar_spec(Spec(metrics=["automation_rate"]), fundacao=FUNDACAO_ANTT)
mf_vol = executar_gold(sql_vol, settings.antt_duckdb)[0][0]
mf_aut = executar_gold(sql_aut, settings.antt_duckdb)[0][0]
ok_vol = abs(float(mf_vol) - float(verdade_vol)) < 1
ok_aut = abs(float(mf_aut) - float(verdade_aut)) < 1e-6
print(f"  volume  : mf={float(mf_vol):,.0f}  sql={float(verdade_vol):,.0f}  "
      f"{'OK' if ok_vol else 'DIVERGE'}")
print(f"  automação: mf={float(mf_aut):.6f}  sql={float(verdade_aut):.6f}  "
      f"{'OK' if ok_aut else 'DIVERGE'}")
falhas += (not ok_vol) + (not ok_aut)

print(f"\n{'FUNDAÇÃO ANTT PRONTA' if not falhas else f'{falhas} PROBLEMA(S)'}")
raise SystemExit(1 if falhas else 0)
