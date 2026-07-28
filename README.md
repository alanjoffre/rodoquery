<div align="center">

# 🚂 RodoQuery

**Agente de Analytics (Text-to-SQL) sobre um lakehouse governado — pergunte em português, receba o número certo.**

Data Engineering × AI Engineering · avaliação com rigor · R$0 · **dados públicos reais (ANTT, CC-BY)**.

**Fases 0–18.** Todos os números abaixo são medidos e reproduzíveis em `reports/`. Roda com `docker compose up` ou `kubectl apply -k k8s`.

</div>

---

> **Tese:** o valor não é *"LLM gera SQL"*. É provar, **com número e intervalo de confiança**, que servir sobre o **Semantic Layer governado** (dbt/MetricFlow) dá a resposta **certa** onde o SQL cru dá uma resposta **plausível e errada**.

**A tese foi comprovada — em dado sintético, replicada em DADO REAL e testada contra dois SUTs de portes opostos.** Mesmo modelo nas duas pontas de cada linha; muda só a interface:

| Conjunto selado | SUT | Tier-A (spec → MetricFlow) | Baseline SQL cru | Δ | McNemar |
|---|---|---|---|---|---|
| **TEST-ANTT (n=146, dados REAIS)** | `claude-opus-5` | **100%** [97,4; 100] | 44,5% | **+55,5 pp** | 81 × 0, p≈0 |
| **TEST-ANTT (n=146, dados REAIS)** | `qwen2.5-coder:7b` | **89,7%** [83,7; 93,7] | 26,7% | **+63,0 pp** | 95 × 3, p≈0 |
| TEST-v2 sintético (n=167) | `qwen2.5-coder:7b` | 73,7% [66,5; 79,8] | 15,0% | +58,7 pp | 104 × 6, p≈0 |
| TEST-v1 sintético (n=42) | `qwen2.5-coder:7b` | 97,6% [87,7; 99,6] | 42,9% | +54,8 pp | 23 × 0, p≈0 |

Os conjuntos têm dificuldades diferentes e **não são comparáveis entre si** — o que se repete em todos é a **vantagem da interface governada**.

**Mas as duas primeiras linhas são comparáveis entre si** (mesmo conjunto, mesmo dia, só o SUT muda), e é delas que sai o achado mais útil do projeto:

> **A vantagem do Semantic Layer é inversamente proporcional à força do SUT: +63,0 pp com um 7B local, +55,5 pp com um modelo de fronteira.**

O gap **encolheu** porque o baseline quase dobrou (26,7% → 44,5%): um modelo de fronteira escreve SQL cru bem melhor. Esse é o número que um cético usaria contra a versão forte da tese — então ele está aqui em cima, não no anexo. O que sobra é um argumento **econômico e concreto**: o Semantic Layer vale mais justamente para quem roda modelo barato. Ver [Fase 18](docs/FASE18_PROVEDOR.md).

