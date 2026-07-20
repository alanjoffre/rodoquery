# Fase 3 — Endurecimento do golden + Baselines executados

Esta fase fez **duas** coisas: fechou furos do golden set (3a) e produziu o **primeiro número real**
com um baseline executado de ponta a ponta (3b). Nada aqui é "a tese provada" — é o **baseline que a
tese precisa bater**, medido com honestidade estrita.

## 3a — Golden endurecido

| O que | Antes (Fase 2) | Agora |
|---|---|---|
| Itens de **abstenção** (fora-de-escopo) | nenhum | **15** (`golden/abstencao.jsonl`) — pergunta que o catálogo não responde; o certo é ABSTER |
| Split **DEV/TEST** | não havia (selei tudo) | **30/70 estratificado** determinístico: DEV=23 (visível), TEST=53 (**selado**, `golden/golden_test.sha256`) |
| Golden completo | 61 | **76** (`golden/golden_full.jsonl`) |

O 8º estrato (`abstencao`) é um **eixo diferente** dos 7 mecanismos: não entra no Execution
Accuracy; é medido como **acurácia de abstenção**. É onde o vocabulário fechado do Semantic Layer
vira vantagem (sabe dizer "não sei") e onde o SQL cru tende a alucinar.

> **Ressalva honesta de N:** a meta pré-registrada era ≥25/estrato (~200). Continuamos abaixo
> (6–12/estrato). Os IC de Wilson saem **largos de propósito** — expandir o golden é backlog
> priorizado. O TEST (53) segue **cego** para a avaliação final do sistema (Fase 4+).

## 3b — Baselines (avaliados no DEV, 3 variantes de test-suite)

Harness (`src/rodoquery/avaliacao.py`): pergunta → sistema → SQL → **sandbox** → executa em **todas**
as variantes → compara com o gold (**Test-Suite EX**: só conta se bate em todas). Dois eixos
separados; na dúvida, conta **erro**.

| Sistema | EX (respondíveis, n=19) | Abstenção (n=4) |
|---|---|---|
| **`sql_cru`** (LLM escreve SQL sobre o schema cru, prompt justo) | **26,3%** — IC95 [11,8; 48,8] | 75% — IC95 [30; 95] |
| `sempre_abster` (piso trivial) | 0,0% | 100% |
| *oráculo semântico* (referência, não-sistema) | *100% por construção* | *100%* |

**EX do `sql_cru` por estrato** (onde o SQL cru quebra):

| Estrato | Acerto | Leitura |
|---|---|---|
| `controle_trivial` | 2/2 (100%) | count simples — ambos acertam (guarda contra scorer viciado ✅) |
| `join_grao` | 2/2 (100%) | join direto sem regra de negócio |
| `grao_temporal` | 1/3 (33%) | acerta dia/mês; erra semana (início da semana difere) |
| `metrica_filtrada` | 0/4 (0%) | não sabe que `revenue` só conta COMPLETED → soma tudo |
| `metrica_derivada` | 0/3 (0%) | ratio/derivada com denominador/conversão errados |
| `valor_categorico` | 0/3 (0%) | receita de FAILED/REVERSED deveria ser 0 (regra da métrica) |
| `coalesce_nulo` | 0/2 (0%) | dias sem atividade somem em vez de virar 0 |

### O que os números dizem (e o que NÃO dizem)

- ✅ **A tese ganha suporte, sem ser declarada vencedora.** O baseline nasce forte no trivial
  (count/join = 100%) e desaba justamente nos mecanismos que o Semantic Layer governa
  (métrica filtrada/derivada, coalesce, valor categórico = 0%). Isso é o mecanismo da tese, visível.
- ✅ **O scorer não é viciado.** O piso `sempre_abster` tira **0%** no eixo respondível — não há
  acerto de graça. E `controle_trivial` = 100% mostra que o scorer credita o baseline quando ele
  acerta de verdade.
- ⚠️ **Ainda NÃO é a prova.** O head-to-head estatístico é **Tier-A × sql_cru** (McNemar pareado),
  e o Tier-A (NL→spec via LLM) é a **Fase 4**. O oráculo semântico (100%) é só teto por construção.
- ⚠️ **N pequeno → sem significância.** McNemar `sql_cru` vs piso nos respondíveis: b=5, c=0,
  **p=0,0625** (não < 0,05). Com N=19 não dá para cravar significância — exatamente a ressalva de N.
- 🔒 **Achado qualitativo de segurança:** em `abstencao_07` ("*liste as placas dos veículos com mais
  transações suspeitas*", um pedido de PII row-level), o `sql_cru` **alucinou uma query** em vez de
  abster. O sistema governado (vocabulário de métricas, sem row-level) abstém por construção — conecta
  com a fronteira de segurança da Fase 1.

## Reprodução

```bash
# 3a — golden completo + split + selo do TEST
python golden/montar_split.py

# 3b — baselines no DEV (sobe o Ollama antes: `ollama serve` + `ollama pull qwen2.5-coder:7b`)
python avaliar_fase3.py            # -> reports/fase3/baselines.json
```
