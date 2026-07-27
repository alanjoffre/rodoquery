# Fase 16 — Empacotamento: de "acredite no README" para `docker compose up`

Até aqui o RodoQuery era 15 fases de rigor **trancadas numa máquina**. O serviço da Fase 6 existia,
com SLO e controle de admissão medidos — mas ninguém além de mim conseguia rodá-lo. Esta fase
resolve isso, e o caminho revelou mais dívida técnica do que eu esperava.

## Quatro acoplamentos que impediam empacotar

Empacotar não é escrever um Dockerfile — é **descobrir o que estava preso à minha máquina**:

| Acoplamento | Era | Agora |
|---|---|---|
| binário do MetricFlow | `~/toll-foundation/.venv/bin/mf` | `RODOQUERY_MF_BIN` |
| URL do Ollama | `http://localhost:11434` **hardcoded** | `RODOQUERY_OLLAMA_URL` |
| sistema servido | `import tier_a` (sintético) fixo | `RODOQUERY_FUNDACAO_ATIVA` |
| banco | `settings.toll_duckdb` fixo | resolvido pela fundação ativa |

Os defaults **não mudaram**: `fundacao_ativa="sintetica"` e os caminhos originais. Nada das Fases
0–15 se comporta diferente — a mudança é que agora *dá para sobrescrever*.

## A imagem

**624 MB**, `python:3.12-slim`, usuário não-root (uid 10001), healthcheck em `/saude`.

Duas decisões que valem explicação:

**O `dbt parse` roda no BUILD, não no runtime.** O manifesto semântico é determinístico; assá-lo
tira ~10 s do primeiro request. Isso só é seguro por causa de um invariante que o projeto já
sustentava: **compilar spec→SQL é data-independente** (é o que fundamenta o Test-Suite EX). O `mf`
não precisa do banco para gerar SQL — só a execução precisa.

**O DuckDB (27 MB) vai assado, não montado.** É dado público (ANTT, CC-BY). Assado, `docker compose
up` funciona em qualquer máquina — que é o motivo de a imagem existir. Montado do host, só
funcionaria na minha.

## O que foi de fato testado

Não publico Dockerfile que não rodei. Verificado dentro do container:

| Etapa | Resultado |
|---|---|
| build (inclui `dbt parse`) | ✅ |
| serviço sobe, `/saude` responde | ✅ `{"fundacao":"antt","banco":"antt_analytics.duckdb"}` |
| **MetricFlow compila** | ✅ 159 chars de SQL |
| **DuckDB executa** | ✅ 30 concessionárias reais |
| **loop completo** (pergunta → spec → SQL → número) | ✅ ver abaixo |
| `docker compose config` (base e +GPU) | ✅ válida |

Pergunta real, resposta real, dentro do container:

```
POST /consulta  {"pergunta": "Quantos veículos passaram por concessionária?"}
→ spec: {metrics:[traffic_volume], group_by:[plaza__concessionaria]}
→ 30 linhas: RIOSP 52.657.885 · AUTOPISTA LITORAL SUL 36.436.912 · ...
```

E a taxa de automação por sentido deu **0,620 / 0,626** — consistente com o global de **0,6230**
que verifiquei contra SQL puro na Fase 11. O dado atravessa a stack sem se corromper.

## ⚠️ O container NÃO cumpre o SLO da Fase 6

Isto é o achado desconfortável, e ele precisa estar aqui e não escondido:

| Cenário | LLM | Compilação | Total |
|---|---|---|---|
| Fase 6 (nativo, GPU) | — | 2,72 s | **p50 4,5 s** |
| Container, frio | 79,0 s | 8,97 s | **88,1 s** |
| Container, quente + cache | 7,3 s | **0,00 s** | **7,3 s** |
| Container, quente + cache miss | 9,4 s | 8,65 s | **18,2 s** |

**~2× mais lento a quente, e o subprocess do `mf` triplicou** (8,65 s contra 2,72 s nativo). O SLO
de 10 s medido na Fase 6 **não vale para esta configuração** — foi medido nativo, com GPU, sem o
salto de rede container→host.

Duas leituras honestas:

1. **O cache de spec da Fase 6 se paga aqui mais do que lá.** Compilação vai a **0,00 s** no
   repeat — num ambiente onde o miss custa 8,65 s, o cache deixou de ser otimização e virou o que
   separa 7 s de 18 s.
2. **Republicar o SLO exigiria remedir.** Não vou herdar o número da Fase 6 para um ambiente
   diferente — seria o mesmo erro de comparar 86,9% (ANTT) com 73,7% (sintético).

Ressalva de escopo: o teste apontou para um Ollama **externo** (o do host), para não rebaixar
4,7 GB de modelo. O caminho `docker compose up` completo — com o Ollama do próprio compose — tem a
config validada mas **não foi executado ponta a ponta**. O que mudaria é a latência de rede, não a
lógica.

## Como rodar

```bash
bash docker/preparar_contexto.sh    # materializa a fundação no contexto de build
docker compose up --build           # sobe Ollama + puxa o SUT + sobe o serviço

curl localhost:8077/saude
curl -X POST localhost:8077/consulta -H 'content-type: application/json' \
     -d '{"pergunta":"Quantos veículos passaram por concessionária?"}'
```

Em GPU (recomendado — sem ela o Ollama roda em CPU e a latência sai da escala acima):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up
```

## Próximo passo

Com a imagem existindo, o manifesto Kubernetes é curto: `/saude` já é *readiness probe* natural, e
o controle de admissão (semáforo 1 + 503) já implementa a política de carga que o HPA precisaria
respeitar. Fica para a Fase 17.
