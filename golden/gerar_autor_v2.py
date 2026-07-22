"""Golden v2 — expansão de N para ≥25/estrato, com cobertura de superfície NOVA do catálogo.

**Por que uma v2 em vez de "gerar mais do mesmo".** Inflar N repetindo as specs da v1 com outro
fraseado não dá poder estatístico: os itens ficam correlacionados e o IC de Wilson finge precisão
que não existe. Aqui toda spec da v2 é **inédita** (assinatura canônica ausente da v1) — isso é
verificado, não prometido.

**Superfície que a v1 nunca cobriu** (achado ao auditar o catálogo contra o golden):
  - métricas `revenue_cents` e `revenue_leakage_cents` — nunca testadas;
  - `transaction__audit_flag` como group_by — nunca usada;
  - valores `POSSIVEL_DUPLICIDADE` e `VALOR_INVALIDO` — nunca filtrados;
  - **ranking/top-N** — nenhum item da v1 usa order_by+limit+ordenado, embora o prompt do sistema
    tenha uma regra sobre isso. Regra de prompt nunca avaliada = risco não medido → estrato novo.

**Ambiguidade evitada de propósito:** `revenue` × `revenue_cents` (e o par de leakage) só se
distinguem pela unidade, então toda pergunta de centavos diz "em centavos" explicitamente. Sem
isso o item seria ambíguo e puniria o modelo por uma falha do anotador (lição da sonda da Fase 2).

HONESTIDADE: itens autorados por modelo, como na v1. κ de MÁQUINA com 2º anotador cego; κ humano
segue no backlog declarado. Ver docs/GUIA_GOLDEN.md.

Roda: `python golden/gerar_autor_v2.py`  → golden/autor_v2.jsonl
"""
import json
import random
from pathlib import Path

G = Path(__file__).resolve().parent
ALVO = 34                      # 32 por estrato × 85% no TEST ≈ 27 ≥ 25 (meta pré-registrada)
rng = random.Random(4242)      # seed distinta da v1 (42), para não reproduzir as mesmas escolhas

TEMPO = ["metric_time__day", "metric_time__week", "metric_time__month"]
CATEG = ["transaction__status", "transaction__payment_method", "transaction__audit_flag"]
ENTID = ["transaction__plaza", "transaction__vehicle"]
DIMS = TEMPO + CATEG + ENTID

CONTAGEM = ["transactions", "suspect_transactions"]
VALOR = ["revenue", "revenue_cents", "revenue_leakage_brl", "revenue_leakage_cents"]
TODAS = CONTAGEM + VALOR + ["suspect_rate"]
# Métricas que embutem filtro na definição (revenue só COMPLETED; suspeitas filtram flag).
COM_FILTRO_EMBUTIDO = ["revenue", "revenue_cents", "revenue_leakage_brl",
                       "revenue_leakage_cents", "suspect_transactions"]
DERIVADAS = ["suspect_rate", "revenue_leakage_brl", "revenue_leakage_cents"]

VALORES = {
    "transaction__status": ["COMPLETED", "FAILED", "REVERSED"],
    "transaction__payment_method": ["AUTOMATIC_TAG", "CARD", "CASH"],
    "transaction__audit_flag": ["OK", "COBRANCA_EM_FALHA", "TARIFA_DIVERGENTE",
                                "POSSIVEL_DUPLICIDADE", "VALOR_INVALIDO"],
}
VAL_LABEL = {
    "COMPLETED": "concluídas", "FAILED": "que falharam", "REVERSED": "estornadas",
    "AUTOMATIC_TAG": "pagas com tag automática", "CARD": "pagas com cartão",
    "CASH": "pagas em dinheiro", "OK": "sem apontamento de auditoria",
    "COBRANCA_EM_FALHA": "com cobrança em falha", "TARIFA_DIVERGENTE": "com tarifa divergente",
    "POSSIVEL_DUPLICIDADE": "com possível duplicidade", "VALOR_INVALIDO": "com valor inválido",
}
DIM_SUF = {
    "metric_time__day": ["por dia", "em cada dia", "dia a dia"],
    "metric_time__week": ["por semana", "semana a semana"],
    "metric_time__month": ["por mês", "mês a mês", "em cada mês"],
    "transaction__status": ["por status", "por situação"],
    "transaction__payment_method": ["por método de pagamento", "por forma de pagamento"],
    "transaction__audit_flag": ["por marcação de auditoria", "por flag de auditoria"],
    "transaction__plaza": ["por praça", "por praça de pedágio", "em cada praça"],
    "transaction__vehicle": ["por veículo", "em cada veículo"],
}
DIM_PLURAL = {
    "transaction__plaza": "praças", "transaction__vehicle": "veículos",
    "transaction__status": "situações", "transaction__payment_method": "métodos de pagamento",
    "transaction__audit_flag": "marcações de auditoria",
}
# Concordância de gênero: "Quais AS praças" × "Quais OS métodos". Pergunta agramatical vira ruído
# de medição — a Fase 7 mostrou que fraseado ruim contamina o resultado.
DIM_ARTIGO = {
    "transaction__plaza": "as", "transaction__vehicle": "os", "transaction__status": "as",
    "transaction__payment_method": "os", "transaction__audit_flag": "as",
}
# Cardinalidade conhecida do catálogo: pedir "top 5" onde só existem 3 valores gera pergunta boba
# e resultado que não exercita o limit. Só entidades (praça/veículo) admitem k=5.
CARD_BAIXA = set(CATEG)
MET_NOME = {
    "transactions": "número de transações",
    "suspect_transactions": "número de transações suspeitas",
    "revenue": "receita", "revenue_cents": "receita em centavos",
    "revenue_leakage_brl": "vazamento de receita",
    "revenue_leakage_cents": "vazamento de receita em centavos",
    "suspect_rate": "taxa de suspeita",
}


