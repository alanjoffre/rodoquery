# Fase 9 — Conserto: por que a falha mecânica se conserta em código, não no prompt

A Fase 8 isolou três modos de falha. Esta fase tentou consertá-los e mediu o conserto num holdout
**novo** (TEST-v3), gerado depois que o código do conserto já estava fechado. O resultado mais
importante é metodológico:

> **Reescrever o prompt para consertar a falha de ranking EMPATOU** (McNemar p=0,89). O mesmo
> conserto feito em **código** deu **+5 pp, p=0,004, zero regressões**. Uma falha mecânica se
> conserta em código; enfiá-la no prompt como mais texto troca um ganho por regressões em outro
> lugar.

## Protocolo anti-overfitting

Eu já tinha visto o TEST-v2 item a item na Fase 8 — então medir qualquer conserto nele seria
ajustar ao teste. A disciplina desta fase:

1. **Desenvolvimento só no DEV-v2** (41 itens). Iterei o prompt duas vezes ali e **parei** — 41
   itens é pouco, e continuar a ajustar viraria overfitting de outro tipo.
2. **TEST-v3 gerado depois** que o texto/código do conserto estava fechado: 211 itens, specs
   inéditas contra v1 **e** v2, mesma regra anti-degenerado, e **selado** (`sha256`) antes de rodar.
3. Tudo **pareado** — prompt/estratégia antigos × novos nos mesmos itens — com McNemar.

O TEST-v3 tem κ de máquina **1,0** em 211 itens (2º anotador cego, 3 chunks), com as 30 abstenções
*near-miss* todas confirmadas fora-de-escopo. Dois anotadores sinalizaram, de forma independente, 7
itens que filtram e agrupam pela **mesma** dimensão (leitura ambígua); removi os 7 **antes** de
rodar qualquer sistema — o mesmo procedimento das paráfrases da Fase 7.

## Tentativa 1 — reescrever o prompt (`sistema_v2`)

Um catálogo/prompt novo, com regras **gerais** (nunca casos específicos do teste): sintaxe de
ordenação, composição de filtro + agrupamento, e a inexistência de operadores derivados. No DEV-v2
parecia bom (EX 55,6% → 69,4%; ranking 0/5 → 3/5). **No holdout v3, empatou:**

| | EX (respondíveis, n=181) | Abstenção (n=30) |
|---|---|---|
| prompt antigo | 66,9% [59,7; 73,3] | 53,3% |
| prompt reescrito | 68,0% [60,8; 74,3] | 63,3% |
| McNemar | b=24, c=26, **p=0,89** | b=4, c=7, p=0,55 |

**Por que empatou** — a decomposição das 28 regressões (itens que o antigo acertava e o novo passou
a errar):

| Causa | Nº |
|---|---|
| **métrica errada** | **18** |
| ordem / where | 6 |
| group_by errado | 2 |
| abstém indevidamente | 2 |

O prompt reescrito consertou ranking (+10) e ajudou grão temporal/abstenção, mas a prosa extra
sobre *seleção de métrica* degradou a escolha de métrica nos itens multidimensionais — 18 erros
novos que anularam o ganho. Estratos que eram fortes caíram: `metrica_filtrada` 30→26, `join_grao`
28→24.

**Decisão: rejeitado.** Um conserto que não bate o baseline num teste justo não entra. Fica no
repositório como resultado negativo documentado (`src/rodoquery/sistema_v2.py`).

## Tentativa 2 — normalizar a ordenação em código

O diagnóstico do ranking foi **cirúrgico**: as 22 falhas eram o **mesmo** padrão. O modelo,
treinado em SQL, escreve a direção como token separado —

```
gold:      order_by = ["-revenue"]          (MetricFlow)
modelo:    order_by = ["revenue", "DESC"]   (estilo SQL)  → não compila
```

A métrica está certa, a intenção de direção está certa; **só a serialização diverge**. Isso não é
matéria de julgamento — é um `if` determinístico:

