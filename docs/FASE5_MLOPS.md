# Fase 5 — MLOps: gate de regressão, observabilidade e custo

Métrica dura do roadmap: **gate ativo comprovado**. Achado honesto previsto: *"flakiness do LLM
desestabiliza o gate"*. **O previsto não se confirmou** — e isso vai reportado como está.

## 1. O achado que contrariou a hipótese

Na Fase 4 eu vi um item de fronteira mudar de veredito entre execuções e **supus** não-determinismo
de GPU (float não-associativo no llama.cpp). Suposição não é medição. Então medi:

**5 runs × 23 itens do DEV**, greedy (`temperature=0`, `top_k=1`, `seed=42`), modelo quente:

| run | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| EX | 0,9474 | 0,9474 | 0,9474 | 0,9474 | 0,9474 |

**Desvio = 0,0 · amplitude = 0,0 pp · itens instáveis = 0.** (`reports/fase5/flakiness.json`)

Ou seja: **nesta configuração o SUT foi perfeitamente estável**. A anomalia da Fase 4 ocorreu *antes*
de eu fixar `top_k=1` e **ficou sem causa confirmada** — não posso creditá-la à GPU. A doc da Fase 4
foi **corrigida** para não afirmar o que não medi.

**O que isso muda no gate:** a margem não vira 0. 5 runs mostram variância **baixa, não nula**, então
a margem é `max(amplitude medida, 1 item)` = **5,26 pp** (1 de 19 respondíveis). Sem esse piso, um
único item que virasse reprovaria o build; com ele, o gate só acusa regressão real (≥2 itens).

## 2. Gate de regressão — 3 níveis

O princípio: **separar o determinístico do estocástico**. Gate que flaka é gate que o time aprende a
ignorar — pior que gate nenhum.

| Nível | O que checa | Precisa de | Onde roda | Flaky? |
|---|---|---|---|---|
| **A · contrato** | selo do golden TEST; agregados batem com os itens; limiares; McNemar significante | só os JSON | **CI** (GitHub Actions) | não |
| **B · replay** | re-executa as predições **congeladas** contra o gold; veredito item-a-item idêntico | DuckDB + MetricFlow | máquina da fundação | não (sem LLM) |
| **C · live** | roda o sistema de verdade | GPU + LLM | agendado | sim → usa a margem medida |

Limiares (com **folga** sobre o observado, de propósito): EX ≥ 0,90 (obs. 0,976) · abstenção ≥ 0,90
(obs. 1,00) · vantagem sobre o baseline ≥ 30 pp (obs. +54,8) · McNemar p < 0,05.

O nível A recomputa os agregados **a partir dos itens**: se alguém editar só o número bonito no topo
do JSON, o gate pega.

**Estado verificado:** nível A ✅ passou (7/7 checagens) · nível B ✅ passou — re-executar as
predições congeladas contra o gold reproduziu **53/53 vereditos idênticos** em ambos os sistemas,
confirmando que canonização, scorer, gold e variantes do test-suite não regrediram.

## 3. "Gate ativo comprovado" — a prova

Um gate que só fica verde é decoração. `provar_gate.py` injeta regressões no relatório **real** e
exige que o gate reprove cada uma (`reports/fase5/gate_ativo.json`):

| Cenário injetado | Gate | Checagem que disparou |
|---|---|---|
| relatório íntegro | ✅ passou | — |
| EX do Tier-A despenca | ❌ reprovou | `ex_minimo`, `vantagem_sobre_baseline` |
| agregado adulterado (não bate com os itens) | ❌ reprovou | `coerencia[tier_a]` |
| baseline alcança o sistema | ❌ reprovou | `vantagem_sobre_baseline` |
| McNemar perde significância | ❌ reprovou | `mcnemar_significante` |
| abstenção desaba (passa a alucinar) | ❌ reprovou | `abstencao_minima` |
| golden TEST editado após o selo | ❌ reprovou | `selo_golden_test` |

**`gate_ativo_comprovado = true`** (6/6 regressões pegas + íntegro aprovado).

## 4. Observabilidade

Telemetria real do Ollama por consulta (`reports/fase5/observabilidade_custo.json`):

| Métrica | Valor |
|---|---|
| Latência p50 | **4,51 s** |
| Latência p95 | **7,94 s** |
| Vazão (1 GPU, sequencial) | ~**13,2 consultas/min** |
| Tokens entrada / saída | **708,5** / **47,1** |

O prompt domina o custo de tokens (15× a saída) — o Tier-A troca tokens de *entrada* (catálogo) por
correção, o que é barato num modelo local.

## 5. Custo por 1.000 consultas

| Modelo de custo | R$/1k | Natureza |
|---|---|---|
| **Local (energia)** | **R$ 0,12** | latência **medida**; potência e tarifa são **premissas rotuladas** (115 W, R$ 0,85/kWh) |
| API por token (ilustrativo) | R$ 1,45 | tokens **medidos**; tarifas são **parâmetros ilustrativos**, não preço cravado de fornecedor |

> **Honestidade:** não medi potência com wattímetro nem cravo preço de API. O valor aqui é a **ordem
> de grandeza** e a **estrutura de comparação**, não uma cifra precisa. O custo local ignora
> amortização de hardware e ociosidade. Trocar as premissas em `src/rodoquery/custo.py` muda o
> número — é para isso que elas são explícitas.

## 6. CI

`.github/workflows/ci.yml` roda em todo push/PR: **ruff → pytest → gate nível A**. Só o que é
determinístico e não precisa de GPU. Os níveis B e C rodam onde há fundação/GPU.

## Reprodução

```bash
python medir_flakiness.py 5      # estabilidade (K runs) -> reports/fase5/flakiness.json
python relatorio_fase5.py        # observabilidade + custo
python provar_gate.py            # prova que o gate reprova regressões
python gate_regressao.py         # nível A (o que o CI roda)
python gate_regressao.py --replay  # nível B (precisa da fundação)
```
