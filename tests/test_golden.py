"""Testes do kit de autoria do golden set (sem MetricFlow — puros, rodam no CI)."""
from rodoquery.estat import cohen_kappa
from rodoquery.gold import Spec
from rodoquery.golden import ItemGolden, canonizar_spec, concordancia_mapeamento


def _item(id_, estrato, metrics, group_by=(), where=None):
    return ItemGolden(id=id_, pergunta_nl="?", estrato=estrato,
                      spec=Spec(list(metrics), list(group_by), where))


def test_cohen_kappa():
    assert cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    assert cohen_kappa([], []) == 0.0
    assert cohen_kappa(["a", "a", "a"], ["a", "a", "b"]) == 0.0     # Po=Pe → κ=0


def test_canonizar_spec_invariante_a_ordem():
    s1 = Spec(["revenue", "transactions"], ["b", "a"])
    s2 = Spec(["transactions", "revenue"], ["a", "b"])
    assert canonizar_spec(s1) == canonizar_spec(s2)                 # ordem não importa
    assert canonizar_spec(Spec(["revenue"])) != canonizar_spec(Spec(["transactions"]))


def test_concordancia_total():
    a = [_item("1", "controle_trivial", ["transactions"]),
         _item("2", "metrica_derivada", ["suspect_rate"])]
    b = [_item("1", "controle_trivial", ["transactions"]),
         _item("2", "metrica_derivada", ["suspect_rate"])]
    r = concordancia_mapeamento(a, b)
    assert r["concordancia_spec_canonica"] == 1.0
    assert r["cohen_kappa_metrica"] == 1.0
    assert r["discordantes"] == []


def test_concordancia_com_discordancia():
    # id 3: anotadores discordam da métrica (revenue vs revenue_cents)
    a = [_item("1", "controle_trivial", ["transactions"]),
         _item("2", "metrica_filtrada", ["revenue"]),
         _item("3", "metrica_filtrada", ["revenue"])]
    b = [_item("1", "controle_trivial", ["transactions"]),
         _item("2", "metrica_filtrada", ["revenue"]),
         _item("3", "metrica_filtrada", ["revenue_cents"])]
    r = concordancia_mapeamento(a, b)
    assert r["n_pares"] == 3
    assert r["concordancia_spec_canonica"] == round(2 / 3, 4)
    assert r["discordantes"] == ["3"]


def test_concordancia_where_e_group_by():
    a = [_item("1", "valor_categorico", ["transactions"], where="x = 'A'"),
         _item("2", "join_grao", ["revenue"], group_by=["transaction__plaza"])]
    b = [_item("1", "valor_categorico", ["transactions"], where="x = 'B'"),   # where difere
         _item("2", "join_grao", ["revenue"], group_by=["transaction__plaza"])]
    r = concordancia_mapeamento(a, b)
    assert r["concordancia_where"] == 0.5
    assert r["concordancia_group_by"] == 1.0
