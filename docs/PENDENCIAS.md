# Pendências — estado verificado em 25/08/2026

Levantamento feito **contra o repositório**, não contra a memória do projeto. Cada item abaixo tem a
evidência que o produziu e o custo de fechá-lo. Ordem: o que **impede a entrega** primeiro.

Commit auditado: `3f1695c` (main, árvore limpa, em sincronia com `origin`).

## O que já está verde (medido hoje, não afirmado)

| Checagem | Comando | Resultado |
|---|---|---|
| Suíte | `pytest -q` | **216 passaram**, 1 warning |
| Lint | `ruff check .` | **All checks passed** |
| Coleta | `python verificar_coleta.py` | **216 testes, piso 216, 0 arquivos vazios** |
| Gate nível A | `python gate_regressao.py` | **PASSOU (7/7)** |
| Fidelidade dos números | `python auditar_documentacao.py` | **43 OK / 0 divergências** |
| CI no Actions | `gh run list` | **verde** nas 2 últimas execuções (33 s / 31 s) |
| Selos anti-vazamento | `sha256sum` dos 8 conjuntos selados | **8/8 conferem** |
| Links relativos em `.md` | varredura de `[..](..)` | **0 quebrados** |

O projeto **não tem defeito de execução**. As pendências são de **distribuição**, **coerência** e
**alvo do gate**.

---

## P0 — Bloqueiam a entrega a terceiros

### P0.1 A fundação ANTT não está publicada em lugar nenhum

`~/antt-foundation` é um repositório git **local, sem remote** (3 commits: `d8e26c8` → `29f1ffa` →
`2c32d05`, árvore limpa, **12 arquivos rastreados**). Tudo das Fases 11–22 — a tese central, o dado
real, o catálogo de 7 métricas da F21 — compila contra ela.

Consequências verificadas:

- `bash docker/preparar_contexto.sh` **aborta** em qualquer máquina que não a do autor: o script
  exige `$HOME/antt-foundation/dbt-antt` e `antt_analytics.duckdb`. É o passo 1 do
  `docker compose up --build` anunciado na seção **Rodar** do README.
- `kubectl apply -k k8s` depende da mesma imagem.
- `gate_regressao.py --replay` (nível B) e todos os `avaliar_fase1*.py` / `preparar_antt.py`
  precisam de `FUNDACAO_ANTT` (`src/rodoquery/config.py:17` → `Path.home()/"antt-foundation"`).
- O que o repo público de fato entrega é o manifesto **sintético**:
  `fundacao/semantic_manifest.json` tem 7 métricas (`transactions`, `revenue_cents`, `revenue`,
  `revenue_leakage_cents`, `revenue_leakage_brl`, `suspect_transactions`, `suspect_rate`).
  A fundação ANTT tem **13** (`traffic_volume`, `automation_rate`, `commercial_share`,
  `manual_share`, `ocr_share`, `passenger_share`, `motorcycle_share` + os numeradores).

**Custo de fechar:** publicar `alanjoffre/antt-foundation` (12 arquivos, ~40 KB de código) e apontar
o README. O `.duckdb` de 27 MB é gitignorado lá e continua sendo — ele se reconstrói.

### P0.2 A cadeia de reconstrução do dado real não está no README

Os comandos existem, mas só em `docs/FASE11_ANTT.md:108-110`, e apontam para o caminho local:

```
python ~/antt-foundation/carregar_landing.py
cd ~/antt-foundation/dbt-antt && dbt build
python ~/antt-foundation/construir_variantes.py
```

Falta, em lugar visível: **de onde vem o CSV da ANTT** (143 MB, CC BY), as armadilhas de leitura já
medidas na Fase 0 de Dados (`sep=";"`, **encoding latin-1**, decimal por vírgula, `volume_total`
como TEXTO), e o aviso de que o `.duckdb` não vem no clone. `docs/FUNDACAO.md` (69 linhas) documenta
**apenas** a fundação sintética.

---

## P1 — Incoerências factuais dentro do repositório

