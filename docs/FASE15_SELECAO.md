# Fase 15 — Os dois itens "abertos": seleção de métrica/dimensão e κ humano

Os dois últimos itens do backlog estavam rotulados como "abertos por serem caros ou dependerem de
humano". Esta fase ataca ambos — um com experimento controlado, o outro com o máximo de rigor que
**não** exige inventar evidência.

## Parte 1 — Seleção de métrica/dimensão

Protocolo: holdout de **ablação fresco** (42 itens), gerado com semente nova e specs **inéditas**
contra o golden ANTT **e** o conjunto de robustez. Nada aqui foi visto antes. Quatro condições
pareadas, McNemar contra a baseline.

| Condição | EX (n=36) | Abstenção | McNemar vs A |
|---|---|---|---|
| **A.** baseline (normalizador da Fase 10) | 47,2% | 83,3% | — |
| **B.** normalizador corrigido | **80,6%** | 83,3% | b=0, c=12, **p=0,0005** |
| **C.** descrições desambiguadas (+B) | **86,1%** | 83,3% | b=0, c=14, **p=0,0001** |
| **D.** SUT maior — `gemma2:9b` | **5,6%** | 50,0% | b=15, c=0, p=0,0001 |

### B — o normalizador tinha um bug **meu**

A guarda "nunca esvaziar o `group_by`" (Fase 10) **contradizia a convenção do meu próprio gold**:
um filtro sozinho ("volume dos veículos tipo moto") é um **agregado** (`group_by=[]`), não uma
linha rotulada com o valor constante. Como os itens ambíguos "entre os X, por X" já saem do golden
na geração, esvaziar é o comportamento correto.

**+33,4 pp, zero regressões (b=0).** O maior ganho isolado do projeto — e não era um problema do
modelo, era uma inconsistência entre duas peças minhas.

### C — descrições melhores funcionam, mas o retorno é menor

O catálogo v2 diz, para cada métrica, **o que ela não é**, lista palavras-armadilha ("arrecadação",
"estorno", "pico") e dá uma regra explícita contra `group_by` espúrio. **+5,5 pp sobre B**
(86,1% × 80,6%), também sem regressões.

A leitura honesta: o lever de descrição é real, mas **secundário** ao conserto estrutural. Vale o
esforço — e é barato — porém quem estava segurando o número era o bug do normalizador.

### D — o modelo maior **colapsou**, e não é bug de harness

`gemma2:9b` (9B) contra `qwen2.5-coder:7b` (7B), **mesmo prompt, mesmos itens**: 5,6%. Antes de
reportar, verifiquei o mecanismo — 5,6% é assinatura de formato quebrado, não de incompetência:

| Violação (39 specs do gemma) | Nº |
|---|---|
| token de `group_by` **inválido** | **23** |
| `where` sem a sintaxe `Dimension()` | 4 |
| **as mesmas violações no qwen 7B** | **0** |

O gemma produz JSON bem-formado com conteúdo inválido: emite `"entidades"` e `"tempo"` — os
**rótulos das seções** do catálogo — como se fossem tokens, e escreve `where` em SQL puro.

> **Achado: em tarefa de vocabulário fechado, aderência ao formato vence tamanho.** Um 9B
> generalista perde feio para um 7B *coder*. O lever "SUT maior" é **refutado** na forma em que eu
> o havia proposto — o que importa não é escala, é o modelo ser treinado para respeitar contratos
> estruturais. Trocar por um 9B seria uma regressão de 41 pp.

### Efeito no TEST-ANTT (re-pontuado, predições congeladas)

| | antes da Fase 15 | depois |
|---|---|---|
| EX Tier-A | 88,7% | **89,7%** [83,7; 93,7] |
| `valor_categorico` | 72,0% | **80,0%** |
| McNemar (Δ tese) | +60,7 pp | **+63,0 pp** |

## Parte 2 — κ humano: auditoria adversarial (o que é possível **sem** fabricar)

O κ humano exige um humano. O que **posso** fazer é submeter as labels ao teste mais duro que uma
máquina permite — e foi o que fiz.

**Auditoria adversarial**: diferente do κ de máquina (2º anotador cego que *re-anota*), aqui o
crítico **vê a spec do autor** e tem missão única: **encontrar labels erradas**. É um teste mais
forte de qualidade de rótulo. Amostra de 60 itens.

**Resultado: 53 corretas / 7 defeituosas (88,3%).** Todos os 7 com mecanismo verificável:

| Defeito | Nº | Mecanismo |
|---|---|---|
| `ranking_degenerado_cardinalidade` | 4 | `limit=3` sobre dimensão com **exatamente 3** valores — o "top 3" devolve o domínio inteiro |
| `filtro_degenera_metrica` | 1 | `commercial_share` filtrada por `categoria_eixo='6'` — **todo veículo de 6 eixos é comercial**, métrica presa em 1,0 |
| `order_by_temporal_ausente` | 1 | "em cada dia" sem o token de tempo no `order_by`, divergindo dos outros 25 itens diários |
| `ambiguidade_dimensao` | 1 | "classe de veículo" — no jargão de pedágio, "classe" é a categoria tarifária por **eixos** |

Os 7 foram **removidos antes de qualquer nova medição** (mesmo protocolo da Fase 7 e da 9), e duas
classes novas viraram guarda no gerador:

- **Degeneração por dimensão CORRELACIONADA** — a G1 só olhava a dimensão que a métrica usa
  *diretamente*. Filtrar `commercial_share` por `categoria_eixo` degenera por **correlação física**
  (eixos altos ⇒ comercial). Guarda estendida.
- **Termo ambíguo no domínio** — "classe de veículo" saiu do vocabulário do gerador.

O auditor também **declarou o que decidiu não marcar** (`commercial_share` *agrupada* por
`categoria_eixo` carrega sinal real, ao contrário de filtrada) — uma auditoria que não delimita a
própria fronteira não é auditável.

### O que isto é, e o que não é

**É:** evidência forte de qualidade de rótulo (88,3% correto, com mecanismo em cada defeito) e um
processo que **encontrou erros reais** que três rodadas de κ de máquina não encontraram.

**Não é κ humano.** Continua sendo máquina avaliando máquina. O instrumento de anotação humana
(Fase 14) segue pronto e não preenchido; `reports/fase14/kappa_humano.json` não existe de propósito.
O item permanece aberto — mas o golden agora passou por um crivo adversarial, o que é mais do que
tinha antes.

## Limitações honestas

- **A ablação tem n=36 respondíveis.** Os efeitos B e C são grandes (+33 pp, +5,5 pp) e
  significativos, mas os IC são largos; a ordem de grandeza é confiável, o decimal não.
- **D testou UM modelo maior**, não "modelos maiores". A conclusão correta é "um 9B generalista
  perde para um 7B coder nesta tarefa", não "escala não ajuda".
- **A auditoria é de máquina**, com a mesma família de vieses que ela audita.
- **O catálogo v2 (C) ainda não está no serving.** O ganho foi medido em holdout fresco, mas
  promovê-lo ao sistema principal muda o SUT de todas as fases anteriores — decisão para tomar
  explicitamente, não de passagem.

## Reprodução

```bash
python golden/gerar_ablacao_antt.py     # holdout fresco, disjunto de tudo
python avaliar_fase15.py                # 4 condições, pareadas, McNemar
python golden/exportar_auditoria.py     # amostra de 60 labels
#   (auditoria adversarial roda como agente independente)
python aplicar_auditoria.py             # remove os defeitos, re-sela o TEST
python avaliar_fase12.py test           # re-pontua no TEST auditado
```
