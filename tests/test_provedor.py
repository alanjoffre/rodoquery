"""Testes do provedor plugável (Fase 18). NENHUM toca a API — custo zero, sempre.

O que estes testes protegem, em ordem de importância:

1. **O default não mudou.** Se `provedor=None` deixar de chamar o Ollama, as Fases 0–16 param de
   ser reproduzíveis e ninguém percebe até a próxima execução. É o teste que mais importa aqui.
2. **O corte do prompt é sem perda.** O caching depende de partir o prompt em system+user; se o
   corte perder ou duplicar um byte, o SUT recebe um prompt diferente do que o Qwen recebeu e a
   comparação vira ruído. Esse é o modo de falha silencioso desta fase.
3. **A conta de custo bate.** Um relatório de gasto errado é pior que nenhum.
"""
from __future__ import annotations

import json

import pytest

from rodoquery.provedor import (
    PRECOS,
    ProvedorAnthropic,
    ProvedorOllama,
    _carregar_env,
    _limpar_tags,
    estimar_custo,
    obter_provedor,
)


# ---------------------------------------------------------------------------- default intocado
def test_default_e_ollama():
    assert isinstance(obter_provedor(), ProvedorOllama)
    assert isinstance(obter_provedor("ollama"), ProvedorOllama)


def test_provedor_desconhecido_falha_alto():
    with pytest.raises(ValueError, match="provedor desconhecido"):
        obter_provedor("openai")


def test_tier_a_sem_provedor_usa_ollama(monkeypatch):
    """`provedor=None` tem de cair no `_chamar_ollama` — o caminho das Fases 11–16."""
    from rodoquery import sistema_antt

    vistos = {}

    def falso(prompt, modelo, temperatura):
        vistos["prompt"] = prompt
        return '{"metrics": ["traffic_volume"], "group_by": [], "where": null,' \
               ' "order_by": [], "limit": null, "ordenado": false}', {}

    monkeypatch.setattr(sistema_antt, "_chamar_ollama", falso)
    p = sistema_antt.tier_a_antt("Quantos veículos passaram?")
    assert p.tipo == "spec"
    assert "traffic_volume" in vistos["prompt"]      # o catálogo da ANTT foi injetado


def test_sql_cru_sem_provedor_usa_ollama(monkeypatch):
    from rodoquery import baselines_antt

    monkeypatch.setattr(baselines_antt, "_chamar_ollama",
                        lambda *a, **k: ("SELECT sum(volume) FROM fct_traffic_volume", {}))
    assert baselines_antt.sql_cru_antt("Quantos veículos?").tipo == "sql"


def test_provedor_injetado_substitui_o_ollama(monkeypatch):
    """E o injetado recebe (prompt, modelo, temperatura) — o mesmo contrato."""
    from rodoquery import sistema_antt

    monkeypatch.setattr(sistema_antt, "_chamar_ollama",
                        lambda *a, **k: pytest.fail("não deveria chamar o Ollama"))
    chamadas = []

    def fake(prompt, modelo, temperatura):
        chamadas.append((modelo, temperatura))
        return "ABSTENHO", {"tokens_prompt": 700, "tokens_saida": 3}

    p = sistema_antt.tier_a_antt("Qual a receita?", provedor=fake)
    assert p.tipo == "abster"
    assert len(chamadas) == 1
    assert p.meta["tokens_prompt"] == 700          # a telemetria do provedor chega na Predicao


