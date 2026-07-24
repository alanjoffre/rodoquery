"""Gerador do CATÁLOGO — a fonte de verdade do agente (Fase 0).

Deriva do dbt (manifest.json + semantic_manifest.json) + DuckDB um `catalog.json` que contém
SÓ o que o agente pode ver: as marts Gold públicas (allowlist), as métricas/dimensões do
Semantic Layer, e os valores das dimensões categóricas. O DuckDB tem dezenas de objetos que o
agente NÃO pode tocar (dbt_project_evaluator, elementary, testes, landing/raw com PII) — a
allowlist derivada de `package_name == projeto` + `marts` no fqn os exclui por construção.

O catálogo é **gerado**, nunca escrito à mão — se o modelo dbt muda, o catálogo muda junto (e o
CI pega divergência). Uso: `python -m rodoquery.catalogo`.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from rodoquery.config import REPO_ROOT, settings
from rodoquery.proveniencia import carimbar

PROJETO_DBT = "toll_analytics"
_CATEGORICAS = ("status", "audit_flag", "payment_method")


def _marts_do_projeto(manifest: dict, projeto: str | None = None) -> dict[str, dict]:
    """Allowlist: models do PROJETO sob `marts/` (exclui pacotes evaluator/elementary, testes,
    staging e landing por construção). `projeto=None` = o sintético (Fases 0–10)."""
    projeto = projeto or PROJETO_DBT
    out = {}
    for v in manifest["nodes"].values():
        if (
            v.get("resource_type") == "model"
            and v.get("package_name") == projeto
            and "marts" in "/".join(v.get("fqn", []))
            and v.get("access") == "public"  # só o que o dbt marca como público entra na allowlist
        ):
            alias = v.get("alias") or v["name"]
            out[alias] = {
                "schema": v.get("schema"),
                "materializacao": v.get("config", {}).get("materialized"),
                "access": v.get("access"),
                "descricao": (v.get("description") or "").strip(),
                "descricoes_colunas": {
                    c: (info.get("description") or "").strip()
                    for c, info in v.get("columns", {}).items()
                },
            }
    return out


def _metricas(sm: dict) -> list[dict]:
    return [
        {
            "nome": m["name"],
            "label": m.get("label"),
            "descricao": (m.get("description") or "").strip(),
            "tipo": m.get("type"),
        }
        for m in sm.get("metrics", [])
    ]


def _dimensoes_entidades(sm: dict) -> tuple[list[dict], list[dict]]:
    modelos = sm.get("semantic_models", [])
    dims, ents = [], []
    for sm_model in modelos:
        for d in sm_model.get("dimensions", []):
            dims.append({
                "nome": d["name"],
                "tipo": d.get("type"),
                "granularidade": (d.get("type_params") or {}).get("time_granularity"),
            })
        for e in sm_model.get("entities", []):
            ents.append({"nome": e["name"], "tipo": e.get("type"), "expr": e.get("expr")})
    return dims, ents


def gerar_catalogo(
    manifest_path: Path, semantic_manifest_path: Path, duckdb_path: Path,
    projeto: str | None = None, fato: str | None = None,
    categoricas: tuple[str, ...] | None = None,
) -> dict:
    """`projeto`/`fato`/`categoricas` = None mantêm a fundação SINTÉTICA (Fases 0–10)."""
    projeto = projeto or PROJETO_DBT
    fato = fato or "fct_toll_transactions"
    cats = categoricas if categoricas is not None else _CATEGORICAS
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sm = json.loads(semantic_manifest_path.read_text(encoding="utf-8"))
    marts = _marts_do_projeto(manifest, projeto)

    con = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        tabelas = {}
        for nome, meta in sorted(marts.items()):
            schema = meta["schema"]
            colunas = con.execute(
                "select column_name, data_type from information_schema.columns "
                "where table_schema = ? and table_name = ? order by ordinal_position",
                [schema, nome],
            ).fetchall()
            n_linhas = con.execute(f'select count(*) from "{schema}"."{nome}"').fetchone()[0]
            tabelas[nome] = {
                "schema": schema,
                "materializacao": meta["materializacao"],
                "access": meta["access"],
                "descricao": meta["descricao"],
                "n_linhas": n_linhas,
                "colunas": [
                    {"nome": c, "tipo": t, "descricao": meta["descricoes_colunas"].get(c, "")}
                    for c, t in colunas
                ],
            }
        # valores das dimensões categóricas (baixa cardinalidade) a partir do fato
        valores_cat = {}
        for dim in cats:
            try:
                vals = con.execute(
                    f'select distinct "{dim}" from "main"."{fato}" '
                    f'where "{dim}" is not null order by 1'
                ).fetchall()
                valores_cat[dim] = [r[0] for r in vals]
            except duckdb.Error as e:
                # numa "fonte de verdade gerada", engolir drift de coluna seria cegueira — avisa.
                import sys
                print(f"  aviso: dimensão categórica '{dim}' não lida: {e}", file=sys.stderr)
    finally:
        con.close()

    dims, ents = _dimensoes_entidades(sm)
    return carimbar({
        "fonte": {
            "manifest": str(manifest_path),
            "semantic_manifest": str(semantic_manifest_path),
            "duckdb": str(duckdb_path),
            "projeto_dbt": PROJETO_DBT,
        },
        "tabelas": tabelas,
        "metricas": _metricas(sm),
        "dimensoes": dims,
        "entidades": ents,
        "valores_categoricos": valores_cat,
        "saved_queries": [
            {"nome": q["name"], **q.get("query_params", {})} for q in sm.get("saved_queries", [])
        ],
    })


def main() -> int:
    cat = gerar_catalogo(
        settings.toll_manifest, settings.toll_semantic_manifest, settings.toll_duckdb
    )
    saida = REPO_ROOT / "reports" / "fase0" / "catalog.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(cat, ensure_ascii=False, indent=2))
    print(f"catálogo gerado: {len(cat['tabelas'])} tabelas (allowlist), "
          f"{len(cat['metricas'])} métricas, {len(cat['dimensoes'])} dimensões -> {saida}")
    print("  tabelas:", ", ".join(cat["tabelas"]))
    print("  métricas:", ", ".join(m["nome"] for m in cat["metricas"]))
    print("  valores categóricos:", {k: v for k, v in cat["valores_categoricos"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
