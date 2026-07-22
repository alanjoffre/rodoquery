"""Fase 6 — load test: p95 e throughput em 1 GPU, e o TESTE da hipótese do roadmap.

Hipótese prevista: *"em 6GB a inferência serializa"* — ou seja, subir a concorrência **não** aumenta
a vazão, porque o Ollama processa uma geração por vez na GPU (6 GB não cabem múltiplos contextos).

Como se testa: varre a concorrência (1, 2, 4, 8) mandando o MESMO número de requisições e mede a
vazão. Se serializa, a vazão fica ~constante e a latência p95 cresce proporcionalmente à
concorrência (fila). Se paralelizasse, a vazão subiria.

O cache spec→SQL é aquecido antes, para o gargalo medido ser a INFERÊNCIA, não o subprocess do mf.

Uso: python load_test.py [n_requisicoes_por_nivel]    (default 12)
"""
import json
import statistics as st
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rodoquery.proveniencia import carimbar

BASE = "http://127.0.0.1:8077"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 12
NIVEIS = [1, 2, 4, 8]

PERGUNTAS = [
    "Qual foi a receita por praça?",
    "Quantas transações houve por mês?",
    "Qual a taxa de suspeita por método de pagamento?",
    "Qual foi o faturamento por status?",
]


def consultar(pergunta: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}/consulta", data=json.dumps({"pergunta": pergunta}).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    return {"latencia_s": time.perf_counter() - t0, "tipo": d["tipo"]}


def _pct(v, p):
    s = sorted(v)
    return round(s[min(len(s) - 1, int(len(s) * p))], 3)


print(f"aquecendo cache ({len(PERGUNTAS)} specs)...")
for p in PERGUNTAS:
    consultar(p)

resultados = []
for c in NIVEIS:
    tarefas = [PERGUNTAS[i % len(PERGUNTAS)] for i in range(N)]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=c) as ex:
        saidas = list(ex.map(consultar, tarefas))
    parede = time.perf_counter() - t0
    lat = [s["latencia_s"] for s in saidas]
    r = {
        "concorrencia": c,
        "requisicoes": N,
        "parede_s": round(parede, 2),
        "vazao_req_por_s": round(N / parede, 3),
        "latencia_p50_s": _pct(lat, 0.50),
        "latencia_p95_s": _pct(lat, 0.95),
        "latencia_media_s": round(st.mean(lat), 3),
    }
    resultados.append(r)
    print(f"  c={c:2d}: vazao={r['vazao_req_por_s']:.3f} req/s  "
          f"p50={r['latencia_p50_s']}s p95={r['latencia_p95_s']}s  parede={r['parede_s']}s")

base = resultados[0]["vazao_req_por_s"]
ganho = {r["concorrencia"]: round(r["vazao_req_por_s"] / base, 2) for r in resultados}
serializa = all(g <= 1.30 for c, g in ganho.items() if c > 1)   # <=30% de ganho => serializa

rel = carimbar({
    "fase": "6_load_test",
    "gpu": "NVIDIA RTX 4050 Laptop, 6 GB VRAM",
    "cache_aquecido": True,
    "niveis": resultados,
    "ganho_de_vazao_vs_c1": ganho,
    "hipotese_roadmap": "em 6GB a inferencia serializa (vazao nao escala com concorrencia)",
    "hipotese_confirmada": bool(serializa),
    "leitura": ("Se a vazao fica ~constante e o p95 cresce com a concorrencia, o gargalo e a "
                "GPU processando uma geracao por vez: concorrencia so enfileira."),
})
dest = Path(__file__).resolve().parent / "reports" / "fase6" / "load_test.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nganho de vazao vs c=1: {ganho}")
print(f"hipotese 'serializa' confirmada: {serializa}")
print(f"-> {dest}")