# ------------------------------------------------- proveniencia: o artefato nao pode mentir
# Bug real, pego DEPOIS da 1a corrida completa: as 342 predicoes ficaram gravadas com
# `qwen2.5-coder:7b` porque `modelo or settings.modelo_sut` resolve para o default local e o
# provedor nunca reportava qual modelo de fato usou. O EX nao depende disso; a auditabilidade
# do artefato congelado depende inteiramente.
@pytest.mark.parametrize("fn_nome, resposta", [
    ("tier_a_antt", '{"metrics": ["traffic_volume"], "group_by": [], "where": null,'
                    ' "order_by": [], "limit": null, "ordenado": false}'),
    ("sql_cru_antt", "SELECT sum(volume) FROM fct_traffic_volume"),
])
def test_predicao_grava_o_modelo_que_de_fato_respondeu(fn_nome, resposta):
    import rodoquery.baselines_antt as ba
    import rodoquery.sistema_antt as sa

    fn = sa.tier_a_antt if fn_nome == "tier_a_antt" else ba.sql_cru_antt
    p = fn("Quantos veículos?",
           provedor=lambda *a: (resposta, {"modelo_efetivo": "claude-opus-5"}))
    assert p.meta["modelo"] == "claude-opus-5"
    assert p.meta["modelo"] != "qwen2.5-coder:7b"


def test_caminho_ollama_mantem_o_modelo_local(monkeypatch):
    """Sem `modelo_efetivo` na telemetria, nada muda — as Fases 0–16 gravam o mesmo de sempre."""
    from rodoquery import sistema_antt

    monkeypatch.setattr(sistema_antt, "_chamar_ollama", lambda *a, **k: ("ABSTENHO", {}))
    assert sistema_antt.tier_a_antt("Qual a receita?").meta["modelo"] == "qwen2.5-coder:7b"


def test_provedor_anthropic_reporta_modelo_efetivo():
    """Mesmo recebendo o nome do modelo LOCAL, a telemetria diz qual modelo da API respondeu."""
    p = _provedor_com_resposta(_RespostaFalsa("ABSTENHO", ent=40, sai=5))
    _, tel = p("a\nPergunta: b", "qwen2.5-coder:7b", 0.0)   # nome que a API nao conhece
    assert tel["modelo_efetivo"] == "claude-opus-5"


# --------------------------------------------------------------------- corte do prompt sem perda
def _sem_cliente() -> ProvedorAnthropic:
    """Constrói o provedor sem SDK nem chave: `_cliente` preenchido pula o `__post_init__`."""
    return ProvedorAnthropic(_cliente=object())


@pytest.mark.parametrize("sistema, kwargs", [
    ("tier_a", {}),
    ("sql_cru", {}),
])
def test_corte_do_prompt_e_sem_perda(sistema, kwargs):
    from rodoquery.baselines_antt import PROMPT_ANTT, SCHEMA_ANTT
    from rodoquery.sistema import PROMPT
    from rodoquery.sistema_antt import CATALOGO_ANTT

    prompt = (PROMPT.format(catalogo=CATALOGO_ANTT, pergunta="Quantos veículos por sentido?")
              if sistema == "tier_a"
              else PROMPT_ANTT.format(schema=SCHEMA_ANTT, pergunta="Quantos veículos por sentido?"))
    prefixo, sufixo = _sem_cliente()._partir(prompt)
    assert prefixo + sufixo == prompt              # byte a byte: é isto que mantém a comparação
    assert sufixo.startswith("\nPergunta: ")
    assert "Quantos veículos por sentido?" in sufixo
    assert "Quantos veículos por sentido?" not in prefixo   # o cacheável não pode variar


def test_prefixo_e_identico_entre_perguntas():
    """Se o prefixo variasse, o cache nunca pegaria e o custo seria o cheio, em silêncio."""
    from rodoquery.sistema import PROMPT
    from rodoquery.sistema_antt import CATALOGO_ANTT

    p = _sem_cliente()
    a, _ = p._partir(PROMPT.format(catalogo=CATALOGO_ANTT, pergunta="Quantos veículos?"))
    b, _ = p._partir(PROMPT.format(catalogo=CATALOGO_ANTT, pergunta="Qual a taxa de automação?"))
    assert a == b


def test_prefixo_passa_do_minimo_de_cache_do_opus5():
    """~750 tokens > 512 (mínimo do Opus 5). Se cair abaixo, o custo triplica sem aviso."""
    from rodoquery.sistema import PROMPT
    from rodoquery.sistema_antt import CATALOGO_ANTT

    prefixo, _ = _sem_cliente()._partir(
        PROMPT.format(catalogo=CATALOGO_ANTT, pergunta="X"))
    assert len(prefixo) // 4 > PRECOS["claude-opus-5"].minimo_cache


