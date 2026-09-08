# Fase 23 — o catálogo enriquecido pode ir ao serving?

A [Fase 21](FASE21_CATALOGO_RICO.md) mediu o catálogo de 7 métricas em **47 itens** do conjunto duro
e ele venceu: o rebaixamento de tipo caiu de **6/6 para 1/8** e a abstenção subiu de 50% para 75%.
Mas ele nunca foi medido no **benchmark principal**, e o serving continuou com o de 3. O item ficou
no limbo — nem promovido, nem declarado como decisão adiada. Esta fase o resolve **medindo**.

O que me incomodava não era o ganho da F21, era o denominador: 47 itens de um conjunto desenhado
contra as fraquezas do catálogo antigo. Promover com base nisso seria servir uma configuração cuja
acurácia no conjunto principal ninguém tinha medido.

## O desenho, e por que ele é válido

Comparação **pareada** contra as predições **congeladas** da Fase 18: mesmo SUT (`claude-opus-5`),
mesmo conjunto selado (TEST-ANTT, 171 itens), mesmo gold. Muda **só o catálogo** — o `PROMPT` é
byte a byte o mesmo.

**Verificado antes de gastar** (o script aborta se não valer): as 3 métricas do catálogo original
sobrevivem **intactas** no rico, e o gold dos 146 respondíveis usa **apenas** essas 3
(`automation_rate` 57 · `traffic_volume` 49 · `commercial_share` 42). Nenhuma foi renomeada ou
removida, então pontuar predições novas contra o gold antigo é legítimo.

> **As 25 abstenções não entram no placar, de propósito.** Uma pergunta é abstenção porque o
> catálogo não tem como respondê-la; quando ele passa a ter, ela pode virar legitimamente
> respondível — foi o que ocorreu com 4 itens na F21. Contá-las como falha puniria o sistema por
> acertar. Elas foram para um diagnóstico separado, marcando quais foram respondidas com métrica
> **nova** (mudança causada pelo catálogo) e quais com métrica **antiga** (aí sim, alucinação).
>
> **A precaução não foi necessária: nenhuma das 25 virou respondível.** Zero foram respondidas com
> métrica nova. Bom saber — mas eu não tinha como saber antes de medir, e um desenho que só
> funciona se a suposição for verdadeira não é desenho.

## O resultado

| | catálogo de 3 (F18) | catálogo de 7 (F23) |
|---|---|---|
| Respondíveis (EX) | **146/146** = 100% | **145/146** = 99,32% [96,2; 99,9] |
| Abstenção | 24/25 = 96% | **25/25 = 100%** |
| McNemar (pareado, respondíveis) | — | b=1, c=0, **p = 1,0** |
| Custo | — | US$ 0,4632 |

**Estatisticamente indistinguível.** O catálogo rico não custa acurácia no benchmark principal.

Por estrato, o rico faz 100% em seis dos sete (`coalesce_nulo`, `join_grao`, `metrica_derivada`,
`grao_temporal`, `valor_categorico`, `controle_trivial`) e 11/12 em `ranking`.

## O mecanismo: um só, e não o que eu esperava

Eu previa que a regressão seria a ambiguidade que a F21 mediu — com `passenger_share` disponível,
"entre os veículos de passeio…" viraria `share` em vez de filtro. **Fui verificar a spec em vez de
presumir, e era outra coisa.**

O item que regrediu (`ranking_antt_22`, *"Entre os veículos de passeio, quais as 3 categorias de
eixo com maior taxa de automação?"*) não foi respondido errado: o sistema **absteve**
(`raw = "ABSTENHO"`, abstenção genuína, não falha de parse — conferido). E o item que a F18 errou
(`abstencao_antt_10`, *"Qual o volume acumulado no ano?"*) o rico **absteve corretamente**.

Os dois movimentos são o mesmo movimento: **com 7 métricas o sistema ficou mais abstêmio**
(24 → 26 abstenções no total). Ganhou uma recusa certa e perdeu uma resposta certa.

## Como isso vira uma decisão

Três coisas pesam, e a terceira é a que decide:

1. **Não há perda medida** no benchmark principal (p = 1,0).
2. **Há ganho medido** no conjunto duro da F21, em conjunto selado: o rebaixamento de tipo — que é
   **resposta silenciosamente errada**, o modo de falha mais caro deste domínio — cai de 6/6 para
   1/8.
3. **O benchmark principal não consegue mostrar o lado bom, por construção.** As suas perguntas
   foram autoradas contra o catálogo de 3, então nenhuma delas *exige* `manual_share`, `ocr_share`,
   `passenger_share` ou `motorcycle_share` — verificado: o gold usa só as 3 antigas. Perguntar a
   este conjunto se o catálogo rico ajuda é perguntar a quem não pode responder. O que ele **pode**
   dizer é se o catálogo rico atrapalha. Disse que não.

Com uma pergunta legítima sobre o dado — *"qual a proporção de cobrança manual?"* — o catálogo de 3
não apenas falha: ele responde **contagem** no lugar de **proporção**, sem sinalizar nada. Trocar
isso por um sistema que responde certo, ao custo de ficar marginalmente mais abstêmio, é uma boa
troca para um serviço.

**Decisão: promovido.** `RODOQUERY_CATALOGO_ANTT=rico` é o default do serving no caminho ANTT.

### O que NÃO foi feito, e por quê

- **`tier_a_antt` não foi tocado.** Ele é o sistema avaliado nas Fases 12–21; reescrevê-lo mudaria
  o SUT de dez fases medidas e faria o gate nível B divergir. O serving **escolhe** entre dois
  sistemas — há teste travando exatamente isso (`test_o_sistema_avaliado_nas_fases_12_a_21_nao_foi_trocado`).
- **A promoção é reversível por configuração**, não por edição de código:
  `RODOQUERY_CATALOGO_ANTT=basico`.
- **O catálogo v2 da F15 continua fora**, e por motivo diferente: ele reescrevia *descrições* do
  mesmo catálogo, então promovê-lo mudaria o significado das comparações sem oferecer cobertura
  nova. Este aqui adiciona **vocabulário**, que é outra coisa.

## Limitações declaradas

- **A diferença é de 1 item para cada lado, e o SUT não é determinístico.** Desde a F18 está dito
  que Claude ≥ 4.7 rejeita `temperature`/`seed`, então o número publicado é reproduzível
  (predições congeladas) mas a **coleta** não é. Duas execuções independentes diferirem em 2 de 171
  itens está dentro do esperado. O que sustenta a leitura de "mais abstêmio" não é a significância
  — não há — é o fato de os dois movimentos apontarem para o **mesmo lado**, com mecanismo
  verificado nas specs. É sinal, não prova.
- **Isto não mede a experiência real de uso.** Mede que o catálogo rico não regride no conjunto que
  eu tenho. As perguntas que ele destrava não estão neste conjunto, e medi-las exigiria um golden
  novo, autorado contra o catálogo de 7 — trabalho aberto.
- **A abstenção de 100% (25/25) é sobre 25 itens.** O IC vai de 86,7% a 100%.

## Reprodução

```bash
python avaliar_rico_test_antt.py --confirmar --teto-usd 0.65   # US$ 0,4632
```

As predições ficam congeladas em `reports/fase23/predicoes_tier_a_rico_test_antt.json`; rodar de
novo **reusa** e não gasta. Artefato: `reports/fase23/resultado_rico_test_antt.json`.
