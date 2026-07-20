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
