"""Fase 6 — define e VERIFICA o SLO do serviço, com alvos derivados da medição.

Um SLO inventado ("p95 < 1 s") seria fantasia num 7B em 1 GPU de 6 GB. Os alvos aqui saem do que foi
medido no load test e no canário — e a carga admitida é limitada porque a medição mostrou que
concorrência acima de 2 **piora** tudo.

Sai com código != 0 se qualquer objetivo for violado (dá para pendurar num agendador).
"""
import json
from pathlib import Path

from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
load = json.loads((REPO / "reports" / "fase6" / "load_test.json").read_text(encoding="utf-8"))
can = json.loads((REPO / "reports" / "fase6" / "canario.json").read_text(encoding="utf-8"))

por_conc = {n["concorrencia"]: n for n in load["niveis"]}

# ---- SLO (alvos justificados pela medição) ----------------------------------------------------
# Latência: p95 medido em c=1 foi 4,36 s e em c=2 foi 8,24 s. Alvo com folga ~2x sobre c=2.
# Correção: EX de canário >= 0,85 (o canário roda no DEV e é sinal operacional, não a métrica
# científica — esta é o TEST selado da Fase 4).
# Carga: o serviço só promete o SLO dentro do limite de admissão (2 simultâneas).
SLO = {
    "latencia_p95_s_ate_c2": 10.0,
    "ex_canario_minimo": 0.85,
    "taxa_erro_maxima": 0.05,
    "concorrencia_admitida": 2,
}

p95_c1 = por_conc[1]["latencia_p95_s"]
p95_c2 = por_conc[2]["latencia_p95_s"]
ex_can = can["ex_canario"]
erros = sum(1 for r in can["resultados"] if not r["ok"] and "erro" in r["motivo"].lower())
taxa_erro = round(erros / can["n"], 4)

checagens = [
    {"nome": "latencia_p95_c1", "ok": p95_c1 <= SLO["latencia_p95_s_ate_c2"],
     "detalhe": f"p95={p95_c1}s (alvo <= {SLO['latencia_p95_s_ate_c2']}s)"},
    {"nome": "latencia_p95_c2", "ok": p95_c2 <= SLO["latencia_p95_s_ate_c2"],
     "detalhe": f"p95={p95_c2}s (alvo <= {SLO['latencia_p95_s_ate_c2']}s)"},
    {"nome": "ex_canario", "ok": ex_can >= SLO["ex_canario_minimo"],
     "detalhe": f"EX canário={ex_can} (alvo >= {SLO['ex_canario_minimo']})"},
    {"nome": "taxa_erro", "ok": taxa_erro <= SLO["taxa_erro_maxima"],
     "detalhe": f"erros={taxa_erro} (alvo <= {SLO['taxa_erro_maxima']})"},
]
ok = all(c["ok"] for c in checagens)

rel = carimbar({
    "fase": "6_slo",
    "slo": SLO,
    "justificativa_dos_alvos": (
        "p95: medido 4,36s em c=1 e 8,24s em c=2 -> alvo 10s com folga. "
        "concorrencia admitida = 2 porque o load test mostrou vazao caindo (0,75x) e p95 "
        "explodindo (43s) em c=4/8: admitir mais so enfileira. "
        "EX de canario e sinal OPERACIONAL (roda no DEV); a metrica cientifica e o TEST selado."),
    "medido": {"p95_c1_s": p95_c1, "p95_c2_s": p95_c2, "vazao_c1_req_s":
               por_conc[1]["vazao_req_por_s"], "ex_canario": ex_can, "taxa_erro": taxa_erro},
    "checagens": checagens,
    "slo_atendido": ok,
})
dest = REPO / "reports" / "fase6" / "slo.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

for c in checagens:
    print(f"{'OK  ' if c['ok'] else 'FALHA'} {c['nome']}: {c['detalhe']}")
print(f"\nSLO atendido: {ok}\n-> {dest}")
raise SystemExit(0 if ok else 1)
