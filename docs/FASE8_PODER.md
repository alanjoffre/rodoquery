# Fase 8 — Poder estatístico: o que aparece quando o N cresce

Meta pré-registrada desde a Fase 2: **≥25 itens por estrato**. Cumprida — TEST-v2 tem 223 itens,
26–29 por estrato. Mas o resultado importante não é o N: é **o que o N revelou**.

> **Manchete honesta: o EX de 97,6% da Fase 4 não replica.** Num holdout fresco, com specs
> inéditas e cobrindo superfície do catálogo que a v1 nunca tocou, o Tier-A faz **73,7%** nos
> mesmos 7 estratos. A tese continua de pé — e com margem maior —, mas o número que eu vinha
> reportando descrevia uma fatia bem mais estreita do catálogo do que parecia.

## O que mudou no golden

| | v1 | v2 |
|---|---|---|
| Itens | 76 | 264 |
| TEST | 53 | **223** |
| Respondíveis no TEST | 42 | 196 |
| Estratos | 8 | 9 (`ranking` é novo) |
| N por estrato no TEST | 4–11 | **26–29** |

**Toda spec da v2 é inédita** — nenhuma repete uma assinatura canônica da v1. Isso é verificado no
gerador, não prometido: repetir specs com outro fraseado inflaria o N com itens correlacionados e
faria o IC de Wilson fingir uma precisão que não existe.

**Superfície que a v1 nunca cobria**, descoberta ao auditar o catálogo contra o golden:
`revenue_cents` e `revenue_leakage_cents` (métricas nunca testadas), `transaction__audit_flag` como
group_by, os valores `POSSIVEL_DUPLICIDADE` e `VALOR_INVALIDO`, e **ranking/top-N** — sobre o qual
o prompt do sistema tem uma regra que **nenhum item jamais avaliou**.

### Regra anti-degenerado (novo filtro de qualidade)

Um item cujo gold é **idêntico nas 3 variantes de seed** não oferece proteção de Test-Suite EX: o
resultado não depende dos dados, então uma spec **errada** que produza o mesmo valor (tipicamente
`0` ou `1.0`) acerta em todas as variantes. Isso infla o EX.

Acontece quando o filtro da pergunta conflita com o filtro **embutido** na métrica — `revenue` (só
COMPLETED) filtrado por `FAILED` dá sempre 0; `suspect_rate` filtrado por uma flag de auditoria dá
sempre 1.0. **16 itens saíram** por essa regra; na reposição, **12 de 23** candidatos testados eram
degenerados — ou seja, é uma propriedade pervasiva do catálogo, não uma exceção.

**A v1 também tem o defeito: 2 itens, ambos no TEST.** Análise de sensibilidade:

| TEST-v1 | Tier-A | sql_cru |
|---|---|---|
| como reportado na Fase 4 | 97,62% | 42,86% |
| **sem os 2 degenerados** | **97,50%** | 45,00% |

Impacto desprezível, McNemar segue p≈0 — a conclusão da Fase 4 **sobrevive** ao defeito. (Um dos
dois, `valor_categorico_02`, já havia sido reprovado pelo revisor cego da Fase 7 por outro motivo.
Duas evidências independentes contra o mesmo item.)

### Concordância inter-anotador

κ de **máquina** (2º anotador LLM cego, 4 chunks disjuntos, só perguntas + catálogo): **1,0** em
264 itens; decisão respondível × fora-de-escopo **264/264**.

Sendo franco sobre o que isso vale: κ=1,0 sobre perguntas de template com convenções compartilhadas
é quase vacuoso — foi a mesma crítica que fiz a mim mesmo na Fase 2, onde a sonda de perguntas
naturais derrubou o κ para 0,875. **O valor real aqui é outro:** as 32 abstenções *near-miss* que
autorei ("ticket médio", "taxa de estorno", "receita por UF") foram **todas confirmadas
fora-de-escopo** pelo anotador cego. Sem esse aval, uma queda na abstenção mediria rótulo ruim.
κ humano segue no backlog.

## Resultados no TEST-v2

Sistema **congelado**: prompt, catálogo e SUT byte a byte iguais aos da Fase 4. Isto é replicação,
não desenvolvimento.

