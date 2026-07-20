"""Gera o golden set do AUTOR (modelo) — estratificado, reprodutível (seed fixa).

HONESTIDADE: este golden set é **autorado por modelo**, não por humano. A circularidade que
importa (autor escrever o SQL-gold) NÃO existe aqui — o gold sai do MetricFlow. A concordância
inter-anotador é medida contra um 2º anotador-LLM independente (κ de MÁQUINA, não humano). O κ
humano fica como backlog declarado. Ver docs/GUIA_GOLDEN.md.

Roda: `python golden/gerar_autor.py > golden/autor.jsonl`
"""
import json
import random

random.seed(42)

DIM = {
    "metric_time__day": "por dia", "metric_time__week": "por semana",
    "metric_time__month": "por mês", "transaction__status": "por status",
    "transaction__payment_method": "por método de pagamento",
    "transaction__plaza": "por praça", "transaction__vehicle": "por veículo",
}
CAT = {
    "transaction__status": ["COMPLETED", "FAILED", "REVERSED"],
    "transaction__payment_method": ["AUTOMATIC_TAG", "CARD", "CASH"],
    "transaction__audit_flag": ["OK", "COBRANCA_EM_FALHA", "TARIFA_DIVERGENTE"],
}
CAT_LABEL = {
    "COMPLETED": "concluídas", "FAILED": "que falharam", "REVERSED": "estornadas",
    "AUTOMATIC_TAG": "pagas com tag automática", "CARD": "pagas com cartão",
    "CASH": "pagas em dinheiro", "COBRANCA_EM_FALHA": "com cobrança em falha",
    "TARIFA_DIVERGENTE": "com tarifa divergente", "OK": "sem apontamento de auditoria",
}


def pergunta(m: str, sufixo: str = "") -> str:
    """Frase gramatical por tipo de métrica."""
    s = f" {sufixo}" if sufixo else ""
    if m == "transactions":
        return f"Quantas transações houve{s}?"
    if m == "suspect_transactions":
        return f"Quantas transações suspeitas houve{s}?"
    if m == "revenue":
        return f"Qual foi {random.choice(['a receita', 'o faturamento'])}{s}?"
    if m == "suspect_rate":
        alt = random.choice(["a taxa de suspeita", "a proporção de transações suspeitas"])
        return f"Qual {alt}{s}?"
    if m == "revenue_leakage_brl":
        return f"Qual {random.choice(['o vazamento de receita', 'a perda de receita'])}{s}?"
    raise ValueError(m)


itens: list[dict] = []


def add(estrato, pergunta_nl, metrics, group_by=(), where=None, order_by=()):
    n = sum(1 for i in itens if i["estrato"] == estrato) + 1
    itens.append({
        "id": f"{estrato}_{n:02d}", "pergunta_nl": pergunta_nl, "estrato": estrato,
        "spec": {"metrics": list(metrics), "group_by": list(group_by), "where": where,
                 "order_by": list(order_by), "limit": None, "ordenado": False},
        "revisado_humano": False,
    })


# 1) metrica_filtrada — métricas que embutem filtro (revenue só COMPLETED; suspect filtra flag)
for m in ["revenue", "suspect_transactions", "revenue_leakage_brl"]:
    add("metrica_filtrada", pergunta(m, "no total"), [m])
    for d in ["transaction__plaza", "transaction__payment_method", "transaction__status"]:
        add("metrica_filtrada", pergunta(m, DIM[d]), [m], [d])

# 2) metrica_derivada — ratio/derivada
for m in ["suspect_rate", "revenue_leakage_brl"]:
    add("metrica_derivada", pergunta(m, "no geral"), [m])
    for d in ["transaction__payment_method", "transaction__plaza", "metric_time__month",
              "transaction__status"]:
        add("metrica_derivada", pergunta(m, DIM[d]), [m], [d])

# 3) grao_temporal — truncamento de data
for m in ["revenue", "transactions", "suspect_rate"]:
    for d in ["metric_time__day", "metric_time__week", "metric_time__month"]:
        add("grao_temporal", pergunta(m, DIM[d]), [m], [d], order_by=[d])

# 4) coalesce_nulo — grupos sem atividade viram 0 (grão diário fino)
for m in ["revenue", "suspect_transactions", "revenue_leakage_brl", "transactions",
          "suspect_rate", "revenue"]:
    add("coalesce_nulo", pergunta(m, "em cada dia do período"), [m],
        ["metric_time__day"], order_by=["metric_time__day"])

# 5) join_grao — join de dimensão / fan-out
for m in ["revenue", "transactions", "suspect_transactions"]:
    add("join_grao", pergunta(m, "por praça de pedágio"), [m], ["transaction__plaza"])
    add("join_grao", pergunta(m, "por praça e por status"), [m],
        ["transaction__plaza", "transaction__status"])
for m in ["revenue", "transactions"]:
    add("join_grao", pergunta(m, "por veículo"), [m], ["transaction__vehicle"])

# 6) valor_categorico — filtro por valor exato de dimensão
for dim, vals in CAT.items():
    m = "transactions" if dim == "transaction__audit_flag" else "revenue"
    for v in vals:
        base = ("Quantas transações {c} houve?" if m == "transactions"
                else "Qual foi a receita das transações {c}?")
        add("valor_categorico", base.format(c=CAT_LABEL[v]), [m],
            where=f"{{{{ Dimension('{dim}') }}}} = '{v}'")

# 7) controle_trivial — count simples (ambos os sistemas devem acertar)
add("controle_trivial", "Quantas transações há no total?", ["transactions"])
add("controle_trivial", "Qual o total de transações suspeitas?", ["suspect_transactions"])
for d in ["transaction__status", "transaction__payment_method", "transaction__plaza",
          "metric_time__month", "transaction__vehicle"]:
    add("controle_trivial", pergunta("transactions", DIM[d]), ["transactions"], [d])

for it in itens:
    print(json.dumps(it, ensure_ascii=False))
