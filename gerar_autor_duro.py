"""Fase 20 — autora o conjunto DURO, desenhado contra o que saturou.

## Por que estes itens e não outros

Os 8 estratos das Fases 2–19 fizeram **100%** contra `claude-opus-5`. Em vez de escrever mais
perguntas do mesmo tipo, medi qual superfície do catálogo nunca foi tocada:

    em 168 itens respondíveis:  `where` composto = 0 itens   |   2+ métricas = 2 itens
    o único eixo que ainda discrimina: abstenção (24/25)

Daí os quatro grupos abaixo. Cada um tem uma razão explícita para ser difícil — item que eu não
consigo justificar por que um modelo forte erraria não entra.

## As três armadilhas que evitei (cada uma custou uma fase para aprender)

- **G1 — filtro que colide com a definição da métrica.** `automation_rate` filtrada por
  `tipo_cobranca` daria 1,0 constante; `commercial_share` por `tipo_de_veiculo`, idem. A Fase 15
  mostrou que vale também para dimensão **correlacionada** (`categoria_eixo='6'` ⇒ todo veículo é
  comercial ⇒ share = 1,0).
- **G2 — filtrar e agrupar pela MESMA dimensão** é ambíguo; dois anotadores discordaram na Fase 9.
- **G4 — ranking cujo corte cai num empate**, ou `limit` maior que a cardinalidade. Custou 10
  itens defeituosos na Fase 14.

## Anti-circularidade

Aqui só nasce a **spec do autor**. O gold sai do MetricFlow compilando essa spec, nunca de SQL
escrito à mão — é a regra que o projeto segue desde a Fase 0. `preparar_duro.py` valida, aplica as
guardas e sela.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
DEST = REPO / "golden" / "duro_antt_autor.jsonl"


def spec(metrics, group_by=None, where=None, order_by=None, limit=None, ordenado=False):
    return {"metrics": metrics, "group_by": group_by or [], "where": where,
            "order_by": order_by or [], "limit": limit, "ordenado": ordenado}


def D(dim, val):
    return f"{{{{ Dimension('{dim}') }}}} = '{val}'"


def E(*filtros):
    return " AND ".join(filtros)


VOL, TAXA, SHARE = "traffic_volume", "automation_rate", "commercial_share"

ITENS = []


def add(estrato, pergunta, s, porque):
    """`porque` não vai para o golden — é a justificativa de dificuldade, revisável no código."""
    n = sum(1 for i in ITENS if i["estrato"] == estrato) + 1
    ITENS.append({"id": f"{estrato}_duro_{n:02d}",
                  "pergunta_nl": pergunta, "estrato": estrato, "spec": s,
                  "revisado_humano": False})


# =============================================================================================
# 1) filtro_composto — dois filtros de igualdade com AND. Zero itens assim existiam.
#    Dificuldade: exige compor duas restrições SEM transformar nenhuma em group_by (o modo de
#    falha que a Fase 10 mediu: o modelo agrupa pela dimensão que ele mesmo filtrou).
# =============================================================================================
add("filtro_composto",
    "Quantos veículos comerciais passaram em cobrança automática, por concessionária?",
    spec([VOL], ["plaza__concessionaria"],
         E(D("plaza__tipo_de_veiculo", "Comercial"), D("plaza__tipo_cobranca", "Automática"))),
    "dois filtros; ambos podem virar group_by espúrio")
add("filtro_composto", "Qual o volume de motos no sentido crescente, por praça?",
    spec([VOL], ["plaza__praca"],
         E(D("plaza__tipo_de_veiculo", "Moto"), D("plaza__sentido", "Crescente"))),
    "dois filtros + entidade")
add("filtro_composto", "Volume mensal de veículos de passeio em cobrança manual",
    spec([VOL], ["metric_time__month"],
         E(D("plaza__tipo_de_veiculo", "Passeio"), D("plaza__tipo_cobranca", "Manual"))),
    "dois filtros + grão temporal")
add("filtro_composto", "Quantos veículos de 2 eixos passaram no sentido decrescente?",
    spec([VOL], [], E(D("plaza__categoria_eixo", "2"), D("plaza__sentido", "Decrescente"))),
    "dois filtros, group_by VAZIO — o agregado disfarçado da Fase 15")
add("filtro_composto", "Volume diário de veículos comerciais em cobrança por OCR/PLACA",
    spec([VOL], ["metric_time__day"],
         E(D("plaza__tipo_de_veiculo", "Comercial"), D("plaza__tipo_cobranca", "OCR/PLACA"))),
    "valor com barra no texto — armadilha de parsing")
add("filtro_composto",
    "Qual a taxa de automação dos veículos comerciais no sentido crescente, por concessionária?",
    spec([TAXA], ["plaza__concessionaria"],
         E(D("plaza__tipo_de_veiculo", "Comercial"), D("plaza__sentido", "Crescente"))),
    "razão + 2 filtros, nenhum colidindo com a definição (G1 respeitada)")
add("filtro_composto", "Participação de veículos comerciais em cobrança manual, por sentido",
    spec([SHARE], ["plaza__sentido"], D("plaza__tipo_cobranca", "Manual")),
    "share filtrado por cobranca — NAO colide (share e sobre tipo_de_veiculo)")
add("filtro_composto", "Volume de motos em cobrança automática por mês",
    spec([VOL], ["metric_time__month"],
         E(D("plaza__tipo_de_veiculo", "Moto"), D("plaza__tipo_cobranca", "Automática"))),
    "dois filtros + tempo")
add("filtro_composto", "Quantos veículos de 6 eixos passaram em cobrança automática?",
    spec([VOL], [], E(D("plaza__categoria_eixo", "6"), D("plaza__tipo_cobranca", "Automática"))),
    "agregado com 2 filtros")
add("filtro_composto", "Volume por praça de veículos de passeio no sentido decrescente",
    spec([VOL], ["plaza__praca"],
         E(D("plaza__tipo_de_veiculo", "Passeio"), D("plaza__sentido", "Decrescente"))),
    "dois filtros + entidade de alta cardinalidade")
add("filtro_composto", "Qual a taxa de automação das motos, por concessionária?",
    spec([TAXA], ["plaza__concessionaria"], D("plaza__tipo_de_veiculo", "Moto")),
    "razão com filtro em dimensao NAO correlacionada")
add("filtro_composto", "Volume de veículos comerciais de 5 eixos por concessionária",
    spec([VOL], ["plaza__concessionaria"],
         E(D("plaza__tipo_de_veiculo", "Comercial"), D("plaza__categoria_eixo", "5"))),
    "dois filtros correlacionados entre si, mas nenhum colide com a metrica (VOL e simples)")

# =============================================================================================
# 2) metrica_mista — SIMPLES + RAZÃO na mesma spec. Impossível de compilar até a Fase 19.
#    Dificuldade: a pergunta pede DUAS grandezas de naturezas diferentes; o modo de falha
#    esperado é escolher uma só, ou emitir duas chamadas.
# =============================================================================================
add("metrica_mista", "Quantos veículos passaram e qual a taxa de automação, por sentido?",
    spec([VOL, TAXA], ["plaza__sentido"]), "contagem + razao, explicitamente pedidas")
add("metrica_mista", "Mostre o volume e a participação de veículos comerciais por concessionária",
    spec([VOL, SHARE], ["plaza__concessionaria"]), "contagem + share")
add("metrica_mista", "Volume total e taxa de automação por mês",
    spec([VOL, TAXA], ["metric_time__month"]), "mista + grao temporal")
add("metrica_mista", "Por praça, quantos veículos passaram e que fração era comercial?",
    spec([VOL, SHARE], ["plaza__praca"]), "'fracao' em vez de 'participacao' — sinonimo")
add("metrica_mista", "Qual o tráfego e a taxa de automação em cada tipo de cobrança?",
    spec([VOL, TAXA], ["plaza__tipo_cobranca"]),
    "agrupar por tipo_cobranca com automation_rate NAO e degenerado (o grupo varia)")
add("metrica_mista", "Volume e participação comercial por sentido e por mês",
    spec([VOL, SHARE], ["plaza__sentido", "metric_time__month"]), "mista + 2 group_by")
add("metrica_mista", "Quantos veículos e qual a proporção de comerciais, por categoria de eixo?",
    spec([VOL, SHARE], ["plaza__categoria_eixo"]), "mista sobre dimensao de alta cardinalidade")
add("metrica_mista", "Tráfego semanal com a respectiva taxa de automação",
    spec([VOL, TAXA], ["metric_time__week"]), "grao de semana + mista")
add("metrica_mista", "Volume e taxa de automação dos veículos comerciais, por concessionária",
    spec([VOL, TAXA], ["plaza__concessionaria"], D("plaza__tipo_de_veiculo", "Comercial")),
    "mista COM filtro — a forma que nem existia")
add("metrica_mista", "Por sentido, mostre o volume e a participação de comerciais no sentido",
    spec([VOL, SHARE], ["plaza__sentido"]), "redundancia no enunciado; nao muda a spec")
add("metrica_mista", "Volume e taxa de automação por dia",
    spec([VOL, TAXA], ["metric_time__day"]), "grao diario + mista")
add("metrica_mista", "Quantos veículos passaram por concessionária e qual a fração automatizada?",
    spec([VOL, TAXA], ["plaza__concessionaria"]), "'fracao automatizada' = automation_rate")

# =============================================================================================
# 3) composicao — combos. Dificuldade: acumular ranking/multi-group_by sobre as formas acima.
# =============================================================================================
add("composicao", "Quais as 5 praças com maior volume de motos no sentido crescente?",
    spec([VOL], ["plaza__praca"],
         E(D("plaza__tipo_de_veiculo", "Moto"), D("plaza__sentido", "Crescente")),
         ["-traffic_volume"], 5, True), "filtro composto + ranking")
add("composicao", "Top 5 concessionárias por volume, com a taxa de automação de cada uma",
    spec([VOL, TAXA], ["plaza__concessionaria"], None, ["-traffic_volume"], 5, True),
    "mista + ranking")
add("composicao", "As 10 praças com mais veículos comerciais em cobrança automática",
    spec([VOL], ["plaza__praca"],
         E(D("plaza__tipo_de_veiculo", "Comercial"), D("plaza__tipo_cobranca", "Automática")),
         ["-traffic_volume"], 10, True), "filtro composto + ranking com limite maior")
add("composicao", "Volume de veículos de passeio por concessionária e por mês, em cobrança manual",
    spec([VOL], ["plaza__concessionaria", "metric_time__month"],
         E(D("plaza__tipo_de_veiculo", "Passeio"), D("plaza__tipo_cobranca", "Manual"))),
    "2 filtros + 2 group_by")
add("composicao", "Quais as 3 concessionárias com menor taxa de automação entre os comerciais?",
    spec([TAXA], ["plaza__concessionaria"], D("plaza__tipo_de_veiculo", "Comercial"),
         ["automation_rate"], 3, True), "ranking ASCENDENTE (menor) — inverte o sinal")
add("composicao", "Top 5 praças em volume de motos, mostrando também a participação comercial",
    spec([VOL, SHARE], ["plaza__praca"], D("plaza__tipo_de_veiculo", "Moto"),
         ["-traffic_volume"], 5, True),
    "mista + filtro + ranking; o share fica 1,0? NAO — filtro e Moto, share e sobre Comercial")
add("composicao",
    "Volume mensal de comerciais no sentido decrescente, do mês mais movimentado ao menos",
    spec([VOL], ["metric_time__month"],
         E(D("plaza__tipo_de_veiculo", "Comercial"), D("plaza__sentido", "Decrescente")),
         ["-traffic_volume"], None, True), "ranking SEM limit — ordenacao e a resposta")
add("composicao", "Por sentido e tipo de cobrança, qual o volume e a participação comercial?",
    spec([VOL, SHARE], ["plaza__sentido", "plaza__tipo_cobranca"]),
    "mista + 2 group_by categoricos")
add("composicao", "As 5 concessionárias com maior volume de veículos de 6 eixos",
    spec([VOL], ["plaza__concessionaria"], D("plaza__categoria_eixo", "6"),
         ["-traffic_volume"], 5, True), "filtro + ranking")
add("composicao", "Volume e taxa de automação por praça, nas 5 praças de maior tráfego",
    spec([VOL, TAXA], ["plaza__praca"], None, ["-traffic_volume"], 5, True),
    "mista + ranking sobre alta cardinalidade")
add("composicao", "Tráfego diário de motos em cobrança automática, por praça",
    spec([VOL], ["plaza__praca", "metric_time__day"],
         E(D("plaza__tipo_de_veiculo", "Moto"), D("plaza__tipo_cobranca", "Automática"))),
    "2 filtros + 2 group_by com tempo")
add("composicao", "Quais as 3 praças com maior participação de veículos comerciais?",
    spec([SHARE], ["plaza__praca"], None, ["-commercial_share"], 3, True),
    "ranking sobre RAZAO — ordena por proporcao, nao por contagem")

# =============================================================================================
# 4) abstencao (near-miss) — cada uma está a UM PASSO de uma métrica existente.
#    Dificuldade: o catálogo tem `automation_rate` e `commercial_share`; um modelo apressado
#    generaliza para "proporção de qualquer categoria", que NÃO existe.
#    Nota sobre `1 - automation_rate`: NÃO resolve "proporção de manual", porque tipo_cobranca
#    tem TRÊS valores (Automática, Manual, OCR/PLACA) — o complemento não é o manual.
# =============================================================================================
VAZIA = spec([])
for pergunta, porque in [
    ("Qual a proporção de cobrança manual?",
     "so existe automation_rate (Automatica/total); manual NAO e o complemento (ha OCR/PLACA)"),
    ("Que percentual do tráfego usa OCR/PLACA?", "share de OCR nao e metrica"),
    ("Qual a participação de motos no tráfego total?", "share de Moto nao existe; so de Comercial"),
    ("Qual a proporção de veículos de passeio?", "share de Passeio nao existe"),
    ("Qual o percentual de veículos de 2 eixos?", "share por categoria_eixo nao existe"),
    ("Qual a razão entre tráfego comercial e tráfego de passeio?",
     "commercial_share e Comercial/TOTAL, nao Comercial/Passeio"),
    ("Que fração do tráfego segue no sentido crescente?", "share por sentido nao existe"),
    ("Qual a taxa de cobrança não automatizada?", "complemento nao e metrica do catalogo"),
    ("Qual a participação de cada concessionária no tráfego nacional?",
     "share por concessionaria nao existe"),
    ("Qual o percentual de praças com cobrança automática?",
     "proporcao de PRACAS (entidades), nao de trafego — grao diferente do fato"),
    ("Qual a proporção entre veículos comerciais e o total de motos?",
     "denominador arbitrario; nenhuma razao do catalogo"),
    ("Quantos por cento do volume é de veículos de 7 eixos?", "share por eixo nao existe"),
]:
    add("abstencao", pergunta, VAZIA, porque)


if __name__ == "__main__":
    DEST.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in ITENS) + "\n",
                    encoding="utf-8")
    from collections import Counter
    print(f"autorados: {len(ITENS)} -> {DEST}")
    for e, n in sorted(Counter(i["estrato"] for i in ITENS).items()):
        print(f"  {e:18s} {n}")
