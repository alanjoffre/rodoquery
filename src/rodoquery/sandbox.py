"""Sandbox — a fronteira de segurança do agente (Fase 1).

**Princípio staff: nunca confie no LLM para ENFORÇAR segurança.** O prompt pode *pedir* "só
SELECT"; quem *garante* é este validador, em código, sobre a AST. Se a segurança vive no prompt,
vale zero — um revisor derruba na primeira tentativa de `ATTACH`.

Defesa em profundidade (3 camadas independentes):
  1. **Validador AST (sqlglot)** — só `SELECT`, statement único, allowlist de tabelas, bloqueio de
     DDL/DML, de funções que leem arquivo (`read_parquet`/`read_csv`/`glob`) e de comandos
     (`ATTACH`/`COPY`/`INSTALL`/`LOAD`/`PRAGMA`/`SET`).
  2. **Conexão endurecida** — `read_only=True` + `enable_external_access=false` (mata httpfs e
     leitura de arquivo) + `lock_configuration=true` (o SQL não consegue afrouxar config).
  3. **Limites de recurso** — `LIMIT` forçado, timeout por watchdog (`interrupt`), memory_limit.

**Deny-by-default em DUAS frentes** (a auditoria staff de 2026-07 pegou um bypass quando só uma
delas existia — `query_table('landing.raw_vehicles')` exfiltrava PII):
  - **Comandos:** o sqlglot rebaixa sintaxe desconhecida a `exp.Command`, que bloqueamos inteiro —
    `ATTACH`/`INSTALL`/`LOAD` e comandos futuros já nascem barrados.
  - **Funções:** as que o sqlglot NÃO tipa viram `exp.Anonymous` — e aqui vivem os vetores de
    exfiltração (`query`, `query_table` leem o banco in-process; `duckdb_tables/columns`,
    `current_setting`, `read_ndjson_auto`, `iceberg_scan` vazam schema/config/arquivo). Por isso
    **anônima fora da `_ANON_PERMITIDAS` é REJEITADA** — allowlist, não blocklist. Uma função
    exótica futura falha fechado, não aberto.

Nota honesta: as camadas 2 e 3 existem porque a 1 pode ter bug. Nenhuma delas depende do modelo.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import duckdb
import sqlglot
from sqlglot import exp

from rodoquery.config import REPO_ROOT, settings

SCHEMA_SERVING = "main"
LIMITE_LINHAS_PADRAO = 1_000
TIMEOUT_S_PADRAO = 15.0

# Blocklist de funções que o sqlglot TIPA (têm classe própria) mas são perigosas — backstop.
# A defesa primária contra funções é a ALLOWLIST de anônimas abaixo (deny-by-default).
_FUNCOES_TIPADAS_PROIBIDAS = {
    "read_parquet", "parquet_scan", "read_csv", "read_csv_auto", "csv_scan",
    "read_json", "read_json_auto", "read_text", "read_blob", "glob",
}
# ALLOWLIST de funções ANÔNIMAS (que o sqlglot NÃO tipa). Deny-by-default: qualquer anônima fora
# desta lista é REJEITADA. É isto que mata `query`/`query_table` (exfiltra dado in-process),
# `duckdb_tables/columns/databases`, `current_setting`, `pragma_table_info`, `iceberg_scan`,
# `parquet_metadata`, `read_ndjson_auto` — e qualquer função exótica FUTURA, sem manter blocklist.
# Só funções escalares/agregadas/janela comprovadamente seguras de analytics entram aqui.
_ANON_PERMITIDAS = {
    # data/tempo
    "date_trunc", "date_part", "datepart", "date_diff", "datediff", "date_add", "dateadd",
    "strftime", "strptime", "epoch", "epoch_ms", "make_date", "last_day", "monthname", "dayname",
    "dayofweek", "dayofyear", "weekofyear", "yearweek", "time_bucket",
    # string
    "split_part", "str_split", "string_split", "regexp_matches", "regexp_replace",
    "regexp_extract", "starts_with", "ends_with", "contains", "printf", "format", "concat_ws",
    "levenshtein", "editdist3",
    # numérico / agregação / janela
    "greatest", "least", "ifnull", "nvl", "nullif", "div", "mod", "log2", "log10",
    "percentile_cont", "percentile_disc", "median", "mode", "arg_max", "arg_min",
    "first", "last", "any_value", "bool_and", "bool_or", "count_if",
    "approx_count_distinct", "approx_quantile", "regr_slope",
    # listas (comuns em duckdb analytics)
    "list", "list_aggregate", "array_agg", "string_agg", "histogram",
}
# Nós de AST que nunca podem aparecer (DDL/DML/comandos).
_NOS_PROIBIDOS = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
    exp.Command,      # catch-all do sqlglot p/ ATTACH/INSTALL/LOAD/PRAGMA/etc.
    exp.Set, exp.Use, exp.Copy,
)
# SELECT e set-operations legítimas no topo (EXCEPT/INTERSECT são analytics válido).
_RAIZES_OK = (exp.Select, exp.Union, exp.Except, exp.Intersect, exp.Subquery, exp.With)


@dataclass(frozen=True)
class Veredito:
    ok: bool
    motivo: str = ""

    def __bool__(self) -> bool:
        return self.ok


def carregar_allowlist(catalogo: Path | None = None) -> set[str]:
    """A allowlist vem do catálogo GERADO (marts Gold) — nunca de uma lista escrita à mão."""
    caminho = catalogo or (REPO_ROOT / "reports" / "fase0" / "catalog.json")
    cat = json.loads(caminho.read_text(encoding="utf-8"))
    return set(cat["tabelas"])


def validar_sql(sql: str, allowlist: set[str]) -> Veredito:
    """Valida na AST. Devolve Veredito(ok=False, motivo) para qualquer coisa fora do contrato."""
    if not sql or not sql.strip():
        return Veredito(False, "sql vazio")
    try:
        statements = sqlglot.parse(sql, dialect="duckdb")
    except Exception as e:
        return Veredito(False, f"não parseia: {type(e).__name__}")

    statements = [s for s in statements if s is not None]
    if len(statements) == 0:
        return Veredito(False, "sem statement")
    if len(statements) > 1:
        return Veredito(False, "múltiplos statements (;-stacking)")

    raiz = statements[0]
    if not isinstance(raiz, _RAIZES_OK):
        return Veredito(False, f"não é SELECT: {type(raiz).__name__}")

    for no in raiz.walk():
        if isinstance(no, _NOS_PROIBIDOS):
            return Veredito(False, f"nó proibido: {type(no).__name__}")
        # Funções ANÔNIMAS (não tipadas pelo sqlglot): deny-by-default. É aqui que vivem
        # query()/query_table()/duckdb_tables()/current_setting()/read_ndjson_auto() etc.
        if isinstance(no, exp.Anonymous):
            nome = str(no.this).lower()
            if nome not in _ANON_PERMITIDAS:
                return Veredito(False, f"função não permitida (deny-by-default): {nome}")
        # Funções TIPADAS perigosas (read_csv/read_parquet quando o sqlglot as modela): backstop.
        elif isinstance(no, exp.Func):
            nome = (no.sql_name() or "").lower()
            if nome in _FUNCOES_TIPADAS_PROIBIDAS:
                return Veredito(False, f"função proibida: {nome}")

    # Tabelas: allowlist (aliases de CTE não são tabelas reais).
    ctes = {c.alias_or_name.lower() for c in raiz.find_all(exp.CTE)}
    for t in raiz.find_all(exp.Table):
        nome = (t.name or "").lower()
        schema = (t.db or "").lower()
        if not nome or (nome in ctes and not schema):
            continue
        if schema and schema != SCHEMA_SERVING:
            return Veredito(False, f"schema fora do contrato: {schema}.{nome}")
        if nome not in allowlist:
            return Veredito(False, f"tabela fora da allowlist: {nome}")
    return Veredito(True)


def _com_limite(sql: str, limite: int) -> str:
    """Envelopa a query para garantir teto de linhas (sem confiar no LIMIT do modelo)."""
    return f"select * from ({sql.rstrip().rstrip(';')}) as _rq limit {limite}"


def conectar(duckdb_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Conexão endurecida: read-only, sem acesso externo, config travada."""
    caminho = duckdb_path or settings.toll_duckdb
    return duckdb.connect(
        str(caminho),
        read_only=True,
        config={
            "enable_external_access": "false",  # mata httpfs / leitura de arquivo
            "lock_configuration": "true",       # o SQL não consegue afrouxar nada depois
            "memory_limit": "2GB",
            "threads": "2",
        },
    )


def executar(
    sql: str,
    allowlist: set[str] | None = None,
    duckdb_path: Path | None = None,
    limite: int = LIMITE_LINHAS_PADRAO,
    timeout_s: float = TIMEOUT_S_PADRAO,
) -> tuple[Veredito, list[tuple]]:
    """Valida → executa com teto de linhas e timeout. Nunca levanta por SQL malicioso."""
    allow = allowlist if allowlist is not None else carregar_allowlist()
    v = validar_sql(sql, allow)
    if not v:
        return v, []

    con = conectar(duckdb_path)
    watchdog = threading.Timer(timeout_s, con.interrupt)
    watchdog.start()
    try:
        linhas = con.execute(_com_limite(sql, limite)).fetchall()
        return Veredito(True), linhas
    except duckdb.Error as e:
        return Veredito(False, f"erro de execução: {type(e).__name__}: {str(e)[:120]}"), []
    finally:
        watchdog.cancel()
        con.close()
