"""Testes do validador AST — puros (sem banco), rodam no CI sem a fundação buildada."""
import pytest

from rodoquery.sandbox import _com_limite, validar_sql

ALLOW = {"fct_toll_transactions", "dim_plaza", "dim_date", "agg_daily_revenue_by_plaza"}


@pytest.mark.parametrize("sql", [
    "DROP TABLE main.fct_toll_transactions",
    "DELETE FROM main.dim_plaza",
    "INSERT INTO main.dim_plaza VALUES ('x')",
    "UPDATE main.dim_plaza SET plaza_name='x'",
    "CREATE TABLE evil AS SELECT 1",
    "ALTER TABLE main.dim_plaza ADD COLUMN x INT",
])
def test_bloqueia_ddl_dml(sql):
    assert not validar_sql(sql, ALLOW)


def test_bloqueia_multiplos_statements():
    v = validar_sql("SELECT 1; DROP TABLE main.dim_plaza", ALLOW)
    assert not v and "múltiplos" in v.motivo


@pytest.mark.parametrize("sql", [
    "ATTACH 'evil.duckdb' AS e",
    "INSTALL httpfs",
    "LOAD httpfs",
    "PRAGMA database_list",
    "SET memory_limit='100GB'",
])
def test_bloqueia_comandos_deny_by_default(sql):
    # o sqlglot cai p/ exp.Command em sintaxe desconhecida → bloqueado por padrão
    assert not validar_sql(sql, ALLOW)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM read_csv_auto('/etc/passwd')",
    "SELECT * FROM read_parquet('/x/**/*.parquet')",
    "SELECT * FROM glob('/**')",
    "SELECT * FROM duckdb_settings()",
])
def test_bloqueia_leitura_de_arquivo(sql):
    assert not validar_sql(sql, ALLOW)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM landing.raw_toll_transactions",          # raw/PII
    "SELECT * FROM main_elementary.dbt_models",             # observabilidade
    "SELECT * FROM information_schema.columns",             # introspecção
    "SELECT * FROM main.stg_toll_transactions",             # staging (fora da allowlist)
])
def test_bloqueia_fora_do_contrato_de_exposicao(sql):
    assert not validar_sql(sql, ALLOW)


def test_bloqueia_raw_escondido_em_cte():
    assert not validar_sql(
        "WITH x AS (SELECT * FROM landing.raw_vehicles) SELECT * FROM x", ALLOW
    )


@pytest.mark.parametrize("sql", [
    # P0 achado pela auditoria staff: table-valued functions leem o banco in-process (exfil PII)
    "SELECT * FROM query_table('landing.raw_vehicles')",
    "SELECT * FROM query('SELECT * FROM landing.raw_vehicles')",
    # P1: introspecção (schema/config/path) — funções anônimas fora da allowlist
    "SELECT * FROM duckdb_tables()",
    "SELECT * FROM duckdb_columns()",
    "SELECT * FROM duckdb_databases()",
    "SELECT * FROM pragma_table_info('fct_toll_transactions')",
    "SELECT current_setting('memory_limit')",
    "SELECT * FROM read_ndjson_auto('/etc/hostname')",
    "SELECT * FROM iceberg_scan('/tmp/t')",
])
def test_bloqueia_funcoes_exoticas_deny_by_default(sql):
    # regressão do bypass: anônima fora da allowlist falha FECHADO
    v = validar_sql(sql, ALLOW)
    assert not v and "deny-by-default" in v.motivo


@pytest.mark.parametrize("sql", [
    "SELECT plaza_id FROM main.dim_plaza EXCEPT SELECT plaza_id FROM main.fct_toll_transactions",
    "SELECT plaza_id FROM main.dim_plaza INTERSECT SELECT plaza_id FROM main.dim_plaza",
    "SELECT date_trunc('month', event_date), sum(amount_cents) "
    "FROM main.fct_toll_transactions GROUP BY 1",
])
def test_permite_setops_e_funcoes_de_analytics(sql):
    v = validar_sql(sql, ALLOW)
    assert v, f"falso positivo: {v.motivo}"


@pytest.mark.parametrize("sql", [
    "SELECT count(*) FROM main.fct_toll_transactions",
    "SELECT count(*) FROM fct_toll_transactions",                       # sem schema = main
    "SELECT plaza_id, sum(amount_cents) FROM main.fct_toll_transactions GROUP BY 1",
    "SELECT p.plaza_name FROM main.fct_toll_transactions f "
    "JOIN main.dim_plaza p ON p.plaza_id = f.plaza_id",
    "WITH d AS (SELECT event_date FROM main.fct_toll_transactions) SELECT * FROM d",
    "SELECT * FROM (SELECT plaza_id FROM main.fct_toll_transactions) t",
])
def test_permite_legitimas_sem_falso_positivo(sql):
    v = validar_sql(sql, ALLOW)
    assert v, f"falso positivo: {v.motivo}"


def test_sql_vazio_e_lixo():
    assert not validar_sql("", ALLOW)
    assert not validar_sql("isso não é sql", ALLOW)


def test_limite_e_forcado():
    envelopado = _com_limite("SELECT 1", 10)
    assert "limit 10" in envelopado.lower()
