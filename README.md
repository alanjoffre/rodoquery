<div align="center">

# 🚂 RodoQuery

**Agente de Analytics (Text-to-SQL) sobre um lakehouse governado — pergunte em português, receba o número certo.**

Data Engineering × AI Engineering · avaliação com rigor · R$0 · dados sintéticos.

**Status: completo (fases 0–7).** Todos os números abaixo são medidos e reproduzíveis em `reports/`.

</div>

---

> **Tese:** o valor não é *"LLM gera SQL"*. É provar, **com número e intervalo de confiança**, que servir sobre o **Semantic Layer governado** (dbt/MetricFlow) dá a resposta **certa** onde o SQL cru dá uma resposta **plausível e errada**.

**A tese foi comprovada.** No TEST selado, com **o mesmo modelo** (`qwen2.5-coder:7b`) — muda só a interface:

| Sistema | Execution Accuracy (respondíveis, n=42) | Abstenção (n=11) |
|---|---|---|
| **Tier-A — spec governada → MetricFlow** | **97,6%** [87,7; 99,6] | **100%** [74,1; 100] |
| Baseline — SQL cru | 42,9% | — |

**McNemar pareado: b=23, c=0, p≈0, Δ = +54,8 pp.** Vinte e três itens que o SQL cru erra e a spec governada acerta; **zero** no sentido contrário. Como o SUT é idêntico, o ganho é atribuível **à interface**, não ao modelo.

