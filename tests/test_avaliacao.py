"""Testes do harness de avaliação (Fase 3) — foco na LÓGICA de scoring (sem depender de DB/LLM).

O caminho de EX-match (executar SQL válido e bater hash) é exercido pelo run real da Fase 3; aqui
travamos os ramos que decidem certo/errado, que são onde a honestidade do scorer vive.
"""
from pathlib import Path

from rodoquery.avaliacao import Predicao, avaliar_item
from rodoquery.gold import Spec
from rodoquery.golden import ItemGolden

DBS = {"seed1": Path("/inexistente.duckdb")}  # não deve ser tocado nos ramos testados
ALLOW = {"fct_toll_transactions"}


def _item_abstencao():
    return ItemGolden("abstencao_x", "Qual o lucro líquido?", "abstencao", Spec(metrics=[]))


def _item_respondivel():
    return ItemGolden("controle_x", "Quantas transações?", "controle_trivial",
                      Spec(metrics=["transactions"]))


def test_abstencao_acerta_quando_abstem():
    r = avaliar_item(_item_abstencao(), Predicao.abster(), {}, DBS, ALLOW)
    assert r["correto"] is True
    assert r["abstencao"] is True


def test_abstencao_erra_quando_responde():
    r = avaliar_item(_item_abstencao(), Predicao.com_sql("SELECT 1"), {}, DBS, ALLOW)
    assert r["correto"] is False
    assert "fora-de-escopo" in r["motivo"]


def test_respondivel_erra_quando_abstem():
    r = avaliar_item(_item_respondivel(), Predicao.abster(), {}, DBS, ALLOW)
    assert r["correto"] is False
    assert "respondível" in r["motivo"]


def test_respondivel_sql_rejeitado_pelo_sandbox_conta_erro():
    # SQL proibido é barrado na AST ANTES de conectar no banco → não toca em DBS.
    r = avaliar_item(_item_respondivel(), Predicao.com_sql("DROP TABLE fct_toll_transactions"),
                     {"seed1": "seed1"}, DBS, ALLOW)
    assert r["correto"] is False
    assert "sandbox" in r["motivo"]


def test_predicao_fabricas():
    assert Predicao.abster().tipo == "abster"
    p = Predicao.com_sql("SELECT 1", latencia_s=0.5)
    assert p.tipo == "sql" and p.sql == "SELECT 1" and p.meta["latencia_s"] == 0.5


def test_predicao_com_spec():
    p = Predicao.com_spec(Spec(metrics=["revenue"], group_by=["transaction__plaza"]))
    assert p.tipo == "spec" and p.sql is None and p.spec.metrics == ["revenue"]


def test_roundtrip_predicao_spec():
    # congelar/descongelar predição com spec tem de preservar tudo (reprodutibilidade)
    from rodoquery.avaliacao import predicao_de_dict, predicao_para_dict
    p = Predicao.com_spec(Spec(metrics=["suspect_rate"], group_by=["metric_time__month"]),
                          modelo="qwen")
    d = predicao_para_dict(p)
    p2 = predicao_de_dict(d)
    assert p2.tipo == "spec" and p2.spec == p.spec and p2.meta["modelo"] == "qwen"


def test_roundtrip_predicao_abster():
    from rodoquery.avaliacao import predicao_de_dict, predicao_para_dict
    p2 = predicao_de_dict(predicao_para_dict(Predicao.abster(falha_parse=True)))
    assert p2.tipo == "abster" and p2.spec is None and p2.meta["falha_parse"] is True


def test_abstencao_com_spec_em_respondivel_nao_e_abster():
    # numa pergunta de abstenção, devolver spec (tentou responder) conta como ERRO
    item = _item_abstencao()
    r = avaliar_item(item, Predicao.com_spec(Spec(metrics=["revenue"])), {}, DBS, ALLOW)
    assert r["correto"] is False
