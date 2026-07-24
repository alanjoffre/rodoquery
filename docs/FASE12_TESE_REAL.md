# Fase 12 — A tese sobre DADO REAL

Fim do passo 2: golden set, gold via MetricFlow e avaliação sobre a base da ANTT. Os números das
Fases 4–10 **não** continuam aqui — aqueles medem dado sintético. Isto é uma medição do zero.

## Resultado no TEST-ANTT selado

Mesmo SUT (`qwen2.5-coder:7b`) nas duas pontas; muda só a **interface**.

| Sistema | Execution Accuracy (n=160) | Abstenção (n=25) |
|---|---|---|
| **Tier-A — spec governada → MetricFlow** | **86,9%** [80,8; 91,3] | **88,0%** |
| Baseline — SQL cru sobre o schema | 28,8% [22,3; 36,2] | 72,0% |

**McNemar pareado: 97 × 4, p≈0, Δ = +58,1 pp.** Noventa e sete itens que o SQL cru erra e a spec
governada acerta; quatro no sentido contrário. Com o SUT idêntico, o ganho é da **interface**.

### Por estrato (Tier-A)

| Estrato | EX | IC95 |
|---|---|---|
| `controle_trivial` | **100%** (8/8) | [67,6; 100] |
| `grao_temporal` | **100%** (26/26) | [87,1; 100] |
| `coalesce_nulo` | 92,0% (23/25) | [75,0; 97,8] |
| `metrica_derivada` | 92,0% (23/25) | [75,0; 97,8] |
| `join_grao` | 88,5% (23/26) | [71,0; 96,0] |
| `ranking` | 72,0% (18/25) | [52,4; 85,7] |
| `valor_categorico` | 72,0% (18/25) | [52,4; 85,7] |

`coalesce_nulo` sai de 14,8% (sintético, Fase 8) para **92%** aqui — os normalizadores das Fases
9/10 tocaram **78 das 160 specs**, o que confirma que aqueles dois consertos não eram específicos
do conjunto sintético.

## Dois bugs de harness que eu quase reportei como resultado

Esta é a parte que mais importa registrar.

**1. EX = 0/160 nos DOIS sistemas.** Zero uniforme, inclusive no `controle_trivial`, não é
resultado — é pipeline quebrado. Causa: `avaliacao.py` chamava `compilar_spec(pred.spec)` **sem
fundação**, compilando as specs contra o projeto dbt *sintético*, que não conhece `traffic_volume`.
Nada compilava, e o *fail-closed* da Fase 7 convertia tudo em erro. Corrigido com
`fundacao=` propagado por `avaliar_sistema` → `avaliar_item`.

**2. Baseline em 0/160 — e este inflaria a tese a meu favor.** Com o Tier-A já em 86,9%, o SQL cru
zerado daria "+86,9 pp" e uma tese espetacular. Era a allowlist do sandbox, gerada do catálogo
**sintético**: `fct_traffic_volume` não estava nela, e as 160 consultas foram **bloqueadas antes de
executar**. O baseline nunca teve chance de errar por mérito próprio.

> O sinal em ambos foi o mesmo: **um zero limpo demais**. Um modelo ruim erra de formas variadas;
> um harness quebrado erra tudo igual. Vale como heurística — quando o número favorece a sua tese e
> é redondo demais, procure o bug antes de escrever a conclusão.

A allowlist da ANTT agora é gerada do **manifesto dela** (`catalog_antt.json`), mantendo o princípio
original: allowlist vem do catálogo gerado, nunca de lista escrita à mão.

## Por que o SQL cru erra

| Motivo | Nº |
|---|---|
| resultado não bate o gold em nenhuma das 3 variantes | 104 |
| erro de execução (SQL inválido) | 10 |

O erro dominante é **semântico**, não sintático: o SQL roda e devolve um número — errado. É o modo
de falha que o Semantic Layer elimina por construção, e é exatamente a tese. O prompt do baseline
entrega o schema completo e todos os valores categóricos; o que ele **não** entrega é o que
significa "taxa de automação", "participação de comerciais", nem que a praça só é única quando
combinada com a concessionária.

## Qualidade do golden

**220 autorados → 216 válidos → TEST de 185 itens** (25–26 por estrato; `controle_trivial` tem 8,
cap estrutural). Só 4 descartes na geração do gold — as guardas embutidas no gerador pegaram o resto
antes de virar item ruim:

- **G1** — filtro que conflita com a definição da métrica (`automation_rate` filtrada por
  `tipo_cobranca` dá sempre 1,0). Vale para `where` **e** `group_by`: `commercial_share` *agrupada*
  por `tipo_de_veiculo` também é constante. (Peguei esse segundo caso corrigindo a própria guarda.)
- **G2** — filtrar e agrupar pela mesma dimensão é ambíguo.
- **G3** — sem estrato `metrica_filtrada`: o catálogo limpo não tem métrica com filtro embutido.

### κ de máquina: 0,977 — e finalmente não é 1,0

Decisão respondível × fora-de-escopo: **185/186**, κ = **0,9773**. Concordância de spec nos
respondíveis: **1,0**, zero divergências.

A única discordância foi um **erro meu**: rotulei *"Qual o dia de maior movimento?"* como abstenção,
e o anotador cego mostrou que é respondível (volume por dia, ordenado, limite 1). Ele está certo —
o item foi **removido antes de qualquer resultado ser visto**, e o TEST re-selado. É o mesmo
protocolo das paráfrases da Fase 7 e dos ambíguos da Fase 9.

## Limitações honestas

- **κ é de máquina.** A base da ANTT não vem com benchmark humano de perguntas — foi a falha
  não-bloqueante registrada na Fase 0 de Dados. κ humano segue no backlog (é o que o passo 3,
  BIRD Mini-Dev, endereça).
- **Perguntas ainda são de template**, autoradas por modelo.
- **`ranking` e `valor_categorico` em 72%** são o resíduo real. O normalizador de ordem resolveu a
  sintaxe; o que sobra é escolha de métrica e de dimensão — o problema caro, ainda aberto.
- **Não comparável com as Fases 4–10.** Base diferente, catálogo diferente, dificuldade diferente.
  Quem comparar 86,9% com os 73,7% da Fase 8 estará comparando coisas distintas.

## Reprodução

```bash
python golden/gerar_autor_antt.py     # 220 itens, guardas G1/G2/G3 na geração
python preparar_antt.py               # gold via MetricFlow nas 3 variantes + split + selo
python golden/kappa_maquina_antt.py   # κ de máquina (2º anotador cego)
python avaliar_fase12.py test         # Tier-A × SQL cru (predições congeladas)
```
