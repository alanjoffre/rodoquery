"""Fase 14 (#3) — o roteador 2-tiers, derivado dos RESULTADOS já pontuados da Fase 12 (sem LLM,
sem recompilar). Cada item já tem, congelado: se o Tier-A acertou, se ele abstém ou a spec não
compila, e se o SQL cru acertou. O roteador é então pura lógica de decisão sobre esses sinais.

Duas políticas, ambas usando só sinais OBSERVÁVEIS em tempo de serviço:
  INGÊNUA      — cai para Tier-B quando Tier-A abstém OU a spec não compila.
  CONSERVADORA — cai para Tier-B SÓ quando a spec não compila; nunca sobrepõe uma abstenção
                 deliberada do Tier-A (preserva a disciplina de abstenção, o forte dele).
"""
import json
from pathlib import Path

from rodoquery.estat import wilson
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
res = json.loads((REPO / "reports" / "fase12" / "resultado_test_antt.json").read_text(
    encoding="utf-8"))
ta = {x["id"]: x for x in res["resultados_por_item"]["tier_a_antt"]}
sc = {x["id"]: x for x in res["resultados_por_item"]["sql_cru_antt"]}
ids = list(ta)

só, ingenuo, conserv = {}, {}, {}
stats = {"ingenuo": {"fb": 0, "rec": 0, "estr": 0}, "conserv": {"fb": 0, "rec": 0, "estr": 0}}
for i in ids:
    a, b = ta[i], sc[i]
    só[i] = a["correto"]
    absteve = a["predicao"] == "abster"
    nao_compila = "não compila" in a.get("motivo", "")

    if absteve or nao_compila:
        ingenuo[i] = b["correto"]
        s = stats["ingenuo"]
        s["fb"] += 1
        s["rec"] += b["correto"] and not a["correto"]
        s["estr"] += a["correto"] and not b["correto"]
    else:
        ingenuo[i] = a["correto"]

    if nao_compila:
        conserv[i] = b["correto"]
        s = stats["conserv"]
        s["fb"] += 1
        s["rec"] += b["correto"] and not a["correto"]
        s["estr"] += a["correto"] and not b["correto"]
    else:
        conserv[i] = a["correto"]

resp = [i for i in ids if not ta[i]["abstencao"]]
abst = [i for i in ids if ta[i]["abstencao"]]


def taxa(subset, vec):
    ac = sum(vec[i] for i in subset)
    lo, hi = wilson(ac, len(subset))
    return {"n": len(subset), "acertos": ac, "taxa": round(ac / len(subset), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


rel = carimbar({
    "fase": "14_roteador_2tiers",
    "medido_de": "resultados JA pontuados da Fase 12 — sem LLM, sem recompilar.",
    "politicas": {
        "ingenua": "fallback p/ Tier-B quando Tier-A abstem OU a spec nao compila",
        "conservadora": "fallback SO quando a spec nao compila; nunca sobrepoe abstencao",
    },
    "estatisticas_de_fallback": stats,
    "execution_accuracy": {"so_tier_a": taxa(resp, só), "ingenuo": taxa(resp, ingenuo),
                           "conservador": taxa(resp, conserv)},
    "abstencao": {"so_tier_a": taxa(abst, só), "ingenuo": taxa(abst, ingenuo),
                  "conservador": taxa(abst, conserv)},
    "leitura": ("o Tier-A NUNCA abstem num respondivel neste TEST, entao o fallback ingenuo so "
                "pode ESTRAGAR abstencoes corretas (Tier-B alucina onde Tier-A cala). O "
                "conservador dispara so em spec-nao-compila e preserva a abstencao."),
})
(REPO / "reports" / "fase14").mkdir(parents=True, exist_ok=True)
(REPO / "reports" / "fase14" / "roteador.json").write_text(
    json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

ex, ab = rel["execution_accuracy"], rel["abstencao"]
print("== ROTEADOR 2-tiers (TEST-ANTT, dos resultados congelados) ==")
for pol in ("ingenuo", "conserv"):
    s = stats[pol]
    print(f"  {pol:9s}: {s['fb']} fallbacks -> recuperou {s['rec']}, estragou {s['estr']}")
print(f"  EX  Tier-A={ex['so_tier_a']['taxa']}  ingenuo={ex['ingenuo']['taxa']}  "
      f"conservador={ex['conservador']['taxa']}")
print(f"  abs Tier-A={ab['so_tier_a']['taxa']}  ingenuo={ab['ingenuo']['taxa']}  "
      f"conservador={ab['conservador']['taxa']}")
print(f"\n-> {REPO / 'reports' / 'fase14' / 'roteador.json'}")
