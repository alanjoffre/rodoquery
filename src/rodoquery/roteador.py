"""Roteador 2-tiers (Fase 14, #3) — construído, validado e desligado por MEDIÇÃO, não por suposição.

O README sempre descreveu "Tier-A primário; Tier-B (SQL cru) como fallback". O Tier-B foi
construído e o sandbox validado (39/39), mas nunca ligado. A Fase 14 mediu duas políticas de
fallback nas predições congeladas do TEST-ANTT:

  INGÊNUA (fallback quando Tier-A abstém OU a spec não compila):
      recuperou 1 respondível, ESTRAGOU 4 abstenções → abstenção 88% → 72%. RUIM.
  CONSERVADORA (fallback SÓ quando a spec não compila; nunca sobrepõe uma abstenção deliberada):
      recuperou 1, estragou 0 → EX 88,7% → 89,3%, abstenção intacta em 88%. SEGURA, mas marginal.

Decisão de engenharia, agora baseada em evidência: **não** fiar o Tier-B no caminho quente do
serviço. O ganho da política conservadora é +0,7 pp (1 item em 175), e o custo seria uma segunda
chamada de LLM + a superfície do sandbox na latência do usuário. Não compensa. Este módulo deixa a
política pronta e testada — ligar é trocar `SO_TIER_A` por `rotear`, com o tradeoff documentado.

A função é PURA sobre os dois sub-sistemas: recebe as duas predições e o sinal de compilação, e
decide. Assim ela é testável sem LLM e sem banco.
"""
from __future__ import annotations

from collections.abc import Callable

from rodoquery.avaliacao import Predicao


def rotear(
    pred_tier_a: Predicao,
    spec_compila: bool,
    tier_b: Callable[[], Predicao],
    *,
    conservador: bool = True,
) -> Predicao:
    """Decide qual predição serve.

    conservador=True (recomendado pela medição): cai para Tier-B só quando a spec do Tier-A NÃO
    compila. Uma abstenção deliberada do Tier-A é respeitada — é a competência mais forte dele, e
    sobrepô-la com SQL cru só troca "não sei" honesto por um número alucinado.

    conservador=False (ingênuo): cai para Tier-B também quando o Tier-A abstém. Medido como
    prejudicial (derruba a acurácia de abstenção); existe aqui só para reproduzir a comparação.
    """
    if pred_tier_a.tipo == "abster":
        return tier_b() if not conservador else pred_tier_a
    if pred_tier_a.tipo == "spec" and not spec_compila:
        return tier_b()
    return pred_tier_a
