# Fase 11 — Migração para dados REAIS da ANTT

Passo 2 do plano: trocar o dado sintético pelo dado público real, mantendo toda a infraestrutura
(semantic layer, harness, gate, serving). O projeto e o nome continuam — o domínio é o mesmo.

## O que mudou

| | Sintético (Fases 0–10) | **ANTT real (Fase 11+)** |
|---|---|---|
| Origem | gerador próprio | [Portal de Dados Abertos da ANTT](https://dados.antt.gov.br/dataset/volume-trafego-praca-pedagio), **CC-BY** |
| Linhas no fato | 2.005 | **1.534.142** |
| Praças | ~5 | **241** (233 nomes — ver abaixo) |
| Concessionárias | — | **30** |
| Cobertura | sintética | diária, 01/01 a 31/05/2026 |
| Métricas expostas | 7 | **3** |

A fundação sintética **não foi tocada**: vive em `~/toll-foundation`, e a nova em
`~/antt-foundation/dbt-antt`. Mexer nela invalidaria a reprodutibilidade das Fases 4–10.

## Fase 0 de Dados: **GO** (com ressalvas registradas)

O crivo rodou **antes** de qualquer modelagem (`fase0_dados.py`) — que é o ponto: validar a base na
entrada, não na saída. Veredito **GO**, com duas falhas não-bloqueantes:

1. **Não existe benchmark humano** para esta base → o golden set será de máquina, e o κ humano
   segue no backlog. (É o que o passo 3, BIRD Mini-Dev, endereça.)
2. **Dívida de staging**: `volume_total` vem como **texto** com vírgula decimal (`"17683,00"`) e
   `categoria_eixo` é numérico mas **categórico**. Ambos resolvidos no staging.

> **O próprio validador errou na 1ª versão.** Ele classificou `volume_total` como *dimensão* (por
> ser VARCHAR) e `categoria_eixo` como *medida* (por ser BIGINT). Corrigido: quem define medida é
> **cardinalidade**, não tipo. Um validador que confunde a medida deixaria passar um desenho ruim —
> por isso ele também ganhou um check de dívida de staging.

## Duas armadilhas do dado real

**1. Praça não é chave.** Cinco nomes (`P1`, `P2`…) aparecem em mais de uma concessionária: são
**233 nomes para 241 praças reais**. Agrupar por nome fundiria praças distintas e produziria
números errados **em silêncio**. A entidade é `(concessionaria, praca)`.

**2. Uma razão que retornava 1,0 para tudo.** Declarei o numerador da `automation_rate` como
*filtro* da própria métrica — o MetricFlow aplicou o filtro aos **dois** lados e devolveu `1,0`
universalmente. Número errado, sem erro nenhum. **Só peguei porque confrontei com a verdade em SQL
puro** (0,6230). Corrigido para o padrão (filtro na *measure*), e agora bate: `0,62297`.
Fica o registro: em semantic layer, verificar contra o SQL cru é obrigatório, não zelo.

## O catálogo nasce limpo — 3 métricas

| Métrica | Tipo | Por que existe |
|---|---|---|
| `traffic_volume` | simple | a única medida do dado |
| `automation_rate` | ratio | proporção do tráfego com tag/AVI |
| `commercial_share` | ratio | proporção de veículos comerciais |

**São poucas de propósito.** O dado da ANTT tem **uma** medida (volume); inventar métricas a partir
dela só recriaria a ambiguidade que a Fase 10 mediu. As duas razões entram porque são as únicas
coisas que **não** dá para expressar com um `where`.

Os numeradores (`automated_traffic_volume`, `commercial_traffic_volume`) existem no manifesto mas
estão marcados `meta: {catalogo_usuario: false}` — curadoria **declarada e auditável**, não
comentário. Se estivessem no catálogo, *"quantos veículos passaram em cobrança automática?"* teria
duas respostas certas (a métrica, ou `traffic_volume` + `where`) — exatamente o erro da Fase 10.

**Consequência declarada:** o estrato `metrica_filtrada` **deixa de existir** por construção. Um
catálogo bem desenhado elimina uma classe inteira de falha.

## Test-Suite EX sobre dado real

Sem gerador, não há "outra seed". A adaptação: cada variante recebe **um terço disjunto** do fato,
por hash determinístico. Uma spec errada teria de produzir o mesmo hash em três subconjuntos
distintos — improvável por acaso, que é a propriedade que importa.

| Variante | Linhas | Volume |
|---|---|---|
| `antt_p0` | 512.107 | 130.867.847 |
| `antt_p1` | 511.317 | 130.511.481 |
| `antt_p2` | 510.718 | 130.233.649 |

Verificado (`verificar_fundacao_antt.py`): 6 specs representativas compilam, executam nas 3
variantes, produzem **hashes distintos** entre elas, e o total bate com o SQL puro.

## Canário: 11/12 — e o que o número esconde

O caminho fecha ponta a ponta sobre dado real: pergunta → spec → MetricFlow → SQL → número.
Achados reais que saíram: motos quase não usam tag (**0,01%** de automação, contra **84,8%** dos
comerciais); NITERÓI-1 é a praça de maior volume (11,8 mi de veículos em 5 meses).

Duas ressalvas honestas sobre esse 11/12:

- **A falha conhecida persiste.** *"volume médio por praça"* devia abster (não há métrica de média)
  e o modelo respondeu com a soma — a **substituição semântica** que a Fase 8 isolou. O catálogo
  declara explicitamente que média não existe, e ainda assim acontece.
- **Um "OK" é provavelmente errado.** Em *"quantos veículos comerciais passaram em cada praça?"* o
  modelo devolveu `commercial_share` (proporção) onde a pergunta pede **contagem**
  (`traffic_volume` + `where`). O canário só verifica que a consulta **roda**, não que está certa —
  por isso ele é sinal operacional, e a medida científica é o golden set com gold do MetricFlow.

## O que esta fase NÃO entrega

Os números das Fases 4–10 **não** transferem: eles medem o sistema sobre dado sintético. Sobre a
ANTT, tudo se remede do zero. O golden set estratificado, o gold via MetricFlow e o Test-Suite EX
sobre a base real são a próxima etapa — esta fase entrega a **fundação verificada** sobre a qual
essa medição vai rodar.

## Reprodução

```bash
python ~/antt-foundation/carregar_landing.py        # CSV público -> landing (cast, encoding)
cd ~/antt-foundation/dbt-antt && dbt build          # staging -> marts -> semantic layer (17/17)
python ~/antt-foundation/construir_variantes.py     # 3 partições disjuntas p/ Test-Suite EX
python fase0_dados.py ~/antt_dados/volume_2026_diario.csv --sep ';' --encoding latin-1
python verificar_fundacao_antt.py                   # fumaça ponta a ponta + confronto com SQL
python canario_antt.py                              # o agente sobre dado real
```
