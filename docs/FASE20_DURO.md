# Fase 20 — o conjunto duro: o teto era do catálogo, e a abstenção é que estava frouxa

## O desenho, e por que ele não é palpite

Os 8 estratos das Fases 2–19 fizeram **100%** contra `claude-opus-5`. Antes de escrever mais
perguntas, medi qual superfície do catálogo nunca tinha sido tocada:

| Forma | Itens nos conjuntos antigos (168 respondíveis) |
|---|---|
| `where` **composto** (AND em duas dimensões) | **0** |
| Specs com **2+ métricas** | 2 (ambas só de razões) |
| Abstenção **near-miss** | poucas — as antigas são obviamente fora do escopo (receita, multa, acidentes) |

Daí os quatro grupos: `filtro_composto`, `metrica_mista`, `composicao` e `abstencao` near-miss.
**48 autorados, 47 selados** (`duro_antt.jsonl`, sha `b10b297f`).

## O resultado

`claude-opus-5` nas duas pontas, US$ 0,2965:

| Eixo | Tier-A | `sql_cru` |
|---|---|---|
| **Respondíveis** (n=35) | **100%** [90,1; 100] | 60,0% [43,6; 74,5] |
| **Abstenção near-miss** (n=12) | **50,0% (6/12)** | **0,0% (0/12)** |

McNemar nos respondíveis: b=0 / c=14, **p=0,0001**, Δ = **+40,0 pp**.

Por estrato, o Tier-A: `filtro_composto` 12/12 · `metrica_mista` 12/12 · `composicao` 11/11.

## Duas conclusões, e a segunda é a que importa

### 1. O teto dos respondíveis não é defeito do benchmark — é do catálogo

Desenhei explicitamente contra as formas nunca cobertas, incluindo uma que era **impossível de
compilar** até a Fase 19. Saturou igual. Com **3 métricas e 9 dimensões**, um SUT de fronteira
simplesmente não erra composição.

Isso reclassifica o item de backlog: *"golden mais difícil"* estava errado como enunciado. Não há
golden mais difícil a construir **neste catálogo** — o limite é a superfície semântica disponível.
Medir o teto real do Tier-A exigiria uma fundação mais rica (mais métricas, hierarquias, janelas),
não mais perguntas.

### 2. A abstenção despencou de 96% para 50% — e o modo de falha é único

As 6 falhas têm **exatamente o mesmo mecanismo**:

> A pergunta pede uma **proporção**; o modelo responde com a **contagem**.

| Pergunta | Tier-A respondeu |
|---|---|
| Qual a proporção de cobrança manual? | `traffic_volume` |
| Qual o percentual de veículos de 2 eixos? | `traffic_volume` |
| Qual a razão entre tráfego comercial e de passeio? | `traffic_volume` |
| Que fração do tráfego segue no sentido crescente? | `traffic_volume` |
| Qual a participação de cada concessionária no tráfego nacional? | `traffic_volume` |
| Quantos por cento do volume é de veículos de 7 eixos? | `traffic_volume` |

Não é alucinação: ele não inventa métrica. É **rebaixamento de tipo** — pedem percentual, ele
entrega número absoluto. É um modo de falha **novo**, diferente do da Fase 8 (lá a substituição
era entre duas razões: "taxa de estorno" → `suspect_rate`).

E é silencioso: a resposta compila, executa e devolve um número plausível. O usuário que perguntou
"que percentual?" recebe "4.668.786".

## A tensão que estes itens expõem — e que eu não vou esconder

Olhe o que o baseline fez nos mesmos 6 itens:

```sql
-- "Qual a proporção de cobrança manual?"
SELECT SUM(CASE WHEN tipo_cobranca = 'Manual' THEN volume ELSE 0 END) / SUM(volume) ...
```

**O `sql_cru` respondeu certo a pergunta de negócio.** Ele abstém 0/12 — mas nestes casos isso não
é alucinação, é computar uma razão derivada que o catálogo escolheu não expor.

Ou seja: o eixo de abstenção **confunde duas coisas**.

| O que a abstenção mede | Interpretação |
|---|---|
| "o catálogo não tem como responder isso" | governança funcionando |
| "o catálogo **deveria** ter essa métrica" | **lacuna de cobertura**, não virtude |

`manual_share`, `moto_share`, share por eixo — todas são métricas que o semantic layer *poderia*
expor e não expõe. A ausência é decisão de modelagem, não lei da natureza.

**O que continua valendo:** a Fase 13 mostrou que 74,9% dos erros do SQL cru são *silenciosos*
(executa e devolve número errado). O risco de deixar o modelo derivar razões livremente é que
ninguém validou o denominador — se deve excluir linhas nulas, se o total é do grupo ou global.
Aqui ele acertou; a tese nunca foi "o SQL cru sempre erra", e sim que **erra sem avisar**.

**O que a Fase 20 acrescenta, honestamente:** parte do que eu vinha contando como "abstenção
correta" era o catálogo sendo pequeno. Um catálogo melhor teria *menos* abstenções e *mais*
respostas certas — e o número de abstenção cairia sem que nada piorasse.

## Uma guarda nova pegou um erro meu

`preparar_duro.py` ganhou a **G5 — razão viva**: se a spec tem métrica de razão e a coluna sai
constante entre as linhas, o item é descartado. É a versão *medida* da G1 (que eu aplicava a
olho).

Ela descartou `composicao_duro_06` — *"Top 5 praças em volume de motos, mostrando também a
participação comercial"* — item em que eu tinha **escrito no código** que não haveria problema
("o share fica 1,0? NÃO — filtro é Moto, share é sobre Comercial"). Estava errado: filtrando só
motos, `commercial_share` = 0 em toda linha, porque moto nunca é comercial.

Eu raciocinei e errei; a guarda olhou o dado e acertou. É o mesmo padrão do bug do CTE — **medir
bate deduzir**.

## Limitações declaradas

- **n=12 na abstenção** é pouco: o IC de 50% é largo. O valor aqui é o **mecanismo** (uniforme nos
  6 casos), não a taxa pontual.
- **Sem κ de segundo anotador.** Os conjuntos anteriores têm κ de máquina e o TEST-ANTT tem κ
  humano 1,0; este ainda não tem. As guardas G0/G4/G5 são automáticas e pegaram 1 defeito, mas
  não substituem uma segunda leitura.
- **Autorado por mim**, que também escrevi as guardas. A auditoria adversarial da Fase 15 seria o
  próximo crivo.
