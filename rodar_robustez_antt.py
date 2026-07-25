"""Fase 14 (#4) — mede robustez a SCHEMA OPACO no conjunto DEDICADO (disjunto do TEST-ANTT).

1. gold do conjunto de robustez via MetricFlow nas 3 variantes (mesmas guardas de qualidade);
2. roda o Tier-A ORIGINAL (catálogo com nomes reais) e o Tier-A OPACO (mesmos itens, catálogo com
   identificadores `m1`/`c2`… e as MESMAS descrições);
3. comparação pareada → McNemar. O gabarito não muda; só a apresentação do schema.

A pergunta (a mesma da Fase 7, agora num conjunto próprio e sobre dado real): a competência do
Tier-A está na DESCRIÇÃO (semântica) ou em casar a palavra com o identificador (lexical)?
"""
import hashlib
import json
from pathlib import Path

from rodoquery.avaliacao import (
    avaliar_sistema,
    carregar_allowlist,
    coletar_predicoes,
    vetor_correto,
)
from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.estat import mcnemar, wilson
from rodoquery.gold import FUNDACAO_ANTT, Spec, compilar_spec, executar_gold
from rodoquery.golden import carregar, salvar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.perturbacao_antt import tier_a_antt_opaco
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt import tier_a_antt

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
D = REPO / "reports" / "fase14"
D.mkdir(parents=True, exist_ok=True)
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
CAT = REPO / "reports" / "fase12" / "catalog_antt.json"


def _sem_limit(s):
    return Spec(metrics=s.metrics, group_by=s.group_by, where=s.where, order_by=s.order_by,
               limit=None, ordenado=s.ordenado)


# ---- 1) gold + selo (só se ainda não existe) ---------------------------------------------------
sel = G / "robustez_antt.jsonl"
if not sel.exists():
    itens0 = carregar(G / "robustez_antt_autor.jsonl")
    validos, respostas = [], []
    for it in itens0:
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
        if it.spec.ordenado and it.spec.limit:            # G4: empate na zona de corte
            vals0 = [r[-1] for r in executar_gold(
                compilar_spec(_sem_limit(it.spec), fundacao=FUNDACAO_ANTT), DBS["p0"])]
            n = it.spec.limit
            if len(vals0) < n or len(set(vals0[:n])) < min(n, len(vals0)) \
                    or (len(vals0) > n and vals0[n - 1] == vals0[n]):
                continue
        validos.append(it)
        respostas.append({"id": it.id, "estrato": it.estrato,
                          "hashes_por_variante": hashes})
    salvar(validos, sel)
    sha = hashlib.sha256(sel.read_bytes()).hexdigest()
    (G / "robustez_antt.sha256").write_text(sha + "\n", encoding="utf-8")
    (D / "gold_robustez.json").write_text(
        json.dumps(carimbar({"respostas": respostas, "sha256": sha}), ensure_ascii=False,
                   indent=2), encoding="utf-8")
    print(f"gold robustez: {len(validos)}/{len(itens0)} validos; selado {sha[:16]}...", flush=True)

itens = carregar(sel)
gold = json.loads((D / "gold_robustez.json").read_text(encoding="utf-8"))
hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]}
allow = carregar_allowlist(CAT)
print(f"[robustez-ANTT] {len(itens)} itens (disjuntos do TEST)", flush=True)

# ---- 2) roda ORIGINAL e OPACO (predições congeladas) -------------------------------------------
SIST = {"orig": tier_a_antt, "opaco": tier_a_antt_opaco}
preds = {}
for nome, fn in SIST.items():
    fp = D / f"predicoes_robustez_{nome}.json"
    if fp.exists():
        preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
        print(f"  {nome}: congeladas reusadas", flush=True)
    else:
        print(f"  {nome}: coletando...", flush=True)
        preds[nome] = coletar_predicoes(itens, fn)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")

# normaliza os dois (F9/F10) — mesmo tratamento
from rodoquery.avaliacao import Predicao, predicao_de_dict, predicao_para_dict  # noqa: E402

for nome in SIST:
    out = {}
    for i, d in preds[nome].items():
        p = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            ns = normalizar_spec(p.spec)
            if ns != p.spec:
                p = Predicao.com_spec(ns, **p.meta)
        out[i] = predicao_para_dict(p)
    preds[nome] = out

av = {n: avaliar_sistema(itens, None, hashes, DBS, n, predicoes=preds[n],
                         fundacao=FUNDACAO_ANTT, catalogo=CAT) for n in SIST}
ids = [it.id for it in itens]
vo, vp = vetor_correto(av["orig"]), vetor_correto(av["opaco"])
mc = mcnemar([vo[i] for i in ids], [vp[i] for i in ids])


def taxa(vec):
    ac = sum(vec[i] for i in ids)
    lo, hi = wilson(ac, len(ids))
    return {"n": len(ids), "acertos": ac, "taxa": round(ac / len(ids), 4),
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


rel = carimbar({
    "fase": "14_robustez_dedicada_schema_opaco",
    "conjunto": "DEDICADO, disjunto do TEST-ANTT (specs ineditas vs golden_antt inteiro).",
    "perturbacao": "identificadores opacos (m1/c2...), MESMAS descricoes; gabarito inalterado.",
    "execution_accuracy": {"original": taxa(vo), "schema_opaco": taxa(vp),
                           "delta_pp": round((taxa(vp)["taxa"] - taxa(vo)["taxa"]) * 100, 2)},
    "mcnemar_original_vs_opaco": mc,
    "quebrou": [i for i in ids if vo[i] and not vp[i]],
    "consertou": [i for i in ids if vp[i] and not vo[i]],
})
(D / "robustez_schema_opaco.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
ex = rel["execution_accuracy"]
print(f"\n== ROBUSTEZ a schema opaco (conjunto dedicado, n={len(ids)}) ==")
print(f"  original     EX={ex['original']['taxa']} IC{ex['original']['wilson_ic95']}")
print(f"  schema opaco EX={ex['schema_opaco']['taxa']} IC{ex['schema_opaco']['wilson_ic95']}")
print(f"  delta={ex['delta_pp']}pp  McNemar={mc}")
print(f"-> {D / 'robustez_schema_opaco.json'}")
