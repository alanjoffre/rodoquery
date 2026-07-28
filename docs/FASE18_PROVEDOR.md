# Fase 18 — provedor plugável e a tese contra um SUT de fronteira

## A pergunta que sobrou depois da Fase 15

A Fase 12 mediu, sobre dado real da ANTT e com `qwen2.5-coder:7b` nas duas pontas:

| Sistema | EX (respondíveis) |
|---|---|
| Tier-A (spec governada) | **89,7%** |
| `sql_cru` (baseline) | 26,7% |
| **Δ** | **+63,0 pp**, McNemar p≈0 |

A Fase 15 fechou o **lado de baixo** dessa curva: `gemma2:9b`, um generalista maior, colapsou em
5,6% — 23 de 39 specs usaram vocabulário inválido (emitiu `"entidades"`/`"tempo"`, que são os
*rótulos de seção* do catálogo). Em tarefa de vocabulário fechado, **aderência a formato vence
tamanho**.

Falta o **lado de cima**, e é a primeira coisa que um cético pergunta:

> O ganho de +63 pp é uma propriedade da **interface**, ou era compensação de um SUT fraco?

Os dois resultados possíveis são publicáveis:

- **o gap encolhe** → a tese fica mais modesta e mais útil: *o Semantic Layer vale mais quanto
  mais barato é o SUT* — que é exatamente o argumento econômico de quem roda modelo local;
- **o gap persiste** → a tese fica mais forte: o problema é de interface, não de capacidade.

Nenhum dos dois é fracasso. É por isso que vale medir.

## O resultado: o gap ENCOLHEU, e a tese fica mais precisa

TEST-ANTT selado, 171 itens (146 respondíveis + 25 abstenções), `claude-opus-5` nas duas pontas,
US$ 0,96 de API:

| SUT | Tier-A | `sql_cru` | Δ | Abstenção (Tier-A) |
|---|---|---|---|---|
| `qwen2.5-coder:7b` (Fase 15) | 89,7% | 26,7% | **+63,0 pp** | 88% |
| **`claude-opus-5` (Fase 18)** | **100% (146/146)** | **44,5%** | **+55,5 pp** | 96% |

IC95 do Tier-A: [97,44%; 100%]. McNemar b=0 / c=81, p≈0.

**A tese sobrevive, mas a leitura honesta é mais modesta que "o Semantic Layer vence".** O que os
dois pontos juntos dizem é mais específico — e mais útil:

> A vantagem do Semantic Layer é **inversamente proporcional à força do SUT**: enorme com um 7B
> local (+63 pp), e ainda grande, porém menor, com um modelo de fronteira (+55,5 pp).

O baseline **quase dobrou** (26,7% → 44,5%): um modelo de fronteira escreve SQL cru bem melhor.
Esse é o número que um cético usaria contra a versão forte da tese — então é ele que precisa
estar em destaque, não no anexo.

### O achado que eu não esperava: os normalizadores valem ZERO aqui

Os dois normalizadores determinísticos das Fases 9/10 valem **+17,7 pp acumulados** sobre o Qwen e
tocaram 78 de 160 specs na Fase 12. Sobre o Opus 5 tocaram **0 de 146** — o modelo já emite a spec
na forma canônica.

É a mesma lei por outro ângulo: **a camada determinística é uma muleta cuja altura é exatamente a
fraqueza do SUT.** Ela não sai do sistema (é o que faz o serving barato funcionar), mas o crédito
dela não transfere para cima.

### Onde este resultado PARA: o benchmark saturou

100% não quer dizer "o sistema é perfeito". Quer dizer que **este golden não mede mais o Tier-A**
— o teto passou a ser o do instrumento, não o do sistema. O que segue disso:

- **O McNemar aqui é menos informativo do que parece.** `b=0` (baseline acerta onde o Tier-A erra)
  é trivialmente verdadeiro quando o Tier-A não erra. A 89,7% o teste discriminava; a 100% ele só
  confirma a direção.
- **Não dá para saber quanto do +55,5 pp é piso.** O Tier-A pode estar em 100% ou em 99,9%; o
  instrumento não separa. Contra um golden mais duro, o delta real seria **menor ou igual** a este.
- **Medir o teto do Tier-A com modelo de fronteira exige um golden novo e mais difícil**, com o
  mesmo protocolo anti-vazamento das Fases 8/9 (specs inéditas, holdout selado antes de rodar).
  Fica declarado como **aberto**, não como feito.

A abstenção **não** saturou: 24/25 (96%), com uma falha em `abstencao_antt_10`. O eixo que ainda
discrimina é o de recusa, não o de acerto.

### Um bug meu, pego depois da corrida

