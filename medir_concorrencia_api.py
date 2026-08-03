"""Fase 21 (#5) — a concorrência do caminho de API, MEDIDA.

## A dívida que isto quita

O semáforo do serving é 1 porque a Fase 6 mediu que **uma GPU não paraleliza**: c=4 derruba a
vazão para 0,75× e o p95 de 4,4 s para 43 s. No caminho de API essa premissa não existe — o
gargalo é rate limit, não VRAM —, então o default virou 8. **Escolhido por raciocínio, não
medido**, e `/saude` admite isso em `concorrencia_medida: false`.

Isto mede. O que importa não é o número bruto de vazão (depende do tier da conta e do horário),
e sim a **forma da curva**: se a vazão escala com a concorrência, o default 8 é defensável; se
satura ou cai, não é — e aí o serving estaria estrangulando ou enfileirando por nada.

Mede no PROVEDOR, não via HTTP, de propósito: subir o uvicorn acrescentaria FastAPI, semáforo e
rede à medição, e a pergunta aqui é sobre a API. O semáforo do serving é justamente o que se
quer dimensionar — medi-lo junto seria circular.

Uso: python medir_concorrencia_api.py --confirmar [--n 6]
"""
import argparse
import json
import statistics as st
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rodoquery.provedor import ProvedorAnthropic
from rodoquery.proveniencia import carimbar
from rodoquery.sistema import PROMPT
from rodoquery.sistema_antt import CATALOGO_ANTT

REPO = Path(__file__).resolve().parent
D = REPO / "reports" / "fase21"
D.mkdir(parents=True, exist_ok=True)

# Perguntas curtas e reais do catálogo; o que se mede é transporte, não acerto.
PERGUNTAS = [
    "Quantos veículos passaram por sentido?",
    "Qual a taxa de automação por concessionária?",
    "Volume por mês?",
    "Participação de comerciais por praça?",
    "Quantos veículos passaram em cobrança manual?",
    "Volume por categoria de eixo?",
]
NIVEIS = (1, 2, 4, 8)
# Fase 6, MESMA métrica, no caminho local com 1 GPU — para comparar a FORMA da curva.
GPU_LOCAL = {1: 1.00, 2: 1.11, 4: 0.75, 8: 0.76}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmar", action="store_true")
    ap.add_argument("--n", type=int, default=6, help="requisicoes por nivel")
    ap.add_argument("--modelo", default="claude-opus-5")
    args = ap.parse_args()
    if not args.confirmar:
        print("Recusado: '--confirmar' e obrigatorio.", file=sys.stderr)
        raise SystemExit(2)

    prov = ProvedorAnthropic(modelo_padrao=args.modelo)
    prompts = [PROMPT.format(catalogo=CATALOGO_ANTT, pergunta=PERGUNTAS[i % len(PERGUNTAS)])
               for i in range(args.n)]

    # Aquece o cache de prompt: sem isto o nível 1 pagaria a escrita e pareceria lento.
    prov(prompts[0], args.modelo, 0.0)

    medidas = {}
    for c in NIVEIS:
        lat = []

        def uma(p):
            t = time.perf_counter()
            prov(p, args.modelo, 0.0)
            return time.perf_counter() - t

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=c) as ex:
            lat = list(ex.map(uma, prompts))
        parede = time.perf_counter() - t0
        medidas[c] = {
            "n": args.n, "parede_s": round(parede, 2),
            "vazao_req_s": round(args.n / parede, 4),
            "p50_s": round(st.median(lat), 2),
            "p95_s": round(sorted(lat)[min(len(lat) - 1, int(len(lat) * 0.95))], 2),
        }
        print(f"  c={c}: vazao {medidas[c]['vazao_req_s']:.3f} req/s  "
              f"p50 {medidas[c]['p50_s']}s  p95 {medidas[c]['p95_s']}s  "
              f"(parede {medidas[c]['parede_s']}s)", flush=True)

    base = medidas[1]["vazao_req_s"]
    rel = {c: round(medidas[c]["vazao_req_s"] / base, 2) for c in NIVEIS}
    melhor = max(NIVEIS, key=lambda c: medidas[c]["vazao_req_s"])
    escala = rel[8] > 1.5      # criterio declarado ANTES de olhar: 8 so se justifica se escalar

    saida = carimbar({
        "fase": "21_concorrencia_do_caminho_de_api",
        "quita": "o default 8 do serving na API era raciocinio, nao medicao",
        "modelo": args.modelo, "n_por_nivel": args.n,
        "medidas": medidas, "vazao_relativa": rel,
        "melhor_nivel": melhor,
        "criterio_pre_declarado": "manter 8 se a vazao em c=8 for > 1,5x a de c=1",
        "escala": escala,
        "referencia_gpu_local_fase6": GPU_LOCAL,
        "custo_usd": round(prov.custo_usd, 4), "chamadas": prov.chamadas,
    })
    (D / "concorrencia_api.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2),
                                             encoding="utf-8")

    print("\n== VAZÃO RELATIVA (c=1 é a base) ==")
    print(f"  {'c':>3} {'API':>8} {'GPU local (F6)':>16}")
    for c in NIVEIS:
        print(f"  {c:>3} {rel[c]:>8.2f} {GPU_LOCAL[c]:>16.2f}")
    print(f"\n  melhor nivel: c={melhor}")
    print(f"  criterio (c=8 > 1,5x c=1): {'ATENDIDO' if escala else 'NAO atendido'}")
    print(f"  custo: ${prov.custo_usd:.4f} em {prov.chamadas} chamadas")


if __name__ == "__main__":
    main()