def sp(metrics, group_by=(), where=None, order_by=(), limit=None, ordenado=False):
    return {"metrics": list(metrics), "group_by": list(group_by), "where": where,
            "order_by": list(order_by), "limit": limit, "ordenado": ordenado}


def w(dim, val):
    return f"{{{{ Dimension('{dim}') }}}} = '{val}'"


def sig(spec):
    """Assinatura canônica de uma spec — é o que garante que a v2 não repete a v1."""
    return (tuple(spec["metrics"]), tuple(spec["group_by"]), spec["where"],
            tuple(spec["order_by"]), spec["limit"], bool(spec["ordenado"]))


def frase(m, suf=""):
    """Pergunta gramatical por métrica (v1 já ensinou: template genérico gera frase quebrada)."""
    s = f" {suf}" if suf else ""
    op = {
        "transactions": [f"Quantas transações houve{s}?", f"Qual o número de transações{s}?",
                         f"Qual o volume de transações{s}?"],
        "suspect_transactions": [f"Quantas transações suspeitas houve{s}?",
                                 f"Qual o número de transações suspeitas{s}?"],
        "revenue": [f"Qual foi a receita{s}?", f"Qual o faturamento{s}?",
                    f"Quanto foi arrecadado{s}?"],
        "revenue_cents": [f"Qual a receita em centavos{s}?",
                          f"Qual o faturamento em centavos{s}?"],
        "revenue_leakage_brl": [f"Qual o vazamento de receita{s}?", f"Qual a perda de receita{s}?",
                                f"Qual o prejuízo de receita{s}?"],
        "revenue_leakage_cents": [f"Qual o vazamento de receita em centavos{s}?",
                                  f"Qual a perda de receita em centavos{s}?"],
        "suspect_rate": [f"Qual a taxa de suspeita{s}?",
                         f"Qual a proporção de transações suspeitas{s}?",
                         f"Qual o percentual de transações suspeitas{s}?"],
    }[m]
    return rng.choice(op)


def frase_filtro(m, label, suf_dim=""):
    """Pergunta com filtro por valor — estrutura diferente por família de métrica, senão quebra
    a gramática ("Quantas transações houve pagas com cartão?")."""
    d = f" {suf_dim}" if suf_dim else ""
    if m == "transactions":
        return f"Quantas transações {label} houve{d}?"
    if m == "suspect_transactions":
        return f"Quantas transações suspeitas {label} houve{d}?"
    if m == "revenue":
        return rng.choice([f"Qual foi a receita das transações {label}{d}?",
                           f"Qual o faturamento das transações {label}{d}?"])
    if m == "revenue_cents":
        return f"Qual a receita em centavos das transações {label}{d}?"
    if m == "revenue_leakage_brl":
        return rng.choice([f"Qual o vazamento de receita das transações {label}{d}?",
                           f"Qual a perda de receita das transações {label}{d}?"])
    if m == "revenue_leakage_cents":
        return f"Qual o vazamento de receita em centavos das transações {label}{d}?"
    if m == "suspect_rate":
        return f"Qual a taxa de suspeita das transações {label}{d}?"
    raise ValueError(m)


