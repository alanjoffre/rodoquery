# Fase 6 — Serving + SLO

Métricas duras do roadmap: **p95, throughput em 1 GPU, EX de canário**. Achado honesto previsto:
*"em 6 GB a inferência serializa"*. **Confirmado — e pior que o previsto.**

Hardware medido: **NVIDIA RTX 4050 Laptop, 6.141 MiB de VRAM**.

## 1. O serviço

`src/rodoquery/servico.py` (FastAPI). **Só o Tier-A é exposto**: o usuário manda pergunta em
linguagem natural, o LLM devolve uma *spec* do vocabulário fechado e o **MetricFlow** gera o SQL.
O usuário **nunca** injeta SQL — não há superfície de injeção por construção.

| Endpoint | O quê |
|---|---|
| `POST /consulta` | pergunta → resposta (com a **spec exposta**, auditável) ou abstenção honesta |
| `GET /saude` | liveness, modelo, specs em cache, limite de admissão |
| `GET /metricas` | p50/p95, taxa de abstenção/erro, cache hit, latência **por etapa** |

### Cache spec→SQL (otimização com base no breakdown)

O breakdown de latência mostrou que a compilação do MetricFlow (subprocess `mf query --explain`)
custava **~2,7 s** por consulta. Como a compilação é **data-independente** (a mesma spec sempre gera
o mesmo SQL — é o que sustenta o Test-Suite EX), dá para cachear com segurança:

| Etapa | 1ª chamada | 2ª chamada (cache) |
|---|---|---|
| compilação | 2,72 s | **0,00 s** |
| total | 12,84 s | **2,33 s** |

## 2. Load test — a hipótese do roadmap, testada

12 requisições por nível, cache aquecido (para o gargalo medido ser a **inferência**):

| Concorrência | Vazão (req/s) | Ganho vs c=1 | p50 | p95 |
|---|---|---|---|---|
| 1 | 0,251 | 1,00× | 4,04 s | 4,36 s |
| 2 | **0,279** | 1,11× | 6,96 s | 8,24 s |
| 4 | 0,189 | **0,75×** | 21,5 s | 23,1 s |
| 8 | 0,192 | **0,76×** | 38,1 s | **43,1 s** |

**Confirmado, e pior:** a vazão não só deixa de escalar — ela **cai 25%** em c=4/8, enquanto o p95
**explode 10×** (4,4 s → 43,1 s). Em 6 GB não cabem múltiplos contextos: concorrência vira fila
**mais** contenção. O ótimo medido é **c=2**.

## 3. A resposta de engenharia: controle de admissão

Medição vira decisão. Mas cheguei na configuração certa **errando duas vezes** — e as duas tentativas
ficam registradas porque o raciocínio é o valor:

| Tentativa | Config | Resultado em c=8 | Veredito |
|---|---|---|---|
| 1ª | semáforo=2, espera **30 s** | p95 = 37,3 s, **0 recusas** | ❌ "aceitava tudo" e violava o SLO — a espera era incoerente com um SLO de 10 s |
| 2ª | semáforo=2, espera **6 s** | p95(atendidas) = **11,4 s**, 7/12 recusadas | ❌ perto, mas ainda viola: em c=2 a inferência já custa ~8,2 s, **não sobra orçamento de fila** |
| **3ª** | semáforo=**1**, espera **5 s** | p95(atendidas) = **8,85 s**, 3/12 atendidas, 9 recusadas | ✅ SLO respeitado nas atendidas |

**O achado que isso revelou:** o **ótimo de vazão não é o ótimo de SLO**. c=2 rende 11% mais vazão
(0,279 vs 0,251 req/s) mas dobra a latência (8,2 s vs 4,4 s), consumindo todo o orçamento do SLO.
Para um serviço com SLO, **previsibilidade vale mais que 11% de vazão** — então o limite é **1**.

> O limitador **não cria vazão** (a GPU é o teto). O que ele faz é trocar *"aceitar tudo e violar o
> SLO para todo mundo"* por *"atender dentro do SLO e **recusar o excesso na hora**"*. A recusa é a
> degradação honesta: o cliente sabe imediatamente em vez de esperar 43 s.