def test_prompt_sem_marcador_vai_inteiro_para_o_usuario():
    """Degradar o CUSTO é aceitável; degradar a fidelidade do prompt não é."""
    prefixo, sufixo = _sem_cliente()._partir("prompt sem o marcador esperado")
    assert prefixo == ""
    assert sufixo == "prompt sem o marcador esperado"


# ------------------------------------------------------------------------ limpeza de tags vazadas
@pytest.mark.parametrize("bruto, esperado", [
    ("<thinking>vou abster</thinking>ABSTENHO", "ABSTENHO"),
    ("<thinking>\nmulti\nlinha\n</thinking>\n{\"metrics\": []}", '{"metrics": []}'),
    ('{"metrics": ["traffic_volume"]}', '{"metrics": ["traffic_volume"]}'),
])
def test_limpar_tags(bruto, esperado):
    assert _limpar_tags(bruto) == esperado


def test_tag_vazada_nao_cria_abstencao_falsa():
    """O risco real: raciocínio contendo 'ABSTENHO' dispararia abstenção falsa sem a limpeza."""
    bruto = '<thinking>não devo ABSTENHO aqui</thinking>{"metrics": ["traffic_volume"]}'
    assert "ABSTENHO" not in _limpar_tags(bruto).upper()


# -------------------------------------------------------------------------------- conta de custo
def test_custo_soma_as_quatro_faixas():
    p = PRECOS["claude-opus-5"]        # $5 entrada / $25 saída por 1M
    # 1M frescos + 1M escrita(1,25x) + 1M leitura(0,10x) + 1M saída
    esperado = 5.0 + 5.0 * 1.25 + 5.0 * 0.10 + 25.0
    assert p.custo(1_000_000, 1_000_000, 1_000_000, 1_000_000) == pytest.approx(esperado)


def test_cache_de_leitura_e_dez_por_cento():
    p = PRECOS["claude-opus-5"]
    assert p.custo(0, 0, cache_r=1_000_000) == pytest.approx(p.custo(1_000_000, 0) * 0.10)


def test_estimativa_reconhece_quem_nao_cacheia():
    """Haiku exige 4096 tokens de prefixo; o nosso tem ~1000. Cacheia => False, e custa mais."""
    arg = dict(n_itens=186, tokens_prompt_medio=788.5, tokens_saida_medio=61.2,
               tokens_prefixo=750)
    assert estimar_custo("claude-haiku-4-5", **arg)["cacheia"] is False
    assert estimar_custo("claude-opus-5", **arg)["cacheia"] is True


def test_cache_reduz_o_custo_estimado_do_opus5():
    arg = dict(modelo="claude-opus-5", n_itens=186, tokens_prompt_medio=788.5,
               tokens_saida_medio=61.2)
    com = estimar_custo(tokens_prefixo=750, **arg)["custo_usd_estimado"]
    sem = estimar_custo(tokens_prefixo=100, **arg)["custo_usd_estimado"]   # abaixo do mínimo
    assert com < sem


def test_opus5_estimado_cabe_no_orcamento_declarado():
    """Trava viva: se o preço ou o prompt crescer, este teste denuncia antes da cobrança."""
    total = sum(
        estimar_custo("claude-opus-5", 186, 788.5, 61.2, 750)["custo_usd_estimado"]
        for _ in range(2)          # o par: Tier-A + sql_cru
    )
    assert total < 2.00