A lição registrada na Fase 14 — ao quitar dívida, grepar o repo inteiro por frases de status — pegou
mais três casos que passaram batido.

### P1.1 Um artefato versionado afirma que o κ humano não existe

`concordancia_opus5.py:113-114` grava, dentro do JSON de saída:

> `"NAO_E_KAPPA_HUMANO": "maquina auditando maquina. O kappa humano segue ABERTO;`
> `reports/fase14/kappa_humano.json nao existe de proposito."`

Essa string está **hoje** em `reports/fase18/concordancia_opus5_x_autor.json`, que é versionado — e
`reports/fase14/kappa_humano.json` **existe** desde 28/07/2026, com κ = 1,0 (n=40).

É o item mais grave da lista, porque é *o artefato* mentindo, não a prosa: mesma família do bug de
proveniência da F18 (as 342 predições gravadas como `qwen2.5-coder:7b`). **Fechar exige** corrigir a
fonte **e** re-gerar o artefato — o script custa US$ 0,00, lê predições congeladas.

### P1.2 `docs/FASE13_BIRD.md:58` ainda declara a dívida aberta

> "**κ humano do golden set do RodoQuery continua no backlog.**"

O resto do parágrafo (o BIRD traz anotação humana *dele*, não do *meu* conjunto) continua correto e
deve ficar; só a frase de status caiu.

### P1.3 `docs/FASE14_BACKLOG.md:118` conclui o oposto do que a Fase 19 mediu

Fechando o item #4:

> "a competência do Tier-A depende fortemente das pistas lexicais dos identificadores — investir em
> descrições boas no semantic layer não é cosmético, é o que sustenta a acurácia."

A **Fase 19 refutou isso**, com pré-registro commitado: o schema opaco custou **−29,4 pp no Qwen 7B
e 0,00 pp no Opus 5**. A fragilidade era **do SUT, não da interface** — o diagnóstico da F14 estava
errado, e o doc não diz. Menor, no mesmo arquivo: o item #2 deixa o resíduo "caracterizado e aberto"
(linhas 75 e 126) sem apontar que a F18 o zerou.

O padrão do repo em casos assim é **nota de superação, não reescrita** — o doc registra o que se
sabia na época; falta o carimbo do que veio depois.

---

## P2 — Números errados no README (fora do alcance do auditor)

### P2.1 `README.md:138` diz **199 testes**

Na tabela de rastreabilidade: *"Python de produção | todas | **199 testes** · ruff limpo"*. O badge,
o cabeçalho da seção de fases (`:52`), a seção **Rodar** (`:158`) e o rodapé (`:252`) dizem **216** —
que é o número real, medido hoje. Resíduo da sequência F18 (148) → F21 → F22 (216).

### P2.2 `README.md:52` e `:252` dizem **22 fases (0–21)**

A tabela vai até a **Fase 22**, e existe ainda a **17b**. São **23 fases numeradas (0–22)** mais a
17b. O badge (`:13`) já diz `fases-0–22` — ou seja, o README se contradiz internamente.

### P2.3 `README.md:228` promete mais do que o auditor entrega

> "confere **cada** valor citado aqui contra os artefatos em `reports/`"

`auditar_documentacao.py` lê `reports/` de **8 fases**: 12, 13, 14, 18, 19, 20, 21, 22. Ficam **sem
trava** números que o README cita das fases:

| Fase | Número no README | Artefato existente, não conferido |
|---|---|---|
| 1 | attack-block 39/39 · FP 0% | `reports/fase1/security_redteam.json` |
| 4 | 97,6% × 42,9%, +54,8 pp | `reports/fase4/resultado_test.json` |
| 5 | gate pega 6/6 · p50 4,5 s / p95 7,9 s | `reports/fase5/{gate_ativo,flakiness}.json` |
| 6 | p95 4,36 s · canário 10/10 · ~0,25 req/s | `reports/fase6/{slo,canario,load_test}.json` |
| 8 | 73,7% [66,5; 79,8] | `reports/fase8/resultado_test_v2.json` |
| 9 / 10 | +5 pp (p=0,004) · +12,7 pp | `reports/fase9/`, `reports/fase10/` |
| 15 | +33,4 pp · 5,6% · 7 defeitos em 60 | `reports/fase15/resultado_ablacao.json` |
| 16 | imagem **624 MB** | **sem artefato** — número só na prosa |

