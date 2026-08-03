"""Fase 21 — completar as partições conserta o rebaixamento de tipo?

Mesmas 47 perguntas da Fase 20. Muda **só o catálogo** (3 métricas → 7): o PROMPT é byte a byte
o mesmo, o SUT é o mesmo, o conjunto é o mesmo. Se este sistema for melhor, o mérito é do
CATÁLOGO.

O gabarito muda em 4 itens, e tem de mudar: uma pergunta é abstenção porque o catálogo não pode
respondê-la. Os outros 8 near-miss **seguem abstenção** — é o que impede o experimento de ser
tautológico.

A pergunta central não é o EX agregado, é: **os 8 que continuam abstenção ainda falham por
rebaixamento de tipo** (pedem proporção, responde contagem)?

Uso: python avaliar_duro_rico.py --confirmar [--teto-usd 0.40]
"""
import argparse
import json
import sys
from pathlib import Path

from rodoquery.avaliacao import (
    Predicao,
    avaliar_sistema,
    predicao_de_dict,
    predicao_para_dict,
)
from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.provedor import ProvedorAnthropic
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt_rico import METRICAS_RICAS, tier_a_antt_rico

REPO = Path(__file__).resolve().parent
D20, D21 = REPO / "reports" / "fase20", REPO / "reports" / "fase21"
CAT = REPO / "reports" / "fase12" / "catalog_antt.json"
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}

# Fase 20, catálogo de 3 métricas, MESMO SUT e MESMAS perguntas.
F20 = {"respondiveis": "35/35 (100%)", "abstencao": "6/12 (50%)",
       "modo_de_falha": "rebaixamento de tipo: pedem proporcao, responde traffic_volume"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmar", action="store_true")
    ap.add_argument("--teto-usd", type=float, default=0.40)
    ap.add_argument("--modelo", default="claude-opus-5")
    args = ap.parse_args()
    if not args.confirmar:
        print("Recusado: '--confirmar' e obrigatorio.", file=sys.stderr)
        raise SystemExit(2)

    itens = carregar(REPO / "golden" / "duro_rico_antt.jsonl")
    gold = json.loads((D21 / "gold_duro_rico.json").read_text(encoding="utf-8"))
    hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]}
    print(f"[DURO-RICO] {len(itens)} itens (selo {gold['sha256'][:12]}...), "
          f"catalogo de {len(METRICAS_RICAS)} metricas", flush=True)

    fp = D21 / "predicoes_tier_a_rico.json"
    if fp.exists():
        preds = json.loads(fp.read_text(encoding="utf-8"))
        print("  congeladas reusadas (nao gastou)", flush=True)
    else:
        prov = ProvedorAnthropic(modelo_padrao=args.modelo)
        preds = {}
        for i, it in enumerate(itens, 1):
            if prov.custo_usd > args.teto_usd:
                print(f"\nABORTADO em {i}/{len(itens)}: ${prov.custo_usd:.4f} > teto",
                      file=sys.stderr)
                raise SystemExit(2)
            preds[it.id] = predicao_para_dict(tier_a_antt_rico(it.pergunta_nl, provedor=prov))
            if i % 10 == 0 or i == len(itens):
                print(f"    {i}/{len(itens)}  ${prov.custo_usd:.4f}", flush=True)
        fp.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")

    out = {}
    for i, d in preds.items():
        p = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            ns = normalizar_spec(p.spec)
            if ns != p.spec:
                p = Predicao.com_spec(ns, **p.meta)
        out[i] = predicao_para_dict(p)
    preds = out

    av = avaliar_sistema(itens, None, hashes, DBS, "tier_a_rico", predicoes=preds,
                         fundacao=FUNDACAO_ANTT, catalogo=CAT)
    ex, ab = av["execution_accuracy_respondiveis"], av["acuracia_abstencao"]

    # A pergunta central: os que CONTINUAM abstencao ainda erram por rebaixamento de tipo?
    res = {x["id"]: x for x in av["resultados"]}
    diagnostico = []
    for it in itens:
        if not it.eh_abstencao:
            continue
        p = preds[it.id]
        respondeu = p["tipo"] == "spec" and p["spec"] and p["spec"]["metrics"]
        diagnostico.append({
            "id": it.id, "pergunta": it.pergunta_nl,
            "correto": res[it.id].get("correto"),
            "respondeu_com": p["spec"]["metrics"] if respondeu else None,
            "rebaixamento_de_tipo": bool(respondeu and p["spec"]["metrics"] == ["traffic_volume"]),
        })
    rebaixou = sum(1 for d in diagnostico if d["rebaixamento_de_tipo"])

    metas = [v["meta"] for v in preds.values()]
    custo = round(sum(m.get("custo_usd", 0.0) for m in metas), 4)

    rel = carimbar({
        "fase": "21_catalogo_com_particoes_completas",
        "mudanca": "catalogo 3 -> 7 metricas; PROMPT, SUT e perguntas identicos",
        "regra": "completar a particao onde um membro ja estava exposto (nao 'expor tudo')",
        "sut": args.modelo, "selo": gold["sha256"], "custo_usd": custo,
        "referencia_fase20_catalogo_de_3": F20,
        "execution_accuracy_respondiveis": ex, "acuracia_abstencao": ab,
        "ex_por_estrato": av["ex_por_estrato"],
        "abstencoes_remanescentes": diagnostico,
        "rebaixamento_de_tipo_remanescente": rebaixou,
        "resultados_por_item": av["resultados"],
    })
    (D21 / "resultado_duro_rico.json").write_text(
        json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n== CATALOGO ENRIQUECIDO (7 metricas) — {args.modelo} ==")
    print(f"  respondiveis EX={ex['taxa']} IC{ex['wilson_ic95']} ({ex['acertos']}/{ex['n']})")
    print(f"  abstencao      ={ab['taxa']} ({ab['acertos']}/{ab['n']})")
    print(f"\n  Fase 20 (catalogo de 3): respondiveis {F20['respondiveis']} | "
          f"abstencao {F20['abstencao']}")
    print(f"\n  rebaixamento de tipo remanescente: {rebaixou}/{len(diagnostico)}")
    for d in diagnostico:
        marca = "OK   " if d["correto"] else "ERROU"
        print(f"    {marca} {d['pergunta'][:58]:58s} -> {d['respondeu_com'] or '(absteve)'}")
    print(f"\n  custo: ${custo}")


if __name__ == "__main__":
    main()
