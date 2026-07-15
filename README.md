<div align="center">

# 🚂 RodoQuery

**Agente de Analytics (Text-to-SQL) sobre um lakehouse governado — pergunte em português, receba o número certo.**

Data Engineering × AI Engineering · avaliação com rigor · R$0 · dados sintéticos.

</div>

---

> **Tese:** o valor não é *"LLM gera SQL"*. É provar, **com número e intervalo de confiança**, que servir sobre o **Semantic Layer governado** (dbt/MetricFlow) dá a resposta **certa** onde o SQL cru dá uma resposta **plausível e errada**.

RodoQuery é o irmão de [**RodoIA**](https://github.com/alanjoffre/rodoia) no eixo de dados: um agente conversacional que traduz linguagem natural em consultas **seguras** sobre a plataforma [**toll-analytics-platform**](https://github.com/alanjoffre/toll-analytics-platform) (lakehouse de auditoria de pedágio, dados sintéticos, DuckDB dev → Databricks prod), reusando o **dbt Semantic Layer** já modelado.

## 🏗️ Arquitetura — roteador de 2 camadas

```
NL do usuário
   │
   ▼
[Router] ── coberto pelo Semantic Layer? (sim→A / não→B / ambíguo→clarify / fora→refuse)
   │
   ├─► TIER A — semantic query (MetricFlow)   ← primário, alta acurácia
   │      LLM escolhe {métricas, dimensões, filtros} → validado contra o manifesto
   │      → MetricFlow compila SQL correto → executa (read-only) → resultado
   │
   └─► TIER B — SQL cru (fallback governado)   ← só p/ o que o SL não modela
          schema-linking + few-shot → validação AST (sqlglot) → execução → repair (≤2)
```

**Segurança é fronteira de código, nunca de prompt:** validador AST (só `SELECT`, single-statement, allowlist de tabelas, bloqueio de `ATTACH`/`COPY`/`read_parquet`/extensões) + conexão read-only + limites/timeout.

## 📋 Fases

| Fase | Objetivo | Métrica dura | Achado honesto esperado |
|---|---|---|---|
| **0** · Fundação | contrato de exposição + catálogo do manifesto + **harness** (canonicalizador em centavos, test-suite EX por seed) | harness reproduz; 0 objeto não-serving acessível | bug no harness invalida tudo |
| **1** · Sandbox seguro | executor read-only endurecido + validador AST + red-team | **attack-block = 100%** (gate duro) | segurança no prompt vale zero |
| **2** · Golden set | ~150–300 pares NL→(semantic+SQL) estratificados, verificados, splits disjuntos | nº/estrato + IC · **κ do 2º anotador** | X% do gold errado — publicar |
| **3** · Baselines | naïve + SQL-cru (zero/few-shot) + ablation de tamanho | **Execution Accuracy (test-suite) + Wilson** | EX despenca em join/agregação |
| **4** · Sistema | router 2-tiers + MetricFlow + few-shot + repair | **Δ EX (semantic − cru) nos ambíguos** · ganho por **McNemar** | ganho concentrado no Tier A |
| **5** · MLOps | gate de regressão no CI + observabilidade + custo R$/1k | gate ativo comprovado | flakiness do LLM desestabiliza o gate |
| **6** · Serving + SLO | FastAPI + canário de correção + load test | p95, throughput em 1 GPU, EX de canário | em 6GB a inferência serializa |
| **7** *(opcional)* · Robustez | held-out de paráfrase + perturbação de schema + volume | quanto o EX cai (com IC) | o "held-out derruba memorização" daqui |

## ⚖️ Princípios (herdados do RodoIA)

- Toda métrica com **intervalo de confiança** (Wilson/bootstrap); n pequeno assumido.
- **Execução como oráculo** — nada de LLM-juiz para acurácia.
- **Test-suite EX** (múltiplas seeds de DB) para matar falsos positivos.
- Comparação de sistemas é **pareada** → **McNemar** + IC da diferença.
- Tudo versionado em `reports/<fase>/*.json` carimbado (seed, git_sha, digest do modelo, hash do prompt).
- **R$0**, dados **sintéticos**, LLM **local** (Qwen2.5-Coder-7B-Q4 em 6GB — teto declarado honestamente).

## 🚀 Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Pré-requisito da Fase 0: a fundação de dados vem do **toll-analytics-platform** buildado (`dbt build` → DuckDB + `manifest.json`). Ver `docs/`.

## 📄 Licença
MIT. Dados sintéticos (nenhum dado real).
