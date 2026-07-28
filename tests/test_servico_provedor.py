"""Serving com provedor plugável (Fase 18). Nenhum teste toca a API nem exige chave.

O que se protege aqui:

1. **O default não mudou.** Serviço sem configuração = Ollama, semáforo 1, exatamente o que as
   Fases 6–17b mediram. Um serviço que passasse a gastar dinheiro por mudança de default seria
   a pior regressão possível deste projeto.
2. **A concorrência não é herdada.** O limite 1 veio de "1 GPU não paraleliza" (Fase 6); no
   caminho de API essa premissa não existe. O serviço tem de dizer, em `/saude`, se o número que
   está usando foi MEDIDO ou é só um default plausível.
3. **`/saude` não mente sobre o modelo.** No caminho de API, reportar `settings.modelo_sut` diria
   `qwen2.5-coder:7b` — o mesmo descuido que fez as predições da Fase 18 nascerem mal rotuladas.
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def servico_com(monkeypatch):
    """Recarrega o `servico` sob uma configuração, e SEMPRE restaura o default no fim.

    O provedor é escolhido no import (para o processo morrer no start, não num request), então
    testá-lo exige reload. Sem o restore no finally, um teste contaminaria todos os seguintes.
    """
    carregados = []

    def _carregar(**cfg):
        import rodoquery.config as c
        import rodoquery.provedor as p
        import rodoquery.servico as s

        for k, v in cfg.items():
            monkeypatch.setattr(c.settings, k, v)
        # dublê: não precisa de chave, SDK, nem rede
        monkeypatch.setattr(p, "ProvedorAnthropic", lambda **kw: _ProvedorFalso(**kw))
        importlib.reload(s)
        carregados.append(s)
        return s

    yield _carregar

    if carregados:
        monkeypatch.undo()
        importlib.reload(carregados[-1])   # devolve o módulo ao default


class _ProvedorFalso:
    nome = "anthropic"

    def __init__(self, **kw):
        self.modelo_padrao = kw.get("modelo_padrao", "claude-opus-5")
        self.custo_usd = 0.25
        self.chamadas = 10
        self.tokens_cache_leitura = 7000

    def __call__(self, prompt, modelo, temperatura):
        return "ABSTENHO", {"modelo_efetivo": self.modelo_padrao}


# ------------------------------------------------------------------ o default nao pode mudar
def test_default_e_ollama_com_semaforo_medido():
    import rodoquery.servico as s

    assert s._PROVEDOR is None
    assert s.MAX_INFERENCIA_SIMULTANEA == 1        # o numero MEDIDO na Fase 6
    assert s.CONCORRENCIA_MEDIDA is True

    saude = TestClient(s.app).get("/saude").json()
    assert saude["provedor"] == "ollama"
    assert saude["modelo"] == "qwen2.5-coder:7b"
    assert saude["concorrencia_medida"] is True


def test_metricas_sem_custo_no_caminho_local():
    import rodoquery.servico as s

    assert TestClient(s.app).get("/metricas").json()["custo"] is None


# ------------------------------------------------------------------------ o caminho de API
def test_provedor_anthropic_entra_por_configuracao(servico_com):
    s = servico_com(provedor="anthropic", modelo_api="claude-opus-5")
    assert s._PROVEDOR is not None
    assert s._PROVEDOR.modelo_padrao == "claude-opus-5"


def test_concorrencia_da_api_nao_herda_a_medida_da_gpu(servico_com):
    """1 veio de 'uma GPU nao paraleliza'. Na API o gargalo e rate limit — herdar estrangularia."""
    s = servico_com(provedor="anthropic")
    assert s.MAX_INFERENCIA_SIMULTANEA == 8
    assert s.CONCORRENCIA_MEDIDA is False          # e /saude admite que NAO foi medido
    assert TestClient(s.app).get("/saude").json()["concorrencia_medida"] is False


def test_saude_reporta_o_modelo_que_de_fato_responde(servico_com):
    s = servico_com(provedor="anthropic", modelo_api="claude-opus-5")
    saude = TestClient(s.app).get("/saude").json()
    assert saude["modelo"] == "claude-opus-5"
    assert saude["modelo"] != "qwen2.5-coder:7b"   # o descuido da 1a corrida da Fase 18
    assert saude["provedor"] == "anthropic"


def test_metricas_expoem_custo_acumulado(servico_com):
    """Sem isto, descobrir que o serviço queima crédito só na fatura — tarde demais."""
    s = servico_com(provedor="anthropic")
    custo = TestClient(s.app).get("/metricas").json()["custo"]
    assert custo["usd_acumulado"] == 0.25
    assert custo["chamadas"] == 10
    assert custo["usd_por_chamada"] == pytest.approx(0.025)


def test_override_explicito_da_concorrencia(servico_com):
    s = servico_com(provedor="anthropic", max_inferencia_simultanea=3)
    assert s.MAX_INFERENCIA_SIMULTANEA == 3


def test_provedor_invalido_falha_no_start(servico_com):
    """Falhar no import e melhor que falhar no request de um usuario."""
    with pytest.raises(ValueError, match="RODOQUERY_PROVEDOR invalido"):
        servico_com(provedor="openai")
