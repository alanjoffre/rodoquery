# Fase 7 — Robustez: paráfrase, perturbação de schema e volume

Métrica dura do roadmap: **quanto o EX cai (com IC)**. Achado previsto: *"o held-out derruba
memorização daqui"*. **Resultado: parcialmente — e o que quebra não é o que eu esperava.**

Tudo é comparação **pareada** contra as predições **congeladas** da Fase 4 (mesmos itens, mesmo
gabarito), com McNemar. As perturbações mudam só a *entrada*; a resposta certa nunca muda.

## Resumo

| Perturbação | EX original | EX perturbado | Δ | McNemar | Significativo? |
|---|---|---|---|---|---|
| **Paráfrase** (n=39) | 97,4% [86,8; 99,6] | 89,7% [76,4; 95,9] | −7,7 pp | b=4, c=1, **p=0,375** | ❌ **não** |
| **Schema opaco** (n=42) | 97,6% [87,7; 99,6] | 83,3% [69,4; 91,7] | **−14,3 pp** | b=6, c=0, **p=0,031** | ✅ **sim** |

Abstenção: paráfrase 100% → 81,8% (n=11, minúsculo); schema opaco 100% → **100%** (intacta).

## 7a — Held-out de paráfrase

**O que testa.** As perguntas do golden foram geradas por **template** (fraqueza que declarei nas
fases 2 e 3). Se o sistema aprendeu o *fraseado* em vez da *semântica*, reescrevê-las como um
analista real falaria derruba o EX.

**Protocolo anti-viés** (sem isto, o teste não vale nada):
1. Paráfrases escritas por um **LLM diferente** (Claude) — rotuladas como geradas por máquina.
2. Um **2º LLM revisor, cego ao desempenho**, validou equivalência semântica **antes** de qualquer
   execução. Aprovou 50/53 e reprovou 3 — que foram **excluídas**:

   | Excluída | Por quê |
   |---|---|
   | `valor_categorico_08` | "Quantas cobranças falharam?" lê-se como `status=FAILED`, mas o gabarito é `audit_flag=COBRANCA_EM_FALHA` |
   | `valor_categorico_02` | "ficaram com falha" confunde as mesmas duas coisas |
   | `coalesce_nulo_04` | "passagens **foram cobradas**" insinua um filtro `status=COMPLETED` inexistente |

   Sem essa exclusão, a queda mediria **paráfrase ruim**, não fragilidade do modelo.
3. Comparação pareada nos mesmos ids contra as predições congeladas da Fase 4.

**Resultado honesto.** O ponto estimado cai 7,7 pp, mas **p=0,375**: com n=39 (4 quebras, 1
conserto) **não dá para rejeitar "não houve diferença"**. Os IC se sobrepõem largamente.
**Não posso afirmar que a paráfrase expôs memorização** — só que, se há efeito, é pequeno demais
para este N detectar. (O N insuficiente é o backlog que venho declarando desde a Fase 2.)

Quebraram: `controle_trivial_02`, `join_grao_02`, `metrica_derivada_06`, `metrica_filtrada_08`.
Consertou: `valor_categorico_06`.

## 7b — Perturbação de schema (identificadores opacos)

**O que testa.** O Tier-A acerta porque *entende a descrição* da métrica, ou porque casa a palavra
"receita" com o identificador `revenue`? Num warehouse real os nomes raramente são inglês
transparente.

**Como, sem tocar na fundação.** O dbt/MetricFlow mantém os nomes reais. Trocamos só a
**apresentação**: o prompt mostra `m03`, `d04`, `t_mes`… com as **mesmas descrições**; o modelo
responde em alias e traduzimos de volta antes de compilar. O gabarito não muda.

**Resultado: queda de 14,3 pp, estatisticamente significativa (p=0,031; 6 quebras, 0 consertos).**
O modelo **depende de pistas lexicais** dos identificadores. Ele não inventou nenhum código
(respeitou o vocabulário fechado) — errou *qual* código escolher.