| Conjunto | Tier-A | sql_cru | Δ | McNemar |
|---|---|---|---|---|
| TEST-v1 (Fase 4, n=42) | 97,6% [87,7; 99,6] | 42,9% | +54,8 pp | 23 × 0, p≈0 |
| **TEST-v2, 7 estratos originais (n=167)** | **73,7% [66,5; 79,8]** | 15,0% | **+58,7 pp** | **104 × 6, p≈0** |
| Pooled v1+v2 (n=209) | 78,5% [72,4; 83,5] | 20,6% | +57,9 pp | 127 × 6, p≈0 |
| `ranking` — cobertura nova (n=29) | 17,2% [7,6; 34,6] | 24,1% | −6,9 pp | 5 × 3, **p=0,73** |

**A tese fica mais forte, não mais fraca:** a vantagem sobe de +54,8 pp para +58,7 pp. O que cai é
o valor absoluto do Tier-A — e o baseline cai junto.

### EX por estrato (Tier-A, TEST-v2)

| Estrato | EX | IC95 |
|---|---|---|
| `metrica_filtrada` | **100%** (26/26) | [87,1; 100] |
| `grao_temporal` | 89,7% (26/29) | [73,6; 96,4] |
| `join_grao` | 89,7% (26/29) | [73,6; 96,4] |
| `valor_categorico` | 79,3% (23/29) | [61,6; 90,2] |
| `metrica_derivada` | 65,4% (17/26) | [46,2; 80,6] |
| **`ranking`** | **17,2%** (5/29) | [7,6; 34,6] |
| **`coalesce_nulo`** | **14,8%** (4/27) | [5,9; 32,5] |

## Os três achados que só o N maior expôs

### 1. A regra do prompt não **compõe**

`coalesce_nulo` desaba para 14,8%. A causa não é o coalesce — é composição:

> "Qual foi a receita das transações **que falharam** **em cada dia**?"
> **gold:** `where status='FAILED'`, `group_by=[day]`
> **predito:** `group_by=[day, status]`, sem `where`

