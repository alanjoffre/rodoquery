"""Golden set sobre a base REAL da ANTT (Fase 12).

Nasce com as guardas que as fases anteriores custaram caro para descobrir — aqui elas são
CONDIÇÃO DE GERAÇÃO, não filtro de limpeza depois:

  G1 (Fase 8) — filtro que conflita com a definição da métrica gera gold degenerado.
     `automation_rate` filtrada por tipo_cobranca dá sempre 1,0 ou 0,0; `commercial_share`
     filtrada por tipo_de_veiculo, idem. Esses pares nunca são gerados.

  G2 (Fase 9) — filtrar por uma dimensão E agrupar por ela é AMBÍGUO: duas leituras se
     defendem, e a discordância mediria convenção, não capacidade. Nunca gerado.

  G3 (Fase 10) — o catálogo tem UMA métrica por conceito e nenhuma contagem filtrada como
     métrica. Por isso o estrato `metrica_filtrada` **não existe** aqui: ele media um problema
     que este catálogo não tem.

HONESTIDADE: itens autorados por modelo, como nas versões anteriores. κ de MÁQUINA com 2º
anotador cego; κ humano segue no backlog (a base da ANTT não vem com benchmark humano — foi a
falha não-bloqueante registrada na Fase 0 de Dados).

Roda: python golden/gerar_autor_antt.py  → golden/autor_antt.jsonl
"""
import collections
import json
import random
from pathlib import Path

G = Path(__file__).resolve().parent
ALVO = 30
rng = random.Random(2026)

TEMPO = ["metric_time__day", "metric_time__week", "metric_time__month"]
ENTID = ["plaza__praca", "plaza__concessionaria"]
CATEG = ["plaza__sentido", "plaza__tipo_cobranca", "plaza__categoria_eixo",
         "plaza__tipo_de_veiculo"]
DIMS = TEMPO + ENTID + CATEG
METRICAS = ["traffic_volume", "automation_rate", "commercial_share"]

VALORES = {
    "plaza__tipo_cobranca": ["Automática", "Manual", "OCR/PLACA"],
    "plaza__tipo_de_veiculo": ["Comercial", "Passeio", "Moto"],
    "plaza__sentido": ["Crescente", "Decrescente"],
    "plaza__categoria_eixo": ["2", "3", "4", "5", "6", "7", "8", "9"],
}
# G1: métrica → dimensões cujo filtro a torna degenerada.
# Inclui a dimensão que a métrica usa DIRETAMENTE e as CORRELACIONADAS (achado da auditoria
# adversarial da Fase 15): filtrar `commercial_share` por `categoria_eixo` alto prende a métrica em
# 1,0, porque todo veículo de 5+ eixos é comercial — degeneração por correlação, não por definição.
CONFLITO = {"automation_rate": {"plaza__tipo_cobranca"},
            "commercial_share": {"plaza__tipo_de_veiculo", "plaza__categoria_eixo"}}
# G4 (Fase 14): cardinalidade das dimensões de baixa contagem. Ranking com limit > cardinalidade
# é degenerado — "as 3 praças" tem sentido, "os 3 sentidos" (só há 2) não. Entidades de alta
# cardinalidade (praça=241, concessionária=30) não entram aqui: qualquer limit realista cabe.
CARDINALIDADE = {"plaza__sentido": 2, "plaza__tipo_cobranca": 3, "plaza__tipo_de_veiculo": 3}

VAL_LABEL = {
    "Automática": "com cobrança automática", "Manual": "com cobrança manual",
    "OCR/PLACA": "com leitura de placa", "Comercial": "comerciais",
    "Passeio": "de passeio", "Moto": "do tipo moto",
    "Crescente": "no sentido crescente", "Decrescente": "no sentido decrescente",
    **{str(n): f"de {n} eixos" for n in range(2, 21)},
}
DIM_SUF = {
    "metric_time__day": ["por dia", "em cada dia"],
    "metric_time__week": ["por semana", "semana a semana"],
    "metric_time__month": ["por mês", "em cada mês"],
    "plaza__praca": ["por praça", "em cada praça", "por praça de pedágio"],
    "plaza__concessionaria": ["por concessionária", "em cada concessionária"],
    "plaza__sentido": ["por sentido"],
    "plaza__tipo_cobranca": ["por tipo de cobrança", "por forma de cobrança"],
    "plaza__categoria_eixo": ["por categoria de eixo", "por número de eixos"],
    # "classe de veículo" saiu (auditoria da Fase 15): no jargão de pedágio "classe" designa a
    # categoria tarifária por EIXOS, então o termo é ambíguo entre duas dimensões do catálogo.
    "plaza__tipo_de_veiculo": ["por tipo de veículo"],
}
DIM_PLURAL = {"plaza__praca": "praças", "plaza__concessionaria": "concessionárias",
              "plaza__sentido": "sentidos", "plaza__tipo_cobranca": "formas de cobrança",
              "plaza__categoria_eixo": "categorias de eixo",
              "plaza__tipo_de_veiculo": "tipos de veículo"}
