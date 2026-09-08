"""Fase 23 — o catálogo enriquecido pode ir ao serving? A pergunta que a F21 deixou aberta.

A Fase 21 mediu o catálogo de 7 métricas em **47 itens** do conjunto duro e ele venceu: o
rebaixamento de tipo caiu de 6/6 para 1/8 e a abstenção subiu de 50% para 75%. Mas ele **nunca
foi medido no benchmark principal** (TEST-ANTT, 171 itens), e o serving continuou com o catálogo
de 3. Promover às cegas seria servir uma configuração cuja acurácia no conjunto principal ninguém
mediu — contra o padrão do resto do projeto.

A F21 também mediu o preço da troca: **1 regressão** ("maior VOLUME de motos" virou `share` quando
`motorcycle_share` passou a existir). Catálogo maior compra cobertura e paga em ambiguidade. Este
script mede quanto se paga onde importa.

## O desenho, e por que ele é válido

Comparação **pareada** contra as predições CONGELADAS da Fase 18 (mesmo SUT `claude-opus-5`, mesmo
conjunto selado, mesmo gold). Muda **só o catálogo** — o PROMPT é byte a byte o mesmo.

**O gabarito dos 146 respondíveis não muda, e isto foi verificado antes de gastar:** as 3 métricas
do catálogo original (`traffic_volume`, `automation_rate`, `commercial_share`) sobrevivem
**intactas** no rico, e o gold dos 146 usa **apenas** essas 3 (57 + 49 + 42). Nenhuma métrica do
gabarito foi renomeada ou removida, então pontuar as predições novas contra o gold antigo é
legítimo.

**As 25 abstenções são outra história, e NÃO entram como acerto/erro.** Uma pergunta é abstenção
porque o catálogo não tem como respondê-la; quando o catálogo passa a ter, ela pode virar
legitimamente respondível — foi exatamente o que aconteceu com 4 itens na F21. Contá-las como
falha puniria o sistema por fazer a coisa certa. Elas ficam num diagnóstico separado, marcando
quais foram respondidas **com métrica nova** (mudança causada pelo catálogo, candidata a
respondível) e quais foram respondidas com métrica **antiga** (aí sim é alucinação, porque o
catálogo de 3 já bastava para saber que não dava).

Uso: python avaliar_rico_test_antt.py --confirmar [--teto-usd 0.65]
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
from rodoquery.estat import mcnemar
from rodoquery.gold import FUNDACAO_ANTT
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.provedor import ProvedorAnthropic
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt_rico import METRICAS_RICAS, tier_a_antt_rico

REPO = Path(__file__).resolve().parent
D12, D18 = REPO / "reports" / "fase12", REPO / "reports" / "fase18"
D23 = REPO / "reports" / "fase23"
CAT = REPO / "reports" / "fase12" / "catalog_antt.json"
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}

METRICAS_ANTIGAS = ("traffic_volume", "automation_rate", "commercial_share")
NOVAS = tuple(m for m in METRICAS_RICAS if m not in METRICAS_ANTIGAS)


def _normalizar(preds: dict) -> dict:
    """Normalizadores das F9/F10 — o mesmo pré-processamento que a F18 aplicou."""
    out = {}
    for i, d in preds.items():
        p = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            ns = normalizar_spec(p.spec)
            if ns != p.spec:
                p = Predicao.com_spec(ns, **p.meta)
        out[i] = predicao_para_dict(p)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmar", action="store_true")
    ap.add_argument("--teto-usd", type=float, default=0.65)
    ap.add_argument("--modelo", default="claude-opus-5")
    args = ap.parse_args()
    if not args.confirmar:
        print("Recusado: '--confirmar' e obrigatorio para gastar credito.", file=sys.stderr)
        raise SystemExit(2)

    D23.mkdir(parents=True, exist_ok=True)
    itens = carregar(REPO / "golden" / "golden_test_antt.jsonl")
    gold = json.loads((D12 / "gold_respostas_antt.json").read_text(encoding="utf-8"))
    hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]
              if r.get("hashes_por_variante")}

    # Trava de validade do desenho: se o gold usasse metrica que o catalogo rico nao tem, a
    # comparacao seria invalida. Verificado ANTES de gastar — falha fechada.
    usadas = {m for it in itens if not it.eh_abstencao
              for m in (it.spec.metrics if it.spec else [])}
    fora = sorted(usadas - set(METRICAS_RICAS))
    if fora:
        print(f"ABORTADO: o gold usa metricas ausentes no catalogo rico: {fora}", file=sys.stderr)
        raise SystemExit(2)

    print(f"[TEST-ANTT] {len(itens)} itens | catalogo de {len(METRICAS_RICAS)} metricas "
          f"| gold usa {sorted(usadas)}", flush=True)

    fp = D23 / "predicoes_tier_a_rico_test_antt.json"
    if fp.exists():
        preds = json.loads(fp.read_text(encoding="utf-8"))
        print("  congeladas reusadas (nao gastou)", flush=True)
    else:
        prov = ProvedorAnthropic(modelo_padrao=args.modelo)
        preds = {}
        for i, it in enumerate(itens, 1):
            if prov.custo_usd > args.teto_usd:
                # Salva o que ja foi pago antes de abortar: trava de orcamento que joga fora
                # trabalho pago e pior que nao ter trava (licao da F21).
                fp.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"\nABORTADO em {i}/{len(itens)}: ${prov.custo_usd:.4f} > teto "
                      f"${args.teto_usd} (parcial salvo)", file=sys.stderr)
                raise SystemExit(2)
            preds[it.id] = predicao_para_dict(tier_a_antt_rico(it.pergunta_nl, provedor=prov))
            if i % 20 == 0 or i == len(itens):
                print(f"    {i}/{len(itens)}  ${prov.custo_usd:.4f}", flush=True)
        fp.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")

    preds = _normalizar(preds)
    av = avaliar_sistema(itens, None, hashes, DBS, "tier_a_antt_rico", predicoes=preds,
                         fundacao=FUNDACAO_ANTT, catalogo=CAT)
    ex, ab = av["execution_accuracy_respondiveis"], av["acuracia_abstencao"]

    # --- Pareado contra a F18 (catalogo de 3), SO nos respondiveis ---
    f18 = json.loads((D18 / "resultado_test_antt_api.json").read_text(encoding="utf-8"))
    antes = {r["id"]: r["correto"] for r in f18["resultados_por_item"]["tier_a_antt"]}
    agora = vetor_correto(av)
    ids_resp = [it.id for it in itens if not it.eh_abstencao]
    mc = mcnemar([antes[i] for i in ids_resp], [agora[i] for i in ids_resp])
    regressoes = [i for i in ids_resp if antes[i] and not agora[i]]
    ganhos = [i for i in ids_resp if not antes[i] and agora[i]]

    # --- As 25 abstencoes: diagnostico, nao placar ---
    perg = {it.id: it.pergunta_nl for it in itens}
    diagnostico = []
    for it in itens:
        if not it.eh_abstencao:
            continue
        p = preds[it.id]
        met = (p.get("spec") or {}).get("metrics") if p["tipo"] == "spec" else None
        diagnostico.append({
            "id": it.id, "pergunta": perg[it.id],
            "absteve": not met,
            "respondeu_com": met,
            # Metrica NOVA => o catalogo mudou o que e respondivel (candidata legitima).
            # Metrica ANTIGA => o catalogo de 3 ja bastava para saber que nao dava: alucinacao.
            "usou_metrica_nova": bool(met and any(m in NOVAS for m in met)),
        })
    absteve = sum(1 for d in diagnostico if d["absteve"])
    com_nova = sum(1 for d in diagnostico if d["usou_metrica_nova"])
    alucinou = sum(1 for d in diagnostico if not d["absteve"] and not d["usou_metrica_nova"])

    custo = round(sum(v["meta"].get("custo_usd", 0.0) for v in preds.values()), 4)

    rel = carimbar({
        "fase": "23_catalogo_rico_no_benchmark_principal",
        "pergunta": "o catalogo de 7 metricas pode ir ao serving sem custo no conjunto principal?",
        "mudanca": "catalogo 3 -> 7 metricas; PROMPT, SUT, conjunto e gold identicos",
        "validade_do_desenho": (
            "as 3 metricas originais sobrevivem intactas no rico e o gold dos respondiveis usa "
            "APENAS elas — verificado antes de gastar, com aborto em caso contrario"),
        "abstencoes_nao_pontuadas": (
            "as 25 abstencoes NAO entram no placar: trocar o catalogo muda o que e respondivel, "
            "entao conta-las como falha puniria o sistema por acertar. Ficam no diagnostico."),
        "sut": args.modelo, "n": len(itens), "custo_usd": custo,
        "referencia_fase18_catalogo_de_3": {
            "execution_accuracy_respondiveis":
                f18["sistemas"]["tier_a_antt"]["execution_accuracy_respondiveis"],
            "acuracia_abstencao": f18["sistemas"]["tier_a_antt"]["acuracia_abstencao"],
        },
        "execution_accuracy_respondiveis": ex,
        "acuracia_abstencao_NAO_COMPARAVEL": ab,
        "mcnemar_vs_fase18_respondiveis": mc,
        "regressoes": [{"id": i, "pergunta": perg[i]} for i in regressoes],
        "ganhos": [{"id": i, "pergunta": perg[i]} for i in ganhos],
        "diagnostico_abstencoes": diagnostico,
        "abstencoes_mantidas": absteve,
        "abstencoes_respondidas_com_metrica_nova": com_nova,
        "abstencoes_respondidas_com_metrica_antiga_ALUCINACAO": alucinou,
        "ex_por_estrato": av["ex_por_estrato"],
        "resultados_por_item": av["resultados"],
    })
    (D23 / "resultado_rico_test_antt.json").write_text(
        json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

    f18ex = f18["sistemas"]["tier_a_antt"]["execution_accuracy_respondiveis"]
    print(f"\n== CATALOGO RICO (7) no TEST-ANTT — {args.modelo} ==")
    print(f"  respondiveis  EX={ex['taxa']} IC{ex['wilson_ic95']} ({ex['acertos']}/{ex['n']})")
    print(f"  F18 (cat. 3)  EX={f18ex['taxa']} ({f18ex['acertos']}/{f18ex['n']})")
    print(f"  McNemar: b={mc['b_only']} c={mc['c_only']} p={mc['p_valor']}")
    print(f"  regressoes: {len(regressoes)}  ganhos: {len(ganhos)}")
    for i in regressoes:
        print(f"    REGREDIU  {perg[i][:66]}")
    print(f"\n  abstencoes (diagnostico, nao placar): {absteve}/{len(diagnostico)} mantidas")
    print(f"    respondidas com metrica NOVA (catalogo mudou o respondivel): {com_nova}")
    print(f"    respondidas com metrica ANTIGA (alucinacao):                 {alucinou}")
    for d in diagnostico:
        if not d["absteve"]:
            tag = "NOVA " if d["usou_metrica_nova"] else "ANTIGA"
            print(f"    [{tag}] {d['pergunta'][:52]:52s} -> {d['respondeu_com']}")
    print(f"\n  custo: ${custo}")


if __name__ == "__main__":
    main()
