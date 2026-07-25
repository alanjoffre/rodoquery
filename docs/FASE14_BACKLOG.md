# Fase 14 — Quitando o backlog declarado

As quatro dívidas que o projeto vinha declarando, atacadas de uma vez. Três se resolvem com
medição e código; uma **não pode** ser resolvida por mim, e a resolução honesta é dizer por quê e
entregar o instrumento.

## #1 — κ humano do golden: **instrumento pronto, não fabricado**

O κ humano é dívida desde a Fase 2. Eu **não posso produzi-lo**: gerar specs e chamá-las de humanas
seria fabricar evidência — a fronteira que este projeto nunca cruza. O que eu posso fazer é reduzir
o custo de "trabalho de construção" para "~1h de um humano real".

`anotar_humano.py` gera uma **folha de anotação** estratificada (40 itens), mostra pergunta +
catálogo (cego às specs do autor), e calcula o κ com o **mesmo** `concordancia_mapeamento` do κ de
máquina — então o número será comparável, não ad-hoc. O comando `kappa` **se recusa a rodar** sem
input humano:

```
$ python anotar_humano.py kappa
NENHUM item preenchido. O κ humano NÃO pode ser calculado por máquina —
este script se recusa a inventar. Preencha 'spec_humano' à mão primeiro.
```

**Status honesto:** `reports/fase14/kappa_humano.json` não existe. O item continua **aberto** até
um humano preencher a folha — mas agora é uma tarefa de 1h, não de construção. Nada aqui é
preenchido por máquina.

## #2 — Resíduo de `ranking`/`valor_categorico`: metade era **defeito de gold**

O resíduo de 72% (Fase 12) tinha **duas naturezas**, e só a diagnose separou:

**Defeito de gold (resolvido).** 10 itens de ranking pediam "as N com maior X" onde a zona de corte
cai num **empate** — muitos eram "os **3 sentidos**" quando só existem **2 sentidos**. Com empate,
`LIMIT N` sem desempate total é **não-determinístico**: o modelo produz a spec **idêntica ao gold**
e ainda "erra", porque a ordem entre iguais mudou. Isso é a mesma família da regra anti-degenerado
(Fase 8), agora na *ordem* e não no *valor*. Detectados por uma propriedade do gold (aplicada a
**todos** os rankings, não só às falhas) e removidos; o TEST foi re-selado. Duas guardas novas no
gerador impedem a recorrência: **G4-estrutural** (`limit` < cardinalidade da dimensão) e
**G4-dados** (empate na zona de corte, checado no `preparar_antt`).

Efeito, das predições **já congeladas** (sem re-rodar o LLM):

| | antes | depois |
|---|---|---|
| EX global | 86,9% | **88,7%** |
| `ranking` | 72,0% | **80,0%** |
| McNemar (Δ tese) | +58,1 pp | **+60,7 pp** |

**Resíduo genuíno (caracterizado, não resolvido).** O que sobra (~7 em `valor_categorico`) é o
problema **caro** que eu vinha classificando como "julgamento, não mecânica". A diagnose mostra
duas sub-causas:
- **ambiguidade de canonização** — "volume dos veículos tipo moto" com ou sem a coluna-rótulo
  "Moto"; ambas defensáveis, o gold escolheu uma;
- **seleção de dimensão errada** — o modelo agrupa por `categoria_eixo`/`concessionária` que a
  pergunta não pede.

Isto **não** tem conserto mecânico, e eu **não** o persegui com um ajuste de normalizador — o
TEST-ANTT já foi visto, e ajustar contra ele seria fitar ao teste. Fica caracterizado e aberto: o
caminho é descrição melhor ou SUT maior, medido em holdout novo.

## #3 — Tier-B no roteador: desligado por **medição**, não por suposição

O roteador "Tier-A primário; Tier-B fallback" sempre esteve no README, com o Tier-B construído
(sandbox 39/39) mas nunca ligado. Medi duas políticas nas predições congeladas:

| Política | EX respondíveis | Abstenção |
|---|---|---|
| Só Tier-A | 88,7% | **88,0%** |
| Fallback **ingênuo** (Tier-A abstém → Tier-B) | 89,3% | **72,0%** ❌ |
| Fallback **conservador** (só quando a spec não compila) | 89,3% | **88,0%** ✅ |

**Achado central:** o Tier-A **nunca abstém** num respondível neste TEST. Logo o fallback ingênuo
só pode **estragar** abstenções corretas — o Tier-B alucina onde o Tier-A calou (−16 pp de
abstenção, 4 itens). O fallback **conservador** dispara só em spec-não-compila (2 casos), recupera
1 e **não estraga nenhuma abstenção**.

**Decisão de engenharia, agora com evidência:** o ganho conservador é +0,7 pp (1 item em 175). Fiar
uma segunda chamada de LLM + a superfície do sandbox no caminho quente do serviço por isso **não
compensa**. O roteador vive em `roteador.py` — função pura, 5 testes, política conservadora pronta;
ligar é trocar uma linha. O serviço segue Tier-A por **escolha medida**, não por omissão.

## #4 — Conjunto de robustez **dedicado** (disjunto do TEST)

A Fase 7 mediu robustez reusando o TEST — cada reuso erode um holdout. Aqui: um conjunto **próprio**
(`robustez_antt.jsonl`), semente diferente, specs **inéditas** contra o golden ANTT inteiro (34
itens após o gold), **selado**. O TEST-ANTT não foi tocado.

Perturbação de **schema opaco** (identificadores `m1`/`c2`…, MESMAS descrições — a que a Fase 7
mostrou ser a fragilidade real):

| | EX | IC95 |
|---|---|---|
| catálogo original | 85,3% | [69,9; 93,6] |
| **schema opaco** | **55,9%** | [39,5; 71,1] |
| Δ | **−29,4 pp** | McNemar b=11, c=1, **p=0,006** |

**A fragilidade lexical é ainda maior aqui do que na Fase 7** (−14,3 pp no sintético). Faz sentido:
os nomes da ANTT (`traffic_volume`, `plaza__tipo_cobranca`) carregam **mais** semântica que os
aliases opacos, então trocá-los custa mais. Confirmado num holdout limpo e dedicado, a conclusão da
Fase 7 se fortalece: **a competência do Tier-A depende fortemente das pistas lexicais dos
identificadores** — investir em descrições boas no semantic layer não é cosmético, é o que sustenta
a acurácia.

## Placar do backlog

| # | Item | Status |
|---|---|---|
| 1 | κ humano | **instrumento pronto**; aberto até input humano (1h de trabalho, não de build) |
| 2 | resíduo 72% | **defeito de gold resolvido** (→88,7%); resíduo caro caracterizado e aberto |
| 3 | Tier-B no roteador | **resolvido**: medido, módulo pronto, off por escolha baseada em evidência |
| 4 | robustez dedicada | **resolvido**: conjunto próprio selado; schema opaco −29,4 pp (p=0,006) |

## Reprodução

```bash
python corrigir_gold_ranking.py       # #2: remove ranking com empate, re-sela o TEST
python avaliar_fase12.py test         # re-pontua no TEST limpo (predições congeladas) -> 88,7%
python avaliar_roteador.py            # #3: políticas de fallback, dos resultados congelados
python anotar_humano.py amostra 40    # #1: gera a folha (depois um HUMANO preenche)
python golden/gerar_robustez_antt.py  # #4: conjunto dedicado, disjunto
python rodar_robustez_antt.py         # #4: gold + original × schema opaco
```
