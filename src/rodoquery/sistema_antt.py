"""Tier-A sobre a fundação REAL da ANTT (Fase 11).

O catálogo abaixo é o mesmo formato do sistema congelado, mas o conteúdo nasce das lições caras:

- **3 métricas, uma por conceito.** Não existe a mesma grandeza em duas unidades (Fase 10).
- **Contagem filtrada NÃO é métrica.** O semantic layer tem `automated_traffic_volume` e
  `commercial_traffic_volume` como numeradores das razões, e eles estão marcados
  `catalogo_usuario: false` no manifesto — de propósito. Se estivessem aqui, "quantos veículos
  passaram em cobrança automática?" teria duas respostas certas (a métrica ou
  `traffic_volume` + where), que é exatamente a ambiguidade que a Fase 10 mediu.
- **O que NÃO existe é declarado.** O dado da ANTT é agregado (volume por praça/dia/categoria),
  não transacional: não há receita, tarifa, transação individual, hora do dia nem geografia.
  Dizer isso no catálogo é o que separa "abster" de "inventar um vizinho plausível" — o modo de
  falha que a Fase 8 isolou.

O PROMPT é importado byte a byte de `sistema.py`: muda a fundação e o catálogo, não a instrução.
"""
from __future__ import annotations

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import _chamar_ollama
from rodoquery.config import settings
from rodoquery.sistema import PROMPT, _parse_spec

CATALOGO_ANTT = """MÉTRICAS (use o `nome` exato; só existem estas 3):
- traffic_volume     — volume de veículos que passaram nas praças de pedágio (contagem).
- automation_rate    — taxa/proporção do tráfego cobrado automaticamente (tag/AVI) sobre o total.
- commercial_share   — participação/proporção de veículos comerciais sobre o tráfego total.
(NÃO existe métrica de receita, faturamento, arrecadação, tarifa, custo, lucro, multa, evasão,
média, mediana, máximo, contagem de veículos distintos, acumulado, crescimento nem previsão.
Os dados são AGREGADOS por praça/dia — não há transação individual, placa nem usuário.)

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


def tier_a_antt(pergunta: str, modelo: str | None = None,
                temperatura: float | None = None, provedor=None) -> Predicao:
    """Idêntico ao `tier_a` congelado, exceto pelo catálogo (a fundação entra na compilação).

    `provedor` é a costura da Fase 18: `None` chama o Ollama exatamente como sempre — o caminho
    das Fases 11–16 segue byte a byte o mesmo. Passar um `ProvedorAnthropic` troca SÓ o SUT;
    prompt, catálogo e parsing ficam intocados, que é o que mantém a comparação honesta.
    """
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    chamar = provedor or _chamar_ollama
    resp, tel = chamar(PROMPT.format(catalogo=CATALOGO_ANTT, pergunta=pergunta), modelo, temp)
    # O provedor pode ter usado outro modelo (a API ignora `settings.modelo_sut`). Sem isto a
    # predição congelada seria gravada com o nome errado — artefato que mente sobre si mesmo.
    modelo = tel.get("modelo_efetivo", modelo)
    if "ABSTENHO" in resp.upper():
        return Predicao.abster(modelo=modelo, raw=resp[:400], **tel)
    spec = _parse_spec(resp)
    if spec is None:
        return Predicao.abster(modelo=modelo, raw=resp[:400], falha_parse=True, **tel)
    return Predicao.com_spec(spec, modelo=modelo, raw=resp[:400], **tel)