# ------------------------------------------------------------------ candidatos por estrato
def c_ranking():
    out = []
    for m in ["revenue", "transactions", "suspect_transactions", "revenue_cents",
              "revenue_leakage_brl", "suspect_rate"]:
        for d in ENTID + CATEG:
            art = DIM_ARTIGO[d]
            for k in ((3,) if d in CARD_BAIXA else (3, 5)):
                out.append((sp([m], [d], None, [f"-{m}"], k, True),
                            f"Quais {art} {k} {DIM_PLURAL[d]} com maior {MET_NOME[m]}?"))
            out.append((sp([m], [d], None, [m], 3, True),
                        f"Quais {art} 3 {DIM_PLURAL[d]} com menor {MET_NOME[m]}?"))
    return out


def c_valor_categorico():
    out = []
    for dim, vals in VALORES.items():
        for v in vals:
            for m in TODAS:
                out.append((sp([m], (), w(dim, v)), frase_filtro(m, VAL_LABEL[v])))
    return out


def c_coalesce_nulo():
    """Grão diário fino + filtro: muitos grupos ficam sem atividade (o buraco vira 0 ou some)."""
    out = []
    for m in TODAS:
        for dim, vals in VALORES.items():
            for v in vals:
                out.append((sp([m], ["metric_time__day"], w(dim, v), ["metric_time__day"]),
                            frase_filtro(m, VAL_LABEL[v], "em cada dia")))
    return out


def c_join_grao():
    """group_by envolvendo entidade (join) — inclusive pares, onde o fan-out morde."""
    out = []
    pares = [(e, c) for e in ENTID for c in CATEG] + [("transaction__plaza",
                                                       "transaction__vehicle")]
    for m in TODAS:
        for a, b in pares:
            out.append((sp([m], [a, b]),
                        frase(m, f"{rng.choice(DIM_SUF[a])} e {rng.choice(DIM_SUF[b])}")))
    return out


def c_grao_temporal():
    out = []
    for m in TODAS:
        for t in TEMPO:
            out.append((sp([m], [t], None, [t]), frase(m, rng.choice(DIM_SUF[t]))))
            for c in CATEG:
                out.append((sp([m], [t, c], None, [t]),
                            frase(m, f"{rng.choice(DIM_SUF[t])} e {rng.choice(DIM_SUF[c])}")))
    return out


def c_metrica_derivada():
    out = []
    for m in DERIVADAS:
        out.append((sp([m]), frase(m, "no geral")))
        for d in DIMS:
            out.append((sp([m], [d]), frase(m, rng.choice(DIM_SUF[d]))))
        for dim, vals in VALORES.items():
            for v in vals:
                for d in ENTID:
                    out.append((sp([m], [d], w(dim, v)),
                                frase_filtro(m, VAL_LABEL[v], rng.choice(DIM_SUF[d]))))
    return out


def c_metrica_filtrada():
    out = []
    for m in COM_FILTRO_EMBUTIDO:
        out.append((sp([m]), frase(m, "no total")))
        for d in DIMS:
            out.append((sp([m], [d]), frase(m, rng.choice(DIM_SUF[d]))))
    return out


def c_controle_trivial():
    """CAP ESTRUTURAL, declarado: 'trivial' = contagem simples de uma métrica SEM filtro embutido.
    No catálogo só `transactions` é assim (revenue filtra COMPLETED, suspect_* filtra flag,
    suspect_rate é razão). Logo o espaço inteiro é `transactions` × {sem dim, 8 dims} = 9 specs —
    e a v1 já usou 7. Este estrato NÃO escala para 25 e não deve: é um controle de sanidade
    (ambos os sistemas têm de acertar), não um estrato de hipótese. Inflá-lo exigiria torná-lo
    não-trivial, o que destruiria a função dele."""
    out = [(sp(["transactions"]), frase("transactions", "no total"))]
    for d in DIMS:
        out.append((sp(["transactions"], [d]), frase("transactions", rng.choice(DIM_SUF[d]))))
    return out


