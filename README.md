<div align="center">

# 🚂 RodoQuery

**Agente de Analytics (Text-to-SQL) sobre um lakehouse governado — pergunte em português, receba o número certo.**

Data Engineering × AI Engineering · avaliação com rigor · **dados públicos reais da ANTT (CC BY)**

[![CI](https://github.com/alanjoffre/rodoquery/actions/workflows/ci.yml/badge.svg)](https://github.com/alanjoffre/rodoquery/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Testes](https://img.shields.io/badge/testes-216%20passando-brightgreen.svg)
![Gate](https://img.shields.io/badge/gate%20de%20regressão-7%2F7-brightgreen.svg)
![Fases](https://img.shields.io/badge/fases-0–22-e0a326.svg)
![Sandbox](https://img.shields.io/badge/attack--block-39%2F39%20·%20FP%200%25-brightgreen.svg)
![Custo](https://img.shields.io/badge/custo%20de%20API-US%24%201%2C82-blue.svg)

[**🗺️ Fases**](#️-fases--previsto--medido) · [**🔬 O que a medição refutou**](#-o-que-a-medição-refutou) · [**🏗️ Arquitetura**](#️-arquitetura--o-que-de-fato-está-servido) · [**✅ Rastreabilidade**](#-rastreabilidade-requisito--fase) · [**🚀 Rodar**](#-rodar) · [**🎯 Backlog**](#-backlog-declarado)

</div>

---

> **Tese:** o valor não é *"LLM gera SQL"*. É provar, **com número e intervalo de confiança**, que servir sobre o **Semantic Layer governado** (dbt/MetricFlow) dá a resposta **certa** onde o SQL cru dá uma resposta **plausível e errada**.

O LLM **nunca escreve SQL**. Ele escolhe métricas e dimensões de um **vocabulário fechado** e devolve uma *spec*; quem gera o SQL é o MetricFlow. Fora do catálogo, **abstém**.

## 📊 O número

Mesmo modelo nas duas pontas de cada linha — muda só a interface:

| Conjunto selado | SUT | Tier-A (spec → MetricFlow) | Baseline SQL cru | Δ | McNemar |
|---|---|---|---|---|---|
| **TEST-ANTT** (n=146, dado REAL) | `claude-opus-5` | **100%** [97,4; 100] | 44,5% | **+55,5 pp** | 81 × 0, p≈0 |
| **TEST-ANTT** (n=146, dado REAL) | `qwen2.5-coder:7b` | **89,7%** [83,7; 93,7] | 26,7% | **+63,0 pp** | 95 × 3, p≈0 |
| TEST-v2 sintético (n=167) | `qwen2.5-coder:7b` | 73,7% [66,5; 79,8] | 15,0% | +58,7 pp | 104 × 6, p≈0 |
| TEST-v1 sintético (n=42) | `qwen2.5-coder:7b` | 97,6% [87,7; 99,6] | 42,9% | +54,8 pp | 23 × 0, p≈0 |

**As duas primeiras linhas são comparáveis entre si** — mesmo conjunto, só o SUT muda — e é delas que sai o achado mais útil do projeto:

> **A vantagem do Semantic Layer é inversamente proporcional à força do SUT: +63,0 pp com um 7B local, +55,5 pp com um modelo de fronteira.**

O gap **encolheu** porque o baseline quase dobrou (26,7% → 44,5%). Esse é o número que um cético usaria contra a versão forte da tese, então está aqui em cima. O que sobra é um argumento econômico concreto: **o Semantic Layer vale mais justamente para quem roda modelo barato.**

**E o baseline não é espantalho.** O mesmo modelo tira **43,4%** [39,1; 47,8] no [BIRD Mini-Dev](https://bird-bench.github.io/) — 500 perguntas e SQL de referência **humanos**. Ele sabe escrever SQL; o que muda o resultado é a **interface**.

> ⚠️ **Os três limites deste número, declarados.** (1) O **100% é teto de instrumento**: com o Tier-A saturado, o McNemar perde poder (`b=0` vira trivial) e o Δ real contra um conjunto mais duro seria **menor ou igual**. (2) A [Fase 20](docs/FASE20_DURO.md) construiu esse conjunto mais duro e ele **saturou igual** — o teto é da **superfície do catálogo**, não do benchmark. (3) No mesmo conjunto duro a **abstenção caiu para 50%**, com um modo de falha novo: pedem *proporção*, o sistema responde *contagem*.
>
> A [Fase 21](docs/FASE21_CATALOGO_RICO.md) atacou o (3) e mostrou que o defeito era **do catálogo**, não do modelo: ele expunha `automation_rate` e escondia os irmãos da mesma partição. Completando as partições (3 → 7 métricas), o rebaixamento de tipo cai de **6 de 6 falhas para 1 de 8** e a abstenção sobe para **75%** — ao custo de **1 regressão** nova (contagem × proporção). É uma troca medida, não um ganho grátis.

## 🗺️ Fases — previsto × medido

**22 fases (0–21) · 216 testes · gate 7/7 · custo total de API US$ 1,82.** Cada número aponta para um relatório versionado em `reports/` com carimbo de proveniência (seed, git_sha, modelo, versões) — e é conferido por `python auditar_documentacao.py`.

| Fase | Métrica dura | **Resultado medido** |
|:---:|---|---|
| **0** · Fundação | harness reproduz; 0 objeto não-serving acessível | ✅ Test-Suite EX em 3 seeds + canonicalizador em centavos |
| **1** · Sandbox | **attack-block = 100%** (gate duro) | ✅ **39/39 bloqueados, falso-positivo 0%** (10/10 legítimas passam) |
| **2** · Golden set | nº/estrato + IC · **κ do 2º anotador** | ✅ 76 itens, 8 estratos · κ de máquina 1,0 · **κ humano 1,0** (n=40, IC [0,912; 1,0]) — dívida [quitada](docs/FASE14_KAPPA_HUMANO.md) |
| **3** · Baselines | Execution Accuracy + Wilson | ✅ SQL cru **26,3%** no DEV [11,8; 48,8] |
| **4** · Sistema | Δ EX + **McNemar** | ✅ **97,6% × 42,9%, +54,8 pp**, b=23/c=0, p≈0 |
| **5** · MLOps | gate ativo comprovado | ✅ gate em 3 níveis **pega 6/6 regressões injetadas** · p50 4,5 s / p95 7,9 s |
| **6** · Serving + SLO | p95, vazão em 1 GPU, canário | ✅ SLO atendido (p95 4,36 s em c=1) · canário 10/10 · capacidade **~0,25 req/s** |
| **7** · Robustez | quanto o EX cai (com IC) | ⚠️ paráfrase −7,7 pp (**p=0,375, não significativo**) · schema opaco −14,3 pp (p=0,031) |
| **8** · Poder estatístico | **≥25 itens/estrato** | ✅ 223 no TEST-v2 · ⚠️ **o 97,6% não replica: 73,7%** · 3 modos de falha novos |
| **9** · Conserto | Δ EX no holdout v3 (pareado) | ⚠️ reescrever o prompt **empatou** (p=0,89) · ✅ **normalizar em código: +5 pp, p=0,004, zero regressões** |
| **10** · Catálogo | Δ EX (pareado, determinístico) | ⚠️ limpar o catálogo **empatou** (p=1,0) · ✅ o gargalo real era outro: **+12,7 pp, p≈0** |
| **11** · Dados reais | fundação ANTT verificada ponta a ponta | ✅ **1,5 M de linhas reais (CC BY)** · catálogo nasce com 3 métricas · 2 armadilhas pegas antes de virarem número errado |
| **12** · Tese sobre dado real | Δ EX + McNemar no TEST-ANTT selado | ✅ **86,9% × 28,8%, +58,1 pp** na medição original¹ · **2 bugs de harness pegos antes de virarem resultado** |
| **13** · Calibração externa | EX num benchmark de perguntas **humanas** | ✅ **43,4%** [39,1; 47,8] no BIRD Mini-Dev · **74,9% dos erros são silenciosos** |
| **14** · Quitação do backlog | as 4 dívidas declaradas | ✅ gold de ranking corrigido · roteador medido (Tier-B off **por evidência**) · robustez dedicada **−29,4 pp** |
| **15** · Seleção + qualidade de label | Δ EX em holdout de ablação fresco | ✅ normalizador corrigido **+33,4 pp** · ⚠️ **SUT 9B colapsa (5,6%)** · auditoria adversarial acha **7 labels ruins em 60** |
| **16** · Empacotamento | a stack roda fora da minha máquina | ✅ imagem **624 MB**, loop completo no container · 4 acoplamentos hardcoded removidos · ⚠️ **não herda o SLO nativo** |
| **17** · Kubernetes | o deploy sobe e o sistema responde | ✅ cluster efêmero: 8/8 recursos · rootfs read-only · **NetworkPolicy testada por diferença** · inferência ponta a ponta · **sem HPA, [e o porquê é medido](k8s/README.md)** |
| **18** · SUT de fronteira | Δ EX com o SUT trocado, mesmo conjunto | ✅ **100% × 44,5%, +55,5 pp** (US$ 0,96) · **o gap encolhe** · normalizadores valem **zero** aqui · ⚠️ **benchmark saturou** |
| **19** · Fragilidade lexical | Δ EX sob schema opaco, **previsão pré-registrada** | ✅ **0,00 pp** contra −29,4 pp do 7B — era **do SUT, não da interface** · ❌ **minha previsão pontual refutada** |
| **20** · Conjunto duro | o benchmark discrimina atacando a superfície nunca coberta? | ⚠️ respondíveis **saturam de novo (35/35)** → o teto é do **catálogo** · ✅ abstenção near-miss cai para **50%**, modo de falha novo · guarda nova **pegou um erro meu** |
| **21** · Catálogo enriquecido | completar as partições conserta o rebaixamento de tipo? | ✅ **rebaixamento 6/6 → 1/8**, abstenção 50% → **75%**, total **41/47 → 44/47** · ⚠️ **1 regressão** (contagem × proporção): é troca, não ganho grátis · auditoria adversarial **44/47 (93,6%)** · **concorrência da API medida: 5,74× em c=8** |
| **22** · CI de verdade | o pipeline que eu já declarava ter **de fato roda a suíte**? | ❌ **não rodava desde a Fase 6**: 1 verde em 33 execuções, 32 vermelhas em 12 dias — `[dev]` não instalava `fastapi` e a **coleta** quebrava · ✅ extra `[test]` + **trava de coleta** (0 erros · 0 arquivo vazio · piso 216) |

<sub>¹ As Fases 14 e 15 corrigiram defeitos de gold e **re-pontuaram as mesmas predições**: 86,9% → 88,7% → **89,7%**. O artefato em `reports/fase12/` guarda o valor re-pontuado (89,7%), que é o usado na tabela da tese. Os dois números são verdadeiros em momentos diferentes.</sub>

## 🔬 O que a medição refutou

O diferencial não são os números altos — é **o rigor ter corrigido os próprios números**. Cada fase pré-registrou um achado esperado; estas são as vezes em que a evidência contrariou a narrativa e a narrativa cedeu.

- **O EX de 97,6% não descreve o sistema** *(F4 → F8)*. Com N 4× maior e superfície nova, o Tier-A faz **73,7%**. A tese sobrevive com folga (a vantagem sobe para +58,7 pp); o valor absoluto, não. Três buracos que o conjunto pequeno escondia — e a abstenção de 100% era artefato de perguntas óbvias: com *near-miss* cai para **55,6%**.

- **Consertar falha mecânica é código, não prompt** *(F9, F10)*. Reescrever o prompt para ensinar a sintaxe de ranking **empatou** (p=0,89) — consertou ranking e causou 18 erros novos de seleção. O mesmo conserto em **código** (normalizar `["x","DESC"]` → `["-x"]`) deu **+5 pp, p=0,004, zero regressões**. Repetido na F10: **+12,7 pp**. Acumulado **+17,7 pp em código, sem tocar no modelo nem no prompt**.

- **"SUT maior" é falso; "SUT mais capaz" é verdadeiro** *(F15 → F18)*. Trocar o 7B *coder* por um 9B generalista derruba o EX de 86,1% para **5,6%** — o 9B emite `"entidades"`/`"tempo"` (os *rótulos das seções* do catálogo) como se fossem tokens: **23 de 39 specs com vocabulário inválido**, contra **zero** do 7B. Em vocabulário fechado, **aderência ao formato vence tamanho**. Mas um SUT genuinamente mais capaz (`claude-opus-5`) zera o resíduo: 100% nos mesmos estratos que travavam em 72–80%.

- **A vantagem da interface não é constante** *(F18)*. Com o SUT trocado no mesmo conjunto, o Δ cai de **+63,0 para +55,5 pp**, porque o baseline quase dobra. Corolário medido: os dois normalizadores que valem +17,7 pp no 7B tocaram **0 de 146 specs** no Opus 5. **A camada determinística é uma muleta cuja altura é exatamente a fraqueza do SUT.**

- **Minha própria previsão, pré-registrada e refutada** *(F19)*. Registrei em [pré-registro commitado](docs/FASE19_PREREGISTRO.md) que a fragilidade lexical encolheria mas deixaria resíduo (Δ ≈ −9 pp, faixa −18 a −2). Medi **0,00 pp**. A afirmação falsificável central (`|Δ| < 29,4`) confirmou; a previsão pontual **caiu** — apostei num piso que não existe. A fragilidade lexical **não é estrutural da interface: era capacidade do SUT**.

- **O teto era do catálogo, não do benchmark** *(F20)*. Construí um conjunto duro contra as formas que **medi** nunca terem sido cobertas (`where` composto: 0 de 168 itens; métrica mista: impossível de compilar até a F19). Saturou igual — **35/35**. Com 3 métricas e 9 dimensões, um SUT de fronteira não erra composição.

- **O defeito era do catálogo, e o conserto tem preço** *(F21)*. Registrei o rebaixamento de tipo como falha do modelo. Era **assimetria do catálogo**: expunha `automation_rate` e escondia os irmãos da mesma partição, então "proporção de cobrança manual" era uma pergunta legítima sem resposta. Completando as partições, o rebaixamento cai de **6/6 para 1/8** — mas **um item que acertava passou a errar**: com `motorcycle_share` disponível, *"as 5 praças com maior **volume** de motos"* virou `motorcycle_share` em vez da contagem filtrada. Catálogo maior compra cobertura e paga em ambiguidade. **A troca líquida é +3 em 47, e ela tem os dois lados.**

- **Eu tinha CI; eu não tinha CI verde** *(F22)*. Contei "CI/CD" como entregue porque o `ci.yml` existia e o gate rodava na minha máquina. O histórico do Actions diz outra coisa: **1 execução verde em 33**, e a única foi o commit que criou o workflow. O commit seguinte trouxe `tests/test_servico.py`, que importa `fastapi` — extra `[serve]`, ausente do `pip install -e ".[dev]"` do runner. A **coleta** do pytest quebrava, e o build ficou vermelho por **32 execuções, 12 dias e 16 fases**, com o badge estampado no topo deste README. O CI funcionou perfeitamente; **eu é que não li**. Consertado com um extra `[test]` nomeado e uma [trava de coleta](verificar_coleta.py) — porque o modo de falha pior seria *pular* os dois arquivos e ficar **verde com 26 testes a menos**. Ver [Fase 22](docs/FASE22_CI.md).

- **Um bug de 19 fases, e a retratação do impacto que atribuí a ele** *(F20)*. O extrator de SQL cortava no primeiro `SELECT`, destruindo o `WITH` do CTE. Afirmei que isso tinha descartado itens em silêncio e explicava parte da saturação. **A auditoria me refutou:** dos 220 autorados, os 4 descartes foram todos por gold degenerado, e em 291 itens autorados a forma **nunca foi escrita**. O bug era **latente**. Errei por inferir consequência a partir do mecanismo em vez de **medir** o impacto.

- **Duas guardas que pegaram erros meus.** A **G5 (razão viva)** descartou um item em que eu tinha *escrito no código* que não haveria problema — filtrando só motos, `commercial_share` = 0 em toda linha, porque moto nunca é comercial. E a auditoria de proveniência achou as 342 predições da API gravadas como `qwen2.5-coder:7b`: o EX não dependia do campo, mas **artefato que mente sobre a própria origem não é auditável**.

**Heurística que ficou:** *um zero limpo demais é bug, não resultado* — modelo ruim erra variado, harness quebrado erra tudo igual. E o simétrico: **um 100% exige mais prova que um 89%**. Os dois resultados saturados deste README passaram por auditoria de 4–5 hipóteses de falso positivo antes de serem reportados.

## 🏗️ Arquitetura — o que de fato está servido

```
NL do usuário
   │
   ▼
[Tier A] LLM escolhe {métricas, dimensões, filtros} de um VOCABULÁRIO FECHADO
   │        → valida contra o catálogo → MetricFlow compila o SQL → executa (read-only)
   │        → fora do catálogo? ABSTÉM (não inventa)
   │
   └─ [Tier B] SQL cru + sandbox AST — construído e testado, DESLIGADO por evidência (F14)

SUT plugável: Ollama local (default) │ API Anthropic  ·  Serving: FastAPI → Docker → Kubernetes
```

**Por que o Tier-A dispensa o sandbox:** o LLM nunca emite SQL. Ele emite uma *spec* sobre vocabulário fechado, e quem gera SQL é o MetricFlow. **Não há superfície de injeção** — a segurança é estrutural, não um filtro depois do fato. O sandbox existe para o Tier-B e foi validado com as **duas** métricas juntas: attack-block 100% (39/39) **e** falso-positivo 0% (10/10) — bloquear tudo daria 100% de block e seria inútil.

## ✅ Rastreabilidade requisito → fase

<details>
<summary><b>Cada requisito de uma vaga de Engenharia de Dados/IA rastreado até a fase que o prova com código e evidência (clique para expandir)</b></summary>

<br>

| Requisito | Onde é provado | Evidência |
|---|---|---|
| SQL avançado e modelagem dimensional | F11 · fundação | dbt + **MetricFlow** sobre 1,5 M linhas reais; razões declaradas na *measure*, não no filtro da métrica |
| Semantic Layer / métricas governadas | F10–F12 | catálogo de 3 métricas com curadoria auditável (`meta: {catalogo_usuario: false}` nos numeradores) |
| Python de produção | todas | 199 testes · `ruff` limpo · gate bloqueante no CI |
| Avaliação de LLM com rigor estatístico | F3–F20 | Wilson em toda taxa · **McNemar** pareado · **Test-Suite EX** em 3 variantes de banco |
| Qualidade de rótulo | F2 · F12 · F14 · F15 · F18 | κ de máquina 0,977 → **Opus 5 cego 0,992** → **κ humano 1,0** · auditoria adversarial acha 7/60 defeitos |
| Benchmark externo | F13 | **BIRD Mini-Dev**: 500 perguntas e SQL humanos, CC BY-SA |
| Segurança de LLM | F1 | sandbox AST com attack-block **e** falso-positivo medidos juntos |
| MLOps / CI | F5 | gate em 3 níveis, **comprovado ativo** (pega 6/6 regressões injetadas) |
| Serving + SLO | F6 | FastAPI, cache spec→SQL, **controle de admissão decidido por medição** (semáforo 1 + 503) |
| Containers | F16 | imagem 624 MB, não-root, healthcheck, fundação assada |
| Kubernetes | F17 | Deployment/Service/PDB/StatefulSet/NetworkPolicy · **sem HPA, com o número que justifica** |
| API de LLM (provider plugável) | F18 | `RODOQUERY_PROVEDOR=ollama\|anthropic` · prompt caching (341/342 hits) · custo em `/metricas` |
| Custo sob controle | F18–F20 | teto verificado **a cada item** · `--confirmar` obrigatório · projeto inteiro custou **US$ 1,82** |

</details>

## 🚀 Rodar

```bash
git clone https://github.com/alanjoffre/rodoquery && cd rodoquery
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"                   # o mesmo extra que o CI usa — ver Fase 22
pytest                                     # 216 testes
python verificar_coleta.py                 # nenhum teste some por falta de extra
python gate_regressao.py                   # gate nível A (contrato, sem GPU)
uvicorn rodoquery.servico:app --port 8077  # serving do Tier-A (SUT local)
```

**Container / Kubernetes:**

```bash
bash docker/preparar_contexto.sh && docker compose up --build   # Ollama + SUT + serviço
kubectl apply -k k8s                                            # manifestos testados em cluster efêmero
```

**Trocar o SUT por API** (opcional; extra `api`, chave em `.env`, **gitignorado**):

```bash
pip install -e ".[api]"
RODOQUERY_PROVEDOR=anthropic uvicorn rodoquery.servico:app --port 8077
python avaliar_fase18.py estimar           # a conta ANTES de gastar, zero chamadas
```

Nenhum caminho gasta crédito por acidente: o default é o SUT **local**, `--confirmar` é obrigatório (sem ele o script sai com código 2 **sem uma chamada**), e `--teto-usd` é verificado **a cada item** — orçamento conferido só no fim não é orçamento.

> ⚠️ **O container não cumpre o SLO nativo** (medido com GPU): ~7 s a quente com cache contra p50 4,5 s. **Não herdo o número** — ver [Fase 16](docs/FASE16_DOCKER.md). O mesmo vale para K8s (66,9 s em CPU). Já a concorrência do serving na API **deixou de ser dívida na F21**: medida em 5,74× a c=8 com p95 plano, e `/saude` reporta `concorrencia_medida: true` nos dois caminhos.

## 🎯 Backlog declarado

Nenhum item é surpresa: todos foram declarados na fase em que apareceram.

**Aberto — três itens, todos com o custo declarado:**
- **O extra `llm` é metadado morto** — nada em `src/` importa `httpx` ou `ollama` (o cliente do Ollama fala HTTP por `urllib` da stdlib); achado na F22. **Não removido ainda de propósito:** o `Dockerfile` instala `.[serve,llm]`, e os **624 MB** de imagem medidos na F16 incluem esses pacotes. Removê-lo sem reconstruir e re-medir tornaria aquele número falso. Sai no mesmo commit que re-mede a imagem.
- **Os 3 defeitos que a auditoria adversarial da F21 achou**, todos `abstencao_errada`: completar as partições tornou perguntas respondíveis **por composição** (`manual_share + ocr_share`), e o meu gold não antecipou isso. **Não corrigidos de propósito** — o conjunto está selado e a auditoria veio depois de medir; ajustar seria fitar. Ficam para a próxima revisão de golden, e implicam que a abstenção de 6/8 é **piso, não estimativa**.
- **GPU no Kubernetes** — **bloqueio de hardware, não falta de trabalho.** Diagnosticado na F17b: `docker run --gpus all` funciona e o runtime `nvidia` está registrado, mas o `kind` cria o nó sem `--gpus` e o **Docker Desktop ignora `"default-runtime": "nvidia"`** no `daemon.json` (testado; config restaurada depois). Exercitar `nvidia.com/gpu` exige k3s/kubeadm em Linux nativo ou cluster gerenciado com node pool de GPU. **Nenhuma quantidade de código resolve isto nesta máquina** — o bloco no manifesto segue comentado e declarado.

**Quitado na Fase 22:**
- ~~**"CI/CD real"**~~ — eu contava como entregue porque o `ci.yml` existia. **1 execução verde em 33**: quebrou no commit seguinte ao que criou o CI e ficou vermelho **12 dias**. Causa: a suíte importa `fastapi` (extra `[serve]`) e o runner instalava só `[dev]` — a **coleta** do pytest morria. Conserto: extra `[test]` nomeado no `pyproject.toml` + [`verificar_coleta.py`](verificar_coleta.py) (0 erro de coleta · 0 arquivo vazio · piso de 216), validado em **venv limpo** rodando a sequência exata do CI. Ver [Fase 22](docs/FASE22_CI.md).

**Quitado na Fase 21:**
- ~~**Catálogo mais rico**~~ · ~~**Rebaixamento de tipo**~~ · ~~**Cobertura do catálogo**~~ — eram **um problema só**: o catálogo era **assimétrico** (expunha `automation_rate` e escondia Manual/OCR; expunha `commercial_share` e escondia Passeio/Moto). Regra aplicada: **completar a partição onde um membro já estava exposto** — não "expor tudo" (`categoria_eixo` tem 19 valores; `sentido` não tinha membro exposto). 3 → 7 métricas, com as partições somando **exatamente 1,0** (testado). Rebaixamento de tipo **6/6 → 1/8**, abstenção **50% → 75%**, total **41/47 → 44/47** — e **1 regressão** declarada. Ver [Fase 21](docs/FASE21_CATALOGO_RICO.md).
- ~~**Conjunto duro sem κ de 2º anotador**~~ — resolvido com **auditoria adversarial** (método da F15), que é mais forte que re-anotação cega e mais adequado que κ de máquina aqui: nas formas duras um 7B erraria por incompetência e a discordância mediria o anotador, não o rótulo. **44/47 corretas (93,6%)**.
- ~~**Concorrência do serving na API**~~ — **medida**, com critério declarado antes de olhar (manter 8 só se c=8 > 1,5× c=1). Deu **5,74×** com p95 **plano** — o oposto exato da GPU local, onde a vazão colapsa para 0,75× e o p95 vai a 43 s. `/saude` agora reporta `concorrencia_medida: true` nos dois caminhos.
- ~~**Promover o catálogo v2 ao serving**~~ — **não promover, e o item está superado.** O v2 era um experimento sobre o catálogo de 3 métricas (+5,5 pp no Qwen), e a lei da F18 prevê que esse ganho evapora num SUT forte — como os normalizadores (+17,7 pp → 0) e a fragilidade lexical (−29,4 pp → 0). O caminho adiante é o catálogo enriquecido, que ataca um **defeito medido** em vez de uma diferença de redação.

**Quitado antes:**
- ~~**κ humano do golden**~~ — a dívida mais antiga (Fase 2): **κ = 1,0** (n=40, IC [0,912; 1,0]), anotador humano cego. Duas ressalvas declaradas em [docs/FASE14_KAPPA_HUMANO.md](docs/FASE14_KAPPA_HUMANO.md): **1 dos 40 itens não foi cego** (excluindo, 39/39, IC [0,910; 1,0]) e concordância perfeita com n=40 mede **reprodutibilidade das convenções**, não perfeição do golden. Evidência de que foi anotação e não cópia: as specs são **canonicamente idênticas** mas só **26 de 40 são idênticas byte a byte**.
- ~~**Fragilidade lexical**~~ — era do SUT, não da interface (F19: **0,00 pp**).
- ~~**Resíduo de seleção**~~ — era capacidade do SUT (F18: 100% nos estratos que travavam).
- ~~Tier-B / roteador~~ — medido na F14: fallback ingênuo **derruba** a abstenção; off por evidência.
- ~~Conjunto de robustez próprio~~ · ~~resíduo de ranking~~ · ~~N ≥ 25/estrato~~ — F8 e F14.

## 🚫 O que decidi **não** medir — e por quê

**[Spider 2.0](https://spider2-sql.github.io/) é o benchmark mais alinhado a esta tese** — tem até uma trilha `Spider2-DBT`. Ficou de fora, e a razão é aritmética: modelos de fronteira fazem **17–21%** ali, e este projeto nasceu num **Qwen2.5-Coder-7B em 6 GB**. O resultado esperado era indistinguível de zero — e um zero não separa *"o Semantic Layer ajuda"* de *"o modelo não dá conta"*. Renderia uma linha bonita no README e **nenhuma informação**. A escolha honesta foi o **BIRD Mini-Dev**, onde o SUT tem sinal mensurável.

## 📚 Documentação

| Documento | Para quê |
|---|---|
| [docs/GUIA_GOLDEN.md](docs/GUIA_GOLDEN.md) | Como o golden é autorado, validado e **selado** (anti-vazamento) |
| [docs/FASE12_TESE_REAL.md](docs/FASE12_TESE_REAL.md) | A tese sobre dado real + os 2 bugs de harness pegos a tempo |
| [docs/FASE13_BIRD.md](docs/FASE13_BIRD.md) | Calibração externa: o baseline não é espantalho |
| [docs/FASE14_KAPPA_HUMANO.md](docs/FASE14_KAPPA_HUMANO.md) | O κ humano: instrumento, roteiro, resultado e as ressalvas |
| [docs/FASE18_PROVEDOR.md](docs/FASE18_PROVEDOR.md) | Provider plugável, prompt caching e a lei da muleta |
| [docs/FASE19_PREREGISTRO.md](docs/FASE19_PREREGISTRO.md) · [FASE19_FRAGILIDADE.md](docs/FASE19_FRAGILIDADE.md) | Pré-registro **e** o resultado que refutou minha previsão |
| [docs/FASE20_DURO.md](docs/FASE20_DURO.md) | O conjunto duro, o teto do catálogo e o modo de falha novo |
| [docs/FASE21_CATALOGO_RICO.md](docs/FASE21_CATALOGO_RICO.md) | Partições completas, a troca medida, auditoria adversarial e concorrência |
| [k8s/README.md](k8s/README.md) | O deploy — e **por que não há HPA**, com o número |
| [docs/FUNDACAO.md](docs/FUNDACAO.md) | A fundação dbt/MetricFlow e as armadilhas do dado real |

Auditoria de fidelidade dos números: **`python auditar_documentacao.py`** — confere cada valor citado aqui contra os artefatos em `reports/`.

## 🔒 Higiene do repositório

- **Sem segredos** — `.env` no `.gitignore` desde sempre; a chave de API nunca foi versionada (verificado a cada commit).
- **Dados públicos** — sintéticos nas Fases 0–10; **ANTT sob CC BY** a partir da F11 (1,5 M linhas, jan–mai/2026, sem PII). BIRD Mini-Dev sob CC BY-SA, fora do repo.
- **Anti-vazamento** — todo conjunto de teste é **selado com sha256 antes** de qualquer sistema rodar; predições **congeladas** em disco para que a pontuação seja determinística.
- **Anti-circularidade** — o gold sai **sempre** do MetricFlow, nunca de SQL escrito à mão.

## 👤 Autor

**Alan Joffre** — Engenharia de Dados / IA
[GitHub](https://github.com/alanjoffre) · [LinkedIn](https://www.linkedin.com/in/alanjoffre/)

## 📄 Licença

**MIT** para o código.

Dados: **públicos e reais** desde a Fase 11 — volume de tráfego nas praças de pedágio federais, publicado pela **ANTT** sob **CC BY** (1,5 M linhas, jan–mai/2026, sem PII). As Fases 0–10 usam dados **sintéticos** gerados pelo [toll-analytics-platform](https://github.com/alanjoffre/toll-analytics-platform). O [BIRD Mini-Dev](https://bird-bench.github.io/) (F13) é CC BY-SA e não está versionado aqui. Nenhum dado pessoal ou proprietário em nenhuma fase.

---

<div align="center">

<sub>22 fases · 216 testes · gate 7/7 · custo total de API US$ 1,82 · cada número em <code>reports/</code> com carimbo de proveniência.</sub>

</div>