DIM_ARTIGO = {"plaza__praca": "as", "plaza__concessionaria": "as", "plaza__sentido": "os",
              "plaza__tipo_cobranca": "as", "plaza__categoria_eixo": "as",
              "plaza__tipo_de_veiculo": "os"}
MET_NOME = {"traffic_volume": "volume de tráfego",
            "automation_rate": "taxa de automação",
            "commercial_share": "participação de veículos comerciais"}


def sp(metrics, group_by=(), where=None, order_by=(), limit=None, ordenado=False):
    return {"metrics": list(metrics), "group_by": list(group_by), "where": where,
            "order_by": list(order_by), "limit": limit, "ordenado": ordenado}


def w(dim, val):
    return f"{{{{ Dimension('{dim}') }}}} = '{val}'"


def sig(s):
    return (tuple(s["metrics"]), tuple(s["group_by"]), s["where"], tuple(s["order_by"]),
            s["limit"], bool(s["ordenado"]))


def permitido(metrics, group_by, dim_filtrada=None) -> bool:
    """G1 + G2 aplicadas na geração.

    G1 vale para os DOIS lados, não só para o `where`: `commercial_share` AGRUPADA por
    tipo_de_veiculo devolve 1,0 no grupo Comercial e 0,0 nos demais — constante, não importa o
    dado. Filtrar ou agrupar pela dimensão que a própria métrica já usa produz gold degenerado.
    """
    for m in metrics:
        conflitos = CONFLITO.get(m)
        if not conflitos:
            continue
        if dim_filtrada in conflitos:
            return False
        # a dimensão que define a métrica não pode ser agrupada (constante por grupo); as
        # CORRELACIONADAS só são proibidas no filtro — agrupar por elas ainda carrega sinal.
        if m == "automation_rate" and "plaza__tipo_cobranca" in group_by:
            return False
        if m == "commercial_share" and "plaza__tipo_de_veiculo" in group_by:
            return False
    if dim_filtrada and dim_filtrada in group_by:    # G2: filtra e agrupa pela mesma dimensão
        return False
    return True


def frase(m, suf=""):
    s = f" {suf}" if suf else ""
    op = {
        "traffic_volume": [f"Quantos veículos passaram{s}?", f"Qual o volume de tráfego{s}?",
                           f"Qual o número de veículos{s}?"],
        "automation_rate": [f"Qual a taxa de automação{s}?",
                            f"Qual a proporção do tráfego cobrado automaticamente{s}?"],
        "commercial_share": [f"Qual a participação de veículos comerciais{s}?",
                             f"Qual a proporção de veículos comerciais{s}?"],
    }[m]
    return rng.choice(op)


def frase_filtro(m, label, suf_dim=""):
    d = f" {suf_dim}" if suf_dim else ""
    if m == "traffic_volume":
        return rng.choice([f"Quantos veículos {label} passaram{d}?",
                           f"Qual o volume de tráfego dos veículos {label}{d}?"])
    if m == "automation_rate":
        return f"Qual a taxa de automação dos veículos {label}{d}?"
    if m == "commercial_share":
        return f"Qual a participação de veículos comerciais entre os veículos {label}{d}?"
    raise ValueError(m)


# ------------------------------------------------------------------ candidatos por estrato
def c_controle_trivial():
    out = [(sp(["traffic_volume"]), frase("traffic_volume", "no total"))]
    for d in DIMS:
        out.append((sp(["traffic_volume"], [d]), frase("traffic_volume", rng.choice(DIM_SUF[d]))))
    return out