Duas saídas legítimas: estender o auditor (as fases 1–10 são as mais baratas — os JSON já estão lá) ou
**retratar a frase** para "confere os 43 números das Fases 12–22". A segunda custa uma linha; a
primeira é a que o projeto normalmente escolheria.

O caso da F16 é diferente: **624 MB não tem artefato nenhum**. É a única afirmação do README sem
lastro versionado.

---

## P3 — Coisas medidas que não chegaram ao produto

### P3.1 O gate que bloqueia o CI protege a Fase 4 **sintética**, não a tese atual

`gate_regressao.py` lê `reports/fase4/resultado_test.json` (n=42, EX 97,6%, vantagem +54,8 pp) e sela
`golden/golden_test.jsonl`. A tese que o README exibe no topo vive em `reports/fase18/` (ANTT,
n=146) e `reports/fase12/`. **Uma regressão no caminho ANTT passa verde.**

O gate está comprovadamente ativo (pega 6/6 regressões injetadas) — só que sobre o alvo de 18 fases
atrás. É o análogo exato da lição da F22: *ter pipeline não é ter pipeline no alvo certo.*

**Custo:** o nível A é contrato puro (selo + coerência dos agregados + limiares); apontá-lo para
`reports/fase12/resultado_test_antt.json` + `golden/golden_test_antt.sha256` não exige GPU nem LLM,
logo continua rodando no runner de graça. Os limiares precisam ser re-declarados com folga sobre
89,7% (hoje são 0,90 de EX, o que *reprovaria* a tese ANTT — outro motivo para não deixar como está).

### P3.2 O catálogo enriquecido da F21 venceu no conjunto selado e não foi para o serving

`src/rodoquery/sistema_antt_rico.py` é importado **só** por `avaliar_duro_rico.py` e
`auditar_duro_adversarial.py`. `src/rodoquery/servico.py:36` importa `tier_a_antt` — o catálogo de
**3** métricas.

Diferente do catálogo v2 (que o README declara superado, e com razão), este tem **ganho medido em
conjunto selado**: rebaixamento de tipo 6/6 → 1/8, abstenção 50% → 75%, total 41/47 → 44/47, contra
**1 regressão** declarada. E a fundação ANTT **já está em 13 métricas** — o serving é que ficou para
trás.

Isto **não está no backlog do README**. É decisão em aberto: promover (e re-medir o que a troca custa
nas fases que usam `tier_a_antt`) ou declarar por que não. Hoje não está nem uma coisa nem outra.

### P3.3 O manifesto vendorizado no repo é o sintético

`fundacao/semantic_manifest.json` é o catálogo das Fases 0–10. Quem clona não tem como **ver** o
catálogo sobre o qual a tese do topo do README foi medida. Fecha junto com o **P0.1**.

---

## P4 — Higiene de entrega (barato, e é o que um recrutador vê)

- **Fases 20 e 21 não têm seção de Reprodução.** Os outros docs de fase têm. Consequência medida:
  **8 scripts de raiz não são citados em documentação nenhuma** — `avaliar_duro.py`,
  `avaliar_duro_rico.py`, `preparar_duro_rico.py`, `gerar_autor_duro.py`,
  `auditar_duro_adversarial.py`, `medir_concorrencia_api.py`, `medir_historico_ci.py`,
  `rodar_robustez_api.py`. São exatamente os das F20/F21.
- **Sem `.env.example`.** O README manda pôr a chave em `.env` e não diz o nome da variável. É
  `ANTHROPIC_API_KEY` (`src/rodoquery/provedor.py:173`).
