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

## Estado

- ✅ Provedor, travas, testes (27 novos; 136 no total), ruff limpo
- ✅ `estimar` roda e fecha a conta
- ⏸️ **Nada foi executado contra a API** — aguarda decisão de gasto
