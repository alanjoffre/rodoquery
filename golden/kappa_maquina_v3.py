"""κ de MÁQUINA do TEST-v3 (Fase 9) — 2º anotador LLM cego, 3 chunks disjuntos.

Mesma leitura da v2, com dois eixos: a decisão binária respondível × fora-de-escopo (que valida as
abstenções near-miss) e a concordância de spec nos respondíveis. Continua sendo κ de MÁQUINA — o
humano segue no backlog declarado.

Itens removidos depois da anotação (regra anti-degenerado e remoção dos ambíguos) simplesmente não
entram: o par não existe mais.
"""
import json
from pathlib import Path

from rodoquery.estat import cohen_kappa
from rodoquery.gold import Spec
from rodoquery.golden import (
    ItemGolden,
    canonizar_spec,
    carregar,
    concordancia_mapeamento,
    salvar,
)
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent.parent
G = REPO / "golden"

A = carregar(G / "golden_test_v3.jsonl")
meta = {it.id: it for it in A}

B: list[ItemGolden] = []
for ch in (1, 2, 3):
    for linha in (G / f"_v3_maquina_b_chunk{ch}.jsonl").read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        d = json.loads(linha)
        if d["id"] not in meta:
            continue
        ref = meta[d["id"]]
        B.append(ItemGolden(id=d["id"], pergunta_nl=ref.pergunta_nl, estrato=ref.estrato,
                            spec=Spec(**d["spec"]), revisado_humano=False))

salvar(B, G / "kappa_maquina_v3_b.jsonl")
mb = {it.id: it for it in B}
ids = [it.id for it in A if it.id in mb]

dec_a = ["fora" if not meta[i].spec.metrics else "respondivel" for i in ids]
dec_b = ["fora" if not mb[i].spec.metrics else "respondivel" for i in ids]
acordo = sum(x == y for x, y in zip(dec_a, dec_b, strict=True))
abst_contestadas = [i for i, xa, xb in zip(ids, dec_a, dec_b, strict=True)
                    if xa == "fora" and xb == "respondivel"]

A_resp = [it for it in A if it.spec.metrics and it.id in mb]
rel = concordancia_mapeamento(A_resp, [mb[it.id] for it in A_resp])

por_estrato: dict[str, dict] = {}
for it in A_resp:
    e = por_estrato.setdefault(it.estrato, {"n": 0, "iguais": 0})
    e["n"] += 1
    if canonizar_spec(it.spec) == canonizar_spec(mb[it.id].spec):
        e["iguais"] += 1

saida = carimbar({
    "tipo": "concordancia_inter_anotador_MAQUINA_v3",
    "aviso": "kappa de MAQUINA (2 LLMs), nao humano. kappa humano segue no backlog.",
    "n_itens": len(ids), "sem_anotacao_b": [it.id for it in A if it.id not in mb],
    "decisao_respondivel_x_fora": {
        "n": len(ids), "acordo": acordo, "taxa": round(acordo / len(ids), 4),
        "cohen_kappa": cohen_kappa(dec_a, dec_b),
        "abstencoes_contestadas": abst_contestadas,
    },
    "concordancia_spec_respondiveis": rel,
    "por_estrato": {k: {**v, "taxa": round(v["iguais"] / v["n"], 4)}
                    for k, v in sorted(por_estrato.items())},
})
dest = REPO / "reports" / "fase9" / "concordancia_maquina_v3.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

d = saida["decisao_respondivel_x_fora"]
print(f"pareados: {len(ids)}")
print(f"DECISAO resp x fora: {d['acordo']}/{d['n']} = {d['taxa']:.1%} k={d['cohen_kappa']}")
print(f"  abstencoes contestadas: {abst_contestadas}")
print(f"SPEC (respondiveis n={rel['n_pares']}): bruta={rel['concordancia_spec_canonica']} "
      f"kappa_metrica={rel['cohen_kappa_metrica']}")
print(f"  discordantes: {rel['discordantes'][:12]}")
for k, v in saida["por_estrato"].items():
    print(f"  {k:20s} {v['iguais']:3d}/{v['n']:3d} ({v['taxa']:.0%})")
print(f"-> {dest}")
