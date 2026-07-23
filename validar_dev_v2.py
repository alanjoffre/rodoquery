"""Fase 9 — validação do prompt corrigido **exclusivamente no DEV-v2**.

Este é o único lugar onde é legítimo iterar: o DEV-v2 (41 itens) existe para isso. O TEST-v2 já
foi visto em detalhe na Fase 8, então medir o conserto nele seria ajustar ao teste; a medição
válida acontece no TEST-v3, gerado depois que o texto do prompt já estava fechado.

As predições do sistema NOVO não são cacheadas de propósito — o objetivo aqui é reexecutar a cada
ajuste do texto. As do sistema ANTIGO são, porque ele não muda.
"""
import json
from pathlib import Path

from rodoquery.avaliacao import avaliar_sistema, carregar_hashes_gold, coletar_predicoes
from rodoquery.golden import carregar
from rodoquery.sistema import tier_a
from rodoquery.sistema_v2 import tier_a_v2

REPO = Path(__file__).resolve().parent
itens = carregar(REPO / "golden" / "golden_dev_v2.jsonl")
hashes = carregar_hashes_gold(REPO / "reports" / "fase8" / "gold_respostas_v2.json")
dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
D = REPO / "reports" / "fase9"
D.mkdir(parents=True, exist_ok=True)

print(f"[DEV-v2] {len(itens)} itens", flush=True)

fp = D / "predicoes_tier_a_dev_v2.json"
if fp.exists():
    p_old = json.loads(fp.read_text(encoding="utf-8"))
    print("  antigo: predicoes reusadas", flush=True)
else:
    print("  antigo: coletando...", flush=True)
    p_old = coletar_predicoes(itens, tier_a)
    fp.write_text(json.dumps(p_old, ensure_ascii=False, indent=2), encoding="utf-8")

print("  novo: coletando (sempre, para iterar)...", flush=True)
p_new = coletar_predicoes(itens, tier_a_v2)
(D / "predicoes_tier_a_v2_dev_v2.json").write_text(
    json.dumps(p_new, ensure_ascii=False, indent=2), encoding="utf-8")

a_old = avaliar_sistema(itens, None, hashes, dbs, "tier_a", predicoes=p_old)
a_new = avaliar_sistema(itens, None, hashes, dbs, "tier_a_v2", predicoes=p_new)


def resumo(a, rot):
    ex, ab = a["execution_accuracy_respondiveis"], a["acuracia_abstencao"]
    print(f"\n{rot}:  EX={ex['taxa']} ({ex['acertos']}/{ex['n']})   abstencao={ab['taxa']} "
          f"({ab['acertos']}/{ab['n']})")
    for e, v in sorted(a["ex_por_estrato"].items()):
        print(f"    {e:20s} {v['acertos']:2d}/{v['n']:2d}")


resumo(a_old, "ANTIGO (Fase 4)")
resumo(a_new, "NOVO   (Fase 9)")

r_old = {r["id"]: r["correto"] for r in a_old["resultados"]}
r_new = {r["id"]: r["correto"] for r in a_new["resultados"]}
consertou = [i for i in r_old if not r_old[i] and r_new[i]]
quebrou = [i for i in r_old if r_old[i] and not r_new[i]]
print(f"\nconsertou ({len(consertou)}): {consertou}")
print(f"QUEBROU  ({len(quebrou)}): {quebrou}")
print("\n(DEV = desenvolvimento. O numero que vale sai no TEST-v3.)")