- **`golden/ablacao_antt.jsonl` não tem `.sha256`.** Os outros 8 conjuntos de medição têm selo
  (`golden.jsonl`, `golden_test*.jsonl`, `duro_antt`, `duro_rico_antt`, `robustez_antt`). A ablação da
  F15 produziu o maior ganho isolado do projeto (+33,4 pp) sem a mesma trava anti-vazamento.
- **GitHub sem `topics`**, e `licenseInfo` = `"other"` (o `LICENSE` é MIT seguido de uma seção sobre
  os dados, e o detector do GitHub não reconhece). Duas linhas de configuração.
- **`docs/FASE17*.md` não existe** — a Fase 17/17b vive em `k8s/README.md`. Defensável (o doc mora
  junto do manifesto), mas quebra o padrão `docs/FASEnn_*.md` de todas as outras.

---

## Já declarados e mantidos abertos — com o motivo, sem mudança

Estes três já estão no README e **continuam corretos como estão**. Verificados hoje:

1. **Extra `llm` é metadado morto.** Confirmado: `grep` por `httpx`/`ollama` em `src/` e na raiz só
   acha `src/rodoquery.egg-info/` (build, não versionado). Fica porque o `Dockerfile` instala
   `.[serve,llm]` e os 624 MB da F16 incluem esses pacotes — sai no mesmo commit que re-mede a
   imagem. **Nota:** esse número é justamente o do P2.3 que não tem artefato; os dois se resolvem
   juntos.
2. **Os 3 defeitos `abstencao_errada` da auditoria adversarial da F21.** Conjunto selado, auditoria
   veio depois de medir — corrigir agora seria fitar. Ficam para a próxima revisão de golden, e
   implicam que a abstenção de 6/8 é **piso**.
3. **GPU no Kubernetes.** Bloqueio de hardware, testado e não presumido (o Docker Desktop ignora
   `default-runtime: nvidia`; o `kind` cria o nó sem `--gpus`). Nenhuma quantidade de código resolve
   nesta máquina.

---

## Resumo

| # | Pendência | Classe | Custo |
|---|---|---|---|
| P0.1 | Fundação ANTT não publicada (repo local sem remote) | Bloqueia entrega | baixo |
| P0.2 | Cadeia de reconstrução do dado real fora do README | Bloqueia entrega | baixo |
| P1.1 | Artefato versionado afirma que o κ humano não existe | Coerência (grave) | baixo |
| P1.2 | `FASE13_BIRD.md:58` declara a dívida do κ aberta | Coerência | trivial |
| P1.3 | `FASE14_BACKLOG.md:118` conclui o que a F19 refutou | Coerência | trivial |
| P2.1 | README:138 diz 199 testes (são 216) | Número errado | trivial |
| P2.2 | README:52/:252 diz 22 fases (são 0–22 + 17b) | Número errado | trivial |
| P2.3 | "confere cada valor": auditor cobre só F12–F22; 624 MB sem artefato | Overclaim | médio |
| P3.1 | Gate do CI protege a F4 sintética, não a tese ANTT | Dívida técnica | médio |
| P3.2 | Catálogo rico da F21 não chegou ao serving, e não está no backlog | Decisão em aberto | médio |
| P3.3 | Manifesto vendorizado é o sintético | Distribuição | fecha com P0.1 |
| P4 | Repro das F20/21 · `.env.example` · selo da ablação · topics · `licenseInfo` | Higiene | trivial |
| — | Extra `llm` · 3 defeitos da F21 · GPU no K8s | **Já declarados, sem mudança** | — |

**Leitura:** o projeto está tecnicamente completo e verde. O que falta para **entregar** é quase tudo
de distribuição e coerência — com uma exceção real de engenharia (**P3.1**, o gate no alvo errado) e
uma decisão de produto em aberto (**P3.2**, o catálogo rico).

---

## Placar de fechamento

Fechado em **08/09/2026**. Tudo abaixo foi verificado contra o repositório, não afirmado.