⚠️ **E o 100% é teto de instrumento, não do sistema:** este golden saturou para um SUT de fronteira. Com o Tier-A em 100%, o McNemar perde poder (`b=0` vira trivial) e o Δ real contra um golden mais duro seria **menor ou igual** a +55,5 pp. Golden mais difícil está no [backlog](#-backlog-declarado-o-que-não-está-feito).

**E o baseline não é um espantalho.** O mesmo modelo tira **43,4%** [39,1; 47,8] no [BIRD Mini-Dev](https://bird-bench.github.io/) — 500 perguntas e SQL de referência **humanos**, benchmark público. Ele sabe escrever SQL; o que muda o resultado é a **interface**, não a competência.

> ⚠️ **Leia o primeiro número, não o último.** O 97,6% da Fase 4 **não replica**: num conjunto 4× maior, cobrindo superfície do catálogo que a v1 nunca tocou, o Tier-A faz 73,7%. A tese sobrevive com folga; o valor absoluto, não. Ver [Fase 8](docs/FASE8_PODER.md).

**Dois normalizadores determinísticos recuperam boa parte disso** — sem trocar de modelo, sem tocar no prompt (holdout v3, n=181, pareado):

| Sistema | EX |
|---|---|
| Tier-A cru (Fase 4, congelado) | 66,9% |
| + normalizar ordenação (`["x","DESC"]` → `["-x"]`) | 71,8% |
| **+ normalizar `group_by` (remover dimensão já filtrada)** | **84,5%** |

**+17,7 pp em código**, ambos com **zero regressões**. As duas tentativas de ensinar as mesmas regras *pelo prompt* empataram — ver [Fase 9](docs/FASE9_CONSERTO.md) e [Fase 10](docs/FASE10_CATALOGO.md).

RodoQuery é o irmão de [**RodoIA**](https://github.com/alanjoffre/rodoia) no eixo de dados: um agente que traduz linguagem natural em consultas **seguras** sobre a plataforma [**toll-analytics-platform**](https://github.com/alanjoffre/toll-analytics-platform) (lakehouse de auditoria de pedágio, dados sintéticos, DuckDB dev → Databricks prod), reusando o **dbt Semantic Layer** já modelado.

## 🏗️ Arquitetura — o que de fato está servido

```
NL do usuário
   │
   ▼
[Tier A] LLM escolhe {métricas, dimensões, filtros} de um VOCABULÁRIO FECHADO
   │        → validado contra o catálogo → MetricFlow compila o SQL → executa (read-only)
   │        → fora do catálogo? ABSTÉM (não inventa)
   │
   └─ [Tier B] SQL cru + sandbox AST — construído e testado, DESLIGADO no roteador (ver backlog)
```

**Por que o Tier-A dispensa o sandbox:** o LLM nunca emite SQL. Ele emite uma *spec* sobre um vocabulário fechado; quem gera SQL é o MetricFlow. **Não há superfície de injeção** — a segurança é estrutural, não um filtro depois do fato.

O sandbox existe para o Tier-B e foi validado: **attack-block 100% (39/39)** com **falso-positivo 0% (10/10 consultas legítimas passam)** — as duas métricas juntas, porque bloquear tudo daria 100% de block e seria inútil.

## 📋 Fases — previsto × medido

| Fase | Métrica dura | **Resultado medido** |
|---|---|---|
| **0** · Fundação | harness reproduz; 0 objeto não-serving acessível | ✅ harness + canonicalizador em centavos + Test-Suite EX em 3 seeds |
| **1** · Sandbox | **attack-block = 100%** (gate duro) | ✅ **39/39 bloqueados, 0 falso-positivo** |
| **2** · Golden set | nº/estrato + IC · **κ do 2º anotador** | ⚠️ 76 itens, 8 estratos · **κ de máquina 1,0** (0,875 na sonda de ambiguidade) — **κ humano é backlog declarado** |
| **3** · Baselines | Execution Accuracy + Wilson | ✅ SQL cru **26,3%** no DEV [11,8; 48,8] |
| **4** · Sistema | Δ EX + **McNemar** | ✅ **97,6% × 42,9%, +54,8 pp, b=23/c=0, p≈0** |
| **5** · MLOps | gate ativo comprovado | ✅ gate em 3 níveis **pega 6/6 regressões injetadas** · p50 4,5 s / p95 7,9 s · **R$ 0,12/1k** |
| **6** · Serving + SLO | p95, throughput em 1 GPU, EX de canário | ✅ SLO atendido (p95 4,36 s em c=1) · canário 10/10 · capacidade real **~0,25 req/s** |
| **7** · Robustez | quanto o EX cai (com IC) | ⚠️ paráfrase −7,7 pp (**p=0,375, não significativo**) · **schema opaco −14,3 pp (p=0,031)** |
| **8** · Poder estatístico | **≥25 itens/estrato** (meta da Fase 2) | ✅ 223 no TEST-v2, 26–29/estrato · ⚠️ **o EX de 97,6% não replica: 73,7%** · 3 modos de falha novos |
| **9** · Conserto | Δ EX no holdout v3 (pareado) | ⚠️ reescrever o prompt **empatou** (p=0,89) · ✅ **normalizar em código: +5 pp, p=0,004, zero regressões** |
| **10** · Catálogo | Δ EX (pareado, determinístico) | ⚠️ limpar o catálogo **empatou** (p=1,0) · ✅ o gargalo real era outro: **+12,7 pp, p≈0, zero regressões** |
| **11** · Dados reais | fundação ANTT verificada ponta a ponta | ✅ **1,5 M de linhas reais (CC-BY)** substituem 2 mil sintéticas · catálogo nasce com **3 métricas** · 2 armadilhas do dado real pegas antes de virarem número errado |
| **12** · Tese sobre dado real | Δ EX + McNemar no TEST-ANTT selado | ✅ **86,9% × 28,8%, +58,1 pp, p≈0** · κ de máquina 0,977 · **2 bugs de harness pegos antes de virarem resultado** |
| **13** · Calibração externa | EX num benchmark público de perguntas **humanas** | ✅ **43,4%** [39,1; 47,8] no BIRD Mini-Dev · prova que o baseline **não é espantalho** · 75% dos erros são silenciosos |
| **14** · Quitação do backlog | resolver as 4 dívidas declaradas | ✅ gold de ranking corrigido (→**88,7%**) · roteador medido (Tier-B off por evidência) · robustez dedicada **−29,4 pp** · instrumento de κ humano pronto |
| **15** · Seleção + qualidade de label | Δ EX em holdout de ablação fresco | ✅ normalizador corrigido **+33,4 pp** · descrições **+5,5 pp** · ⚠️ **SUT 9B colapsa (5,6%)** · auditoria adversarial acha **7 labels ruins em 60** |
| **16** · Empacotamento | a stack roda fora da minha máquina | ✅ imagem **624 MB**, loop completo testado no container · **4 acoplamentos hardcoded** removidos · ⚠️ **container não cumpre o SLO nativo** (~2× mais lento) |
| **17** · Kubernetes | o deploy sobe e o sistema responde | ✅ cluster efêmero: 8/8 recursos, **MetricFlow compila com rootfs read-only**, **NetworkPolicy bloqueia (testado por diferença)**, **inferência ponta a ponta com o modelo real** · **sem HPA — e o [porquê](k8s/README.md) é medido** · ⚠️ GPU no `kind` **é impossível** no Docker Desktop (testado) |
| **18** · SUT de fronteira | Δ EX com o SUT trocado, mesmo conjunto | ✅ **100% × 44,5%, +55,5 pp** (US$ 0,96 de API) · **o gap encolhe: a vantagem é inversa à força do SUT** · normalizadores das F9/F10 valem **zero** aqui · ⚠️ **benchmark saturou** · 2 bugs de proveniência meus, pegos e corrigidos |

## 🔬 Previsões que a medição **refutou**

Este é o item de que mais me orgulho no projeto. Cada fase tinha um "achado honesto esperado" **pré-registrado**. Três não se confirmaram — e o repositório registra isso em vez de esconder:

| Previsão da Fase 0 | O que a medição disse |
|---|---|
| *"flakiness do LLM desestabiliza o gate"* (F5) | **Refutada.** 5 execuções com greedy + `top_k=1` e modelo quente deram EX **idêntico** (amplitude 0,0 pp). Eu havia escrito na doc da Fase 4 que uma falha vinha de não-determinismo de GPU — **sem ter medido**. Medi, estava errado, e **corrigi a doc**. |
| *"o held-out de paráfrase derruba memorização"* (F7) | **Não confirmada.** Queda de 7,7 pp com **p=0,375**: com n=39 não dá para rejeitar "não houve diferença". O que **de fato** quebra é trocar `revenue` por `m03` mantendo a mesma descrição: **−14,3 pp, p=0,031**. A fragilidade é **lexical nos identificadores**, não no fraseado. |
| *"em 6 GB a inferência serializa"* (F6) | **Confirmada — e pior.** Vazão cai 25% em c=4/8 e o p95 vai de 4,4 s para **43 s**. O ótimo de vazão (c=2) **não** é o ótimo de SLO: o controle de admissão certo foi semáforo **1** + espera 5 s, recusando o excesso com 503 em vez de enfileirar. |
| *"o EX de 97,6% descreve o sistema"* (implícito, F4) | **Refutada pela Fase 8.** Com N 4× maior e superfície nova, o EX é **73,7%**. Três buracos que o conjunto pequeno escondia: a regra `where`-vs-`group_by` **não compõe** com agrupamento (`coalesce_nulo` 15%); a regra de ranking **nunca fora avaliada** e não funciona (17%, sintaxe SQL em vez de MetricFlow); e a abstenção de 100% era artefato de perguntas óbvias — com *near-miss* cai para **55,6%**, errando por **substituição semântica silenciosa** ("taxa de estorno" → `suspect_rate`). |
| *"consertar a falha de ranking = melhorar o prompt"* (F9) | **Refutada pela medição.** Reescrever o prompt **empatou** no holdout (p=0,89): consertou ranking mas a prosa extra causou 18 erros novos de seleção de métrica. O **mesmo conserto em código** (normalizar `["x","DESC"]` → `["-x"]`) deu **+5 pp, p=0,004, zero regressões**. Falha mecânica se conserta em código, não com mais texto no prompt. |
| *"o resíduo de seleção exige um SUT maior"* (F14) | **Refutada como enunciada — e depois refinada.** *Maior* não basta: trocar `qwen2.5-coder:7b` por `gemma2:9b` (9B) derruba o EX de 86,1% para **5,6%**, com **23 de 39 specs de vocabulário inválido** contra **zero** do 7B — em vocabulário fechado, **aderência ao formato vence tamanho** (F15). Parte do resíduo era bug meu no normalizador (**+33,4 pp** ao corrigir). Mas a [Fase 18](docs/FASE18_PROVEDOR.md) fecha a nuance: um SUT genuinamente **mais capaz** (`claude-opus-5`) zera o resíduo — 100% nos mesmos estratos que travavam em 72–80%. O enunciado correto é **"não é tamanho, é capacidade"**. |
| *"a vantagem da interface é uma constante do sistema"* (implícito, F4–F15) | **Refutada pela Fase 18.** Com o SUT trocado por um modelo de fronteira no **mesmo conjunto**, o Δ cai de **+63,0 para +55,5 pp** — porque o baseline quase dobra (26,7% → 44,5%). A vantagem não é constante: é **inversamente proporcional à força do SUT**. Corolário que a mesma fase mede: os dois normalizadores determinísticos, que valem **+17,7 pp** sobre o 7B e tocaram 78/160 specs, tocam **0 de 146** no Opus 5. **A camada determinística é uma muleta cuja altura é exatamente a fraqueza do SUT.** |
| *"o gargalo é seleção de métrica; limpar o catálogo resolve"* (F10) | **Refutada.** Expor `revenue` e `revenue_cents` (a mesma grandeza) é desenho ruim, mas respondia por só **19%** dos erros — remover empatou (p=1,0). O diagnóstico revelou o gargalo real: em **81%** dos erros a métrica estava **certa** e o modelo **agrupava pela dimensão que já havia filtrado**. Corrigir isso em código deu **+12,7 pp, p≈0, zero regressões** — o maior ganho isolado do projeto. |

Bônus: **a abstenção ficou 100% intacta** sob perturbação de schema. Reconhecer "não existe métrica para isto" depende de o catálogo **não ter** algo, não do nome que as métricas têm — duas competências separadas, e a de segurança é a robusta.

## ⚖️ Princípios

- Toda métrica com **intervalo de confiança** (Wilson/bootstrap); n pequeno assumido e declarado.
- **Execução como oráculo** — nada de LLM-juiz para acurácia.
- **Test-suite EX**: a predição precisa bater o gold em **todas** as seeds de DB, o que mata acerto por coincidência.
- **Anti-circularidade:** o gold sai **sempre** do MetricFlow, nunca de SQL escrito à mão.
- Comparação de sistemas é **pareada** → **McNemar**.
- **Predições congeladas** em disco: o SUT é estocástico, a pontuação é determinística e auditável.
- Tudo em `reports/<fase>/*.json` carimbado (seed, git_sha, modelo, temperatura, versões).
- **O artefato não pode mentir sobre si mesmo.** O relatório descreve o *artefato*, não a execução que o releu — e a predição congelada grava **qual modelo de fato respondeu**. As duas regras nasceram de bugs meus na [Fase 18](docs/FASE18_PROVEDOR.md): as 342 predições da API ficaram rotuladas como `qwen2.5-coder:7b`, e re-pontuar sobre predições congeladas publicaria `custo_usd: 0`.
- **Dados públicos reais** (ANTT, CC-BY) desde a Fase 11; sintéticos nas Fases 0–10.
- **SUT local por padrão** (Qwen2.5-Coder-7B em 6 GB — teto declarado): custo **R$ 0**. O caminho de API existe, é opcional e **nunca é default** — o experimento inteiro da Fase 18 custou **US$ 0,96**.

## 🚫 O que eu decidi **não** medir — e por quê

**[Spider 2.0](https://spider2-sql.github.io/) (ICLR 2025) é o benchmark mais alinhado a esta tese** — tem inclusive uma trilha `Spider2-DBT`, com tarefas em nível de repositório dbt. Seria o alvo natural. Ficou de fora, e a razão é aritmética:

> Modelos de fronteira fazem **17–21%** no Spider 2.0. Este projeto roda um **Qwen2.5-Coder-7B em 6 GB de VRAM**. O resultado esperado é indistinguível de zero.

Um zero não separa "o Semantic Layer ajuda" de "o modelo não dá conta" — não mede a tese, mede o teto de hardware que já declarei na Fase 0. Rodá-lo renderia uma linha bonita no README (*"avaliado no Spider 2.0"*) e **nenhuma informação**.

A escolha honesta foi um benchmark onde o SUT tem sinal mensurável: o **BIRD Mini-Dev**, com 500 perguntas e SQL de referência **humanos** — que é também o que ataca o backlog de κ humano. Ver [Fase 13](docs/FASE13_BIRD.md).

Se o teto de hardware subir, Spider2-DBT é o próximo alvo natural.

## 🎯 Backlog declarado (o que **não** está feito)

Nenhum destes é surpresa: todos foram declarados na fase em que apareceram. A [Fase 14](docs/FASE14_BACKLOG.md) quitou as quatro dívidas abertas — ficou o que é genuinamente caro ou depende de humano.

**Ainda aberto (honestamente):**
- **Golden mais difícil** — *criado pela [Fase 18](docs/FASE18_PROVEDOR.md)*: com um SUT de fronteira o Tier-A faz **100%**, e o conjunto deixa de discriminar. O teto virou o do **instrumento**, não o do sistema. Medir o teto real exige um golden novo com o mesmo protocolo anti-vazamento das Fases 8/9 (specs inéditas, holdout selado antes de rodar). Enquanto isso, o +55,5 pp deve ser lido como **piso, não estimativa pontual**.
- **κ humano do golden RodoQuery** — o único item que **não é fabricável por máquina**, por princípio. A [Fase 14](docs/FASE14_BACKLOG.md) entrega o instrumento (`anotar_humano.py`, que se recusa a calcular sem input humano) e a [Fase 15](docs/FASE15_SELECAO.md) submete as labels a uma **auditoria adversarial** (88,3% corretas, 7 defeitos reais achados e removidos). Ainda assim é máquina auditando máquina: falta ~1h de um anotador humano. O instrumento tem um **anotador guiado** (`python anotar_humano.py anotar`) que monta a spec por escolhas numeradas, salva a cada item e é retomável — mas ele coleta, **nunca preenche**. `reports/fase14/kappa_humano.json` não existe, de propósito.
- **Promover o catálogo v2 ao serving** — a Fase 15 mediu **+5,5 pp** em holdout fresco, mas promovê-lo troca o SUT de todas as fases anteriores. Decisão a tomar explicitamente, não de passagem.
- **Fragilidade lexical do schema** — **medida** (−29,4 pp sob identificadores opacos, Fase 14); mitigar exige descrições mais ricas no semantic layer. Melhoria conhecida, não incógnita.
- **Concorrência do serving na API não foi medida** — o semáforo 1 veio de *"1 GPU não paraleliza"* (Fase 6), premissa que **não vale** para a API. O default lá é 8 e `/saude` expõe `concorrencia_medida: false` para não deixar ninguém confundir default com medição.

**Quitado na Fase 18:**
- ~~O resíduo de seleção é falha sistêmica da interface?~~ — **não era.** Um SUT de fronteira faz **100%** nos mesmos estratos que travavam em 72–80% no 7B. O resíduo era **capacidade do SUT**, e agora está caracterizado como tal em vez de suspeito.

**Quitado na Fase 15:**
- ~~Seleção de métrica/dimensão~~ — era **em boa parte bug meu**: o normalizador contradizia a convenção do próprio gold (**+33,4 pp** ao corrigir). Descrições melhores somam **+5,5 pp**. E "SUT **maior**" foi **refutado**: um 9B generalista colapsa (5,6%) onde o 7B *coder* faz 86,1%.

**Quitado:**
- ~~Ligar o Tier-B / roteador~~ — **medido na Fase 14**: fallback conservador captura o ganho sem custo, ingênuo derruba abstenção. Módulo `roteador.py` pronto; off no serving por **escolha baseada em evidência**.
- ~~Conjunto de robustez próprio~~ — **feito** (Fase 14): conjunto dedicado e selado, disjunto do TEST.
- ~~Resíduo de ranking~~ — **defeito de gold** (empate na zona de corte) corrigido; EX 86,9% → 88,7%.
- ~~Expandir N para ≥25/estrato~~ — feito na Fase 8 (223 itens no TEST-v2).

## 🐳 Rodar

```bash
bash docker/preparar_contexto.sh    # materializa a fundação no contexto de build
docker compose up --build           # Ollama + SUT + serviço

curl localhost:8077/saude
curl -X POST localhost:8077/consulta -H 'content-type: application/json' \
     -d '{"pergunta":"Quantos veículos passaram por concessionária?"}'
```

Imagem de **624 MB** com a fundação ANTT assada (dado público CC-BY), usuário não-root, healthcheck.
Com GPU: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up`.

Em Kubernetes: `kubectl apply -k k8s` — manifestos testados num cluster efêmero, com
`NetworkPolicy` restringindo o egress e **sem HPA de propósito** (a unidade de escala é a GPU, não
a CPU — [o porquê, com número](k8s/README.md)).

> ⚠️ **O container não cumpre o SLO da Fase 6** (medido nativo, com GPU): a quente são ~7 s com
> cache de spec e ~18 s sem, contra p50 4,5 s nativo. Não herdo o número — ver [Fase 16](docs/FASE16_DOCKER.md).

## 🚀 Setup de desenvolvimento

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm,serve]"
pytest                                    # 148 testes
python gate_regressao.py                  # gate nível A (contrato, sem GPU)
uvicorn rodoquery.servico:app --port 8077 # serving do Tier-A (SUT local)
```

**Trocar o SUT por API** (opcional; extra `api`, chave em `.env`, gitignorado):

```bash
pip install -e ".[api]"
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env      # nunca versionado
RODOQUERY_PROVEDOR=anthropic uvicorn rodoquery.servico:app --port 8077

python avaliar_fase18.py estimar                 # a conta ANTES de gastar, zero chamadas
python avaliar_fase18.py piloto --n 12 --confirmar
```

Nenhum caminho gasta crédito por acidente: o default é o SUT local, `--confirmar` é obrigatório
(sem ele o script sai com código 2 sem uma chamada), e `--teto-usd` é verificado **a cada item** —
um orçamento conferido só no fim não é um orçamento. Com o SUT pago, `/metricas` passa a expor
`custo.usd_acumulado`: descobrir o gasto pela fatura é tarde demais.

Pré-requisito: a fundação de dados vem do **toll-analytics-platform** buildado (`dbt build` → DuckDB + `manifest.json`). Ver [`docs/FUNDACAO.md`](docs/FUNDACAO.md).

**Documentação por fase:** [golden set](docs/GUIA_GOLDEN.md) · [baselines](docs/FASE3_BASELINES.md) · [sistema](docs/FASE4_SISTEMA.md) · [MLOps](docs/FASE5_MLOPS.md) · [serving/SLO](docs/FASE6_SERVING_SLO.md) · [robustez](docs/FASE7_ROBUSTEZ.md) · [poder estatístico](docs/FASE8_PODER.md) · [conserto](docs/FASE9_CONSERTO.md) · [catálogo](docs/FASE10_CATALOGO.md) · [dados reais ANTT](docs/FASE11_ANTT.md) · [tese sobre dado real](docs/FASE12_TESE_REAL.md) · [calibração BIRD](docs/FASE13_BIRD.md) · [quitação do backlog](docs/FASE14_BACKLOG.md) · [seleção e qualidade de label](docs/FASE15_SELECAO.md) · [empacotamento](docs/FASE16_DOCKER.md) · [Kubernetes](k8s/README.md) · [SUT de fronteira](docs/FASE18_PROVEDOR.md)

## 📄 Licença

Código: **MIT**.

Dados: **públicos e reais** desde a Fase 11 — volume de tráfego nas praças de pedágio federais,
publicado pela **ANTT** sob **CC-BY** (1,5 M de linhas, jan–mai/2026, sem PII). As Fases 0–10 usam
dados **sintéticos** gerados pelo [toll-analytics-platform](https://github.com/alanjoffre/toll-analytics-platform).
Nenhum dado pessoal ou proprietário em nenhuma fase.
