# Fase 19 — a fragilidade lexical era do SUT, não da interface

**Pré-registro:** [`FASE19_PREREGISTRO.md`](FASE19_PREREGISTRO.md), commit `acaf471`, escrito e
commitado **antes** de qualquer chamada de API. O `git log` prova a ordem.

## O resultado

Mesmo conjunto selado da Fase 14 (34 itens, disjunto do TEST-ANTT), mesma perturbação
(identificadores viram `m1`/`c2`/`e3`, **descrições idênticas**, gabarito inalterado):

| SUT | Catálogo original | Catálogo opaco | Δ | McNemar |
|---|---|---|---|---|
| `qwen2.5-coder:7b` (Fase 14) | 85,29% (29/34) | 55,88% (19/34) | **−29,41 pp** | b=11/c=1, **p=0,0063** |
| **`claude-opus-5` (Fase 19)** | **100%** (34/34) | **100%** (34/34) | **0,00 pp** | b=0/c=0, p=1,0 |

Custo: **US$ 0,1925**.

**A fragilidade desapareceu inteira.** Não encolheu — sumiu, dentro da resolução do instrumento.

## Minha previsão estava errada, e o pré-registro é o que torna isso dizível

Eu registrei Δ ≈ **−9 pp**, faixa aceitável **−18 a −2**. O medido foi **0,00** — **fora da faixa**.

| Afirmação pré-registrada | Veredito |
|---|---|
| `\|Δ_opus5\| < 29,41 pp` (a central, falsificável) | ✅ **confirmada** |
| Δ ≈ −9 pp, entre −18 e −2 (previsão pontual) | ❌ **refutada** |
| McNemar não significativo | ✅ confirmada (p=1,0) |

Eu estava **direcionalmente certo e quantitativamente errado**: previ que a fragilidade encolheria
mas deixaria resíduo, e apostei que existiria um piso — que o mapeamento pergunta → descrição →
identificador opaco custaria alguma coisa mesmo a um modelo forte. Não custou nada.

## O que isso fecha

A Fase 14 mediu a fragilidade e a deixou aberta como *"mitigar exige descrições mais ricas no
semantic layer"* — tratando-a como defeito de desenho da interface. **Era diagnóstico errado.**

> A fragilidade lexical não é estrutural do vocabulário fechado. É **capacidade do SUT**.

O Tier-A nunca precisou que os identificadores carregassem semântica; o Qwen 7B é que precisava.
Com as descrições intactas, um modelo capaz resolve `m2` → *"taxa/proporção do tráfego cobrado
automaticamente"* → a métrica certa, sem nenhuma pista no nome.

Consequência prática: **investir em descrições mais ricas é otimização de custo, não correção de
defeito**. Vale se você roda modelo barato — exatamente o mesmo formato do achado da Fase 18.

## A lei da Fase 18, terceira confirmação

> A ajuda de uma muleta é **inversamente proporcional à força do SUT**.

| Muleta | Vale no Qwen 7B | Vale no Opus 5 |
|---|---|---|
| Normalizadores F9/F10 | +17,7 pp | **0** (0 de 146 specs tocadas) |
| Resíduo de seleção métrica/dimensão | trava em 72–80% | **100%** |
| **Nomes semânticos nos identificadores** | **+29,4 pp** | **0,00 pp** |

Três medições independentes, mesma direção. Deixou de ser observação e virou regularidade.

## ⚠️ A terceira saturação — e por que ela agora é o gargalo do projeto

**100% nos dois braços significa que o instrumento acabou.** Não posso afirmar que a fragilidade é
*exatamente* zero: posso afirmar que está **abaixo da resolução de um conjunto de 34 itens**. O IC
Wilson vai a [0,8985; 1,0] nos dois lados — com 95% de confiança a fragilidade real é **no máximo
~10 pp**, não necessariamente 0.

Some-se às anteriores:

| Instrumento | Contra Qwen 7B | Contra Opus 5 |
|---|---|---|
| TEST-ANTT (171 itens) | 89,7% — discrimina | **100% — saturou** |
| Conjunto de robustez (34 itens) | 85,3% / 55,9% — discrimina | **100% / 100% — saturou** |
| Golden de κ (40 itens) | — | **κ = 1,0 — saturou** |

**Todos os instrumentos de avaliação deste projeto saturaram contra um SUT de fronteira.** Isso
promove "golden mais difícil" de item de backlog a **restrição que limita o eixo inteiro**: sem um
conjunto mais duro, nenhuma medição nova sobre modelo forte consegue produzir informação.

Não é fracasso do projeto — é o sinal de que o instrumento foi construído para um SUT de 7B e
cumpriu o papel dele. Mas é a próxima coisa a construir, e agora está claro por quê.

## O que **não** foi ajustado

O conjunto está selado desde a Fase 14 (`golden/robustez_antt.jsonl`, hash commitado). Nada foi
regerado, nenhum item removido, o gold é o mesmo. Os dois braços rodaram no **mesmo SUT, na mesma
execução** — comparar Opus 5 opaco contra Qwen original mediria o modelo, não a perturbação.

## Como sei que a perturbação de fato aplicou

Um 100%/100% seria trivial se o braço opaco tivesse recebido o catálogo normal por engano.
Verificado nas predições congeladas:

| Verificação | Resultado |
|---|---|
| `raw` do braço opaco citando nome real (`traffic_volume`…) | **0/34** |
| `raw` do braço original citando nome real | 34/34 |
| Marcador `opaco: true` na telemetria | 34/34 |
| Specs do opaco traduzidas de volta aos nomes reais | 34/34 |
| Modelo em ambos os braços | `claude-opus-5` |

O braço opaco emitiu `{"metrics": ["m2"], "group_by": ["e2"], "where": "… Dimension('c3') … = '9'"}`
onde o original emitiu `automation_rate` / `plaza__concessionaria` / `plaza__categoria_eixo`.
Mesma resposta, vocabulário opaco.