**A abstenção ficou intacta (100%).** Faz sentido: reconhecer "não existe métrica para isto"
depende de o catálogo **não ter** algo, não do nome que as métricas têm. É uma separação limpa entre
duas competências.

> **Implicação prática:** ao levar isto para um warehouse com nomes crípticos (`fct_arr_v2`,
> `mtr_017`), esperar ~14 pp a menos — e investir em **descrições boas no semantic layer**, que é
> exatamente o artefato que a governança já exige.

## 7c — Volume

**Escopo honesto, declarado antes de medir:** no Tier-A a spec **não depende do volume** — a mesma
pergunta gera a mesma spec com 2 mil ou 20 mil linhas. Então volume **não testa a correção do
mapeamento** (o EX seria trivialmente idêntico, o que não é evidência de nada). O que ele testa de
verdade é o **custo de execução** do SQL governado e a boa-formação dos resultados.

Fato com **2.005 → 20.102 linhas (10,0×)**, mediana de 3 execuções por spec:

| Spec | 2 mil | 20 mil | fator |
|---|---|---|---|
| `controle_trivial_01` (agregado simples) | 0,0484 s | 0,0512 s | 1,06× |
| `coalesce_nulo_01` (série diária) | 0,0522 s | 0,0495 s | 0,95× |
| `join_grao_02` (join 2 dimensões) | 0,0453 s | 0,0468 s | 1,03× |
| `metrica_derivada_02` (ratio) | 0,0515 s | 0,0524 s | 1,02× |
| `valor_categorico_01` (filtro) | 0,0512 s | 0,0493 s | 0,96× |

**10× de dados → 1,02× de tempo** (mediano). Fortemente sublinear, e todos os resultados
bem-formados.

> **Ressalva que impede exagero:** 20 mil linhas ainda é **minúsculo** para o DuckDB — o tempo aqui
> é dominado por custo fixo (abrir conexão, planejar), não por varrer dados. Isto mostra que o SQL
> governado **não degrada a 10×**; **não** prova comportamento em milhões de linhas.
>
> **A leitura operacional que importa:** a execução custa ~0,05 s contra ~4,5 s de inferência
> (Fase 6). O volume de dados é ~1% da latência do usuário — **o gargalo é o LLM, não o warehouse.**

## O que esta fase mudou no sistema

O held-out achou um **bug no harness**: uma spec que compila no MetricFlow mas gera SQL
sintaticamente inválido **derrubava a avaliação inteira** em vez de contar como erro. Corrigido para
**falhar fechado** (`avaliacao.py`): SQL que não executa = predição errada, não crash.
As predições já estavam **congeladas**, então a correção não custou uma nova rodada de LLM — o
congelamento da Fase 4 pagou por si aqui.

## Limitações honestas

- **N pequeno domina.** 39–42 itens respondíveis: só efeitos grandes (≥14 pp) ficam significativos.
  A paráfrase pode ter um efeito real de ~8 pp que este estudo **não tem poder** para detectar.
- **Reuso do TEST.** O TEST foi selado e avaliado uma vez na Fase 4. Aqui ele é reusado para medir
  *deltas* de robustez. **Nenhum ajuste do sistema foi feito com base nestes resultados** — são
  medições, não desenvolvimento. Ainda assim, cada reuso erode um holdout; um estudo mais rigoroso
  usaria um conjunto de robustez próprio.
- **Paráfrases e validação são de máquina** (rotuladas), como o κ da Fase 2. Revisão humana segue no
  backlog.

## Reprodução

```bash
python rodar_parafrase.py      # 7a -> reports/fase7/heldout_parafrase.json
python rodar_perturbacao.py    # 7b -> reports/fase7/perturbacao_schema.json
python rodar_volume.py 20000   # 7c -> reports/fase7/volume.json
```