## 4. Canário de correção

Load test diz se está **rápido**; canário diz se continua **certo** — é o que pega "subiu, respondeu
200, devolveu número errado", que nenhum health check percebe.

- Roda no **DEV**, não no TEST: o TEST é selado e vale como avaliação final única (Fase 4). Um
  canário que roda de hora em hora o queimaria. O EX de canário é **sinal operacional**, não a
  métrica científica.
- Correção medida contra o gold gerado pelo **MetricFlow no mesmo banco** que o serviço consulta.

**Resultado: 10/10 (EX de canário = 1,00)** — 8 respondíveis batendo o gold através do serviço vivo
+ 2 abstenções corretas.

### O canário achou um bug (que é o ponto de existir)

Na 1ª execução o canário deu **9/10**: em `abstencao_07` (*"liste as placas dos veículos com mais
transações suspeitas"* — pedido de PII) o Tier-A tentou responder, a spec não compilou e o serviço
devolveu **erro 500**. Ele **não** inventou uma resposta, mas 500 é a postura errada.

Correção: spec que não compila = o modelo não conseguiu mapear a pergunta → **abstenção honesta**,
não 500. **Falhar fechado.** Aplicado **no serviço**, não no `tier_a` — assim a avaliação congelada
da Fase 4 segue válida (é endurecimento operacional, não mudança do sistema avaliado).

## 5. SLO

Alvos **derivados da medição**, não inventados (um "p95 < 1 s" seria fantasia num 7B em 1 GPU):

| Objetivo | Alvo | Medido | |
|---|---|---|---|
| p95 até c=1 | ≤ 10 s | 4,36 s | ✅ |
| p95 até c=2 | ≤ 10 s | 8,24 s | ✅ |
| EX de canário | ≥ 0,85 | 1,00 | ✅ |
| Taxa de erro | ≤ 0,05 | 0,00 | ✅ |
| Concorrência admitida | 2 | semáforo ativo | ✅ |

**SLO atendido = true** (`reports/fase6/slo.json`). O SLO só é prometido **dentro do limite de
admissão** — acima disso o serviço recusa, e isso está declarado.

### Sob sobrecarga (8 clientes = 8× a capacidade admitida)

| | p95 (atendidas) | atendidas | 503 |
|---|---|---|---|
| sem limitador | 43,1 s ❌ | 12/12 | 0 |
| **com limitador** | **8,85 s ✅** | 3/12 | 9 (**75% de recusa**) |

Recusar 75% de uma sobrecarga de 8× **não é bug, é a capacidade real** (~0,25 req/s numa GPU).
O limitador não inventa capacidade: ele escolhe *quem* é atendido dentro do SLO em vez de degradar
todo mundo. Precisar de mais vazão exige mais GPU ou modelo menor — não há truque de software.

## 6. Limitações honestas

- Um único nó, 1 GPU, modelo 7B local: **~0,25–0,28 req/s** é o teto real. Escalar exige mais GPU
  ou modelo menor — não há truque de software que contorne.
- O cache spec→SQL é **por processo** e morre no restart; se o manifesto do dbt mudar, o serviço
  precisa ser reiniciado (não há invalidação automática).
- O canário roda no DEV: mede saúde operacional, **não** substitui a avaliação do TEST selado.
- O load test usou 12 requisições por nível — suficiente para ver a tendência, pequeno para
  cravar percentis finos.

## Reprodução

```bash
# sobe o serviço (precisa do Ollama no ar)
PYTHONPATH=src uvicorn rodoquery.servico:app --host 127.0.0.1 --port 8077

python load_test.py 12          # varredura de concorrência -> reports/fase6/load_test.json
python canario.py 8             # correção contra o serviço vivo -> reports/fase6/canario.json
python verificar_admissao.py    # prova que o limitador contém o estrago
python verificar_slo.py         # verifica o SLO (exit != 0 se violado)
```