```python
def normalizar_ordem(order_by):
    # ["revenue","DESC"] -> ["-revenue"] ; ["revenue","ASC"] -> ["revenue"]
    if len(order_by) == 2 and order_by[1].strip().upper() in ("DESC", "ASC"):
        campo = order_by[0].lstrip("-")
        return [f"-{campo}"] if order_by[1].strip().upper() == "DESC" else [campo]
    return order_by
```

Como só age na forma exata `[campo, DESC/ASC]` e **não toca em `metrics`, `group_by` nem `where`**,
é **impossível** ele regredir a seleção de métrica — que foi o custo do prompt reescrito.

O normalizador foi motivado pela Fase 8 (v2), antes de o v3 existir, então o v3 é o holdout que o
mede pela primeira vez. E como é uma transformação determinística das specs **já congeladas**, a
medição não chama o LLM: é exata e reprodutível.

**Resultado (prompt antigo cru × prompt antigo + normalizador, no v3):**

| | EX (respondíveis, n=181) | McNemar |
|---|---|---|
| prompt antigo cru | 66,9% [59,7; 73,3] | — |
| **+ normalizador** | **71,8% [64,9; 77,9]** | **b=0, c=9, p=0,004** |

**b=0 é o ponto:** nenhum item que estava certo virou errado. Ganho **estrito**, significativo, com
**zero** regressões — precisamente o que um conserto cirúrgico em código deve produzir. Por estrato,
só `ranking` mexe (4 → 13, +9); todo o resto fica idêntico ao caractere.

### Ranking ainda não está resolvido — e a doc diz isso

O normalizador leva ranking de 4/26 para **13/26**, não para 26/26. Remover a barreira de sintaxe
foi necessário, não suficiente: os 13 que ainda erram têm um problema **a mais** — quase sempre a
**mesma fraqueza de seleção de métrica** que a Fase 8 já apontava (ex.: unidade BRL × centavos), não
algo específico de ranking. O conserto de sintaxe é um ganho limpo e barato; a seleção de métrica é
um problema aberto, e **não** finjo tê-lo resolvido.

## O que foi para produção

O normalizador entrou no **caminho de serviço** (`servico.py`), aplicado à spec logo depois do
`tier_a` e antes de compilar — o mesmo ponto onde o serviço já falhava fechado. O `tier_a`
congelado **não muda** (as Fases 4–8 seguem reproduzíveis); isto é endurecimento de serviço, como o
fail-closed da Fase 6. Coberto por 9 testes unitários que fixam a propriedade central: o
normalizador só age na forma `[campo, DESC/ASC]` e é idempotente.

## Limitações honestas

- **O prompt reescrito não é lixo — é um trade-off ruim.** Ele de fato ajuda ranking e abstenção;
  só custa mais do que rende, neste SUT. Com um modelo maior a conta poderia inverter. Não testei.
- **Seleção de métrica continua o gargalo real** (Fase 8 e aqui). O conserto barato foi feito; o
  caro (descrições que separem métricas vizinhas, ou um SUT melhor) segue no backlog.
- **v3 é mais multidimensional** que v2, então o EX absoluto dos dois não é comparável. Por isso
  toda conclusão desta fase é **pareada** (mesmos itens, só muda a estratégia), onde a dificuldade
  do conjunto se cancela.
- κ de máquina, não humano; abstenções e paráfrases autoradas por modelo — herdado.

## Reprodução

```bash
python validar_dev_v2.py                    # iteração do prompt (DEV-v2, desenvolvimento)
python golden/gerar_autor_v3.py             # 240 candidatos, specs inéditas vs v1 e v2
python preparar_v3.py                       # gold + anti-degenerado + selo
python limpar_v3.py                         # remove 7 ambíguos sinalizados pelos anotadores
python golden/kappa_maquina_v3.py           # κ de máquina (211 itens)
python avaliar_fase9.py                     # prompt antigo × reescrito  → WASH (p=0,89)
python avaliar_fase9_normalizador.py        # antigo × +normalizador → +5pp, p=0,004, 0 regressões
```
