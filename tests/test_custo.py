"""Testes de custo — checam a ARITMÉTICA (as premissas são do usuário, não do teste)."""
from rodoquery.custo import PremissasEnergia, custo_api_equivalente, custo_local


def test_custo_local_aritmetica():
    # 3600 s a 1000 W = 1 kWh; a R$ 1,00/kWh → R$ 1,00 por consulta
    r = custo_local(3600.0, PremissasEnergia(potencia_gpu_w=1000.0, tarifa_rs_kwh=1.0))
    assert abs(r["rs_por_consulta"] - 1.0) < 1e-9
    assert abs(r["rs_por_1k"] - 1000.0) < 1e-6


def test_custo_local_escala_linear_com_latencia():
    p = PremissasEnergia()
    a = custo_local(1.0, p)["rs_por_1k"]
    b = custo_local(2.0, p)["rs_por_1k"]
    assert abs(b - 2 * a) < 1e-3   # tolerância = arredondamento de rs_por_1k (4 casas)


def test_custo_local_expoe_premissas():
    # premissas têm de aparecer no resultado (honestidade: quem lê sabe o que foi assumido)
    r = custo_local(1.0)
    assert "premissas" in r and "ressalva" in r


def test_custo_api_aritmetica():
    # 1000 tokens entrada a US$1/M + 0 saída → US$0,001/consulta → US$1,00 por 1k
    r = custo_api_equivalente(1000, 0, usd_por_milhao_entrada=1.0,
                              usd_por_milhao_saida=0.0, usd_brl=5.0)
    assert abs(r["usd_por_1k"] - 1.0) < 1e-9
    assert abs(r["rs_por_1k"] - 5.0) < 1e-9