# ------------------------------------------------------------------------------ carregamento .env
def test_carregar_env_le_arquivo_e_respeita_ambiente(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comentário\nANTHROPIC_API_KEY='sk-ant-do-arquivo'\nVAZIO\n",
                   encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _carregar_env(env)
    import os
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-do-arquivo"

    # variável já exportada TEM precedência (setdefault, não sobrescrita)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-do-ambiente")
    _carregar_env(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-do-ambiente"


def test_carregar_env_sem_arquivo_nao_explode(tmp_path):
    _carregar_env(tmp_path / "nao-existe.env")      # silencioso de propósito


def test_provedor_anthropic_sem_chave_falha_com_instrucao(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("rodoquery.provedor._carregar_env", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY ausente"):
        ProvedorAnthropic()


# -------------------------------------------------------------- telemetria compatível com Ollama
class _RespostaFalsa:
    """Dublê do objeto de resposta do SDK — evita depender do pacote nos testes."""

    stop_reason = "end_turn"

    def __init__(self, texto, ent, sai, cw=0, cr=0):
        self.content = [type("B", (), {"type": "text", "text": texto})()]
        self.usage = type("U", (), {
            "input_tokens": ent, "output_tokens": sai,
            "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr,
        })()


def _provedor_com_resposta(resp) -> ProvedorAnthropic:
    cliente = type("C", (), {"messages": type("M", (), {
        "create": staticmethod(lambda **kw: resp)})()})()
    return ProvedorAnthropic(_cliente=cliente)


def test_telemetria_tem_as_chaves_do_ollama():
    """As predições congeladas e o relatório da Fase 5 leem estas chaves. Faltar uma quebra tudo."""
    p = _provedor_com_resposta(_RespostaFalsa("ABSTENHO", ent=40, sai=5, cw=0, cr=750))
    _, tel = p("prefixo\nPergunta: x\nJSON:", "claude-opus-5", 0.0)
    for chave in ("latencia_s", "tokens_prompt", "tokens_saida", "eval_s", "carga_modelo_s"):
        assert chave in tel


def test_tokens_prompt_inclui_o_cache():
    """Reportar só os frescos faria o total de entrada MENTIR para menos no relatório de custo."""
    p = _provedor_com_resposta(_RespostaFalsa("ABSTENHO", ent=40, sai=5, cw=10, cr=750))
    _, tel = p("prefixo\nPergunta: x\nJSON:", "claude-opus-5", 0.0)
    assert tel["tokens_prompt"] == 40 + 10 + 750


def test_acumuladores_e_relatorio():
    p = _provedor_com_resposta(_RespostaFalsa("ABSTENHO", ent=40, sai=5, cw=0, cr=750))
    for _ in range(3):
        p("prefixo\nPergunta: x\nJSON:", "claude-opus-5", 0.0)
    r = p.relatorio()
    assert r["chamadas"] == 3
    assert r["tokens_saida"] == 15
    assert r["tokens_cache_leitura"] == 2250
    assert r["custo_usd"] == pytest.approx(p.custo_usd, abs=1e-4)
    assert r["custo_usd_por_chamada"] == pytest.approx(p.custo_usd / 3, abs=1e-6)


def test_temperatura_e_ignorada_sem_explodir():
    """Claude >= 4.7 rejeita `temperature` com 400; o chamador não precisa saber disso."""
    enviado = {}
    resp = _RespostaFalsa("ABSTENHO", ent=40, sai=5)
    cliente = type("C", (), {"messages": type("M", (), {
        "create": staticmethod(lambda **kw: (enviado.update(kw), resp)[1])})()})()
    ProvedorAnthropic(_cliente=cliente)("a\nPergunta: b", "claude-opus-5", 0.7)
    assert "temperature" not in enviado
    assert "top_k" not in enviado
    assert enviado["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_predicoes_congeladas_da_fase12_continuam_legiveis():
    """Guarda de regressão: o formato do congelamento não pode ter mudado com a Fase 18."""
    from pathlib import Path

    fp = (Path(__file__).resolve().parents[1] / "reports" / "fase12"
          / "predicoes_tier_a_antt_test.json")
    if not fp.exists():
        pytest.skip("predições da Fase 12 ausentes neste checkout")
    d = json.loads(fp.read_text(encoding="utf-8"))
    assert len(d) == 186
    assert {"tipo", "meta"} <= set(next(iter(d.values())))
