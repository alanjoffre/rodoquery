"""Fase 20 — o conjunto DURO discrimina, ou o teto era do sistema mesmo?

Os 8 estratos antigos fizeram 100% contra `claude-opus-5` (Fases 18/19). Este conjunto foi
desenhado contra as formas que nunca foram cobertas — filtro composto, métrica mista, near-miss de
abstenção. **Se ele também saturar**, a conclusão muda de "o instrumento acabou" para "num
catálogo de 3 métricas, o Tier-A com SUT de fronteira é realmente muito bom" — e aí o limite é do
CATÁLOGO, não do benchmark.

Os dois braços (Tier-A e sql_cru) rodam no MESMO SUT, na mesma execução.

Uso: python avaliar_duro.py --confirmar [--teto-usd 0.60]
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
    vetor_correto,
)
from rodoquery.baselines_antt import sql_cru_antt
from rodoquery.config import settings
from rodoquery.estat import mcnemar
from rodoquery.gold import FUNDACAO_ANTT
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.provedor import ProvedorAnthropic
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt import tier_a_antt

REPO = Path(__file__).resolve().parent
D20 = REPO / "reports" / "fase20"
CAT = REPO / "reports" / "fase12" / "catalog_antt.json"
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
SIST = {"tier_a_antt": tier_a_antt, "sql_cru_antt": sql_cru_antt}

# Referência: o MESMO SUT nos 8 estratos antigos (Fase 18).
ANTIGO = {"tier_a": 1.0, "sql_cru": 0.4452, "abstencao_tier_a": 0.96}


def _coletar(itens, fn, prov, teto, rotulo):
    preds = {}
    for i, it in enumerate(itens, 1):
        if prov.custo_usd > teto:
            print(f"\nABORTADO: ${prov.custo_usd:.4f} passou do teto ${teto:.2f} "
                  f"no item {i}/{len(itens)} de {rotulo}.", file=sys.stderr)
            raise SystemExit(2)
        preds[it.id] = predicao_para_dict(fn(it.pergunta_nl, provedor=prov))
        if i % 10 == 0 or i == len(itens):
            print(f"    {rotulo}: {i}/{len(itens)}  ${prov.custo_usd:.4f}", flush=True)
    return preds


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmar", action="store_true")
    ap.add_argument("--teto-usd", type=float, default=0.60)
    ap.add_argument("--modelo", default="claude-opus-5")
    args = ap.parse_args()
    if not args.confirmar:
        print("Recusado: '--confirmar' e obrigatorio para gastar credito.", file=sys.stderr)
        raise SystemExit(2)

    itens = carregar(REPO / "golden" / "duro_antt.jsonl")
    gold = json.loads((D20 / "gold_duro.json").read_text(encoding="utf-8"))
    hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]}
    print(f"[DURO] {len(itens)} itens (selo {gold['sha256'][:12]}...), modelo={args.modelo}",
          flush=True)

    prov, preds = None, {}
    for nome, fn in SIST.items():
        fp = D20 / f"predicoes_{nome}_duro.json"
        if fp.exists():
            preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
            print(f"  {nome}: congeladas reusadas (nao gastou)", flush=True)
            continue
        if prov is None:
            prov = ProvedorAnthropic(modelo_padrao=args.modelo)
        print(f"  {nome}: coletando via API...", flush=True)
        preds[nome] = _coletar(itens, fn, prov, args.teto_usd, nome)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")

    tocadas, out = 0, {}
    for i, d in preds["tier_a_antt"].items():
        p = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            ns = normalizar_spec(p.spec)
            if ns != p.spec:
                tocadas += 1
                p = Predicao.com_spec(ns, **p.meta)
        out[i] = predicao_para_dict(p)
    preds["tier_a_antt"] = out

    av = {n: avaliar_sistema(itens, None, hashes, DBS, n, predicoes=preds[n],
                             fundacao=FUNDACAO_ANTT, catalogo=CAT) for n in SIST}
    ids_resp = [it.id for it in itens if not it.eh_abstencao]
    va, vb = vetor_correto(av["tier_a_antt"]), vetor_correto(av["sql_cru_antt"])
    mc = mcnemar([vb[i] for i in ids_resp], [va[i] for i in ids_resp])

    metas = [v["meta"] for d in preds.values() for v in d.values()]
    custo = round(sum(m.get("custo_usd", 0.0) for m in metas), 4)
    ex_novo = av["tier_a_antt"]["execution_accuracy_respondiveis"]["taxa"]

    rel = carimbar({
        "fase": "20_conjunto_duro",
        "desenho": ("estratos novos contra a superficie nunca coberta: filtro composto (0 itens "
                    "em 168), metrica mista (impossivel ate a F19), near-miss de abstencao"),
        "sut": args.modelo, "selo": gold["sha256"],
        "n": len(itens), "specs_normalizadas": tocadas, "custo_usd": custo,
        "sistemas": {n: {k: v for k, v in av[n].items() if k != "resultados"} for n in SIST},
        "mcnemar_sqlcru_vs_tiera": mc,
        "referencia_8_estratos_antigos_mesmo_SUT": ANTIGO,
        "saturou_de_novo": ex_novo >= 1.0,
        "resultados_por_item": {n: av[n]["resultados"] for n in SIST},
    })
    dest = D20 / "resultado_duro.json"
    dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n== CONJUNTO DURO — {args.modelo} ==")
    for n in SIST:
        ex, ab = (av[n]["execution_accuracy_respondiveis"], av[n]["acuracia_abstencao"])
        print(f"  {n:14s} EX={ex['taxa']} IC{ex['wilson_ic95']} ({ex['acertos']}/{ex['n']})"
              f"  | abstencao={ab['taxa']} ({ab['acertos']}/{ab['n']})")
    print(f"  McNemar: {mc}")
    print("\n  EX do tier_a por estrato:")
    for e, v in sorted(av["tier_a_antt"]["ex_por_estrato"].items()):
        print(f"    {e:18s} {v['acertos']:2d}/{v['n']:2d} = {v['taxa']:.3f}")
    print(f"\n  8 estratos antigos, MESMO SUT: tier_a {ANTIGO['tier_a']} | "
          f"sql_cru {ANTIGO['sql_cru']}")
    print(f"  saturou de novo? {ex_novo >= 1.0}")
    print(f"  custo: ${custo}\n-> {dest}")


if __name__ == "__main__":
    main()
