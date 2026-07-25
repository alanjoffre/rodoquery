"""Testes do roteador 2-tiers (Fase 14). Fixam a propriedade central: o conservador NUNCA
sobrepõe uma abstenção deliberada do Tier-A — foi o que a medição mostrou ser importante."""
from rodoquery.avaliacao import Predicao
from rodoquery.gold import Spec
from rodoquery.roteador import rotear

SPEC = Spec(metrics=["traffic_volume"])


def _tier_b_responde():
    return Predicao.com_sql("SELECT 1")


def _tier_b_abstem():
    return Predicao.abster()


def test_conservador_respeita_abstencao_do_tier_a():
    # Tier-A abstém de propósito → o conservador NÃO chama o Tier-B
    r = rotear(Predicao.abster(), spec_compila=True, tier_b=_tier_b_responde, conservador=True)
    assert r.tipo == "abster"


def test_conservador_cai_para_tier_b_quando_spec_nao_compila():
    r = rotear(Predicao.com_spec(SPEC), spec_compila=False, tier_b=_tier_b_responde,
               conservador=True)
    assert r.tipo == "sql"


def test_conservador_usa_tier_a_quando_spec_compila():
    p = Predicao.com_spec(SPEC)
    r = rotear(p, spec_compila=True, tier_b=_tier_b_responde, conservador=True)
    assert r is p


def test_ingenuo_sobrepoe_abstencao():
    # o ingênuo chama o Tier-B mesmo numa abstenção deliberada (medido como prejudicial)
    r = rotear(Predicao.abster(), spec_compila=True, tier_b=_tier_b_responde, conservador=False)
    assert r.tipo == "sql"


def test_tier_b_nao_e_chamado_a_toa():
    chamado = {"n": 0}

    def tb():
        chamado["n"] += 1
        return Predicao.com_sql("SELECT 1")

    rotear(Predicao.com_spec(SPEC), spec_compila=True, tier_b=tb, conservador=True)
    assert chamado["n"] == 0        # spec compila → Tier-B nem é avaliado (lazy)
