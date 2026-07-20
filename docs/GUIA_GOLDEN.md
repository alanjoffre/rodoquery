# Guia de autoria do golden set (Fase 2)

Este é o roteiro para construir o conjunto de referência do RodoQuery. A máquina já faz a parte
automática (o *gold* sai do MetricFlow); a parte que carrega o valor anti-vazamento é **escrever as
perguntas** e **mapeá-las para uma spec** — sem nunca escrever SQL à mão.

> **A circularidade que importa** é o *gold*: se quem escreve a pergunta também escreve o SQL-gold, o
> benchmark mede "o agente reproduz meu SQL", não "acerta a resposta". Aqui isso **não acontece** — o
> gold sai do MetricFlow a partir da spec, nunca de SQL escrito à mão. Ver a auditoria staff da fase.

## Estado atual (v1) — o que foi feito, sem maquiagem

> Esta seção é deliberadamente explícita porque o portfólio é sobre **rigor**, e rigor inclui não
> vender evidência que não existe.

| Etapa | Padrão documentado (ideal) | O que a v1 realmente fez |
|---|---|---|
| Autoria das perguntas | humano (analista de auditoria) | **modelo** — `golden/gerar_autor.py`, estratificado, `seed=42` |
| Mapeamento pergunta→spec | humano | **modelo** (mesmo gerador) |
| 2º anotador (κ) | 2º **humano** independente | **2º LLM** independente, cego às specs do autor — **κ de MÁQUINA** |
| κ humano | ≥ 0,8 entre humanos | **backlog declarado** (ainda não coletado) |

**Por que isto ainda vale como evidência forte:**
- A anti-circularidade real (gold = MetricFlow, nunca SQL à mão) está **intacta**.
- O κ de máquina é medido com um 2º LLM **cego** e **rotulado como máquina** — não é apresentado
  como concordância humana. Resultados: **κ = 1,0** no golden limpo (61 itens, mapeamento
  inequívoco) e **κ = 0,875** numa *sonda de ambiguidade* de 10 perguntas naturais — ou seja, a
  métrica **discrimina** (cai quando há ambiguidade real; ver `reports/fase2/`).
- A divergência da sonda (`amb_05`, *"Como está a fraude, mês a mês?"* → `suspect_rate` vs
  `suspect_transactions`) é uma **lacuna de guideline** genuína, exatamente o que o κ existe para achar.

**Limitação honesta do κ de máquina:** dois LLMs da mesma família compartilham *prior*; o κ mede
sobretudo se as perguntas são **inequívocas dado o catálogo** — não substitui o κ humano, que
capturaria a bagunça de perguntas reais. Por isso o κ humano fica como **backlog**, não como
"feito". Um κ = 1,0 no golden limpo é, por si só, **fraco** (mede templates sem ambiguidade); é a
sonda que dá dentes à métrica.

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
3. **2º anotador (κ).** Um 2º anotador mapeia as MESMAS perguntas → spec, **independente e cego** às
   specs do 1º. Rode `concordancia_mapeamento`: **κ de Cohen ≥ 0,8** e concordância de spec canônica
   ≥ 0,8. Itens discordantes são adjudicados ou **removidos antes de selar**.
   - **v1 (feito):** o 2º anotador é um **LLM** diferente, cego → **κ de máquina** (rotulado como
     tal). Ver `reports/fase2/concordancia_maquina.json` e `.../sonda_ambiguidade_maquina.json`.
   - **backlog:** repetir com um 2º **humano** para o κ humano. A ferramenta é a mesma — só troca o
     arquivo do anotador B.
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

itens = carregar(GOLDEN_DIR / "golden.jsonl")   # 61 itens validados (autor = modelo)
for it in itens:
    ok, motivo = validar_item(it)               # spec compila + gold não-vazio?
    print(it.id, ok, motivo)

# κ do 2º anotador (mesmos ids, specs independentes). v1 = anotador B é um 2º LLM cego:
a = carregar(GOLDEN_DIR / "golden.jsonl")            # anotador A (autor)
b = carregar(GOLDEN_DIR / "kappa_maquina_b.jsonl")  # anotador B (2º LLM, cego) → κ de máquina
print(concordancia_mapeamento(a, b))                # κ = 1.0 (golden limpo)
# sonda de ambiguidade (dá dentes ao κ): golden/sonda_ambiguidade.jsonl vs sonda_kappa_maquina_b.jsonl → κ = 0.875
```

## Reprodução do κ de máquina (v1)

```bash
# 1) (re)gerar o golden do autor (modelo), estratificado e determinístico
python golden/gerar_autor.py > golden/autor.jsonl

# 2) validar (compila no mf + gold não-vazio) e salvar só os válidos
python golden/validar_golden.py              # -> golden/golden.jsonl (61/61)

# 3) o 2º anotador-LLM é rodado como subagente CEGO (só perguntas + catálogo, sem as specs do autor);
#    a saída dele vira golden/_maquina_b_raw.jsonl. Então:
python golden/kappa_maquina.py               # -> reports/fase2/concordancia_maquina.json  (κ=1.0)
python golden/kappa_sonda.py                 # -> reports/fase2/sonda_ambiguidade_maquina.json (κ=0.875)

# 4) gerar o gold com Test-Suite EX (reconstrói 3 variantes + hash por variante) e selar o golden
python gerar_gold_fase2.py                   # -> reports/fase2/gold_respostas.json + golden/golden.sha256
```
