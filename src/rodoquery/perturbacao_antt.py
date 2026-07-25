"""Perturbação de schema por ALIAS OPACO sobre a fundação ANTT (Fase 14, #4).

A Fase 7 achou a fragilidade REAL do sistema aqui: trocar identificadores em inglês transparente
(`revenue`) por códigos opacos (`m03`), mantendo as MESMAS descrições, derrubou o EX em 14,3 pp
(p=0,031). A pergunta: no catálogo da ANTT — que já tem nomes menos "ingleses" (`traffic_volume`,
`plaza__tipo_cobranca`) — a dependência lexical persiste?

Mecânica idêntica à Fase 7: o MetricFlow continua com os nomes reais; só a APRESENTAÇÃO muda. O
modelo vê `m1`, `d3`… com as mesmas descrições, responde em alias, e traduzimos de volta antes de
compilar. O gabarito não muda — é comparação pareada.
"""
from __future__ import annotations

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.gold import Spec
from rodoquery.sistema import _parse_spec

ALIAS_METRICA = {"m1": "traffic_volume", "m2": "automation_rate", "m3": "commercial_share"}
ALIAS_DIM = {
    "t_d": "metric_time__day", "t_s": "metric_time__week", "t_m": "metric_time__month",
    "e1": "plaza__praca", "e2": "plaza__concessionaria",
    "c1": "plaza__sentido", "c2": "plaza__tipo_cobranca", "c3": "plaza__categoria_eixo",
    "c4": "plaza__tipo_de_veiculo",
}
_REAL_METRICA = {v: k for k, v in ALIAS_METRICA.items()}
_REAL_DIM = {v: k for k, v in ALIAS_DIM.items()}

# MESMAS descrições do catálogo real — só os identificadores foram ofuscados.
CATALOGO_OPACO = """MÉTRICAS (use o código exato; só existem estas 3):
- m1 — volume de veículos que passaram nas praças de pedágio (contagem).
- m2 — taxa/proporção do tráfego cobrado automaticamente (tag/AVI) sobre o total.
- m3 — participação/proporção de veículos comerciais sobre o tráfego total.
(NÃO existe métrica de receita, faturamento, arrecadação, tarifa, custo, lucro, multa, evasão,
média, mediana, máximo, contagem de veículos distintos, acumulado, crescimento nem previsão.
Os dados são AGREGADOS por praça/dia — não há transação individual, placa nem usuário.)

TOKENS de group_by (use exatamente estes):
- tempo:       t_d, t_s, t_m
- entidades:   e1 (praça de pedágio), e2 (concessionária)
- categóricos: c1 (sentido), c2 (forma de cobrança), c3 (nº de eixos), c4 (tipo de veículo)

VALORES p/ filtro `where`:
- c2: Automática, Manual, OCR/PLACA
- c4: Comercial, Passeio, Moto
- c1: Crescente, Decrescente
- c3: número de eixos, de '2' a '20' (texto)
Sintaxe de where: {{ Dimension('c2') }} = 'Automática'"""

# reaproveita o PROMPT do sistema, mas com o catálogo opaco
from rodoquery.sistema import PROMPT  # noqa: E402


def _traduzir(spec: Spec) -> Spec:
    """Alias → nome real, antes de compilar no MetricFlow."""
    metrics = [ALIAS_METRICA.get(m, m) for m in spec.metrics]
    group_by = [ALIAS_DIM.get(d, d) for d in spec.group_by]
    where = spec.where
    if where:
        for al, real in ALIAS_DIM.items():
            where = where.replace(f"Dimension('{al}')", f"Dimension('{real}')")
    order_by = []
    for o in spec.order_by:
        sinal, corpo = ("-", o[1:]) if o.startswith("-") else ("", o)
        order_by.append(sinal + ALIAS_METRICA.get(corpo, ALIAS_DIM.get(corpo, corpo)))
    return Spec(metrics=metrics, group_by=group_by, where=where, order_by=order_by,
               limit=spec.limit, ordenado=spec.ordenado)


def tier_a_antt_opaco(pergunta: str, modelo: str | None = None,
                      temperatura: float | None = None) -> Predicao:
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    resp, tel = _chamar_ollama(PROMPT.format(catalogo=CATALOGO_OPACO, pergunta=pergunta),
                               modelo, temp)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400], **tel)
    spec = _parse_spec(resp)
    if spec is None:
        return Predicao.abster(modelo=modelo, raw=resp[:400], falha_parse=True, **tel)
    return Predicao.com_spec(_traduzir(spec), modelo=modelo, raw=resp[:400], opaco=True, **tel)