def c_grao_temporal():
    out = []
    for m in METRICAS:
        for t in TEMPO:
            out.append((sp([m], [t], None, [t]), frase(m, rng.choice(DIM_SUF[t]))))
            for d in ENTID + CATEG:
                if not permitido([m], [t, d]):      # G1 também sobre group_by
                    continue
                out.append((sp([m], [t, d], None, [t]),
                            frase(m, f"{rng.choice(DIM_SUF[t])} e {rng.choice(DIM_SUF[d])}")))
    return out


def c_join_grao():
    out = []
    pares = [(e, c) for e in ENTID for c in CATEG] + [tuple(ENTID)]
    for m in METRICAS:
        for a, b in pares:
            if not permitido([m], [a, b]):
                continue
            out.append((sp([m], [a, b]),
                        frase(m, f"{rng.choice(DIM_SUF[a])} e {rng.choice(DIM_SUF[b])}")))
        for e in ENTID:                                   # trios com tempo
            for c in CATEG:
                for t in TEMPO:
                    if not permitido([m], [e, c, t]):
                        continue
                    out.append((sp([m], [e, c, t], None, [t]),
                                frase(m, f"{rng.choice(DIM_SUF[e])}, {rng.choice(DIM_SUF[c])} "
                                         f"e {rng.choice(DIM_SUF[t])}")))
    return out


def c_valor_categorico():
    out = []
    for dim, vals in VALORES.items():
        for v in vals:
            for m in METRICAS:
                if not permitido([m], [], dim):
                    continue
                out.append((sp([m], (), w(dim, v)), frase_filtro(m, VAL_LABEL[v])))
                for d in ENTID + CATEG:
                    if not permitido([m], [d], dim):
                        continue
                    out.append((sp([m], [d], w(dim, v)),
                                frase_filtro(m, VAL_LABEL[v], rng.choice(DIM_SUF[d]))))
    return out


def c_coalesce_nulo():
    """Grão diário fino + filtro: muitos grupos ficam sem atividade."""
    out = []
    for m in METRICAS:
        for dim, vals in VALORES.items():
            for v in vals:
                if not permitido([m], ["metric_time__day"], dim):
                    continue
                out.append((sp([m], ["metric_time__day"], w(dim, v), ["metric_time__day"]),
                            frase_filtro(m, VAL_LABEL[v], "em cada dia")))
                for e in ENTID:
                    out.append((sp([m], ["metric_time__day", e], w(dim, v),
                                   ["metric_time__day"]),
                                frase_filtro(m, VAL_LABEL[v],
                                             f"em cada dia e {rng.choice(DIM_SUF[e])}")))
    return out


def c_metrica_derivada():
    """As duas razões — o que NÃO dá para expressar com um `where`."""
    out = []
    for m in ("automation_rate", "commercial_share"):
        out.append((sp([m]), frase(m, "no geral")))
        for d in DIMS:
            if not permitido([m], [d]):
                continue
            out.append((sp([m], [d]), frase(m, rng.choice(DIM_SUF[d]))))
        for dim, vals in VALORES.items():
            for v in vals:
                for d in ENTID:
                    if not permitido([m], [d], dim):
                        continue
                    out.append((sp([m], [d], w(dim, v)),
                                frase_filtro(m, VAL_LABEL[v], rng.choice(DIM_SUF[d]))))
    par = ["automation_rate", "commercial_share"]
    out.append((sp(par), "Qual a taxa de automação e a participação de veículos comerciais?"))
    for d in ENTID + CATEG:
        if not permitido(par, [d]):   # o par herda o conflito das DUAS métricas
            continue
        out.append((sp(par, [d]),
                    f"Qual a taxa de automação e a participação de veículos comerciais "
                    f"{rng.choice(DIM_SUF[d])}?"))
    return out


def c_ranking():
    out = []
    for m in METRICAS:
        for d in ENTID + CATEG:
            if not permitido([m], [d]):
                continue
            art, plu = DIM_ARTIGO[d], DIM_PLURAL[d]
            # G4: só rankeia com limit <= cardinalidade da dimensão (senão o corte é degenerado).
            card = CARDINALIDADE.get(d)
            ks = [k for k in ((3, 5, 10) if d in ENTID else (3,)) if card is None or k < card]
            for k in ks:
                out.append((sp([m], [d], None, [f"-{m}"], k, True),
                            f"Quais {art} {k} {plu} com maior {MET_NOME[m]}?"))
                out.append((sp([m], [d], None, [m], k, True),
                            f"Quais {art} {k} {plu} com menor {MET_NOME[m]}?"))
            if card is not None and card <= 3:   # G4: nem o top-3 com filtro cabe aqui
                continue
            for dim, vals in VALORES.items():
                for v in vals:
                    if not permitido([m], [d], dim):
                        continue
                    out.append((sp([m], [d], w(dim, v), [f"-{m}"], 3, True),
                                f"Entre os veículos {VAL_LABEL[v]}, quais {art} 3 {plu} "
                                f"com maior {MET_NOME[m]}?"))
    return out