| # | Pendência | Estado | Onde |
|---|---|---|---|
| P0.1 | Fundação ANTT não publicada | ✅ **fechado** | [alanjoffre/antt-foundation](https://github.com/alanjoffre/antt-foundation) — pública, MIT |
| P0.2 | Cadeia de reconstrução fora do README | ✅ **fechado** | seção *Rodar* + mensagem de erro do `preparar_contexto.sh` |
| P1.1 | Artefato afirmava que o κ humano não existe | ✅ **fechado** | fonte corrigida e artefato **regerado**; só o rótulo mudou |
| P1.2 | `FASE13_BIRD.md` com a dívida aberta | ✅ **fechado** | nota de superação |
| P1.3 | `FASE14_BACKLOG.md` conclui o que a F19 refutou | ✅ **fechado** | carimbo com a tabela dos dois SUTs |
| P2.1 | README dizia 199 testes | ✅ **fechado** | são 231 hoje |
| P2.2 | README dizia 22 fases (0–21) | ✅ **fechado** | são 24 (0–23, mais a 17b) |
| P2.3 | "confere cada valor" era overclaim | ✅ **fechado** | auditor foi de **43 → 106** checagens, cobrindo F1–F23 |
| P3.1 | Gate do CI no alvo sintético da F4 | ✅ **fechado** | 3 alvos; nível A 7 → **24** checagens; replay **53/53 · 171/171 · 171/171** |
| P3.2 | Catálogo rico não chegou ao serving | ✅ **fechado** | medido (p=1,0) e **promovido** — [Fase 23](FASE23_CATALOGO_SERVING.md) |
| P3.3 | Manifesto vendorizado era o sintético | ✅ **fechado** | `fundacao/semantic_manifest_antt.json` |
| P4 | Repro F19–F22 · `.env.example` · selo · topics · licença | ✅ **fechado** | scripts órfãos **8 → 0**; licença detectada como MIT |
| — | Extra `llm` · 3 defeitos da F21 · GPU no K8s | 🔵 **abertos, como estavam** | com motivo declarado; nenhum é falta de trabalho |

### O que o levantamento errou, e que o fechamento corrigiu

Auditoria também erra, e registrar isso vale mais que o placar:

- **Três coisas que ele não viu.** A frase do κ estava numa **terceira** posição (a docstring do
  `concordancia_opus5.py`); `FASE10_CATALOGO.md` tinha um quarto caso de status obsoleto — mas esse
  **não** foi fechado, porque fala da base sintética, que nunca foi re-medida com SUT de fronteira;
  e o README dizia **+33,4 pp** onde o artefato diz **33,33** (12/36), erro de arredondamento sobre
  arredondamento que o auditor estendido pegou.
- **Um erro factual dele.** O levantamento afirmava que os **624 MB** da imagem eram a única
  afirmação sem lastro versionado. Os 7 defeitos de label da F15 também pareciam não ter — mas têm:
  vivem em `golden/_auditoria_veredito.jsonl`, fora de `reports/`. Hoje estão travados.
- **Um erro meu, ao fechar.** Meu primeiro levantamento de scripts órfãos deu **zero**, e estava
  errado: eu grepava `README.md` + `docs/`, e **este arquivo cita os 8 scripts justamente para
  chamá-los de órfãos**. A denúncia fazia o denunciado parecer documentado. Excluindo-a: 8,
  exatamente os que ele nomeava. *Um teste que inclui a própria denúncia no corpus mede a si mesmo.*

### O que o fechamento produziu além do previsto

- **Os selos deixaram de ser ritual** (`tests/test_selos.py`): os 9 conjuntos selados passaram a ser
  conferidos no CI. Antes, `sha256sum` na mão, quando alguém lembrava.
- **O replay ANTT rodou pela primeira vez** e reproduz — 171/171 vereditos idênticos nos dois
  sistemas, nos dois alvos ANTT.
- **A Fase 23 existe** porque o P3.2 exigia medir em vez de opinar.
