"""Fase 12 — a tese sobre DADO REAL: Tier-A governado × SQL cru, no TEST-ANTT selado.

Mesmo SUT (`qwen2.5-coder:7b`) nas duas pontas; muda só a interface. Os dois normalizadores
determinísticos das Fases 9/10 entram no Tier-A — eles são parte do sistema hoje (estão no
serving), então medi-lo sem eles mediria uma versão que não existe mais.

Os números das Fases 4–10 NÃO são comparáveis com estes: aqueles medem dado sintético, estes
medem a base real da ANTT. É uma medição do zero, não uma continuação.

Uso: python avaliar_fase12.py [dev|test]   (default: test)
"""
import json
import sys
from pathlib import Path

from rodoquery.avaliacao import (
    Predicao,
    avaliar_sistema,
    coletar_predicoes,
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
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt import tier_a_antt

split = (sys.argv[1] if len(sys.argv) > 1 else "test").lower()
assert split in ("dev", "test")
REPO = Path(__file__).resolve().parent
D = REPO / "reports" / "fase12"
D.mkdir(parents=True, exist_ok=True)

itens = carregar(REPO / "golden" / f"golden_{split}_antt.jsonl")
gold = json.loads((D / "gold_respostas_antt.json").read_text(encoding="utf-8"))
hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]
          if r.get("hashes_por_variante")}
dbs = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
SISTEMAS = {"tier_a_antt": tier_a_antt, "sql_cru_antt": sql_cru_antt}

print(f"[{split}-ANTT] {len(itens)} itens, {len(dbs)} variantes reais", flush=True)

preds = {}
for nome, fn in SISTEMAS.items():
    fp = D / f"predicoes_{nome}_{split}.json"
    if fp.exists():
        preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
        print(f"  {nome}: congeladas reusadas", flush=True)
    else:
        print(f"  {nome}: coletando...", flush=True)
        preds[nome] = coletar_predicoes(itens, fn)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {nome}: congeladas", flush=True)

# Normalizadores das Fases 9/10 — só fazem sentido no caminho de spec (Tier-A).
tocadas = 0
norm = {}
for id_, d in preds["tier_a_antt"].items():
    p: Predicao = predicao_de_dict(d)
    if p.tipo == "spec" and p.spec is not None:
        ns = normalizar_spec(p.spec)
        if ns != p.spec:
            tocadas += 1
            p = Predicao.com_spec(ns, **p.meta)
    norm[id_] = predicao_para_dict(p)
preds["tier_a_antt"] = norm
print(f"  normalizadores (F9/F10) tocaram {tocadas} specs", flush=True)

CATALOGO_ANTT = D / "catalog_antt.json"     # allowlist do sandbox, gerada do manifesto da ANTT
avals = {n: avaliar_sistema(itens, None, hashes, dbs, n, predicoes=preds[n],
                            fundacao=FUNDACAO_ANTT, catalogo=CATALOGO_ANTT)
         for n in SISTEMAS}
ids_resp = [it.id for it in itens if not it.eh_abstencao]
va, vb = vetor_correto(avals["tier_a_antt"]), vetor_correto(avals["sql_cru_antt"])
mc = mcnemar([vb[i] for i in ids_resp], [va[i] for i in ids_resp])

rel = carimbar({
    "fase": "12_tese_sobre_dado_real",
    "split": f"{split}_antt",
    "fundacao": "ANTT (CC-BY), 1.534.142 linhas; variantes = partições disjuntas por hash",
    "comparacao": "MESMO SUT; muda só a interface: spec governada vs SQL cru.",
    "nao_comparavel": ("os numeros das Fases 4-10 medem dado SINTETICO. Estes medem a base real. "
                       "Nao sao continuacao um do outro."),
    "normalizadores_aplicados": ["ordem (F9)", "group_by (F10)"],
    "specs_normalizadas": tocadas,
    "n": len(itens), "n_variantes": len(dbs),
    "sistemas": {n: {k: v for k, v in avals[n].items() if k != "resultados"} for n in SISTEMAS},
    "mcnemar_sqlcru_vs_tiera_respondiveis": mc,
    "resultados_por_item": {n: avals[n]["resultados"] for n in SISTEMAS},
})
dest = D / f"resultado_{split}_antt.json"
dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\n== {split.upper()}-ANTT (dado REAL) ==")
for n in SISTEMAS:
    ex, ab = avals[n]["execution_accuracy_respondiveis"], avals[n]["acuracia_abstencao"]
    print(f"  {n:14s} EX={ex['taxa']} IC{ex['wilson_ic95']} ({ex['acertos']}/{ex['n']})"
          f"  | abstenção={ab['taxa']} ({ab['acertos']}/{ab['n']})")
print(f"  McNemar (sql_cru vs tier_a): {mc}")
print("\n  EX do tier_a por estrato:")
for e, v in sorted(avals["tier_a_antt"]["ex_por_estrato"].items()):
    print(f"    {e:20s} {v['acertos']:3d}/{v['n']:3d} = {v['taxa']:.3f} IC{v['wilson_ic95']}")
print(f"\n-> {dest}")
