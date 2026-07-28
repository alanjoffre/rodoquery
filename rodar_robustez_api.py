"""Fase 19 — a fragilidade lexical sobrevive a um SUT de fronteira?

PRE-REGISTRO em `docs/FASE19_PREREGISTRO.md`, commitado ANTES desta execução (git prova a ordem).
Previsão registrada: EX original 97%, opaco 88%, Δ ≈ −9 pp; afirmação falsificável central
`|Δ_opus5| < 29,4 pp`.

Referência (Fase 14, `qwen2.5-coder:7b`, MESMO conjunto selado de 34 itens):
    original 85,29% (29/34) · opaco 55,88% (19/34) · Δ = −29,41 pp · McNemar b=11/c=1, p=0,0063

**Os dois braços rodam no MESMO SUT, na mesma execução.** Comparar Opus 5 opaco contra Qwen
original mediria o modelo, não a perturbação — o confundimento que este projeto existe para
evitar. O gold, o conjunto e o selo são os da Fase 14: **nada foi regerado**.

Uso: python rodar_robustez_api.py --confirmar [--teto-usd 0.50]
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
from rodoquery.config import settings
from rodoquery.estat import mcnemar, wilson
from rodoquery.gold import FUNDACAO_ANTT
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.perturbacao_antt import tier_a_antt_opaco
from rodoquery.provedor import ProvedorAnthropic
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt import tier_a_antt

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
D14 = REPO / "reports" / "fase14"          # conjunto selado + gold, reusados sem tocar
D19 = REPO / "reports" / "fase19"
CAT = REPO / "reports" / "fase12" / "catalog_antt.json"
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
SIST = {"orig": tier_a_antt, "opaco": tier_a_antt_opaco}

# Números da Fase 14 (Qwen), fixos aqui para o relatório comparar sem reler o arquivo antigo.
QWEN = {"orig": 0.8529, "opaco": 0.5588, "delta_pp": -29.41}
PREVISAO = {"ex_orig": 0.97, "ex_opaco": 0.88, "delta_pp": -9.0,
            "faixa_delta_pp": [-18.0, -2.0],
            "afirmacao_falsificavel": "abs(delta_opus5) < 29.41"}


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
    ap.add_argument("--teto-usd", type=float, default=0.50)
    ap.add_argument("--modelo", default="claude-opus-5")
    args = ap.parse_args()
    if not args.confirmar:
        print("Recusado: '--confirmar' e obrigatorio para gastar credito.", file=sys.stderr)
        raise SystemExit(2)

    D19.mkdir(parents=True, exist_ok=True)
    itens = carregar(G / "robustez_antt.jsonl")
    gold = json.loads((D14 / "gold_robustez.json").read_text(encoding="utf-8"))
    hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]}
    print(f"[robustez-API] {len(itens)} itens selados (Fase 14), modelo={args.modelo}, "
          f"teto=${args.teto_usd}", flush=True)

    prov = None
    preds = {}
    for nome, fn in SIST.items():
        fp = D19 / f"predicoes_robustez_{nome}_api.json"
        if fp.exists():
            preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
            print(f"  {nome}: congeladas reusadas (nao gastou)", flush=True)
            continue
        if prov is None:
            prov = ProvedorAnthropic(modelo_padrao=args.modelo)
        print(f"  {nome}: coletando via API...", flush=True)
        preds[nome] = _coletar(itens, fn, prov, args.teto_usd, nome)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")

    # Normalizadores F9/F10 nos DOIS braços — mesmo tratamento, senão a comparação enviesa.
    tocadas = {}
    for nome in SIST:
        out, n = {}, 0
        for i, d in preds[nome].items():
            p = predicao_de_dict(d)
            if p.tipo == "spec" and p.spec is not None:
                ns = normalizar_spec(p.spec)
                if ns != p.spec:
                    n += 1
                    p = Predicao.com_spec(ns, **p.meta)
            out[i] = predicao_para_dict(p)
        preds[nome], tocadas[nome] = out, n

    av = {n: avaliar_sistema(itens, None, hashes, DBS, n, predicoes=preds[n],
                             fundacao=FUNDACAO_ANTT, catalogo=CAT) for n in SIST}
    ids = [it.id for it in itens]
    vo, vp = vetor_correto(av["orig"]), vetor_correto(av["opaco"])
    mc = mcnemar([vo[i] for i in ids], [vp[i] for i in ids])

    def taxa(vec):
        ac = sum(vec[i] for i in ids)
        return {"n": len(ids), "acertos": ac, "taxa": round(ac / len(ids), 4),
                "wilson_ic95": list(wilson(ac, len(ids)))}

    t_o, t_p = taxa(vo), taxa(vp)
    delta = round((t_p["taxa"] - t_o["taxa"]) * 100, 2)
    encolheu = abs(delta) < abs(QWEN["delta_pp"])
    dentro = PREVISAO["faixa_delta_pp"][0] <= delta <= PREVISAO["faixa_delta_pp"][1]

    metas = [v["meta"] for d in preds.values() for v in d.values()]
    custo = round(sum(m.get("custo_usd", 0.0) for m in metas), 4)

    rel = carimbar({
        "fase": "19_fragilidade_lexical_com_sut_de_fronteira",
        "pre_registro": "docs/FASE19_PREREGISTRO.md (commitado ANTES desta execucao)",
        "previsao_registrada": PREVISAO,
        "sut": args.modelo,
        "conjunto": "robustez_antt.jsonl — SELADO na Fase 14, nao regerado",
        "perturbacao": "identificadores opacos (m1/c2...), MESMAS descricoes; gabarito inalterado",
        "execution_accuracy": {"original": t_o, "schema_opaco": t_p, "delta_pp": delta},
        "mcnemar_original_vs_opaco": mc,
        "referencia_qwen_fase14": QWEN,
        "veredito": {
            "delta_encolheu_vs_qwen": encolheu,
            "dentro_da_faixa_prevista": dentro,
            "lei_da_fase18_sustentada": encolheu,
        },
        "specs_normalizadas": tocadas,
        "custo_usd": custo,
        "quebrou": [i for i in ids if vo[i] and not vp[i]],
        "consertou": [i for i in ids if vp[i] and not vo[i]],
        "resultados_por_item": {n: av[n]["resultados"] for n in SIST},
    })
    dest = D19 / "robustez_schema_opaco_api.json"
    dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n== FRAGILIDADE LEXICAL — {args.modelo} ==")
    print(f"  original    EX={t_o['taxa']} IC{t_o['wilson_ic95']} ({t_o['acertos']}/{t_o['n']})")
    print(f"  schema opaco EX={t_p['taxa']} IC{t_p['wilson_ic95']} ({t_p['acertos']}/{t_p['n']})")
    print(f"  delta = {delta:+.2f} pp        (Qwen 7B na Fase 14: {QWEN['delta_pp']:+.2f} pp)")
    print(f"  McNemar: {mc}")
    print(f"\n  previsao pre-registrada: {PREVISAO['delta_pp']:+.1f} pp "
          f"(faixa {PREVISAO['faixa_delta_pp']})  -> dentro? {dentro}")
    print(f"  lei da Fase 18 (muleta ~ 1/forca do SUT) sustentada? {encolheu}")
    print(f"  custo: ${custo}")
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
