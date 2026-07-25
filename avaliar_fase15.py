"""Fase 15 — os dois levers contra o resíduo de seleção, medidos no holdout de ABLAÇÃO fresco.

Condições (todas pareadas, mesmo gold, McNemar contra a baseline):
  A. baseline        — catálogo original + normalizador da Fase 10 (o sistema atual).
  B. norm-corrigido  — catálogo original + normalizador que ESVAZIA o group_by só-filtrado (F15).
  C. descricoes-v2   — catálogo desambiguado (o-que-NÃO-é + regra de group_by) + norm corrigido.
  D. SUT-maior       — catálogo original + gemma2:9b (9B) no lugar do qwen2.5-coder:7b (7B).

B e A compartilham as MESMAS predições (o normalizador é determinístico, aplicado depois). C e D
precisam de nova coleta de predições (mudou o prompt / o modelo). Tudo congelado em disco.
"""
import json
from pathlib import Path

from rodoquery.avaliacao import (
    Predicao,
    avaliar_sistema,
    coletar_predicoes,
    predicao_de_dict,
    predicao_para_dict,
    vetor_correto,
)
from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.estat import mcnemar, wilson
from rodoquery.gold import FUNDACAO_ANTT, compilar_spec, executar_gold
from rodoquery.golden import GOLD_ABSTER, carregar, salvar
from rodoquery.normalizacao_spec import normalizar_ordem, normalizar_spec
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt import tier_a_antt
from rodoquery.sistema_antt_v2 import tier_a_antt_v2

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
D = REPO / "reports" / "fase15"
D.mkdir(parents=True, exist_ok=True)
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
CAT = REPO / "reports" / "fase12" / "catalog_antt.json"

# ---- gold do holdout de ablação (só se ainda não existe) ---------------------------------------
sel = G / "ablacao_antt.jsonl"
if not sel.exists():
    itens0 = carregar(G / "ablacao_antt_autor.jsonl")
    validos, respostas = [], []
    for it in itens0:
        if it.eh_abstencao:
            validos.append(it)
            respostas.append({"id": it.id, "estrato": it.estrato, "hashes_por_variante": {},
                              "gold": GOLD_ABSTER})
            continue
        try:
            sql = compilar_spec(it.spec, fundacao=FUNDACAO_ANTT)
            hashes, vazio = {}, False
            for nome, db in DBS.items():
                linhas = executar_gold(sql, db)
                vazio = vazio or not linhas
                hashes[nome] = hash_resultado(linhas, ordenado=it.spec.ordenado)
        except Exception:
            continue
        if vazio or len(set(hashes.values())) == 1:
            continue
        validos.append(it)
        respostas.append({"id": it.id, "estrato": it.estrato, "hashes_por_variante": hashes})
    salvar(validos, sel)
    (D / "gold_ablacao.json").write_text(
        json.dumps(carimbar({"respostas": respostas}), ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"gold ablacao: {len(validos)}/{len(itens0)} validos", flush=True)

itens = carregar(sel)
gold = json.loads((D / "gold_ablacao.json").read_text(encoding="utf-8"))
hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]
          if r.get("hashes_por_variante")}
print(f"[ablacao] {len(itens)} itens", flush=True)


def congelar(nome, fn, modelo=None):
    fp = D / f"predicoes_{nome}.json"
    if fp.exists():
        print(f"  {nome}: congeladas reusadas", flush=True)
        return json.loads(fp.read_text(encoding="utf-8"))
    print(f"  {nome}: coletando...", flush=True)
    p = coletar_predicoes(itens, (lambda q: fn(q, modelo=modelo)) if modelo else fn)
    fp.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def norm(preds, so_ordem=False):
    out = {}
    for i, d in preds.items():
        p = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            if so_ordem:
                from dataclasses import replace
                ns = replace(p.spec, order_by=normalizar_ordem(p.spec.order_by))
            else:
                ns = normalizar_spec(p.spec)
            if ns != p.spec:
                p = Predicao.com_spec(ns, **p.meta)
        out[i] = predicao_para_dict(p)
    return out


base_raw = congelar("baseline_orig", tier_a_antt)
v2_raw = congelar("descricoes_v2", tier_a_antt_v2)
big_raw = congelar("sut_gemma9b", tier_a_antt, modelo="gemma2:9b")

# A: baseline usa o normalizador ATUAL (que agora já está corrigido no código) — para comparar com
# o antigo comportamento, aplicamos só a ordem (equivalente ao normalizador pré-F15 no group_by).
COND = {
    "A_baseline_normF10": norm(base_raw, so_ordem=True),   # aprox. do comportamento pré-F15
    "B_norm_corrigido":   norm(base_raw),                  # normalizador F15 (esvazia group_by)
    "C_descricoes_v2":    norm(v2_raw),
    "D_sut_gemma9b":      norm(big_raw),
}
av = {k: avaliar_sistema(itens, None, hashes, DBS, k, predicoes=v, fundacao=FUNDACAO_ANTT,
                         catalogo=CAT) for k, v in COND.items()}
resp = [it.id for it in itens if not it.eh_abstencao]
abst = [it.id for it in itens if it.eh_abstencao]
vet = {k: vetor_correto(av[k]) for k in COND}


def taxa(ids, v):
    ac = sum(v[i] for i in ids)
    lo, hi = wilson(ac, len(ids))
    return {"n": len(ids), "acertos": ac, "taxa": round(ac / len(ids), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


base = "A_baseline_normF10"
rel = carimbar({
    "fase": "15_levers_selecao",
    "holdout": "ablacao_antt (fresco, disjunto de golden+robustez)",
    "condicoes": {
        "A": "catalogo original + normalizador so-ordem (aprox. pre-F15)",
        "B": "catalogo original + normalizador F15 (esvazia group_by so-filtrado)",
        "C": "catalogo DESAMBIGUADO (o-que-nao-e + regra group_by) + norm F15",
        "D": "SUT gemma2:9b (9B) no lugar do qwen2.5-coder:7b (7B)",
    },
    "execution_accuracy": {k: taxa(resp, vet[k]) for k in COND},
    "abstencao": {k: taxa(abst, vet[k]) for k in COND},
    "mcnemar_vs_baseline": {
        k: mcnemar([vet[base][i] for i in resp], [vet[k][i] for i in resp])
        for k in COND if k != base},
})
(D / "resultado_ablacao.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

print(f"\n== ABLAÇÃO (holdout fresco, {len(resp)} respondíveis, {len(abst)} abstenções) ==")
for k in COND:
    ex, ab = rel["execution_accuracy"][k], rel["abstencao"][k]
    mc = rel["mcnemar_vs_baseline"].get(k)
    tag = f"  McNemar vs A: b={mc['b_only']} c={mc['c_only']} p={mc['p_valor']}" if mc else ""
    print(f"  {k:22s} EX={ex['taxa']} ({ex['acertos']}/{ex['n']})  abst={ab['taxa']}{tag}")
print(f"\n-> {D / 'resultado_ablacao.json'}")
