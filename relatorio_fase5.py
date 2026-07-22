"""Fase 5 — observabilidade + custo R$/1k, a partir da telemetria MEDIDA na medição de flakiness.

Consome reports/fase5/flakiness.json (latência, tokens) e produz o painel de operação:
latência p50/p95, tokens por consulta, custo local (energia) e o equivalente em API por token.
"""
import json
from pathlib import Path

from rodoquery.custo import PremissasEnergia, custo_api_equivalente, custo_local
from rodoquery.golden import carregar
from rodoquery.proveniencia import carimbar
from rodoquery.regressao import carregar_margem_medida

REPO = Path(__file__).resolve().parent
FLAKY = REPO / "reports" / "fase5" / "flakiness.json"
f = json.loads(FLAKY.read_text(encoding="utf-8"))
# contagem derivada do próprio golden (não é medição): define o piso de 1 item da margem
n_resp = sum(1 for it in carregar(REPO / "golden" / "golden_dev.jsonl") if not it.eh_abstencao)

n_itens = f["n_itens_dev"]
lat_media = f["latencia_s"]["media"]
tok_in = f["tokens_por_run"]["prompt"] / n_itens
tok_out = f["tokens_por_run"]["saida_media"] / n_itens

local = custo_local(lat_media, PremissasEnergia())
# Tarifas ILUSTRATIVAS de uma API por token — parâmetros, não preço cravado de fornecedor.
api = custo_api_equivalente(tok_in, tok_out, usd_por_milhao_entrada=0.30,
                            usd_por_milhao_saida=1.20, usd_brl=5.40)

rel = carimbar({
    "fase": "5_observabilidade_custo",
    "latencia_s": f["latencia_s"],
    "tokens_por_consulta": {"entrada": round(tok_in, 1), "saida": round(tok_out, 1)},
    "vazao_consultas_por_min": round(60 / lat_media, 1) if lat_media else None,
    "custo_local_energia": local,
    "custo_api_equivalente_ILUSTRATIVO": api,
    "estabilidade": {
        "ex_media": f["ex_media"], "ex_desvio": f["ex_desvio"],
        "amplitude_pp": f["amplitude_pp"],
        "margem_para_gate_live": carregar_margem_medida(FLAKY, n_resp),
        "margem_justificativa": (f"max(amplitude medida {f['amplitude_pp']}pp, 1 item de {n_resp}) "
                                 "— 5 runs mostram variância baixa, não nula"),
        "n_itens_instaveis": f["n_itens_instaveis"],
    },
    "leitura": ("Custo local é ENERGIA sob premissas rotuladas; o valor honesto é a ordem de "
                "grandeza e a comparação estrutural com API por token."),
})
dest = REPO / "reports" / "fase5" / "observabilidade_custo.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"latência p50={f['latencia_s']['p50']}s p95={f['latencia_s']['p95']}s "
      f"| vazão ~{rel['vazao_consultas_por_min']}/min")
print(f"tokens/consulta: entrada={rel['tokens_por_consulta']['entrada']} "
      f"saída={rel['tokens_por_consulta']['saida']}")
print(f"custo local (energia): R$ {local['rs_por_1k']}/1k  [premissas: "
      f"{local['premissas']['potencia_gpu_w']}W, R$ {local['premissas']['tarifa_rs_kwh']}/kWh]")
print(f"custo API equivalente (ILUSTRATIVO): R$ {api['rs_por_1k']}/1k")
print(f"estabilidade: EX {f['ex_media']}±{f['ex_desvio']} amplitude={f['amplitude_pp']}pp "
      f"| margem p/ gate live={rel['estabilidade']['margem_para_gate_live']}")
print(f"-> {dest}")