As 342 predições foram congeladas com `meta['modelo'] = "qwen2.5-coder:7b"`. A corrida foi mesmo
na API — `custo_usd` e tokens de cache em todos os registros, `carga_modelo_s = 0`, soma batendo
em US$ 0,9627 — mas o rótulo mentia: quem abrisse `reports/fase18/` concluiria que um 7B local
fez 146/146. Causa: `modelo = modelo or settings.modelo_sut` resolve para o default local, e o
provedor trocava para `claude-opus-5` só internamente.

**O EX não depende desse campo; a auditabilidade do artefato depende inteiramente.** Corrigido na
fonte (`modelo_efetivo` na telemetria) e migrado com `corrigir_proveniencia_fase18.py`, que só
reescreve o rótulo de registros com **prova independente** de origem na API e afirma, por
asserção, que `spec`/`sql`/`raw` ficam intactos.

Segundo caso da mesma família, corrigido junto: o relatório somava o custo dos **acumuladores da
sessão**, então qualquer re-pontuação sobre predições congeladas publicaria `custo_usd: 0`. Agora
a conta é reconstruída **a partir das predições** — o relatório descreve o artefato, não a
execução que o releu.

### Custo real

US$ **0,9627** por 342 chamadas (US$ 0,0028/chamada). O prompt caching funcionou como projetado:
**341 das 342 chamadas com cache hit**, 308.455 tokens lidos de cache contra 713 escritos. A
estimativa a priori era US$ 1,76 — errei **para cima**, por dois motivos que o piloto expôs: a
aproximação `caracteres/4` subestima o português acentuado (o prefixo do `sql_cru` cacheou, e eu
previa que não), e usei 186 itens quando o golden selado tem 171.

## O que foi construído

`src/rodoquery/provedor.py` — um provedor é `(prompt, modelo, temperatura) -> (texto, telemetria)`,
a assinatura exata de `_chamar_ollama`. `sistema_antt` e `baselines_antt` ganharam um parâmetro
`provedor=None`; com `None` chamam o Ollama como sempre.

**O default nunca muda.** As Fases 0–16 continuam byte a byte reproduzíveis — é o primeiro teste
do `test_provedor.py`, porque essa é a regressão que ninguém perceberia até a próxima execução.

## Três decisões de método

### 1. Sem structured outputs — de propósito

A API sabe forçar um JSON Schema (`output_config.format`), o que garantiria spec bem-formada de
graça. **Não uso.** Metade do que o Tier-A mede é *"o modelo consegue emitir uma spec válida a
partir de um vocabulário fechado?"* — foi exatamente aí que o `gemma2:9b` morreu. Forçar o schema
responderia essa pergunta por decreto e tornaria o número incomparável com o do Qwen.

### 2. O determinismo é mais fraco aqui, e isso fica declarado

| | Ollama (Fases 0–16) | API (Fase 18) |
|---|---|---|
| `temperature=0`, `seed=42`, `top_k=1` | sim | **rejeitado** (HTTP 400 no Claude ≥ 4.7) |
| Variância medida | 0,0 pp em 5 execuções (Fase 5) | não medida |
| Predições congeladas | sim | sim |

Ou seja: **o número publicado é reprodutível; a coleta que o gerou, não.** A mitigação é a mesma
que o projeto usa desde a Fase 4 — congelar as predições e pontuar sobre elas. Dizer isso é o
ponto; esconder seria o problema.

### 3. Tag vazada se conserta em código, não em prosa no prompt

Com o thinking desligado, modelos Claude ocasionalmente escrevem `<thinking>` no texto visível.
Eu poderia pedir no prompt para não fazer isso — mas aí o prompt deixaria de ser byte a byte o
mesmo que o Qwen recebeu, e a comparação morre. Então normalizo na borda de transporte
(`_limpar_tags`).

É a mesma lição da Fase 9 (+33,4 pp ao consertar o normalizador) e da Fase 15 (duas tentativas de
ensinar regra por prosa EMPATARAM; duas implementações em código deram ganho estrito):
**falha mecânica se conserta em código.**

O risco concreto que isso mata: raciocínio contendo a palavra `ABSTENHO` dispararia uma
**abstenção falsa**, porque a checagem é `"ABSTENHO" in resp.upper()`. Há teste para isso.

## Prompt caching: por um acidente feliz do prompt congelado

O `PROMPT` da Fase 4 termina em `Pergunta: {pergunta}\nJSON:`. Instrução + catálogo formam um
prefixo **idêntico** nas 186 chamadas; só os últimos ~38 tokens variam. Mando o prefixo em
`system` com `cache_control` e a pergunta no turno do usuário — a concatenação é byte a byte o
mesmo texto, e o prefixo passa a custar 0,10× a partir da 2ª chamada.

