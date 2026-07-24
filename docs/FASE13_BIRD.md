# Fase 13 — Calibração externa: BIRD Mini-Dev (perguntas humanas)

Passo 3 do plano. Todo número deste projeto até aqui saiu de artefatos que **eu** construí: golden
set autorado por modelo, perguntas de template, catálogo desenhado por mim. Isso deixa uma objeção
legítima em aberto:

> *"O baseline de SQL cru vai mal (28,8% na ANTT) porque o modelo é fraco, ou porque o prompt é
> um espantalho?"*

O BIRD Mini-Dev responde isso com evidência que não depende de nada meu.

## O benchmark

[BIRD Mini-Dev](https://bird-bench.github.io/) — **500 perguntas escritas por humanos**, com **SQL
de referência humano** e `evidence` (conhecimento externo anotado por especialista), sobre **11
bancos SQLite** reais. Licença **CC BY-SA 4.0**. Dificuldade estratificada pelos autores:
148 *simple*, 250 *moderate*, 102 *challenging*.

Protocolo do próprio benchmark, para o número ser comparável: o prompt inclui o `evidence`, o
schema vem do `CREATE TABLE` real, e a Execution Accuracy compara o **resultado executado** do
predito contra o do gold — execução como oráculo, nunca LLM-juiz.

## Resultado

| | EX | IC95 |
|---|---|---|
| **`qwen2.5-coder:7b` (o SUT deste projeto)** | **43,4%** | [39,1; 47,8] |
| *simple* (n=148) | 58,1% | — |
| *moderate* (n=250) | 40,8% | — |
| *challenging* (n=102) | 28,4% | — |

O gradiente monotônico por dificuldade é um sinal de sanidade do harness: se o pipeline estivesse
quebrado, o resultado não se ordenaria assim.

Por banco, a variação é grande — de **81%** (`superhero`) a **17%** (`toxicology`) — o que mostra
que a dificuldade é dominada pela complexidade do schema, não pela pergunta.

## O que isso resolve

**1. O baseline não é espantalho.** O SUT tira 43,4% num benchmark público, independente e
anotado por humanos. Ele **sabe escrever SQL**. Logo, os 28,8% do SQL cru sobre a ANTT não são
artefato do meu prompt — estão na faixa da capacidade real do modelo. E os **86,9%** do Tier-A
sobre a mesma base, com o mesmo modelo, são contribuição da **interface**.

> Ressalva necessária: 43,4% (BIRD) e 28,8% (ANTT) **não são diretamente comparáveis** — schemas,
> domínios e dificuldades diferentes. O argumento é direcional: o modelo é competente, então o
> baseline não foi rebaixado de propósito.

**2. Perguntas humanas, gold humano.** Pela primeira vez o SUT é medido contra perguntas que
nenhum modelo escreveu, com gabarito que nenhum modelo produziu. Isso ataca de frente a fraqueza
de "perguntas de template" que venho declarando desde a Fase 2.

## O que isso NÃO resolve

- **O Tier-A não roda aqui.** O BIRD não tem semantic layer — são 11 bancos arbitrários, sem
  catálogo governado. Só o caminho de SQL cru é mensurável. Este número calibra o **modelo**, não
  o sistema.
- **κ humano do golden set do RodoQuery continua no backlog.** O BIRD traz anotação humana *dele*,
  não do *meu* conjunto. A afirmação honesta é: "o SUT foi avaliado contra anotação humana", e
  **não** "o golden set do RodoQuery tem κ humano".

## O achado que confirma o mecanismo da tese

A decomposição dos 283 erros:

| Causa | Nº | % |
|---|---|---|
| **a query executa e devolve o resultado ERRADO** | 212 | **74,9%** |
| referencia **coluna** que não existe | 59 | 20,8% |
| referencia tabela/função inexistente | 5 | 1,8% |
| não é SELECT single-statement | 4 | 1,4% |

Duas leituras, e as duas sustentam o desenho do RodoQuery:

**Três de cada quatro erros são silenciosos.** A query roda, devolve um número com cara de certo, e
nada avisa que está errado. É o modo de falha mais perigoso em analytics — e é o que o Test-Suite
EX deste projeto foi construído para pegar, porque nenhum erro de sintaxe o denunciaria.

**Um em cada cinco erros é alucinação de schema** — coluna que não existe, mesmo com o `CREATE
TABLE` inteiro no prompt. No caminho Tier-A isso é **estruturalmente impossível**: o LLM escolhe de
um vocabulário fechado, e um token inválido não compila — vira **abstenção**, não número errado.
É a mesma observação da Fase 12, agora confirmada num benchmark externo: a garantia do Semantic
Layer não depende de o modelo se comportar bem.

## Reprodução

```bash
bash ~/bird/baixar.sh          # pacote oficial do Mini-Dev (Google Drive, ~800 MB)
python avaliar_bird.py         # 500 perguntas; predições congeladas em reports/fase13/
```

> Nota operacional: o download do Google Drive falha com `Error 400` se a URL for passada inline
> pelo wrapper do `wsl.exe` — o `&` é corrompido. Por isso ele vive num arquivo `.sh`.