# Ordem = do espaço mais ESTREITO para o mais amplo. O dedupe é global (uma spec nunca aparece em
# dois estratos), então quem escolhe por último fica com as sobras: se um estrato de espaço pequeno
# vier depois de um grande, ele passa fome. `controle_trivial` é o caso extremo — ver nota abaixo.
PLANO = [
    ("controle_trivial", c_controle_trivial),
    ("metrica_filtrada", c_metrica_filtrada),
    ("ranking", c_ranking),
    ("metrica_derivada", c_metrica_derivada),
    ("join_grao", c_join_grao),
    ("grao_temporal", c_grao_temporal),
    ("valor_categorico", c_valor_categorico),
    ("coalesce_nulo", c_coalesce_nulo),
]

# ---- abstenções v2: NEAR-MISS de propósito -----------------------------------------------------
# A v1 era fácil demais (lucro, CPF, clima). Uma abstenção só tem valor se for *quase* respondível:
# agregações que não existem (média/mediana/máximo/distinto), grãos inexistentes (hora), dimensões
# ausentes (UF, concessionária) e taxas que soam como `suspect_rate` mas não são.
ABSTENCOES_V2 = [
    "Qual o ticket médio por transação?",
    "Qual o valor médio arrecadado por praça?",
    "Qual a mediana da receita diária?",
    "Qual o maior valor de transação individual?",
    "Quantas transações únicas houve?",
    "Quantos veículos distintos passaram pelas praças?",
    "Qual a receita acumulada até hoje?",
    "Qual o crescimento da receita em relação ao mês anterior?",
    "Qual a variação percentual do faturamento entre semanas?",
    "Quantas transações houve por hora do dia?",
    "Qual a receita por UF?",
    "Qual a receita por concessionária?",
    "Qual a receita por faixa de valor da tarifa?",
    "Qual a taxa de estorno das transações?",
    "Qual a taxa de conversão das cobranças?",
    "Qual o desvio padrão da receita entre praças?",
    "Qual a receita líquida depois dos impostos?",
    "Qual a inadimplência dos usuários de tag?",
    "Quanto cada praça gasta com manutenção por mês?",
    "Qual o ROI de cada praça de pedágio?",
    "Qual o percentual de transações acima da média de valor?",
    "Qual a sazonalidade da receita ao longo do ano?",
    "Qual o nome do operador responsável pela praça P001?",
    "Qual o endereço das praças de pedágio?",
    "Quantos usuários estão cadastrados no sistema de tag?",
    "Qual o tempo médio entre duas passagens do mesmo veículo?",
    "Qual a receita comparada com a da concorrência?",
    "Qual foi a primeira transação registrada no sistema?",
    "Qual a capacidade máxima de veículos por hora em cada praça?",
    "Qual o índice de reclamações por praça?",
    "Qual a margem de contribuição por método de pagamento?",
    "Quantos quilômetros de rodovia cada praça atende?",
]

# ------------------------------------------------------------------ montagem
v1 = [json.loads(x) for x in (G / "golden_full.jsonl").read_text(encoding="utf-8").splitlines()
      if x.strip()]
usados = {sig(it["spec"]) for it in v1 if it["estrato"] != "abstencao"}
perguntas_v1 = {it["pergunta_nl"].strip().lower() for it in v1}
n_v1 = len(usados)

itens = []
for estrato, fn in PLANO:
    cands = fn()
    rng.shuffle(cands)
    n = 0
    for spec, perg in cands:
        if n >= ALVO:
            break
        s = sig(spec)
        if s in usados or perg.strip().lower() in perguntas_v1:
            continue
        usados.add(s)
        perguntas_v1.add(perg.strip().lower())
        n += 1
        itens.append({"id": f"{estrato}_v2_{n:02d}", "pergunta_nl": perg, "estrato": estrato,
                      "spec": spec, "revisado_humano": False})
    if n < ALVO:
        print(f"AVISO: {estrato} só conseguiu {n}/{ALVO} specs inéditas")

vazia = sp([])
for i, p in enumerate(ABSTENCOES_V2[:ALVO], 1):
    assert p.strip().lower() not in perguntas_v1, f"abstenção duplicada da v1: {p}"
    itens.append({"id": f"abstencao_v2_{i:02d}", "pergunta_nl": p, "estrato": "abstencao",
                  "spec": dict(vazia), "revisado_humano": False})

dest = G / "autor_v2.jsonl"
dest.write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in itens),
                encoding="utf-8")

import collections  # noqa: E402

c = collections.Counter(it["estrato"] for it in itens)
print(f"v2: {len(itens)} itens novos  {dict(sorted(c.items()))}")
print(f"specs ineditas garantidas: {len(usados) - n_v1} novas assinaturas (v1 tinha {n_v1})")
print(f"-> {dest}")
