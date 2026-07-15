"""Testes da estatística de avaliação (fundação da Fase 0)."""
from rodoquery.estat import bootstrap_diff_ic, mcnemar, wilson


def test_wilson():
    assert wilson(0, 0) == [0.0, 0.0]
    lo, hi = wilson(31, 50)          # ~0,62 (o hit@5 do RodoIA, de brincadeira)
    assert 0.0 <= lo < 0.62 < hi <= 1.0


def test_mcnemar_sem_discordancia():
    # sistemas idênticos → sem discordância → p=1, delta=0
    r = mcnemar([True, False, True], [True, False, True])
    assert r["b_only"] == 0 and r["c_only"] == 0
    assert r["p_valor"] == 1.0 and r["delta_acuracia"] == 0.0


def test_mcnemar_a_domina():
    # a acerta tudo, b erra tudo → 5 discordantes só de um lado → p pequeno
    a = [True] * 5
    b = [False] * 5
    r = mcnemar(a, b)
    assert r["b_only"] == 5 and r["c_only"] == 0
    assert r["delta_acuracia"] == 1.0
    assert r["p_valor"] < 0.1                     # 2*0.5^5 = 0.0625


def test_bootstrap_diff_ic_pareado():
    a = [True, True, True, True, False]
    b = [True, False, False, False, False]        # a melhor
    lo, hi = bootstrap_diff_ic(a, b)
    assert lo <= hi
    assert -1.0 <= lo and hi <= 1.0
