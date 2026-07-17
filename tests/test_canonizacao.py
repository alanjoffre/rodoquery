"""Testes do oráculo de Execution Accuracy — cada teste trava uma DECISÃO documentada."""
from datetime import date
from decimal import Decimal

from rodoquery.canonizacao import canonicalizar, hash_resultado, resultados_batem


def test_ordem_das_linhas_ignorada_por_padrao():
    assert resultados_batem([(1, "a"), (2, "b")], [(2, "b"), (1, "a")])


def test_ordem_das_linhas_importa_quando_ranking():
    # pergunta de top-N: a ordem É a resposta
    assert not resultados_batem([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], ordenado=True)
    assert resultados_batem([(2, "b"), (1, "a")], [(2, "b"), (1, "a")], ordenado=True)


def test_nome_de_coluna_ignorado_ordem_de_coluna_importa():
    # só valores entram na canonização (nomes nunca chegam aqui) — mas a POSIÇÃO importa
    assert not resultados_batem([("praca", 10)], [(10, "praca")])


def test_int_e_float_equivalentes_e_tolerancia():
    assert resultados_batem([(2.0,)], [(2,)])                       # SUM pode vir int ou float
    assert resultados_batem([(1.0000001,)], [(1.0,)])               # ruído < 6 casas
    assert not resultados_batem([(1.001,)], [(1.0,)])               # diferença real


def test_centavos_inteiros_sao_exatos():
    assert not resultados_batem([(10_050,)], [(10_051,)])           # 1 centavo importa
    assert resultados_batem([(Decimal("100.50"),)], [(100.5,)])     # Decimal ~ float


def test_nulo_nao_e_zero_por_padrao():
    # decisão conservadora: o SL coalesce p/ 0, SQL cru pode dar NULL — não mascarar
    assert not resultados_batem([(None,)], [(0,)])
    assert resultados_batem([(None,)], [(0,)], nulo_igual_zero=True)


def test_data_normalizada():
    assert resultados_batem([(date(2026, 1, 5),)], [("2026-01-05",)])


def test_hash_estavel_e_sensivel():
    a = [(1, "x"), (2, "y")]
    assert hash_resultado(a) == hash_resultado(list(reversed(a)))   # multiset → mesmo hash
    assert hash_resultado(a) != hash_resultado([(1, "x"), (3, "y")])
    assert len(hash_resultado(a)) == 16


def test_canonizar_vazio():
    assert canonicalizar([]) == ()
