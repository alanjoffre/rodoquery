"""Fase 10 — normalizador de group_by: o conserto do modo de falha DOMINANTE.

Braço A: predições congeladas + normalizador de ORDEM (o sistema que está em produção hoje).
Braço B: idem + normalizador de GROUP_BY (remove a dimensão já presa por igualdade no where).

Determinístico e pareado nos 211 itens do TEST-v3: nenhuma chamada de LLM, a única variável é a
regra nova. Como a Fase 9, a regra nasce de um princípio (agrupar por coluna de valor único não
informa nada), não de ajuste item a item.

RESSALVA: o TEST-v3 já foi inspecionado. Isto é sinal forte — a confirmação sai no holdout novo
da migração para os dados reais da ANTT.
"""
import json
from pathlib import Path

from rodoquery.avaliacao import (
    Predicao,
    avaliar_sistema,
    carregar_hashes_gold,
    predicao_de_dict,
    predicao_para_dict,
    vetor_correto,
)
from rodoquery.estat import mcnemar, wilson
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_group_by, normalizar_ordem
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
D = REPO / "reports" / "fase10"
D.mkdir(parents=True, exist_ok=True)

itens = carregar(REPO / "golden" / "golden_test_v3.jsonl")
hashes = carregar_hashes_gold(REPO / "reports" / "fase9" / "gold_respostas_v3.json")
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
_fp = REPO / "reports" / "fase9" / "predicoes_tier_a_antigo_test_v3.json"
bruto = json.loads(_fp.read_text(encoding="utf-8"))


def transformar(preds: dict, com_groupby: bool) -> dict:
    saida, tocadas = {}, 0
    for id_, d in preds.items():
        p: Predicao = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            s = p.spec
            ordem = normalizar_ordem(s.order_by)
            gb = normalizar_group_by(s.group_by, s.where) if com_groupby else s.group_by
            if ordem != s.order_by or gb != s.group_by:
                from dataclasses import replace
                p = Predicao.com_spec(replace(s, order_by=ordem, group_by=gb), **p.meta)
                if gb != s.group_by:
                    tocadas += 1
        saida[id_] = predicao_para_dict(p)
    return saida, tocadas


pred_a, _ = transformar(bruto, com_groupby=False)
pred_b, tocadas = transformar(bruto, com_groupby=True)
print(f"[TEST-v3] {len(itens)} itens; normalizador de group_by tocou {tocadas} specs", flush=True)

av_a = avaliar_sistema(itens, None, hashes, dbs, "so_ordem", predicoes=pred_a)
av_b = avaliar_sistema(itens, None, hashes, dbs, "ordem_e_groupby", predicoes=pred_b)
va, vb = vetor_correto(av_a), vetor_correto(av_b)
resp = [it.id for it in itens if not it.eh_abstencao]
mc = mcnemar([va[i] for i in resp], [vb[i] for i in resp])


def taxa(v):
    ac = sum(v[i] for i in resp)
    lo, hi = wilson(ac, len(resp))
    return {"n": len(resp), "acertos": ac, "taxa": round(ac / len(resp), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


estratos = sorted({it.estrato for it in itens if not it.eh_abstencao})
por_estrato = {}
for e in estratos:
    ide = [it.id for it in itens if it.estrato == e]
    a, b = sum(va[i] for i in ide), sum(vb[i] for i in ide)
    por_estrato[e] = {"n": len(ide), "so_ordem": a, "com_groupby": b, "delta": b - a}

rel = carimbar({
    "fase": "10_normalizador_group_by",
    "regra": ("remove do group_by a dimensao presa a UM valor por igualdade no where: agrupar por "
              "coluna constante gera um unico grupo e nenhuma informacao."),
    "achado_que_motivou": ("22 dos 29 erros de estrutura do TEST-v3 tinham a metrica CERTA e a "
                           "dimensao filtrada indevidamente no group_by."),
    "ressalva": "TEST-v3 ja inspecionado -> sinal; confirmacao no holdout novo da ANTT.",
    "specs_tocadas": tocadas,
    "execution_accuracy": {"so_ordem": taxa(va), "ordem_e_groupby": taxa(vb), "mcnemar": mc},
    "por_estrato": por_estrato,
    "regressoes": {e: v for e, v in por_estrato.items() if v["delta"] < 0},
})
(D / "resultado_normalizador_groupby.json").write_text(
    json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

ex = rel["execution_accuracy"]
print(f"\nEX  so ordem      = {ex['so_ordem']['taxa']} IC{ex['so_ordem']['wilson_ic95']} "
      f"({ex['so_ordem']['acertos']}/{ex['so_ordem']['n']})")
_g = ex["ordem_e_groupby"]
print(f"EX  + group_by    = {_g['taxa']} IC{_g['wilson_ic95']} ({_g['acertos']}/{_g['n']})")
print(f"McNemar: {mc}")
print("\npor estrato:")
for e, v in por_estrato.items():
    marca = "  <-- REGRESSAO" if v["delta"] < 0 else (f"  (+{v['delta']})" if v["delta"] else "")
    print(f"  {e:20s} {v['so_ordem']:3d} -> {v['com_groupby']:3d}  (n={v['n']}){marca}")
print(f"\n-> {D / 'resultado_normalizador_groupby.json'}")
