"""Testes do serviço (Fase 6) — as partes puras, sem LLM/GPU.

O caminho completo (pergunta → LLM → MetricFlow → DuckDB) é exercido pelo canário contra o serviço
vivo; aqui travamos a lógica que não deve regredir silenciosamente.
"""
from rodoquery.gold import Spec
from rodoquery.servico import _chave, _pct, compilar_cacheado


def test_chave_da_spec_e_estavel_e_discrimina():
    a = Spec(metrics=["revenue"], group_by=["transaction__plaza"])
    b = Spec(metrics=["revenue"], group_by=["transaction__plaza"])
    c = Spec(metrics=["revenue"], group_by=["transaction__status"])
    assert _chave(a) == _chave(b)      # mesma spec -> mesma chave (cache acerta)
    assert _chave(a) != _chave(c)      # spec diferente -> chave diferente (não envenena o cache)


def test_cache_evita_recompilar(monkeypatch):
    chamadas = {"n": 0}

    def falso_compilar(spec):
        chamadas["n"] += 1
        return "SELECT 1"

    monkeypatch.setattr("rodoquery.servico.compilar_spec", falso_compilar)
    spec = Spec(metrics=["transactions"], group_by=["metric_time__month"])

    sql1, do_cache1 = compilar_cacheado(spec)
    sql2, do_cache2 = compilar_cacheado(spec)

    assert sql1 == sql2 == "SELECT 1"
    assert do_cache1 is False and do_cache2 is True
    assert chamadas["n"] == 1          # compilou UMA vez só (o mf é o custo caro)


def test_percentil():
    v = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert _pct(v, 0.50) == 6.0
    assert _pct(v, 0.95) == 10.0
    assert _pct([], 0.95) is None
