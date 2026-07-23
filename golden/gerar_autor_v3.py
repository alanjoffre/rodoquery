"""Golden v3 (Fase 9) — holdout NOVO para medir o conserto do prompt sem ajustar ao teste.

Por que existe: o TEST-v2 foi inspecionado item a item na Fase 8 (foi assim que os 3 modos de falha
foram diagnosticados). Medir o conserto nele seria ajustar ao teste. O v3 é gerado **depois** que o
texto do prompt já estava fechado, e é 100% holdout — não tem split de DEV, porque não há mais
desenvolvimento a fazer.

**Toda spec é inédita contra v1 E v2** (verificado por assinatura canônica). Como os estratos mais
estreitos já estavam quase esgotados, o espaço foi ampliado com combinações legítimas que nem v1
nem v2 usavam: pares e trios de dimensões, filtro combinado com agrupamento não-temporal, e
ranking com filtro.

**Consequência declarada:** o v3 NÃO tem a mesma dificuldade do v2 — tem mais itens
multidimensionais. Por isso o EX absoluto do v3 não é comparável ao do v2. O que vale é a
comparação **pareada** (prompt antigo × novo nos MESMOS itens), onde a dificuldade se cancela.
"""
import collections
import json
import random
from pathlib import Path

G = Path(__file__).resolve().parent
ALVO = 30
rng = random.Random(90909)

TEMPO = ["metric_time__day", "metric_time__week", "metric_time__month"]
CATEG = ["transaction__status", "transaction__payment_method", "transaction__audit_flag"]
ENTID = ["transaction__plaza", "transaction__vehicle"]
DIMS = TEMPO + CATEG + ENTID
TODAS = ["transactions", "suspect_transactions", "revenue", "revenue_cents",
         "revenue_leakage_brl", "revenue_leakage_cents", "suspect_rate"]
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
    "metric_time__day": ["por dia", "em cada dia"],
    "metric_time__week": ["por semana", "semana a semana"],
    "metric_time__month": ["por mês", "em cada mês"],
    "transaction__status": ["por status", "por situação"],
    "transaction__payment_method": ["por método de pagamento", "por forma de pagamento"],
    "transaction__audit_flag": ["por marcação de auditoria", "por flag de auditoria"],
    "transaction__plaza": ["por praça", "em cada praça"],
    "transaction__vehicle": ["por veículo", "em cada veículo"],
}
DIM_PLURAL = {"transaction__plaza": "praças", "transaction__vehicle": "veículos",
              "transaction__status": "situações",
              "transaction__payment_method": "métodos de pagamento",
              "transaction__audit_flag": "marcações de auditoria"}
DIM_ARTIGO = {"transaction__plaza": "as", "transaction__vehicle": "os",
              "transaction__status": "as", "transaction__payment_method": "os",
              "transaction__audit_flag": "as"}
MET_NOME = {"transactions": "número de transações",
            "suspect_transactions": "número de transações suspeitas",
            "revenue": "receita", "revenue_cents": "receita em centavos",
            "revenue_leakage_brl": "vazamento de receita",
            "revenue_leakage_cents": "vazamento de receita em centavos",
            "suspect_rate": "taxa de suspeita"}


def sp(metrics, group_by=(), where=None, order_by=(), limit=None, ordenado=False):
    return {"metrics": list(metrics), "group_by": list(group_by), "where": where,
            "order_by": list(order_by), "limit": limit, "ordenado": ordenado}


def w(dim, val):
    return f"{{{{ Dimension('{dim}') }}}} = '{val}'"


def sig(s):
    return (tuple(s["metrics"]), tuple(s["group_by"]), s["where"], tuple(s["order_by"]),
            s["limit"], bool(s["ordenado"]))


def frase(m, suf=""):
    s = f" {suf}" if suf else ""
    op = {
        "transactions": [f"Quantas transações houve{s}?", f"Qual o número de transações{s}?"],
        "suspect_transactions": [f"Quantas transações suspeitas houve{s}?",
                                 f"Qual o número de transações suspeitas{s}?"],
        "revenue": [f"Qual foi a receita{s}?", f"Qual o faturamento{s}?"],
        "revenue_cents": [f"Qual a receita em centavos{s}?",
                          f"Qual o faturamento em centavos{s}?"],
        "revenue_leakage_brl": [f"Qual o vazamento de receita{s}?", f"Qual a perda de receita{s}?"],
        "revenue_leakage_cents": [f"Qual o vazamento de receita em centavos{s}?",
                                  f"Qual a perda de receita em centavos{s}?"],
        "suspect_rate": [f"Qual a taxa de suspeita{s}?",
                         f"Qual a proporção de transações suspeitas{s}?"],
    }[m]
    return rng.choice(op)


