# Fase 19 — pré-registro: a fragilidade lexical sobrevive a um SUT de fronteira?

> **Este documento foi escrito e commitado ANTES de qualquer chamada de API.** O `git log` prova a
> ordem. Sem isso, "eu esperava esse resultado" não vale nada — e a seção de previsões refutadas do
> README, que é o melhor conteúdo deste repositório, só existe porque as previsões foram
> registradas antes.

## A pergunta

A Fase 14 mediu, com `qwen2.5-coder:7b` num conjunto dedicado (34 itens, disjunto do TEST-ANTT):

| Condição | EX |
|---|---|
| Catálogo original (`traffic_volume`, `plaza__sentido`…) | **85,29%** (29/34) |
| Catálogo **opaco** (`m1`, `c2`…, **descrições idênticas**) | **55,88%** (19/34) |
| Δ | **−29,41 pp**, McNemar b=11/c=1, **p=0,0063** |

Só os identificadores mudam. As descrições, o gabarito e as perguntas são os mesmos. O que isso
mede é se a competência do Tier-A está na **semântica da descrição** ou em **casar a palavra da
pergunta com o identificador**.

## A lei sob teste

A Fase 18 formou uma generalização a partir de dois pontos:

> A ajuda de uma muleta é **inversamente proporcional à força do SUT**.

Ela acertou duas vezes: os normalizadores das Fases 9/10 valem +17,7 pp no Qwen e **0** no Opus 5
(tocaram 0 de 146 specs); o resíduo de seleção travava em 72–80% no Qwen e virou **100%**.

Se a fragilidade lexical for da mesma família, ela deve **encolher muito** com o Opus 5.

## Minha previsão (pontual, para poder errar)

| Quantidade | Previsão | Faixa que eu aceito como "acertei" |
|---|---|---|
| EX original (Opus 5) | **97%** | ≥ 91% (31/34) |
| EX opaco (Opus 5) | **88%** | 79–97% |
| **Δ (pp)** | **−9** | **−2 a −18** |
| McNemar | provavelmente **não significativo** (p > 0,05) | — |

**A afirmação falsificável central:** `|Δ_opus5| < |Δ_qwen| = 29,4 pp`.

## O que cada resultado significa

**Se Δ encolher para perto de zero** — a lei se confirma pela terceira vez. A fragilidade lexical
vira "problema de SUT barato", e a mitigação (descrições mais ricas) passa a ser uma otimização de
custo, não uma correção de defeito.

**Se Δ ficar em torno de −29 pp** — a lei **falha pela primeira vez**, e é o resultado mais valioso
que esta fase pode dar. Significaria que a fragilidade lexical é **estrutural da interface**, não
falta de capacidade: o vocabulário fechado só é seguro se os identificadores carregarem semântica.
Isso é um limite real da abordagem, e nenhum modelo maior resolve.

**Se Δ ficar maior que −29 pp** (o Opus 5 sofrer *mais*) — eu não tenho hipótese para isso, e
suspeitaria de bug de harness antes de acreditar. Nesse caso a ação é auditar, não publicar.

## Compromissos

1. **Não ajusto nada depois de ver o número.** O conjunto de robustez está selado desde a Fase 14
   (`golden/robustez_antt.jsonl`, hash commitado). Mexer depois é fitar — disciplina da Fase 8.
2. **Os dois braços rodam no mesmo SUT, na mesma execução.** Comparar Opus 5 opaco contra Qwen
   original mediria o modelo, não a perturbação.
3. **Predições congeladas em disco**, como em toda fase desde a 4.
4. **Publico os dois resultados.** Se a minha previsão furar, ela vira linha na tabela de previsões
   refutadas do README — que é onde as anteriores foram parar.

## Custo

68 chamadas (34 itens × 2 condições) × US$ 0,0028/chamada medido na Fase 18 ≈ **US$ 0,19**.
Teto de segurança na execução: US$ 0,50.
