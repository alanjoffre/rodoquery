"""Tier-A ANTT com CATÁLOGO DESAMBIGUADO (Fase 15, lever 1 contra o resíduo de seleção).

O resíduo de seleção da Fase 12 tinha duas assinaturas, e o catálogo abaixo mira cada uma:

1. SUBSTITUIÇÃO SEMÂNTICA (abstenção que vira número) — o modelo troca "arrecadação" por
   `traffic_volume`, "estorno" por uma métrica qualquer. Reforço: para cada métrica, dizer o que
   ela NÃO é e listar as palavras-armadilha que parecem pedi-la mas não pedem.

2. DIMENSÃO EXTRA ESPÚRIA — o modelo agrupa por `categoria_eixo`/`concessionária` que a pergunta
   não citou. Reforço: uma regra explícita de que SÓ entram no group_by as dimensões nomeadas na
   pergunta, com exemplos do erro.

Nada aqui é ajustado a item de teste — são regras gerais sobre o vocabulário. A medição é no
holdout de ablação (fresco). O PROMPT-base é o mesmo de `sistema.py`; muda só o catálogo.
"""
from __future__ import annotations

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.sistema import PROMPT, _parse_spec

CATALOGO_ANTT_V2 = """MÉTRICAS (use o `nome` exato; só existem estas 3):
- traffic_volume     — CONTAGEM de veículos que passaram. NÃO é receita nem valor em dinheiro.
- automation_rate    — PROPORÇÃO (0 a 1) do tráfego cobrado por tag/AVI. NÃO é contagem.
- commercial_share   — PROPORÇÃO (0 a 1) de veículos comerciais no tráfego. NÃO é contagem.

O que NÃO existe (se a pergunta pede qualquer um destes, responda ABSTENHO — não troque por uma
métrica parecida; um número errado é pior que abster):
- dinheiro: receita, faturamento, arrecadação, tarifa, valor, custo, lucro, multa — NÃO HÁ.
  ("Quanto arrecadou" ≠ traffic_volume. Este dado é volume de veículos, não dinheiro.)
- estatística derivada: média, mediana, máximo, mínimo, desvio, acumulado, crescimento, variação,
  projeção, pico — NÃO HÁ (só a soma de volume e as duas proporções acima).
- contagem de distintos: veículos/placas únicos — NÃO HÁ (o dado é agregado, sem identidade).
- taxa de estorno/evasão/conversão — NÃO HÁ (não confundir com automation_rate).

TOKENS de group_by (use exatamente estes):
- tempo:       metric_time__day, metric_time__week, metric_time__month
- entidades:   plaza__praca (praça), plaza__concessionaria (concessionária)
- categóricos: plaza__sentido, plaza__tipo_cobranca, plaza__categoria_eixo, plaza__tipo_de_veiculo
(NÃO existe dimensão de hora, turno, dia da semana, trimestre, UF, município ou rodovia.)

REGRA DO group_by (erro comum): agrupe SOMENTE pelas dimensões que a pergunta NOMEIA. Não
acrescente nenhuma outra. "volume por praça" → group_by=[plaza__praca] e MAIS NADA (não adicione
tipo de veículo, eixo, etc.). "volume dos veículos comerciais" → é um FILTRO (where), agregado, sem
group_by nenhum.

VALORES p/ filtro `where`:
- plaza__tipo_cobranca:   Automática, Manual, OCR/PLACA
- plaza__tipo_de_veiculo: Comercial, Passeio, Moto
- plaza__sentido:         Crescente, Decrescente
- plaza__categoria_eixo:  número de eixos, de '2' a '20' (texto)
Sintaxe de where: {{ Dimension('plaza__tipo_cobranca') }} = 'Automática'"""


def tier_a_antt_v2(pergunta: str, modelo: str | None = None,
                   temperatura: float | None = None) -> Predicao:
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    resp, tel = _chamar_ollama(PROMPT.format(catalogo=CATALOGO_ANTT_V2, pergunta=pergunta),
                               modelo, temp)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400], **tel)
    spec = _parse_spec(resp)
    if spec is None:
        return Predicao.abster(modelo=modelo, raw=resp[:400], falha_parse=True, **tel)
    return Predicao.com_spec(spec, modelo=modelo, raw=resp[:400], **tel)
