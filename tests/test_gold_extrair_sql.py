"""`_extrair_sql` — o corte da saída do `mf query --explain`.

**O bug que estes testes travam.** A versão original cortava no primeiro `SELECT`. Quando o
MetricFlow emite CTE (o que acontece ao pedir uma métrica SIMPLES junto de uma RAZÃO), o primeiro
`SELECT` está DENTRO do `WITH x AS (` — o corte descartava o cabeçalho e devolvia SQL com um `)`
órfão, que o DuckDB rejeita.

**O impacto real, medido depois de eu ter exagerado.** Afirmei que os geradores tinham descartado
a classe em silêncio e que isso explicava parte da saturação das Fases 18/19. A auditoria refutou:
os 4 descartes do golden ANTT foram **todos** por gold degenerado, e em 291 itens autorados spec
mista **nunca foi escrita**. O bug era **latente** — zero itens perdidos, zero medições afetadas.
Estes testes existem porque ele deixaria de ser latente no minuto em que alguém autorasse essa
classe, que é exatamente o próximo passo do projeto.

Nenhum destes testes chama o `mf`: são sobre o PARSER, com saídas sintéticas.
"""
from __future__ import annotations

import pytest

from rodoquery.gold import _extrair_sql

MARCADOR = "🔎 SQL query\n"


def test_saida_com_cte_preserva_o_with():
    """O caso que o bug quebrava: sem o `WITH`, o `)` do CTE fica órfão."""
    saida = MARCADOR + (
        "WITH sma_10001_cte AS (\n"
        "  SELECT\n"
        "    sentido AS plaza__sentido\n"
        "  FROM \"main\".\"fct_traffic_volume\"\n"
        ")\n"
        "\n"
        "SELECT\n"
        "  plaza__sentido\n"
        "FROM sma_10001_cte\n"
    )
    sql = _extrair_sql(saida)
    assert sql.startswith("WITH sma_10001_cte AS (")
    # o parenteses de fechamento do CTE tem um abridor correspondente
    assert sql.count("(") == sql.count(")")


def test_saida_sem_cte_continua_igual():
    """Guarda de regressão: o caminho de 1 métrica é o de TODAS as fases já medidas."""
    saida = MARCADOR + "SELECT\n  a\nFROM t\n"
    assert _extrair_sql(saida) == "SELECT\n  a\nFROM t"


def test_preambulo_do_mf_e_descartado():
    saida = ("Initiating query...\nHere is the plan\n" + MARCADOR
             + "SELECT 1 AS x\n")
    assert _extrair_sql(saida) == "SELECT 1 AS x"


def test_sem_marcador_ainda_acha_o_sql():
    """Nem toda versão do mf imprime o marcador; o corte não pode depender dele."""
    assert _extrair_sql("blá blá\nSELECT 1\n") == "SELECT 1"


def test_with_dentro_de_literal_nao_engana():
    """Âncora em início de linha: um 'with'/'select' em texto não pode virar o ponto de corte."""
    saida = MARCADOR + "SELECT 'a query with select inside' AS s\nFROM t\n"
    assert _extrair_sql(saida).startswith("SELECT 'a query with select inside'")


def test_indentacao_antes_do_with_e_tolerada():
    assert _extrair_sql(MARCADOR + "   WITH c AS (SELECT 1)\n   SELECT * FROM c\n") \
        .startswith("WITH c AS (")


def test_sem_sql_falha_alto():
    """Devolver string vazia faria o gold nascer errado; melhor explodir."""
    with pytest.raises(RuntimeError, match="não retornou SQL"):
        _extrair_sql("erro: metric not found\n")


@pytest.mark.parametrize("primeira", ["WITH x AS (", "with x as (", "SELECT 1", "select 1"])
def test_case_insensitive(primeira):
    assert _extrair_sql(MARCADOR + primeira + "\n").startswith(primeira)
