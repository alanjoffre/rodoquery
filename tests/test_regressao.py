"""Testes do gate de regressão (Fase 5).

O ponto mais importante aqui: o gate tem de PEGAR um relatório adulterado (número bonito no topo
que não bate com os itens) e tem de NÃO falhar por ruído dentro da margem medida.
"""
import hashlib

from rodoquery.regressao import (
    Limiares,
    carregar_margem_medida,
    gate_contrato,
    gate_live,
    verificar_selo,
)


def _itens(n_resp_ok, n_resp, n_abs_ok, n_abs):
    itens = [{"abstencao": False, "correto": i < n_resp_ok} for i in range(n_resp)]
    itens += [{"abstencao": True, "correto": i < n_abs_ok} for i in range(n_abs)]
    return itens


def _relatorio(ex_tier=0.976, ex_base=0.4286, p=0.0, adulterar=False):
    tier = _itens(41, 42, 11, 11)
    base = _itens(18, 42, 10, 11)
    bloco_tier_ex = {"n": 42, "acertos": 100 if adulterar else 41, "taxa": ex_tier}
    return {
        "sistemas": {
            "tier_a": {"execution_accuracy_respondiveis": bloco_tier_ex,
                       "acuracia_abstencao": {"n": 11, "acertos": 11, "taxa": 1.0}},
            "sql_cru": {"execution_accuracy_respondiveis": {"n": 42, "acertos": 18,
                                                            "taxa": ex_base},
                        "acuracia_abstencao": {"n": 11, "acertos": 10, "taxa": 0.9091}},
        },
        "resultados_por_item": {"tier_a": tier, "sql_cru": base},
        "mcnemar_tier_a_vs_sql_cru_respondiveis": {"p_valor": p},
    }


def test_gate_contrato_passa_no_relatorio_real():
    r = gate_contrato(_relatorio(), Limiares())
    assert r.ok, r.relatorio()


def test_gate_contrato_pega_relatorio_adulterado():
    # agregado no topo não bate com os itens → tem de falhar a coerência
    r = gate_contrato(_relatorio(adulterar=True), Limiares())
    assert not r.ok
    assert any(not c["ok"] and "coerencia" in c["nome"] for c in r.checagens)


def test_gate_contrato_falha_se_ex_regride():
    r = gate_contrato(_relatorio(ex_tier=0.50), Limiares(ex_minimo=0.90))
    assert not r.ok
    assert any(not c["ok"] and c["nome"] == "ex_minimo" for c in r.checagens)


def test_gate_contrato_falha_se_perde_vantagem_sobre_baseline():
    r = gate_contrato(_relatorio(ex_tier=0.95, ex_base=0.94), Limiares(vantagem_minima_pp=30.0))
    assert not r.ok
    assert any(not c["ok"] and c["nome"] == "vantagem_sobre_baseline" for c in r.checagens)


def test_gate_contrato_falha_sem_significancia():
    r = gate_contrato(_relatorio(p=0.42), Limiares())
    assert not r.ok
    assert any(not c["ok"] and c["nome"] == "mcnemar_significante" for c in r.checagens)


def test_gate_live_tolera_ruido_dentro_da_margem():
    # queda de 2pp com margem medida de 5pp NÃO é regressão — é o ruído do SUT
    r = gate_live(0.956, referencia=0.976, limiares=Limiares(ex_minimo=0.5, margem_flaky=0.05))
    assert r.ok, r.relatorio()


def test_gate_live_pega_queda_maior_que_a_margem():
    r = gate_live(0.80, referencia=0.976, limiares=Limiares(ex_minimo=0.5, margem_flaky=0.05))
    assert not r.ok


def test_verificar_selo(tmp_path):
    alvo = tmp_path / "golden_test.jsonl"
    alvo.write_text("linha\n", encoding="utf-8")
    sha = tmp_path / "golden_test.sha256"
    sha.write_text(hashlib.sha256(alvo.read_bytes()).hexdigest() + "\n", encoding="utf-8")
    assert verificar_selo(alvo, sha)["ok"]
    alvo.write_text("adulterado\n", encoding="utf-8")   # golden mudou depois do pré-registro
    assert not verificar_selo(alvo, sha)["ok"]


def test_margem_vem_da_medicao(tmp_path):
    f = tmp_path / "flakiness.json"
    f.write_text('{"ex_max": 1.0, "ex_min": 0.947}', encoding="utf-8")
    assert carregar_margem_medida(f) == 0.053
