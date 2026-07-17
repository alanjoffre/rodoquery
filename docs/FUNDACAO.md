# A fundação de dados — o que o RodoQuery consome (e como reproduzir)

O RodoQuery **não gera dados**: ele serve perguntas sobre o lakehouse da
[**toll-analytics-platform**](https://github.com/alanjoffre/toll-analytics-platform) (dados
**sintéticos** de pedágio, DuckDB em dev). Este doc fixa o contrato e como reproduzir do zero.

## O que é vendorizado aqui (e o que não é — decisão honesta)

| Artefato | Vendorizado? | Por quê |
|---|:---:|---|
| `fundacao/semantic_manifest.json` (9 KB) | ✅ | É o **contrato semântico** (métricas/dimensões/entidades). Pequeno, e seu **hash detecta drift**: se o Semantic Layer muda, a avaliação precisa rodar de novo e os exemplares few-shot são invalidados. |
| `reports/fase0/catalog.json` | ✅ | O **destilado** que o agente consome (allowlist + métricas + valores categóricos). Auto-suficiente. |
| `manifest.json` (3,6 MB) | ❌ | Peso sem ganho — o catálogo já extrai o necessário. |
| `toll_analytics.duckdb` (21 MB) | ❌ | **Regenerável** pelo build abaixo (dados sintéticos). Binário grande não vai pro Git. |

## Reproduzir a fundação do zero

```bash
git clone https://github.com/alanjoffre/toll-analytics-platform
cd toll-analytics-platform

# 1) Ingestão (dlt) → schema landing no DuckDB
cd ingestion-toll-analytics
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python toll_ingestion.py

# 2) Transformação (dbt) → marts + Semantic Layer + manifest
cd ../dbt-toll-analytics
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/dbt deps --profiles-dir . && .venv/bin/dbt build --profiles-dir .
```

Gera: `dbt-toll-analytics/toll_analytics.duckdb`, `target/manifest.json`, `target/semantic_manifest.json`.

## Apontar o RodoQuery para a fundação

Por padrão o RodoQuery procura a plataforma como **irmã** do repo (`../toll-analytics-platform`).
Se estiver em outro lugar, use env vars:

```bash
export RODOQUERY_TOLL_DUCKDB=/caminho/dbt-toll-analytics/toll_analytics.duckdb
export RODOQUERY_TOLL_MANIFEST=/caminho/dbt-toll-analytics/target/manifest.json
export RODOQUERY_TOLL_SEMANTIC_MANIFEST=/caminho/dbt-toll-analytics/target/semantic_manifest.json

python -m rodoquery.catalogo     # regenera reports/fase0/catalog.json
```

## O contrato de exposição (o que o agente PODE ver)

O DuckDB tem **dezenas de objetos que o agente não pode tocar**: `dbt_project_evaluator`
(`fct_*` de metadado), `main_elementary.*` (observabilidade), `main_dbt_test__audit.*` (testes),
`landing.*`/`*_staging` (raw). A allowlist é derivada **por construção** (`package_name` do
projeto + `marts` no `fqn`), resultando em **9 marts Gold públicas**:

`fct_toll_transactions` · `dim_date` · `dim_plaza` · `dim_vehicle` ·
`agg_daily_revenue_by_plaza` · `audit_suspect_transactions` · `py_plaza_audit_stats` ·
`rpt_plaza_revenue_v1` · `rpt_plaza_revenue_v2`

> Catálogo **gerado, nunca escrito à mão** — se o modelo dbt muda, o catálogo muda junto.

## Test-suite de bancos (Fase 0)

O gerador da plataforma aceita `--seed`, então criamos **N bancos variantes** para o
**Test-Suite Execution Accuracy** (acerto só conta se bater em TODAS as variantes → mata falso
positivo de coincidência num único banco):

```bash
python -m rodoquery.suite_dbs --seeds 1 2 3 --escala 3000
```