Há teste garantindo que o corte é **sem perda** (`prefixo + sufixo == prompt`). Se ele perdesse um
byte, o SUT receberia um prompt diferente do que o Qwen recebeu e a comparação viraria ruído —
esse é o modo de falha silencioso desta fase.

## A conta, antes de gastar

Telemetria **medida** nas predições congeladas da Fase 12 (não estimada):

| Sistema | n | prompt médio | saída média | prefixo |
|---|---|---|---|---|
| `tier_a_antt` | 186 | 789 tok | 61 tok | ~599 tok |
| `sql_cru_antt` | 186 | 483 tok | 71 tok | ~368 tok |

Com fator **1,35×** de segurança para o tokenizer da Claude (pior caso documentado):

| Modelo | Cacheia? | Par completo (372 chamadas) |
|---|---|---|
| `claude-opus-5` | parcial¹ | **US$ 1,76** |
| `claude-opus-4-8` | não | US$ 2,43 |
| `claude-sonnet-5` | não | US$ 1,46 |
| `claude-haiku-4-5` | não | US$ 0,49 |

¹ O prefixo do Tier-A (~599 tok) passa do mínimo de 512 do Opus 5; o do `sql_cru` (~368 tok) não.
O baseline tem prompt mais curto, então não cacheia — e é por isso que o par custa mais que o
dobro do Tier-A sozinho. O número real de cache sai do `cache_read_input_tokens` que a API
devolve, medido no piloto.

## As travas

Nenhum caminho de código gasta crédito por acidente:

| Trava | Comportamento |
|---|---|
| `obter_provedor()` sem argumento | devolve **Ollama** |
| `--confirmar` ausente | recusa e sai com **código 2**, sem uma chamada |
| `--teto-usd` (default 2,00) | verificado **a cada item**, não no fim |
| Predições já congeladas | reusadas; não regasta (`--refazer` para forçar) |
| Estouro do teto | aborta com código 2 e **salva** o que já coletou |

Um orçamento verificado só no fim não é um orçamento. O código de saída é explícito
(`SystemExit(2)`) para que um script em volta consiga distinguir recusa de sucesso.

## Fluxo

```bash
python avaliar_fase18.py estimar                    # a conta, zero chamadas
python avaliar_fase18.py piloto --n 12 --confirmar  # custo REAL numa amostra estratificada
python avaliar_fase18.py completo --confirmar       # TEST-ANTT inteiro, os dois sistemas
```

O piloto é estratificado (metade respondíveis, metade abstenção) porque abstenção custa ~5 tokens
de saída e uma spec custa ~90 — amostrar só um dos lados enviesaria a extrapolação.

## Como o 100% foi auditado antes de ser reportado

Um 100% exige mais prova que um 89%. Quatro hipóteses de bug de harness foram testadas e
descartadas — a heurística da Fase 12 é que **"um zero limpo demais é bug, não resultado"**, e
o simétrico vale para um cem:

| Hipótese | Verificação |
|---|---|
| Itens sem gold contados como acerto (`.get(id, {})` devolve `{}`) | 0 respondíveis sem gold |
| Gold vazio / hash nulo dos dois lados | 146/146 com 3 variantes, nenhum nulo |
| O scoring não rodou de fato | o **mesmo código** deu 65/146 no baseline |
| O conjunto encolheu | mesmos 146 da Fase 12, onde o Qwen fez 131/146 |

E a ameaça mais séria, **gold degenerado**: se as 3 variantes de um item tivessem o mesmo hash, o
Test-Suite EX perderia poder de falsear e uma spec errada "acertaria" nas três. Verificado:
**146/146 com os 3 hashes distintos.** Cada acerto exigiu reproduzir o número certo em três
partições disjuntas do fato.

## Estado

- ✅ Provedor, travas, testes (31 do módulo; 140 no total), ruff limpo, gate PASSOU
- ✅ Par completo medido: **Tier-A 100% × `sql_cru` 44,5%, +55,5 pp**, US$ 0,9627
- ✅ Proveniência dos artefatos corrigida e verificada (`claude-opus-5` nos 342 registros)
- ⚠️ **Benchmark saturado**: 100% é teto de instrumento. Golden mais difícil = trabalho aberto
- ⚠️ Coleta **não** é bit-reproduzível (a API rejeita `temperature`/`seed`); predições congeladas
- ✅ κ humano **fechado depois desta fase** (28/07): **1,0 (n=40)** — ver
  [Fase 14 · κ humano](FASE14_KAPPA_HUMANO.md). Nada nesta fase o resolveu; o que ela contribuiu
  foi a camada intermediária, o **Opus 5 cego a 0,992** (`concordancia_opus5.py`, custo US$ 0,00)