def frase_filtro(m, label, suf_dim=""):
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


def sufixo_dims(ds):
    return " e ".join(rng.choice(DIM_SUF[d]) for d in ds)


# ---------------------------------------------------------------- candidatos
def c_controle_trivial():
    out = [(sp(["transactions"]), frase("transactions", "no total"))]
    for d in DIMS:
        out.append((sp(["transactions"], [d]), frase("transactions", rng.choice(DIM_SUF[d]))))
    return out


def c_metrica_filtrada():
    out = []
    for m in COM_FILTRO_EMBUTIDO:
        out.append((sp([m]), frase(m, "no total")))
        for d in DIMS:
            out.append((sp([m], [d]), frase(m, rng.choice(DIM_SUF[d]))))
        for a in CATEG:                       # pares: espaço novo, v1/v2 não usaram aqui
            for b in TEMPO:
                out.append((sp([m], [a, b]), frase(m, sufixo_dims([a, b]))))
    return out


def c_ranking():
    out = []
    for m in TODAS:
        for d in ENTID + CATEG:
            art = DIM_ARTIGO[d]
            ks = (3,) if d in CATEG else (3, 5, 10)
            for k in ks:
                out.append((sp([m], [d], None, [f"-{m}"], k, True),
                            f"Quais {art} {k} {DIM_PLURAL[d]} com maior {MET_NOME[m]}?"))
                out.append((sp([m], [d], None, [m], k, True),
                            f"Quais {art} {k} {DIM_PLURAL[d]} com menor {MET_NOME[m]}?"))
            for dim, vals in VALORES.items():  # ranking COM filtro — espaço novo
                for v in vals:
                    out.append((sp([m], [d], w(dim, v), [f"-{m}"], 3, True),
                                f"Entre as transações {VAL_LABEL[v]}, quais {art} 3 "
                                f"{DIM_PLURAL[d]} com maior {MET_NOME[m]}?"))
    return out


def c_metrica_derivada():
    out = []
    for m in DERIVADAS:
        for d in DIMS:
            out.append((sp([m], [d]), frase(m, rng.choice(DIM_SUF[d]))))
        for dim, vals in VALORES.items():
            for v in vals:
                for d in DIMS:
                    out.append((sp([m], [d], w(dim, v)),
                                frase_filtro(m, VAL_LABEL[v], rng.choice(DIM_SUF[d]))))
    return out


def c_join_grao():
    out = []
    for m in TODAS:
        for e in ENTID:
            for c in CATEG:
                for t in TEMPO:                # trios com entidade — espaço novo
                    out.append((sp([m], [e, c, t]), frase(m, sufixo_dims([e, c, t]))))
            out.append((sp([m], [e, "transaction__plaza"] if e != "transaction__plaza"
                           else [e, "transaction__vehicle"]),
                        frase(m, sufixo_dims(ENTID))))
    return out


def c_grao_temporal():
    out = []
    for m in TODAS:
        for t in TEMPO:
            for d in CATEG + ENTID:
                out.append((sp([m], [t, d], None, [t]), frase(m, sufixo_dims([t, d]))))
            for dim, vals in VALORES.items():
                for v in vals:
                    out.append((sp([m], [t], w(dim, v), [t]),
                                frase_filtro(m, VAL_LABEL[v], rng.choice(DIM_SUF[t]))))
    return out


def c_valor_categorico():
    out = []
    for dim, vals in VALORES.items():
        for v in vals:
            for m in TODAS:
                out.append((sp([m], (), w(dim, v)), frase_filtro(m, VAL_LABEL[v])))
                for d in CATEG + ENTID:        # filtro + agrupamento não-temporal
                    if d == dim:
                        continue
                    out.append((sp([m], [d], w(dim, v)),
                                frase_filtro(m, VAL_LABEL[v], rng.choice(DIM_SUF[d]))))
    return out


