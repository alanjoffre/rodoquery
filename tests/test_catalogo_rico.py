"""Catálogo enriquecido da Fase 21 — a regra de modelagem, travada.

A regra é *"completar a partição onde um membro já estava exposto"*, e ela é **falseável**: se as
métricas de uma partição não somam 1,0, ou o filtro está errado, ou existe valor fora da partição
— e o catálogo estaria mentindo para o usuário.

O teste da soma toca banco e é marcado; os demais são de contrato e rodam sempre.
"""
from __future__ import annotations

import pytest

from rodoquery.config import settings
from rodoquery.sistema import PROMPT
from rodoquery.sistema_antt import CATALOGO_ANTT
from rodoquery.sistema_antt_rico import (
    CATALOGO_ANTT_RICO,
    METRICAS_RICAS,
    PARTICOES,
    tier_a_antt_rico,
)

precisa_fundacao = pytest.mark.skipif(
    not settings.antt_duckdb.exists(), reason="fundação ANTT não materializada neste checkout")


# ------------------------------------------------------------------ contrato do catalogo
def test_sao_sete_metricas():
    """3 originais + 4 irmãos de partição. Nem 6 nem 8."""
    assert len(METRICAS_RICAS) == 7


@pytest.mark.parametrize("metrica", METRICAS_RICAS)
def test_metrica_aparece_no_texto_do_catalogo(metrica):
    """Métrica que existe no contrato mas não no texto é métrica que o modelo nunca vê."""
    assert metrica in CATALOGO_ANTT_RICO


def test_particoes_tem_tres_membros_cada():
    for dim, membros in PARTICOES.items():
        assert len(membros) == 3, dim
        for m in membros:
            assert m in METRICAS_RICAS


def test_sentido_e_eixo_ficaram_de_fora():
    """A regra NÃO é 'expor tudo'. `sentido` não tinha membro exposto; `eixo` tem 19 valores."""
    assert "sentido" not in PARTICOES
    assert "categoria_eixo" not in PARTICOES
    for proibida in ("crescente_share", "decrescente_share", "eixo_share"):
        assert proibida not in CATALOGO_ANTT_RICO


def test_catalogo_nega_explicitamente_as_particoes_nao_completadas():
    """Sem isso, o near-miss de sentido/eixo viraria a mesma armadilha que a F20 mediu."""
    assert "NÃO existe proporção por sentido" in CATALOGO_ANTT_RICO


def test_o_prompt_e_o_mesmo_do_sistema_congelado():
    """Isola a variável: se o rico ganhar, o mérito é do CATÁLOGO, não de um prompt reescrito."""
    a = PROMPT.format(catalogo=CATALOGO_ANTT, pergunta="X")
    b = PROMPT.format(catalogo=CATALOGO_ANTT_RICO, pergunta="X")
    assert a.replace(CATALOGO_ANTT, "") == b.replace(CATALOGO_ANTT_RICO, "")


def test_catalogo_rico_contem_o_original_como_subconjunto():
    """As 3 métricas antigas continuam existindo — enriquecer não pode remover."""
    for m in ("traffic_volume", "automation_rate", "commercial_share"):
        assert m in METRICAS_RICAS


# ---------------------------------------------------------------------- comportamento
def test_provedor_injetado_e_usado(monkeypatch):
    import rodoquery.sistema_antt_rico as sr

    monkeypatch.setattr(sr, "_chamar_ollama",
                        lambda *a, **k: pytest.fail("não deveria chamar o Ollama"))
    p = tier_a_antt_rico("Qual a proporção de cobrança manual?",
                         provedor=lambda *a: ('{"metrics": ["manual_share"], "group_by": [],'
                                              ' "where": null, "order_by": [], "limit": null,'
                                              ' "ordenado": false}',
                                              {"modelo_efetivo": "claude-opus-5"}))
    assert p.spec.metrics == ["manual_share"]
    assert p.meta["modelo"] == "claude-opus-5"


def test_default_continua_ollama(monkeypatch):
    import rodoquery.sistema_antt_rico as sr

    monkeypatch.setattr(sr, "_chamar_ollama", lambda *a, **k: ("ABSTENHO", {}))
    assert tier_a_antt_rico("Qual a receita?").tipo == "abster"


# ------------------------------------------------------- a prova da regra: as particoes fecham
@precisa_fundacao
@pytest.mark.parametrize("dimensao", sorted(PARTICOES))
def test_particoes_somam_um(dimensao):
    """Se não soma 1,0, o filtro está errado ou há valor fora da partição."""
    from rodoquery.gold import FUNDACAO_ANTT, Spec, compilar_spec, executar_gold

    db = settings.antt_suite_dir / "antt_p0.duckdb"
    total = 0.0
    for metrica in PARTICOES[dimensao]:
        linhas = executar_gold(
            compilar_spec(Spec(metrics=[metrica]), fundacao=FUNDACAO_ANTT), db)
        total += float(linhas[0][0])
    assert total == pytest.approx(1.0, abs=1e-9), f"{dimensao} soma {total}"