# ordem: do espaço mais estreito para o mais amplo (o dedupe é global; quem escolhe por último
# fica com as sobras)
PLANO = [("controle_trivial", c_controle_trivial), ("metrica_derivada", c_metrica_derivada),
         ("grao_temporal", c_grao_temporal), ("ranking", c_ranking),
         ("join_grao", c_join_grao), ("coalesce_nulo", c_coalesce_nulo),
         ("valor_categorico", c_valor_categorico)]

# Abstenções NEAR-MISS: o que a base agregada da ANTT NÃO tem. Soam plausíveis de propósito —
# é onde a Fase 8 mostrou que o modelo troca a métrica por um vizinho.
ABSTENCOES = [
    "Qual foi a receita de pedágio arrecadada?",
    "Qual o faturamento por concessionária?",
    "Quanto cada praça arrecadou no mês?",
    "Qual o valor da tarifa em cada praça?",
    "Qual o volume médio de veículos por praça?",
    "Qual a mediana do tráfego diário?",
    "Qual o dia de maior movimento?",
    "Quantos veículos distintos passaram no período?",
    "Quantas placas diferentes foram registradas?",
    "Qual o volume acumulado no ano?",
    "Quanto o tráfego cresceu em relação ao mês anterior?",
    "Qual a variação percentual do volume entre semanas?",
    "Quantos veículos passaram por hora do dia?",
    "Qual o volume por turno (manhã, tarde, noite)?",
    "Qual o tráfego por dia da semana?",
    "Qual o volume por trimestre?",
    "Qual o volume de tráfego por UF?",
    "Qual o tráfego por município?",
    "Qual o volume por rodovia?",
    "Quantos quilômetros tem cada trecho concedido?",
    "Qual o custo operacional de cada praça?",
    "Qual o lucro das concessionárias?",
    "Quantas multas foram aplicadas?",
    "Qual o índice de evasão de pedágio?",
    "Quantos acidentes ocorreram nas rodovias?",
    "Qual a velocidade média dos veículos?",
    "Qual o tempo de espera nas cabines?",
    "Quantas cabines cada praça tem?",
    "Quantos funcionários trabalham em cada praça?",
    "Qual a projeção de tráfego para o próximo mês?",
]

# ------------------------------------------------------------------ montagem
def montar_e_salvar():
    usados, perguntas = set(), set()
    itens, descartes = [], collections.Counter()

    for estrato, fn in PLANO:
        cands = fn()
        rng.shuffle(cands)
        n = 0
        for spec, perg in cands:
            if n >= ALVO:
                break
            if sig(spec) in usados or perg.strip().lower() in perguntas:
                descartes[estrato] += 1
                continue
            usados.add(sig(spec))
            perguntas.add(perg.strip().lower())
            n += 1
            itens.append({"id": f"{estrato}_antt_{n:02d}", "pergunta_nl": perg,
                          "estrato": estrato, "spec": spec, "revisado_humano": False})
        if n < ALVO:
            print(f"AVISO: {estrato} só conseguiu {n}/{ALVO} specs inéditas")

    for i, p in enumerate(ABSTENCOES[:ALVO], 1):
        assert p.strip().lower() not in perguntas, f"abstenção duplicada: {p}"
        itens.append({"id": f"abstencao_antt_{i:02d}", "pergunta_nl": p, "estrato": "abstencao",
                      "spec": sp([]), "revisado_humano": False})

    dest = G / "autor_antt.jsonl"
    dest.write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in itens),
                    encoding="utf-8")
    c = collections.Counter(it["estrato"] for it in itens)
    print(f"golden ANTT: {len(itens)} itens  {dict(sorted(c.items()))}")
    print("guardas na GERAÇÃO: G1 (filtro x definição), G2 (filtra+agrupa mesma dim), "
          "G3 (sem metrica_filtrada), G4 (ranking com limit < cardinalidade)")
    print(f"-> {dest}")


if __name__ == "__main__":
    montar_e_salvar()
