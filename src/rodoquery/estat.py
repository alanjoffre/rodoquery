"""Estatística de avaliação — nenhum número sem incerteza (herdado do RodoIA).

- `wilson`: IC de proporção (robusto a n pequeno) — para Execution Accuracy por estrato.
- `bootstrap_ic`: IC percentílico de uma média.
- `bootstrap_diff_ic`: IC da DIFERENÇA de acurácia entre dois sistemas, PAREADO por item.
- `mcnemar`: teste pareado (exato, binomial) — a forma correta de comparar dois sistemas
  avaliados nos MESMOS itens. Comparar proporções não-pareadas seria erro estatístico.
"""
from __future__ import annotations

import math

import numpy as np


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    """IC de Wilson para uma proporção k/n."""
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denom
    margem = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centro - margem), 4), round(min(1.0, centro + margem), 4)]


def bootstrap_ic(valores: list[float], n_boot: int = 10_000, seed: int = 42) -> list[float]:
    """IC 95% percentílico da média por bootstrap."""
    arr = np.asarray(valores, dtype=float)
    if arr.size == 0:
        return [0.0, 0.0]
    rng = np.random.default_rng(seed)
    medias = rng.choice(arr, size=(n_boot, arr.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(medias, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def bootstrap_diff_ic(
    a: list[bool], b: list[bool], n_boot: int = 10_000, seed: int = 42
) -> list[float]:
    """IC 95% da diferença de acurácia (a − b), PAREADA por item (reamostra os índices)."""
    aa, bb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    n = aa.size
    if n == 0 or bb.size != n:
        return [0.0, 0.0]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    difs = aa[idx].mean(axis=1) - bb[idx].mean(axis=1)
    lo, hi = np.percentile(difs, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def cohen_kappa(a: list, b: list) -> float:
    """κ de Cohen — concordância entre 2 anotadores (rótulos categóricos), corrigida pelo acaso.
    Usado na Fase 2 para o mapeamento pergunta→spec do 2º anotador (limiar pré-registrado ≥ 0,8)."""
    n = len(a)
    if n == 0 or len(b) != n:
        return 0.0
    cats = set(a) | set(b)
    p_obs = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    p_esp = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return round((p_obs - p_esp) / (1 - p_esp), 4) if p_esp < 1 else 1.0


def mcnemar(a: list[bool], b: list[bool]) -> dict:
    """Teste de McNemar EXATO (binomial) entre dois sistemas nos mesmos itens.

    b_only = a acerta & b erra ; c_only = a erra & b acerta. Sob H0, cada discordante é 50/50.
    Retorna as células discordantes, o p-valor exato bicaudal e a diferença de acurácia.
    """
    n = len(a)
    if n == 0 or len(b) != n:
        return {"b_only": 0, "c_only": 0, "p_valor": 1.0, "delta_acuracia": 0.0, "n": 0}
    b_only = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    c_only = sum(1 for x, y in zip(a, b, strict=True) if (not x) and y)
    m = b_only + c_only
    if m == 0:
        p = 1.0
    else:
        k = min(b_only, c_only)
        cauda = sum(math.comb(m, i) for i in range(k + 1)) * (0.5**m)
        p = min(1.0, 2 * cauda)
    return {
        "b_only": b_only,          # a acerta, b erra
        "c_only": c_only,          # a erra, b acerta
        "p_valor": round(p, 4),
        "delta_acuracia": round((sum(a) - sum(b)) / n, 4),
        "n": n,
    }
