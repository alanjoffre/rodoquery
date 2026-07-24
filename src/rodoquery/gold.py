"""Gerador do GOLD via Semantic Layer — o mecanismo anti-circularidade da Fase 2.

**O ponto que quebra a circularidade** (auditoria staff): o gold NUNCA é SQL escrito à mão. Cada
item do golden set é uma **spec semântica** `{metrics, group_by, where, order_by}` — o MetricFlow
compila o SQL correto (join/filtro/grão certos, por construção). O agente **nunca vê a spec**: só a
pergunta em NL + o catálogo. Ele tem de MAPEAR pergunta→métrica sozinho; o gold mede se a resposta
final bate, não se o SQL é igual.

Como o SQL do MetricFlow é gerado da spec (independente dos dados), compilamos **uma vez** e o
tornamos **portável** (removendo o catálogo `"toll_analytics"`) para rodar em TODAS as variantes do
test-suite → **Test-Suite Execution Accuracy** (acerto só conta se bate em todas → mata falso
positivo). O MetricFlow do dbt Core só expõe a CLI `mf query` (não há API) — daí o subprocess.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from rodoquery.canonizacao import canonicalizar, hash_resultado
from rodoquery.config import settings

# Diretório do dbt (onde vive o `mf`) e o binário do MetricFlow, derivados da fundação.
_DBT_DIR = settings.toll_duckdb.parent
_MF_BIN = _DBT_DIR / ".venv" / "bin" / "mf"
# Remove o catálogo qualificado (`"<db>"."main"."x"` → `"main"."x"`), AGNÓSTICO ao nome do banco:
# o build do test-suite clobbera o manifesto e o mf pode qualificar com `"toll_seed2"` etc.
_RE_CATALOGO = re.compile(r'"[^"]+"\.(?="main"\.)')


@dataclass(frozen=True)
class Spec:
    """A pergunta traduzida para a linguagem do Semantic Layer (o gold é o resultado disto)."""
    metrics: list[str]
    group_by: list[str] = field(default_factory=list)
    where: str | None = None
    order_by: list[str] = field(default_factory=list)
    limit: int | None = None
    ordenado: bool = False  # a pergunta pede ranking/top-N? (ordem faz parte da resposta)


def _extrair_sql(saida: str) -> str:
    """Pega o bloco SQL da saída de `mf query --explain`."""
    if "🔎 SQL" in saida:
        saida = saida.split("🔎 SQL", 1)[1]
    idx = saida.find("SELECT")
    if idx == -1:
        raise RuntimeError(f"mf --explain não retornou SQL:\n{saida[:500]}")
    return saida[idx:].strip()


def portabilizar(sql: str) -> str:
    """Remove o prefixo de catálogo (`"<db>"."main"."x"` → `"main"."x"`) para o SQL rodar em
    qualquer DuckDB conectado (as variantes têm nomes de banco diferentes). Remoção por regex de
    propósito: o SQL do MetricFlow para multi-métrica/ratio é complexo demais para reparsear com
    segurança; e o nome do catálogo varia (o build do suite clobbera o manifesto)."""
    return _RE_CATALOGO.sub("", sql)


@dataclass(frozen=True)
class Fundacao:
    """Onde vive um projeto dbt+MetricFlow. Permite compilar specs contra fundações distintas
    (sintética das Fases 0–10; real da ANTT a partir da 11) sem duplicar o compilador."""
    dbt_dir: Path
    mf_bin: Path
    profiles_dir: Path | None = None


FUNDACAO_SINTETICA = Fundacao(dbt_dir=_DBT_DIR, mf_bin=_MF_BIN)
# A ANTT reusa o `mf` do venv da fundação sintética e tem o profiles.yml no próprio projeto.
FUNDACAO_ANTT = Fundacao(dbt_dir=settings.antt_dbt_dir, mf_bin=_MF_BIN,
                         profiles_dir=settings.antt_dbt_dir)


def compilar_spec(spec: Spec, fundacao: Fundacao | None = None) -> str:
    """Compila a spec semântica → SQL portável, via `mf query --explain` (uma vez, sem dados).

    `fundacao=None` mantém a fundação SINTÉTICA — as Fases 0–10 seguem reproduzíveis byte a byte.
    """
    f = fundacao or FUNDACAO_SINTETICA
    cmd = [str(f.mf_bin), "query", "--metrics", ",".join(spec.metrics), "--explain"]
    if spec.group_by:
        cmd += ["--group-by", ",".join(spec.group_by)]
    if spec.where:
        cmd += ["--where", spec.where]
    if spec.order_by:
        cmd += ["--order", ",".join(spec.order_by)]
    if spec.limit:
        cmd += ["--limit", str(spec.limit)]
    # Telemetria off: dbt/MetricFlow "telefonam pra casa" e travam ~180s esperando a rede.
    env = {**os.environ, "DO_NOT_TRACK": "1", "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    if f.profiles_dir:
        env["DBT_PROFILES_DIR"] = str(f.profiles_dir)
    r = subprocess.run(cmd, cwd=f.dbt_dir, capture_output=True, text=True, timeout=120, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"mf falhou p/ {spec.metrics}:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
    return portabilizar(_extrair_sql(r.stdout))


def executar_gold(sql: str, duckdb_path: Path) -> list[tuple]:
    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def gerar_gold(spec: Spec, duckdb_path: Path | None = None) -> dict:
    """Gera o gold de uma spec: compila via MetricFlow, executa, canonicaliza e faz o hash."""
    db = duckdb_path or settings.toll_duckdb
    sql = compilar_spec(spec)
    linhas = executar_gold(sql, db)
    return {
        "sql_metricflow": sql,
        "n_linhas": len(linhas),
        "hash": hash_resultado(linhas, ordenado=spec.ordenado),
        "amostra": [list(r) for r in canonicalizar(linhas, ordenado=spec.ordenado)[:3]],
    }
