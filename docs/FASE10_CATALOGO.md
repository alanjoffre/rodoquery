> **Antes de tudo: minha hipótese estava errada.** Eu disse que limpar o catálogo "ataca o gargalo
> direto". A medição diz que **não**: empate absoluto (p=1,0). Mas o diagnóstico de *por que* não
> funcionou revelou o gargalo verdadeiro — e consertá-lo deu **+12,7 pp com zero regressões**, o
> maior ganho isolado do projeto.

# Fase 10 — Catálogo limpo (refutado) e o modo de falha dominante (consertado)

## Parte 1 — A hipótese do catálogo, e por que ela caiu

O semantic model da fundação mostra, preto no branco, que as métricas de centavos e as de BRL não
são conceitos distintos:

```yaml
revenue:             type: derived   expr: revenue_cents / 100.0
revenue_leakage_brl: type: derived   expr: revenue_leakage_cents / 100.0
```

As de centavos são o bloco interno; as de BRL, a apresentação. Expor as duas a uma interface de
linguagem natural é erro de governança: "qual a receita?" passa a ter **duas respostas certas**.
Minha hipótese era que isso explicava o gargalo de seleção de métrica das Fases 8 e 9.

**Desenho da medição** (pareado, variável isolada): o subconjunto do TEST-v3 cujo gold usa apenas
as 5 métricas limpas — 155 itens, 125 respondíveis (56 excluídos por usarem métrica de centavos).
O **PROMPT é idêntico byte a byte** nos dois braços; muda só a lista de métricas. Os dois braços
recebem o normalizador de ordem da Fase 9.

| | EX (n=125) | Abstenção (n=30) |
|---|---|---|
| catálogo de 7 métricas | 71,2% [62,7; 78,4] | 53,3% |
| catálogo limpo (5) | 70,4% [61,9; 77,7] | 56,7% |
| McNemar | b=7, c=6, **p=1,0** | — |

**Empate absoluto.** A decomposição dos 36 erros do catálogo de 7 explica:

| Causa do erro | Nº |
|---|---|
| **métrica CERTA, erro em `group_by`/`where`/ordem** | **29 (81%)** |
| escolheu métrica de centavos (a hipótese) | 7 (19%) |

A ambiguidade de unidade respondia por **19%** dos erros, não pelo grosso. Removê-la consertou ~6
itens e desestabilizou outros 7 (o `ranking` caiu 11→7, o que não tem relação nenhuma com unidade —
é a variação natural do modelo quando o prompt muda de tamanho). Resultado líquido: zero.

**O que eu mantenho e o que eu retiro.** Retiro a afirmação de que o catálogo era o gargalo — não
era. Mantenho que expor a mesma grandeza em duas unidades é **desenho ruim**: continua indefensável
em governança, só não é a causa da imprecisão. Por isso **não** troquei o sistema atual para o
catálogo de 5 (não há ganho medido, e invalidaria parte dos golden sets) — mas o catálogo dos dados
reais da ANTT já nasce com uma métrica por conceito.

## Parte 2 — O modo de falha dominante, e o conserto que funcionou

Os 29 erros de "métrica certa, estrutura errada" têm um padrão único e repetido:

```
pergunta:  "receita das transações estornadas em cada dia"
gold:      where status='REVERSED'   group_by=[metric_time__day]
predito:   where status='REVERSED'   group_by=[metric_time__day, transaction__status]
                                                                 ^^^^^^^^^^^^^^^^^^^^
                                            agrupa pela dimensão que ele mesmo filtrou
```

**22 dos 29** são isso. É o mesmo problema de *composição* que a Fase 8 isolou e que a reescrita de
prompt da Fase 9 tentou ensinar com prosa — e falhou.

E, como a sintaxe de ordenação, isso é **mecanicamente detectável**: agrupar por uma coluna presa a
um único valor produz exatamente um grupo — acrescenta uma coluna constante e **nenhuma
informação**. É um `if`, não uma questão de julgamento:

```python
def normalizar_group_by(group_by, where):
    presas = dimensoes_filtradas_por_igualdade(where)   # só filtros de IGUALDADE
    limpo = [d for d in group_by if d not in presas]
    return limpo if limpo else group_by                 # nunca esvazia
```

Verificação antes de medir: nas **26** predições do TEST-v3 com esse padrão, o gold **nunca** agrupa
pela dimensão filtrada — 26 candidatas a conserto, **0 quebras possíveis**.

**Resultado (determinístico, sobre as predições já congeladas — nenhuma chamada de LLM):**

| | EX (respondíveis, n=181) | McNemar |
|---|---|---|
| só normalizador de ordem (produção da Fase 9) | 71,8% [64,9; 77,9] | — |
| **+ normalizador de `group_by`** | **84,5% [78,6; 89,1]** | **b=0, c=23, p≈0** |

**Zero regressões, de novo.** Por estrato, todos sobem ou ficam iguais:

| Estrato | antes | depois |
|---|---|---|
| `grao_temporal` | 16/27 | **24/27** (+8) |
| `coalesce_nulo` | 21/29 | **27/29** (+6) |
| `metrica_derivada` | 8/15 | **12/15** (+4) |
| `valor_categorico` | 14/24 | **17/24** (+3) |
| `ranking` | 13/26 | **15/26** (+2) |
| `join_grao`, `metrica_filtrada` | — | inalterados |

### O acumulado dos dois normalizadores

| Sistema | EX no TEST-v3 |
|---|---|
| Tier-A cru (Fase 4, congelado) | 66,9% |
| + normalizador de ordem (Fase 9) | 71,8% |
| **+ normalizador de `group_by` (Fase 10)** | **84,5%** |

**+17,7 pp com duas regras determinísticas**, sem tocar no prompt, sem trocar de modelo e sem uma
única chamada extra de LLM na medição.

## A lição que se confirma pela segunda vez

A Fase 9 já tinha mostrado: **falha mecânica se conserta em código, não com prosa no prompt.** Aqui
isso se repete com um efeito três vezes maior. As duas tentativas de ensinar essas regras por texto
(Fase 9) empataram; as duas implementações em código deram ganho estrito e significativo.

O padrão vale como heurística de engenharia: quando o erro do modelo é **estruturalmente
identificável a partir da própria saída**, ele pertence à camada de validação/normalização — não ao
prompt. O prompt é para o que exige julgamento.

## Limitações honestas

- **O TEST-v3 já foi inspecionado** na Fase 9. Isto é sinal forte (b=0, p≈0, mecanismo verificado
  item a item), mas a confirmação limpa sai no holdout **novo** da migração para a ANTT.
- **A regra não resolve o caso ambíguo** "entre as transações estornadas, por status", em que as
  duas leituras se defendem. Esses itens foram removidos do v3 pelos anotadores cegos **antes** de
  qualquer medição — quem resolve isso é o golden bem construído, não a regra.
- **`join_grao` e `metrica_filtrada` não mudam** porque suas perguntas não combinam filtro com
  agrupamento. O ganho é concentrado onde o modo de falha existe, como esperado.
- Seleção de métrica **continua** sendo o resíduo real: dos 28 erros que sobram, a maioria não é
  mais estrutural. Esse é o problema caro, e segue aberto.

## Reprodução

```bash
python avaliar_fase10.py           # catálogo 7 × 5 -> EMPATE (p=1,0)
python avaliar_fase10_groupby.py   # + normalizador de group_by -> +12,7pp, p≈0, 0 regressões
```
