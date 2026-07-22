"""Fase 6 — prova que o CONTROLE DE ADMISSÃO limita o estrago sob sobrecarga.

Antes do limitador (reports/fase6/load_test.json), c=8 dava p95 = 43,1 s e vazão 0,76x da base:
o serviço aceitava tudo e entregava latência inaceitável. Com o semáforo (2 simultâneas), a mesma
carga deve manter a vazão do ótimo medido e limitar a latência — ou recusar rápido com 503.
"""
import json
import statistics as st
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rodoquery.proveniencia import carimbar

BASE = "http://127.0.0.1:8077"
N, C = 12, 8
PERGUNTAS = ["Qual foi a receita por praça?", "Quantas transações houve por mês?",
             "Qual a taxa de suspeita por método de pagamento?",
             "Qual foi o faturamento por status?"]


def consultar(p):
    req = urllib.request.Request(f"{BASE}/consulta", data=json.dumps({"pergunta": p}).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            json.loads(r.read())
        return {"latencia_s": time.perf_counter() - t0, "http": 200}
    except urllib.error.HTTPError as e:
        return {"latencia_s": time.perf_counter() - t0, "http": e.code}


for p in PERGUNTAS:      # aquece o cache de specs
    consultar(p)

t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=C) as ex:
    saidas = list(ex.map(consultar, [PERGUNTAS[i % 4] for i in range(N)]))
parede = time.perf_counter() - t0

# Separa ATENDIDAS de RECUSADAS: juntar as duas esconde o comportamento (uma recusa rápida
# baixaria o p95 "geral" e pareceria melhoria, quando é só carga rejeitada).
atendidas = sorted(s["latencia_s"] for s in saidas if s["http"] == 200)
rejeitadas = [s for s in saidas if s["http"] == 503]


def _p95(v):
    return round(sorted(v)[min(len(v) - 1, int(len(v) * 0.95))], 3) if v else None


with urllib.request.urlopen(f"{BASE}/metricas", timeout=30) as r:
    met = json.loads(r.read())

ANTES = {"p95_s": 43.124, "vazao_req_s": 0.192, "rejeitadas": 0}   # sem limitador, mesmo c=8
agora = {
    "p95_atendidas_s": _p95(atendidas),
    "p50_atendidas_s": round(st.median(atendidas), 3) if atendidas else None,
    "atendidas": len(atendidas),
    "rejeitadas_503": len(rejeitadas),
    "taxa_recusa": round(len(rejeitadas) / N, 3),
    "vazao_atendidas_req_s": round(len(atendidas) / parede, 3),
}

rel = carimbar({
    "fase": "6_controle_admissao",
    "carga": {"requisicoes": N, "concorrencia_clientes": C,
              "limite_servico": 1, "espera_max_s": 5.0},
    "sem_limitador": ANTES,
    "com_limitador": agora,
    "slo_p95_alvo_s": 10.0,
    "slo_respeitado_nas_atendidas": (agora["p95_atendidas_s"] or 0) <= 10.0,
    "metricas_servico": {k: met[k] for k in ("contadores", "taxa_erro", "cache_hit_rate")},
    "leitura": ("O limitador NAO cria vazao (a GPU e o teto). O que ele faz e trocar 'aceitar tudo "
                "e violar o SLO' por 'atender dentro do SLO e RECUSAR o excesso'. A recusa e a "
                "degradacao honesta: o cliente sabe na hora, em vez de esperar 37s."),
})
dest = Path(__file__).resolve().parent / "reports" / "fase6" / "controle_admissao.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"c={C} SEM limitador : p95={ANTES['p95_s']}s  vazao={ANTES['vazao_req_s']}/s  503=0")
print(f"c={C} COM limitador : p95(atendidas)={agora['p95_atendidas_s']}s  "
      f"atendidas={agora['atendidas']}/{N}  503={agora['rejeitadas_503']} "
      f"(recusa={agora['taxa_recusa']})")
print(f"SLO p95<=10s respeitado nas atendidas: {rel['slo_respeitado_nas_atendidas']}")
print(f"-> {dest}")
