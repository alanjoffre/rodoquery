# Guia de autoria do golden set (Fase 2)

Este é o roteiro humano para construir o conjunto de referência do RodoQuery. A máquina já faz a
parte automática (o *gold* sai do MetricFlow); o que **só um humano pode fazer** — e que é o núcleo
anti-vazamento — é **escrever as perguntas** e **mapeá-las para uma spec**.

> **Por que humano?** Se a mesma pessoa escreve a pergunta, o SQL-gold *e* o prompt do agente, o
> benchmark mede "o agente reproduz meu SQL", não "acerta a resposta" — e a tese fica infalsificável.
> Ver a auditoria staff que blindou esta fase.

## O modelo mental

Cada item do golden set é:

```json
{"id": "...", "pergunta_nl": "pergunta em português", "estrato": "...",
 "spec": {"metrics": [...], "group_by": [...], "where": null, "ordenado": false}}
```

Você escreve a **pergunta** e a **spec** (o mapeamento). O *gold* (a resposta certa) é gerado
automaticamente: `spec → mf query → resultado → hash`. **Você nunca escreve SQL.**

## Vocabulário disponível (o que a spec pode usar)

**Métricas** (`metrics`):

| Métrica | Significado | A armadilha do SQL cru |
|---|---|---|
| `transactions` | contagem de transações | — |
| `revenue` | receita em R$ — **só COMPLETED e valor > 0** | `SUM(amount)` inclui FAILED/REVERSED → inflado |
| `revenue_cents` | receita em centavos inteiros | idem |
| `suspect_transactions` | transações com `audit_flag != 'OK'` | filtro de flag errado |
| `suspect_rate` | suspeitas / total (ratio) | denominador errado |
| `revenue_leakage_brl` | soma das subcobranças em R$ | esquece o `abs()`/sinal |
| `revenue_leakage_cents` | idem, em centavos | idem |

**Agrupamentos** (`group_by`):
- Tempo: `metric_time__day`, `metric_time__week`, `metric_time__month`, `metric_time__quarter`, `metric_time__year`
- Categóricas: `transaction__status`, `transaction__audit_flag`, `transaction__payment_method`
- Entidades: `transaction__plaza`, `transaction__vehicle`

**Filtros** (`where`) — sintaxe MetricFlow:
```
{{ Dimension('transaction__status') }} = 'COMPLETED'
```

**Valores categóricos válidos** (para `where`):
- `status`: `COMPLETED`, `FAILED`, `REVERSED`
- `audit_flag`: `OK`, `COBRANCA_EM_FALHA`, `POSSIVEL_DUPLICIDADE`, `TARIFA_DIVERGENTE`, `VALOR_INVALIDO`
- `payment_method`: `AUTOMATIC_TAG`, `CARD`, `CASH`

> O vocabulário completo está em `reports/fase0/catalog.json` (gerado do dbt). Se o modelo dbt
> mudar, regenere: `python -m rodoquery.catalogo`.

## Os 7 estratos (pré-registrados)

Cada estrato é um **mecanismo** pelo qual o SQL cru erra e o Semantic Layer acerta. **Alvo: ≥ 25
perguntas por estrato** (~200 no total) para o IC ser útil. Exemplos em `golden/candidates.jsonl`.

1. **`metrica_filtrada`** — a métrica embute um filtro. Ex.: *"Qual o faturamento?"* → `revenue`
   (que só conta COMPLETED). O SQL cru soma tudo e infla.
2. **`coalesce_nulo`** — grupos sem atividade devem virar **0**, não sumir. Ex.: *"receita por dia"* —
   um dia sem cobrança concluída aparece como 0.
3. **`join_grao`** — grão/fan-out de join (1:N). Ex.: *"receita por praça e status"* — o SQL cru
   duplica linhas no join.
4. **`metrica_derivada`** — ratio/derivada. Ex.: *"taxa de suspeita"* (`suspect_rate`) — o
   denominador tem de ser o total certo; `revenue` divide por 100 **no fim** (centavos).
5. **`grao_temporal`** — truncamento de data (dia/semana/mês). Ex.: *"receita por mês"*.
6. **`valor_categorico`** — filtro por valor exato de dimensão. Ex.: *"transações concluídas"* →
   `where status = 'COMPLETED'`.
7. **`controle_trivial`** — count numa tabela só, onde **ambos os sistemas devem acertar**. É a
   guarda contra um scorer viciado que sempre favoreceria o Tier semântico.

## O fluxo (em fases, como o resto do projeto)

1. **Autoria (você).** Escreva perguntas realistas de um analista de auditoria — **incluindo
   ambíguas** ("mês passado", "as principais praças") e **fora de escopo** (para testar abstenção).
   Mapeie cada uma para a `spec`. Trabalhe **cego ao output do modelo** (não escreva perguntas
   olhando as falhas do agente — isso vaza).
2. **Validação (automática).** Rode `validar_item` em cada uma: a spec **compila** no MetricFlow e o
   gold é **não-vazio**? Corrija as inválidas.
3. **2º anotador (κ).** Uma 2ª pessoa mapeia as MESMAS perguntas → spec, **independente**. Rode
   `concordancia_mapeamento`: **κ de Cohen ≥ 0,8** e concordância de spec canônica ≥ 0,8. Itens
   discordantes são adjudicados ou **removidos antes de selar**.
4. **Split e selamento.** Divida DEV (visível, ~30%) / TEST (selado, ~70%). Commite o **sha256 do
   TEST antes de rodar qualquer sistema** — pré-registro anti-vazamento (não dá pra editar depois).
5. **Gerar respostas.** `gerar_respostas` faz o hash do gold em cada variante do test-suite.

## Regras de honestidade (não-negociáveis)

- **Nunca** escreva a pergunta olhando o que o modelo errou.
- **Nunca** ajuste a spec para o agente acertar.
- O baseline Tier-B (SQL cru) recebe **schema completo e prompt justo** — senão a comparação é
  contra um espantalho.
- Perguntas **ambíguas** medem abstenção/clarificação — não as jogue fora por serem "difíceis".
- Se um estrato só tem pegadinhas, **diga** que fração do uso real ele representa.

## Como rodar as ferramentas

```python
from rodoquery.golden import carregar, validar_item, concordancia_mapeamento, GOLDEN_DIR

itens = carregar(GOLDEN_DIR / "candidates.jsonl")
for it in itens:
    ok, motivo = validar_item(it)          # spec compila + gold não-vazio?
    print(it.id, ok, motivo)

# κ do 2º anotador (dois arquivos com os mesmos ids, specs independentes):
a = carregar(GOLDEN_DIR / "anotador_a.jsonl")
b = carregar(GOLDEN_DIR / "anotador_b.jsonl")
print(concordancia_mapeamento(a, b))
```