RodoQuery é o irmão de [**RodoIA**](https://github.com/alanjoffre/rodoia) no eixo de dados: um agente que traduz linguagem natural em consultas **seguras** sobre a plataforma [**toll-analytics-platform**](https://github.com/alanjoffre/toll-analytics-platform) (lakehouse de auditoria de pedágio, dados sintéticos, DuckDB dev → Databricks prod), reusando o **dbt Semantic Layer** já modelado.

## 🏗️ Arquitetura — o que de fato está servido

```
NL do usuário
   │
   ▼
[Tier A] LLM escolhe {métricas, dimensões, filtros} de um VOCABULÁRIO FECHADO
   │        → validado contra o catálogo → MetricFlow compila o SQL → executa (read-only)
   │        → fora do catálogo? ABSTÉM (não inventa)
   │
   └─ [Tier B] SQL cru + sandbox AST — construído e testado, DESLIGADO no roteador (ver backlog)
```

**Por que o Tier-A dispensa o sandbox:** o LLM nunca emite SQL. Ele emite uma *spec* sobre um vocabulário fechado; quem gera SQL é o MetricFlow. **Não há superfície de injeção** — a segurança é estrutural, não um filtro depois do fato.

O sandbox existe para o Tier-B e foi validado: **attack-block 100% (39/39)** com **falso-positivo 0% (10/10 consultas legítimas passam)** — as duas métricas juntas, porque bloquear tudo daria 100% de block e seria inútil.

## 📋 Fases — previsto × medido

| Fase | Métrica dura | **Resultado medido** |
|---|---|---|
| **0** · Fundação | harness reproduz; 0 objeto não-serving acessível | ✅ harness + canonicalizador em centavos + Test-Suite EX em 3 seeds |
| **1** · Sandbox | **attack-block = 100%** (gate duro) | ✅ **39/39 bloqueados, 0 falso-positivo** |
| **2** · Golden set | nº/estrato + IC · **κ do 2º anotador** | ⚠️ 76 itens, 8 estratos · **κ de máquina 1,0** (0,875 na sonda de ambiguidade) — **κ humano é backlog declarado** |
| **3** · Baselines | Execution Accuracy + Wilson | ✅ SQL cru **26,3%** no DEV [11,8; 48,8] |
| **4** · Sistema | Δ EX + **McNemar** | ✅ **97,6% × 42,9%, +54,8 pp, b=23/c=0, p≈0** |
| **5** · MLOps | gate ativo comprovado | ✅ gate em 3 níveis **pega 6/6 regressões injetadas** · p50 4,5 s / p95 7,9 s · **R$ 0,12/1k** |
| **6** · Serving + SLO | p95, throughput em 1 GPU, EX de canário | ✅ SLO atendido (p95 4,36 s em c=1) · canário 10/10 · capacidade real **~0,25 req/s** |
| **7** · Robustez | quanto o EX cai (com IC) | ⚠️ paráfrase −7,7 pp (**p=0,375, não significativo**) · **schema opaco −14,3 pp (p=0,031)** |

## 🔬 Previsões que a medição **refutou**

Este é o item de que mais me orgulho no projeto. Cada fase tinha um "achado honesto esperado" **pré-registrado**. Três não se confirmaram — e o repositório registra isso em vez de esconder:

| Previsão da Fase 0 | O que a medição disse |
|---|---|
| *"flakiness do LLM desestabiliza o gate"* (F5) | **Refutada.** 5 execuções com greedy + `top_k=1` e modelo quente deram EX **idêntico** (amplitude 0,0 pp). Eu havia escrito na doc da Fase 4 que uma falha vinha de não-determinismo de GPU — **sem ter medido**. Medi, estava errado, e **corrigi a doc**. |
| *"o held-out de paráfrase derruba memorização"* (F7) | **Não confirmada.** Queda de 7,7 pp com **p=0,375**: com n=39 não dá para rejeitar "não houve diferença". O que **de fato** quebra é trocar `revenue` por `m03` mantendo a mesma descrição: **−14,3 pp, p=0,031**. A fragilidade é **lexical nos identificadores**, não no fraseado. |
| *"em 6 GB a inferência serializa"* (F6) | **Confirmada — e pior.** Vazão cai 25% em c=4/8 e o p95 vai de 4,4 s para **43 s**. O ótimo de vazão (c=2) **não** é o ótimo de SLO: o controle de admissão certo foi semáforo **1** + espera 5 s, recusando o excesso com 503 em vez de enfileirar. |

Bônus: **a abstenção ficou 100% intacta** sob perturbação de schema. Reconhecer "não existe métrica para isto" depende de o catálogo **não ter** algo, não do nome que as métricas têm — duas competências separadas, e a de segurança é a robusta.

## ⚖️ Princípios

- Toda métrica com **intervalo de confiança** (Wilson/bootstrap); n pequeno assumido e declarado.
- **Execução como oráculo** — nada de LLM-juiz para acurácia.
- **Test-suite EX**: a predição precisa bater o gold em **todas** as seeds de DB, o que mata acerto por coincidência.
- **Anti-circularidade:** o gold sai **sempre** do MetricFlow, nunca de SQL escrito à mão.
- Comparação de sistemas é **pareada** → **McNemar**.
- **Predições congeladas** em disco: o SUT é estocástico, a pontuação é determinística e auditável.
- Tudo em `reports/<fase>/*.json` carimbado (seed, git_sha, modelo, temperatura, versões).
- **R$0**, dados **sintéticos**, LLM **local** (Qwen2.5-Coder-7B em 6 GB — teto declarado honestamente).

## 🎯 Backlog declarado (o que **não** está feito)

Nenhum destes é surpresa: todos foram declarados na fase em que apareceram.

- **κ humano** do golden set — hoje só há concordância entre modelos, **rotulada como de máquina**.
- **Expandir N para ≥25/estrato** — com 42 respondíveis, só efeitos **≥14 pp** ficam significativos.
- **Ligar o Tier-B** no roteador — o fallback de SQL cru está construído e o sandbox validado, mas desligado.
- **Conjunto de robustez próprio** — a Fase 7 reusou o TEST para medir deltas. Nenhum ajuste foi feito com base nesses resultados, mas cada reuso erode um holdout.

## 🚀 Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm,serve]"
pytest                                    # 87 testes
python gate_regressao.py                  # gate nível A (contrato, sem GPU)
uvicorn rodoquery.servico:app --port 8077 # serving do Tier-A
```

Pré-requisito: a fundação de dados vem do **toll-analytics-platform** buildado (`dbt build` → DuckDB + `manifest.json`). Ver [`docs/FUNDACAO.md`](docs/FUNDACAO.md).

**Documentação por fase:** [golden set](docs/GUIA_GOLDEN.md) · [baselines](docs/FASE3_BASELINES.md) · [sistema](docs/FASE4_SISTEMA.md) · [MLOps](docs/FASE5_MLOPS.md) · [serving/SLO](docs/FASE6_SERVING_SLO.md) · [robustez](docs/FASE7_ROBUSTEZ.md)

## 📄 Licença
MIT. Dados sintéticos (nenhum dado real).
