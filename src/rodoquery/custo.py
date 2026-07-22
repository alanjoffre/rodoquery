"""Custo por 1.000 consultas (Fase 5).

**Honestidade primeiro:** o SUT roda LOCAL (Ollama/GPU do notebook), então não existe fatura por
token. O custo é ENERGIA — e energia depende de duas coisas que eu **não medi com wattímetro**:
a potência da GPU sob carga e a tarifa. Elas entram aqui como **parâmetros explícitos e rotulados
como premissa**, nunca embutidas como se fossem medidas.

O que É medido de verdade: latência por consulta e tokens de entrada/saída (telemetria do Ollama).
Por isso o valor útil deste módulo é a **ordem de grandeza** e a **estrutura de comparação**
(local vs API), não uma cifra com 4 casas fingindo precisão.
"""
from __future__ import annotations

from dataclasses import dataclass

JOULES_POR_KWH = 3.6e6


@dataclass(frozen=True)
class PremissasEnergia:
    """PREMISSAS (não medidas). Trocar aqui muda o número — é para isso que são explícitas."""
    potencia_gpu_w: float = 115.0   # GPU de notebook sob carga sustentada
    tarifa_rs_kwh: float = 0.85     # tarifa residencial BR (com impostos), ordem de grandeza


def custo_local(latencia_media_s: float, p: PremissasEnergia | None = None) -> dict:
    """Custo de energia por consulta e por 1k, a partir da latência MEDIDA."""
    p = p or PremissasEnergia()
    kwh_consulta = latencia_media_s * p.potencia_gpu_w / JOULES_POR_KWH
    rs_consulta = kwh_consulta * p.tarifa_rs_kwh
    return {
        "modelo_de_custo": "energia (execução local)",
        "medido": {"latencia_media_s": round(latencia_media_s, 3)},
        "premissas": {"potencia_gpu_w": p.potencia_gpu_w, "tarifa_rs_kwh": p.tarifa_rs_kwh},
        "kwh_por_1k": round(kwh_consulta * 1000, 6),
        "rs_por_consulta": round(rs_consulta, 6),
        "rs_por_1k": round(rs_consulta * 1000, 4),
        "ressalva": ("ignora amortização de hardware e ociosidade; potência/tarifa são PREMISSAS "
                     "(não medidas com wattímetro). Vale a ordem de grandeza."),
    }


def custo_api_equivalente(
    tokens_entrada: float,
    tokens_saida: float,
    usd_por_milhao_entrada: float,
    usd_por_milhao_saida: float,
    usd_brl: float,
) -> dict:
    """Quanto custariam as MESMAS consultas numa API por token.

    As tarifas são PARÂMETROS — não cravo preço de fornecedor aqui (muda com o tempo e eu não
    tenho como verificar agora). Os tokens, sim, são medidos."""
    usd_1k = (tokens_entrada * usd_por_milhao_entrada
              + tokens_saida * usd_por_milhao_saida) * 1000 / 1e6
    return {
        "modelo_de_custo": "API por token",
        "medido": {"tokens_entrada_por_consulta": round(tokens_entrada, 1),
                   "tokens_saida_por_consulta": round(tokens_saida, 1)},
        "parametros": {"usd_por_milhao_entrada": usd_por_milhao_entrada,
                       "usd_por_milhao_saida": usd_por_milhao_saida, "usd_brl": usd_brl},
        "usd_por_1k": round(usd_1k, 4),
        "rs_por_1k": round(usd_1k * usd_brl, 4),
        "ressalva": "tarifas são parâmetros ilustrativos; substitua pelas vigentes do fornecedor.",
    }
