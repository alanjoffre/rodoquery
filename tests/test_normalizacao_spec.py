"""Testes do normalizador de ordem (Fase 9) — o conserto da falha de ranking.

A garantia que estes testes protegem: o normalizador só age na forma exata `[campo, DESC/ASC]` e
nunca toca em nada mais. É essa propriedade que fez o conserto ter ZERO regressões no holdout v3.
"""
from rodoquery.gold import Spec
from rodoquery.normalizacao_spec import normalizar_ordem, normalizar_spec


def test_desc_vira_prefixo_menos():
    assert normalizar_ordem(["revenue", "DESC"]) == ["-revenue"]


def test_asc_vira_campo_simples():
    assert normalizar_ordem(["revenue", "ASC"]) == ["revenue"]


def test_direcao_minuscula_tambem():
    assert normalizar_ordem(["suspect_transactions", "desc"]) == ["-suspect_transactions"]


def test_idempotente_no_formato_metricflow():
    # já no formato certo: não pode virar "--revenue" nem mudar
    assert normalizar_ordem(["-revenue"]) == ["-revenue"]
    assert normalizar_ordem(["metric_time__day"]) == ["metric_time__day"]


def test_nao_toca_ordem_vazia():
    assert normalizar_ordem([]) == []


def test_nao_toca_ordem_de_um_elemento():
    assert normalizar_ordem(["metric_time__month"]) == ["metric_time__month"]


def test_nao_confunde_dimensao_de_dois_tokens_legitima():
    # duas dimensões reais no order_by não são [campo, DESC]; devem passar intactas
    assert normalizar_ordem(["metric_time__day", "transaction__plaza"]) == \
        ["metric_time__day", "transaction__plaza"]


def test_normalizar_spec_preserva_o_resto():
    s = Spec(metrics=["revenue"], group_by=["transaction__plaza"],
             where="{{ Dimension('x') }} = 'A'", order_by=["revenue", "DESC"], limit=3,
             ordenado=True)
    n = normalizar_spec(s)
    assert n.order_by == ["-revenue"]
    assert n.metrics == ["revenue"]
    assert n.group_by == ["transaction__plaza"]
    assert n.where == "{{ Dimension('x') }} = 'A'"
    assert n.limit == 3 and n.ordenado is True


def test_normalizar_spec_no_op_quando_ja_certo():
    s = Spec(metrics=["revenue"], group_by=["transaction__plaza"],
             order_by=["-revenue"], limit=3, ordenado=True)
    assert normalizar_spec(s) is s        # devolve o MESMO objeto, sem cópia inútil
