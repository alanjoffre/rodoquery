"""Fase 21 — o catálogo com as PARTIÇÕES COMPLETAS (7 métricas em vez de 3).

## O que a Fase 20 mostrou, e o que estava errado no diagnóstico

A abstenção caiu para 50% num conjunto de near-miss, e as 6 falhas tinham o mesmo mecanismo:
**pedem proporção, o modelo responde contagem** (`traffic_volume`). Eu registrei isso como
"rebaixamento de tipo" — um defeito do modelo.

Olhando de novo, o defeito é do **catálogo**, e é de assimetria:

    tipo_cobranca  = {Automática, Manual, OCR/PLACA}   → só `automation_rate` exposta
    tipo_de_veiculo = {Comercial, Passeio, Moto}       → só `commercial_share` exposta

Quem vê "taxa de automação" espera, com razão, que "proporção de cobrança manual" exista. O
modelo não estava inventando: estava diante de uma pergunta legítima cuja resposta o catálogo
escondia, e devolveu o mais próximo que tinha.

## A regra: completar a partição, não expor tudo

Só entram os **irmãos de partições onde um membro já estava exposto**. Isso NÃO é "adicionar
toda razão possível":

- `categoria_eixo` tem 19 valores — 19 shares recriariam a ambiguidade que a Fase 10 mediu;
- `sentido` fica de fora porque **nenhum** membro dele estava exposto: sem assimetria, sem
  armadilha, e a pergunta "que fração segue no sentido crescente?" **continua sendo abstenção**.

A regra é falseável e tem teste: as duas partições **somam exatamente 1,0** por construção
(verificado no dado, não presumido).

## Por que um módulo novo e não editar o catálogo congelado

Trocar `CATALOGO_ANTT` mudaria o SUT de todas as fases 11–20 de uma vez, e nenhum número
anterior poderia ser comparado com nenhum posterior. Aqui o catálogo enriquecido é um SISTEMA
NOVO, medido contra o antigo no mesmo conjunto — que é o desenho que permite atribuir a
diferença ao catálogo, e não ao acaso.
"""
from __future__ import annotations

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.sistema import PROMPT, _parse_spec

CATALOGO_ANTT_RICO = """MÉTRICAS (use o `nome` exato; só existem estas 7):
- traffic_volume     — volume de veículos que passaram nas praças de pedágio (contagem).
Proporções por FORMA DE COBRANÇA (as três somam 1):
- automation_rate    — proporção do tráfego cobrado automaticamente (tag/AVI) sobre o total.
- manual_share       — proporção do tráfego cobrado manualmente (cabine) sobre o total.
- ocr_share          — proporção do tráfego cobrado por leitura de placa (OCR) sobre o total.
Proporções por TIPO DE VEÍCULO (as três somam 1):
- commercial_share   — proporção de veículos comerciais sobre o tráfego total.
- passenger_share    — proporção de veículos de passeio sobre o tráfego total.
- motorcycle_share   — proporção de motocicletas sobre o tráfego total.
(NÃO existe métrica de receita, faturamento, arrecadação, tarifa, custo, lucro, multa, evasão,
média, mediana, máximo, contagem de veículos distintos, acumulado, crescimento nem previsão.
NÃO existe proporção por sentido, por categoria de eixo, por praça nem por concessionária —
só as 6 proporções acima. Os dados são AGREGADOS por praça/dia: não há transação individual.)

TOKENS de group_by (use exatamente estes):
- tempo:       metric_time__day, metric_time__week, metric_time__month
- entidades:   plaza__praca (praça de pedágio), plaza__concessionaria (concessionária)
- categóricos: plaza__sentido, plaza__tipo_cobranca, plaza__categoria_eixo, plaza__tipo_de_veiculo
(NÃO existe dimensão de hora, turno, dia da semana, trimestre, UF, município, rodovia ou faixa.)

VALORES p/ filtro `where`:
- plaza__tipo_cobranca:   Automática, Manual, OCR/PLACA
- plaza__tipo_de_veiculo: Comercial, Passeio, Moto
- plaza__sentido:         Crescente, Decrescente
- plaza__categoria_eixo:  número de eixos, de '2' a '20' (texto)
Sintaxe de where: {{ Dimension('plaza__tipo_cobranca') }} = 'Automática'"""

# As 6 razões e a métrica base. Serve de contrato para os testes (drift do catálogo).
METRICAS_RICAS = ("traffic_volume", "automation_rate", "manual_share", "ocr_share",
                  "commercial_share", "passenger_share", "motorcycle_share")
PARTICOES = {
    "tipo_cobranca": ("automation_rate", "manual_share", "ocr_share"),
    "tipo_de_veiculo": ("commercial_share", "passenger_share", "motorcycle_share"),
}


def tier_a_antt_rico(pergunta: str, modelo: str | None = None,
                     temperatura: float | None = None, provedor=None) -> Predicao:
    """Idêntico ao `tier_a_antt`, exceto pelo catálogo. O PROMPT é o mesmo, byte a byte.

    Isolar a variável é o ponto: se este sistema for melhor, o mérito é do **catálogo**, e não
    de um prompt reescrito ou de um modelo diferente.
    """
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    chamar = provedor or _chamar_ollama
    resp, tel = chamar(PROMPT.format(catalogo=CATALOGO_ANTT_RICO, pergunta=pergunta), modelo, temp)
    modelo = tel.get("modelo_efetivo", modelo)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400], **tel)
    spec = _parse_spec(resp)
    if spec is None:
        return Predicao.abster(modelo=modelo, raw=resp[:400], falha_parse=True, **tel)
    return Predicao.com_spec(spec, modelo=modelo, raw=resp[:400], **tel)
