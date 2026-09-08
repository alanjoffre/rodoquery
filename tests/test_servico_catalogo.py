"""Qual CATÁLOGO o serving expõe no caminho ANTT (Fase 23).

A Fase 21 mostrou que o catálogo de 3 métricas fazia *rebaixamento de tipo* — perguntavam
proporção e ele respondia contagem, 6 vezes em 6 — porque expunha `automation_rate` e escondia
os irmãos da mesma partição. O de 7 corrige isso (1/8). A Fase 23 mediu o preço dessa troca no
benchmark principal: **nenhum estatisticamente detectável** (145/146 × 146/146, McNemar b=1,
c=0, p=1,0), e o serving passou a usar o rico por default.

O que se protege aqui:

1. **A fundação sintética não mudou.** O default do serviço continua sendo a sintética com
   `tier_a` — a promoção vale só para o caminho ANTT. Dez fases medidas dependem disso.
2. **`tier_a_antt` não foi substituído.** Ele é o sistema avaliado nas Fases 12–21; trocá-lo
   mudaria o SUT de tudo que já foi medido. O serving escolhe entre dois sistemas, não
   reescreve um.
3. **`/saude` diz qual catálogo está no ar.** Sem isso, a troca — que muda o vocabulário que o
   agente pode usar — seria invisível em produção.
4. **Configuração inválida mata o processo no START**, não no primeiro request de um usuário.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def servico_com(monkeypatch):
    """Recarrega o `servico` sob uma configuração e SEMPRE restaura o default no fim."""
    carregados = []

    def _carregar(**cfg):
        import rodoquery.config as c
        import rodoquery.servico as s

        for k, v in cfg.items():
            monkeypatch.setattr(c.settings, k, v)
        importlib.reload(s)
        carregados.append(s)
        return s

    yield _carregar
    if carregados:
        monkeypatch.undo()
        importlib.reload(carregados[-1])


def test_default_e_a_fundacao_sintetica_intacta():
    """Sem configuração nenhuma, nada do que foi medido nas Fases 0–10 muda."""
    import rodoquery.servico as s
    from rodoquery.sistema import tier_a

    assert s._SISTEMA is tier_a
    saude = TestClient(s.app).get("/saude").json()
    assert saude["fundacao"] == "sintetica"
    # No caminho sintético o campo é None em vez de mentir um catálogo que não governa nada.
    assert saude["catalogo_antt"] is None
    assert saude["n_metricas_expostas"] is None


def test_antt_usa_o_catalogo_rico_por_default(servico_com):
    from rodoquery.sistema_antt_rico import tier_a_antt_rico

    s = servico_com(fundacao_ativa="antt")
    assert s._SISTEMA is tier_a_antt_rico
    saude = TestClient(s.app).get("/saude").json()
    assert saude["fundacao"] == "antt"
    assert saude["catalogo_antt"] == "rico"
    assert saude["n_metricas_expostas"] == 7


def test_catalogo_basico_continua_alcancavel(servico_com):
    """Reverter a promoção tem de ser CONFIGURAÇÃO, não edição de código."""
    from rodoquery.sistema_antt import tier_a_antt

    s = servico_com(fundacao_ativa="antt", catalogo_antt="basico")
    assert s._SISTEMA is tier_a_antt
    saude = TestClient(s.app).get("/saude").json()
    assert saude["catalogo_antt"] == "basico"
    assert saude["n_metricas_expostas"] == 3


def test_catalogo_invalido_mata_no_import(servico_com):
    """Erro de configuração aparece no START, não no primeiro request de um usuário."""
    with pytest.raises(ValueError, match="RODOQUERY_CATALOGO_ANTT"):
        servico_com(fundacao_ativa="antt", catalogo_antt="setemetricas")


def test_o_sistema_avaliado_nas_fases_12_a_21_nao_foi_trocado():
    """`tier_a_antt` e `tier_a_antt_rico` são sistemas DISTINTOS, e continuam sendo.

    Se alguém 'promovesse' reescrevendo `tier_a_antt`, as Fases 12–21 deixariam de reproduzir e
    o gate nível B (que re-executa as predições congeladas) passaria a divergir. Este teste é a
    trava contra essa forma de promoção.
    """
    from rodoquery.sistema_antt import CATALOGO_ANTT, tier_a_antt
    from rodoquery.sistema_antt_rico import CATALOGO_ANTT_RICO, tier_a_antt_rico

    assert tier_a_antt is not tier_a_antt_rico
    assert CATALOGO_ANTT != CATALOGO_ANTT_RICO
    assert "só existem estas 3" in CATALOGO_ANTT
    assert "só existem estas 7" in CATALOGO_ANTT_RICO