O prompt tem uma regra exatamente contra isso ("filtro por um valor específico é `where`, NÃO
group_by") — e ela **funciona quando o filtro está sozinho**: `valor_categorico` faz 79,3%. Ela
quebra quando há **também** um agrupamento: o modelo vê duas dimensões citadas e agrupa pelas duas.
A v1 nunca testou filtro + group_by na mesma pergunta, então isso era invisível.

### 2. Regra de prompt nunca avaliada não funciona

`ranking` faz 17,2%. O modelo emite `order_by: ["revenue", "DESC"]` — **sintaxe SQL** — em vez do
`-revenue` que o MetricFlow exige. A spec **não compila**.

O prompt manda usar `ordenado`/`limit` para ranking mas **nunca documenta a sintaxe descendente**.
Eu decidi, antes de rodar, **não tocar no prompt** — justamente para que este buraco aparecesse em
vez de ser silenciosamente consertado. É o custo de uma regra que existia há 4 fases sem nenhum
item que a exercitasse.

Consequência secundária que vale registrar: **é o único estrato onde o Tier-A não vence o
baseline** (17,2% × 24,1%, p=0,73 — empate estatístico). A vantagem do Semantic Layer **não é
automática**: ela depende de o catálogo/prompt documentarem de fato a capacidade.

As specs que não compilam contam como **erro**, não como crash — graças à correção *fail-closed*
da Fase 7. O congelamento das predições pagou por si de novo: o diagnóstico saiu sem rodar o LLM
outra vez.

### 3. A abstenção de 100% era um artefato de perguntas fáceis

Abstenção cai de **100% (v1)** para **55,6% (v2)**. As abstenções da v1 eram óbvias (lucro, CPF,
clima). As da v2 são *near-miss* de propósito — e o padrão de falha é limpo:

**Acerta (15/27)** quando falta uma agregação ou entidade claramente ausente: média, mediana,
máximo, ROI, impostos, operador, endereço, quilômetros.

**Erra (12/27) por substituição semântica silenciosa** — escolhe um vizinho plausível:

| Pergunta fora-de-escopo | O que o modelo respondeu |
|---|---|
| "taxa de **estorno**" | `suspect_rate` |
| "taxa de **conversão**" | `suspect_rate` |
| "**inadimplência** dos usuários" | `suspect_rate` |
| "índice de **reclamações**" | `suspect_rate` |
| "receita por **concessionária**" | `group_by = transaction__plaza` |
| "quanto cada praça **gasta com manutenção**" | `revenue_cents` |
| "receita **acumulada**" / "**crescimento**" / "**variação** %" | a métrica base, sem o operador |

Este é o modo de falha que importa em produção: **um número errado com cara de certo**. É pior que
um erro de SQL, que pelo menos aparece.

### Nota arquitetural que corrige a Fase 7

Numa das abstenções o modelo emitiu `metric_time__hour` — **um token que não existe no catálogo**.
Eu havia escrito na Fase 7 que o modelo "respeitou o vocabulário fechado". Mais preciso: o
vocabulário fechado **não é respeitado pelo modelo — é imposto pelo compilador**. A spec inválida
não compila e vira abstenção. A garantia é **estrutural**, não comportamental. O argumento a favor
do Semantic Layer fica mais forte assim, não mais fraco: ele não depende de o LLM se comportar.

## O que o N comprou (e o que não comprou)

| | v1 | v2 | pooled |
|---|---|---|---|
| Largura do IC — EX global | 11,9 pp | 13,3 pp | 11,1 pp |
| Largura do IC — mediana **por estrato** | **39,0 pp** | **26,9 pp** | — |

**O IC global não estreitou** apesar de ~4× o N, e isso não é um erro: a largura de Wilson é máxima
perto de 0,5 e mínima nos extremos. Com o ponto estimado saindo de 0,976 para 0,737, o ganho de N
foi compensado pela saída da borda. Reportar "aumentei o N, logo o IC estreitou" seria falso.

**O ganho real é por estrato:** a mediana da largura cai de 39 pp para 27 pp. Antes, um estrato com
n=4 tinha IC de ~50 pp — praticamente não dizia nada. Agora dá para afirmar coisas como
"`coalesce_nulo` está entre 6% e 33%" e "`metrica_filtrada` está acima de 87%", que são afirmações
acionáveis.

## Limitações honestas

- **v2 é mais difícil que v1, de propósito.** A queda de 97,6% → 73,7% **não** é só regressão: boa
  parte vem de superfície nova e mais dura (métricas em centavos, `audit_flag`, filtro combinado
  com agrupamento). A leitura correta não é "o sistema piorou" e sim **"o número da Fase 4
  descrevia uma fatia estreita"**. Não dá para separar os dois efeitos com este desenho.
- **`controle_trivial` tem n=1 no TEST-v2** e não escala: só existem 9 specs triviais possíveis
  (`transactions` × {sem dim, 8 dims}) e a v1 já usou 7. É um controle de sanidade, não um estrato
  de hipótese — inflá-lo exigiria torná-lo não-trivial.
- **Pooled reusa o TEST-v1**, que já havia sido consumido na Fase 4 e nos deltas da Fase 7. Está
  rotulado como pooled em toda parte.
- **Perguntas ainda são de template** e os anotadores são máquinas. κ humano segue no backlog.
- **Não consertei nada depois de ver o TEST-v2.** Corrigir o prompt agora e remedir no mesmo
  conjunto seria ajustar ao teste. O conserto é uma fase própria, com validação no DEV-v2 e
  medição num holdout novo.

## Backlog atualizado

1. **Documentar a sintaxe de ordenação** (`-metrica`) e a composição filtro+group_by no prompt →
   validar no DEV-v2 → medir em holdout novo. É a maior melhoria disponível hoje.
2. **Abstenção contra vizinho semântico** — o catálogo precisa dizer o que uma métrica **não** é
   (`suspect_rate` ≠ estorno ≠ conversão ≠ inadimplência).
3. κ humano; ligar o Tier-B; conjunto de robustez próprio (herdados).

## Reprodução

```bash
python golden/gerar_autor_v2.py     # 264 candidatos, specs inéditas
python gerar_gold_v2.py             # gold via MetricFlow nas 3 variantes
python completar_v2.py              # regra anti-degenerado + reposição
python golden/kappa_maquina_v2.py   # κ de máquina (2º anotador cego)
python golden/montar_split_v2.py    # split + selo do TEST-v2
python avaliar_fase8.py test        # Tier-A e sql_cru (predições congeladas)
python analise_fase8.py             # replicação, cobertura nova, pooled, poder
```
