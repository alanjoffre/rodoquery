# Fase 4 — RodoQuery Tier-A vs SQL cru (a tese, testada)

Esta é a fase que **testa a tese** num conjunto **cego**: o Semantic Layer governado supera o SQL
cru? Resposta, no TEST selado: **sim, por +54,8 pontos de Execution Accuracy, com p ≈ 0**.

## O sistema (Tier-A, semântico-primeiro)

O LLM **nunca escreve SQL**. Recebe a pergunta + o catálogo governado (7 métricas, dimensões,
valores) e devolve uma **spec** `{metrics, group_by, where, ...}` — ou **ABSTÉM** se nenhuma métrica
do catálogo responde. O MetricFlow compila o SQL correto a partir da spec (join/filtro/grão certos,
por construção). Código: `src/rodoquery/sistema.py`.

**Segurança de graça:** como o LLM só escolhe de um vocabulário fechado (nunca emite SQL), não há
superfície de injeção → o caminho Tier-A dispensa o sandbox (que existe para o SQL cru do Tier-B).

## A comparação é justa (isola a variável)

Os dois sistemas usam o **mesmo SUT** — `qwen2.5-coder:7b`, greedy (temp 0, top_k 1, seed 42). Mesma
pergunta, mesmo modelo. **Só muda a interface:** spec governada (Tier-A) vs SQL cru (`sql_cru`). Logo
o ganho é atribuível ao **Semantic Layer**, não a um modelo melhor. O baseline recebe prompt justo
(generoso no cosmético, sem entregar a regra de negócio — ver [FASE3](FASE3_BASELINES.md)).

## Resultado — TEST selado (53 itens: 42 respondíveis, 11 abstenção)

| Sistema | Execution Accuracy (n=42) | Abstenção (n=11) |
|---|---|---|
| **RodoQuery Tier-A** | **97,6%** — IC95 [87,7; 99,6] | **100%** (11/11) |
| `sql_cru` (baseline) | 42,9% — IC95 [29,1; 57,8] | 90,9% (10/11) |
| *oráculo semântico* | *100% por construção* | — |

**McNemar pareado (respondíveis):** b=23, c=0, **p ≈ 0**, Δ = **+54,8 pontos**. Ou seja: o Tier-A
acertou **23** itens que o SQL cru errou, e **0** no sentido contrário — dominância completa, não um
empate ruidoso.

**EX do Tier-A por estrato:** metrica_filtrada 8/8 · coalesce_nulo 4/4 · join_grao 6/6 ·
metrica_derivada 7/7 · grao_temporal 6/6 · valor_categorico **5/6** · controle_trivial 5/5.
Onde o SQL cru desabava (métrica filtrada/derivada, coalesce), o Semantic Layer acerta por construção.

## Honestidade (o que sustenta o número — e o que o limita)

- ✅ **Sem overfitting.** O prompt do Tier-A foi desenvolvido no **DEV** (94,7%); o TEST **cego** deu
  **97,6%** — dentro do IC, sem queda. As regras adicionadas ao prompt eram gerais (não coladas a
  itens do TEST, que nunca foi inspecionado durante o desenvolvimento).
- ✅ **Reprodutível.** As **predições são congeladas** em `reports/fase4/predicoes_*.json`: o
  scoring é 100% determinístico a partir delas e cada predição (spec/SQL cru) é **auditável**.
  > **Correção honesta (feita na Fase 5).** Ao construir esta fase eu observei um item de fronteira
  > mudando de veredito entre execuções e **atribuí isso a não-determinismo de GPU**. Depois medi:
  > 5 runs com greedy + `top_k=1` e modelo quente deram **EX idêntico (amplitude 0,0pp, 0 itens
  > instáveis)** — ver [FASE5](FASE5_MLOPS.md). Logo **eu não comprovei aquela causa**; a anomalia
  > ocorreu antes de fixar `top_k=1` e ficou sem explicação confirmada. Mantive o congelamento como
  > seguro barato, não como remédio para uma instabilidade demonstrada.
- ✅ **O scorer não é viciado.** `controle_trivial` = 5/5 para os DOIS sistemas (count simples: ambos
  acertam). O piso `sempre_abster` (Fase 3) tira 0% no eixo respondível.
- ⚠️ **Ressalva de N.** 42 respondíveis / 11 abstenção no TEST; abaixo da meta de ≥25/estrato. O IC
  do Tier-A é largo no limite inferior (87,7%) de propósito. Expandir o golden é backlog.
- ⚠️ **Erros honestos.** Tier-A errou **1/42**: `valor_categorico_06` ("receita das pagas em
  dinheiro") — mapeou o filtro por valor de forma imperfeita (mesma família do único erro do DEV). O
  `sql_cru` alucinou em `abstencao_03` ("custo operacional", sem dado de custo) em vez de abster.
- 🔒 **Segurança na prática.** A abstenção de 100% do Tier-A inclui perguntas de PII/fora-de-domínio
  onde o SQL cru tende a alucinar uma query — o vocabulário fechado do Semantic Layer é a defesa.

## Escopo e backlog

- O **Tier-B (SQL cru como fallback)** existe como baseline mas **não está ligado** no roteador:
  ligá-lo trocaria a segurança da abstenção por cobertura (cairia no SQL cru em vez de abster). É uma
  decisão de produto — fica como backlog documentado.
- κ **humano** do golden e **expansão de N** seguem como backlog (ver [GUIA_GOLDEN](GUIA_GOLDEN.md)).

## Reprodução

```bash
# sobe o SUT: ollama serve && ollama pull qwen2.5-coder:7b
python avaliar_fase4.py dev     # desenvolvimento (94,7%)
python avaliar_fase4.py test    # avaliação final selada (97,6%); reusa predições congeladas
```