def c_coalesce_nulo():
    out = []
    for m in TODAS:
        for dim, vals in VALORES.items():
            for v in vals:
                out.append((sp([m], ["metric_time__day"], w(dim, v), ["metric_time__day"]),
                            frase_filtro(m, VAL_LABEL[v], "em cada dia")))
                for d in ENTID:
                    out.append((sp([m], ["metric_time__day", d], w(dim, v),
                                   ["metric_time__day"]),
                                frase_filtro(m, VAL_LABEL[v],
                                             f"em cada dia e {rng.choice(DIM_SUF[d])}")))
    return out


PLANO = [("controle_trivial", c_controle_trivial), ("metrica_filtrada", c_metrica_filtrada),
         ("ranking", c_ranking), ("metrica_derivada", c_metrica_derivada),
         ("join_grao", c_join_grao), ("grao_temporal", c_grao_temporal),
         ("valor_categorico", c_valor_categorico), ("coalesce_nulo", c_coalesce_nulo)]

# Abstenções v3: near-miss NOVAS (nenhuma repete v1 nem v2), mesma lógica — operadores que não
# existem, dimensões ausentes e métricas de nome vizinho.
ABSTENCOES_V3 = [
    "Qual a receita média por praça de pedágio?",
    "Qual o valor da maior transação já registrada?",
    "Quantos veículos diferentes usaram tag automática?",
    "Qual a receita por dia da semana?",
    "Qual a receita por trimestre?",
    "Qual a receita por turno (manhã, tarde, noite)?",
    "Qual a receita por rodovia?",
    "Qual a receita por município?",
    "Qual a receita por categoria tarifária?",
    "Qual a proporção da receita que cada praça representa no total?",
    "Quanto a receita cresceu em relação ao ano passado?",
    "Qual a média móvel de transações dos últimos 7 dias?",
    "Qual o total acumulado de transações no ano?",
    "Qual a taxa de abandono das cabines?",
    "Qual a taxa de erro de leitura das antenas?",
    "Qual o índice de evasão de pedágio?",
    "Qual a taxa de ocupação das cabines por hora?",
    "Qual o custo de cobrança por transação?",
    "Qual o lucro operacional de cada praça?",
    "Qual a projeção de receita para o próximo semestre?",
    "Quais praças estão acima da meta de arrecadação?",
    "Qual o tempo de permanência médio dos veículos na praça?",
    "Qual a distância média percorrida por veículo?",
    "Quantos funcionários há por turno em cada praça?",
    "Qual o modelo dos veículos que mais passaram?",
    "Qual a cor predominante dos veículos autuados?",
    "Qual o telefone de contato da praça P003?",
    "Quantas multas foram aplicadas no período?",
    "Qual a idade da infraestrutura de cada praça?",
    "Qual o consumo de energia das praças por mês?",
]

# ---------------------------------------------------------------- montagem
usados, perguntas = set(), set()
for arq in ("golden_full.jsonl", "golden_v2.jsonl"):
    for linha in (G / arq).read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        d = json.loads(linha)
        perguntas.add(d["pergunta_nl"].strip().lower())
        if d["estrato"] != "abstencao":
            usados.add(sig(d["spec"]))
n_antes = len(usados)

itens = []
for estrato, fn in PLANO:
    cands = fn()
    rng.shuffle(cands)
    n = 0
    for spec, perg in cands:
        if n >= ALVO:
            break
        s = sig(spec)
        if s in usados or perg.strip().lower() in perguntas:
            continue
        usados.add(s)
        perguntas.add(perg.strip().lower())
        n += 1
        itens.append({"id": f"{estrato}_v3_{n:02d}", "pergunta_nl": perg, "estrato": estrato,
                      "spec": spec, "revisado_humano": False})
    if n < ALVO:
        print(f"AVISO: {estrato} so conseguiu {n}/{ALVO} specs ineditas")

for i, p in enumerate(ABSTENCOES_V3[:ALVO], 1):
    assert p.strip().lower() not in perguntas, f"abstencao duplicada: {p}"
    itens.append({"id": f"abstencao_v3_{i:02d}", "pergunta_nl": p, "estrato": "abstencao",
                  "spec": sp([]), "revisado_humano": False})

dest = G / "autor_v3.jsonl"
dest.write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in itens),
                encoding="utf-8")
c = collections.Counter(it["estrato"] for it in itens)
print(f"v3: {len(itens)} itens  {dict(sorted(c.items()))}")
print(f"specs ineditas: {len(usados) - n_antes} novas (v1+v2 ja usavam {n_antes})")
print(f"-> {dest}")
