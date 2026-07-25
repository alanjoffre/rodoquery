"""Testes do normalizador de ordem (Fase 9) — o conserto da falha de ranking.

A garantia que estes testes protegem: o normalizador só age na forma exata `[campo, DESC/ASC]` e
nunca toca em nada mais. É essa propriedade que fez o conserto ter ZERO regressões no holdout v3.
"""
from rodoquery.gold import Spec
from rodoquery.normalizacao_spec import (
    dimensoes_filtradas_por_igualdade,
    normalizar_group_by,
    normalizar_ordem,
    normalizar_spec,
)

W_STATUS = "{{ Dimension('transaction__status') }} = 'COMPLETED'"


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


# ---------------------------------------------------------------- group_by (Fase 10)
def test_extrai_dimensao_de_filtro_de_igualdade():
    assert dimensoes_filtradas_por_igualdade(W_STATUS) == {"transaction__status"}


def test_where_vazio_nao_extrai_nada():
    assert dimensoes_filtradas_por_igualdade(None) == set()


def test_remove_do_group_by_a_dimensao_filtrada():
    # o modo de falha dominante: filtra status e agrupa por dia E status
    assert normalizar_group_by(["metric_time__day", "transaction__status"], W_STATUS) == \
        ["metric_time__day"]


def test_preserva_group_by_sem_intersecao():
    assert normalizar_group_by(["metric_time__day"], W_STATUS) == ["metric_time__day"]


def test_esvazia_quando_so_a_dimensao_filtrada_e_agrupada():
    # convenção do gold (Fase 15): filtro sozinho é AGREGADO. Agrupar só pela dimensão filtrada
    # (valor constante) vira group_by=[]. Os itens "entre os X, por X" (ambíguos) saem do golden.
    assert normalizar_group_by(["transaction__status"], W_STATUS) == []


def test_sem_where_group_by_intacto():
    assert normalizar_group_by(["transaction__status"], None) == ["transaction__status"]


def test_desigualdade_nao_conta_como_filtro_de_valor_unico():
    # `!=` deixa vários valores possíveis: agrupar continua informativo
    w = "{{ Dimension('transaction__status') }} != 'COMPLETED'"
    assert normalizar_group_by(["transaction__status"], w) == ["transaction__status"]


def test_normalizar_spec_aplica_ordem_e_group_by_juntos():
    s = Spec(metrics=["revenue"], group_by=["metric_time__day", "transaction__status"],
             where=W_STATUS, order_by=["revenue", "DESC"], limit=3, ordenado=True)
    n = normalizar_spec(s)
    assert n.group_by == ["metric_time__day"]
    assert n.order_by == ["-revenue"]
    assert n.where == W_STATUS and n.metrics == ["revenue"]
