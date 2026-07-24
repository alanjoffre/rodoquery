"""κ de MÁQUINA do TEST-ANTT (Fase 12) — 2º anotador LLM cego, 2 chunks disjuntos.

Continua sendo κ de MÁQUINA: a base da ANTT não vem com benchmark humano de perguntas — foi a
falha não-bloqueante registrada na Fase 0 de Dados, e o κ humano segue no backlog declarado.

Dois eixos, como nas versões anteriores:
  1. decisão binária respondível × fora-de-escopo — é o que valida as 30 abstenções near-miss;
  2. concordância de spec nos respondíveis.
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

A = carregar(G / "golden_test_antt.jsonl")
meta = {it.id: it for it in A}

# As specs do anotador B ficam como DADO BRUTO, não como ItemGolden: o `ItemGolden` valida que
# item de abstenção tem metrics vazio, e o caso mais interessante do κ é justamente quando B
# DISCORDA disso (acha que uma "abstenção" é respondível). Validar aqui apagaria o achado.
specs_b: dict[str, Spec] = {}
for ch in (1, 2):
    p = G / f"_antt_maquina_b_chunk{ch}.jsonl"
    for linha in p.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        d = json.loads(linha)
        if d["id"] in meta:
            specs_b[d["id"]] = Spec(**d["spec"])

mb = {i: s for i, s in specs_b.items()}
ids = [it.id for it in A if it.id in mb]

dec_a = ["fora" if not meta[i].spec.metrics else "respondivel" for i in ids]
dec_b = ["fora" if not mb[i].metrics else "respondivel" for i in ids]
acordo = sum(x == y for x, y in zip(dec_a, dec_b, strict=True))
abst_contestadas = [i for i, xa, xb in zip(ids, dec_a, dec_b, strict=True)
                    if xa == "fora" and xb == "respondivel"]
resp_contestados = [i for i, xa, xb in zip(ids, dec_a, dec_b, strict=True)
                    if xa == "respondivel" and xb == "fora"]

A_resp = [it for it in A if it.spec.metrics and it.id in mb]
B_resp = [ItemGolden(id=it.id, pergunta_nl=it.pergunta_nl, estrato=it.estrato,
                     spec=mb[it.id], revisado_humano=False)
          for it in A_resp if mb[it.id].metrics]
ids_resp = {it.id for it in B_resp}
A_resp = [it for it in A_resp if it.id in ids_resp]
rel = concordancia_mapeamento(A_resp, B_resp)
salvar(B_resp, G / "kappa_maquina_antt_b.jsonl")

por_estrato: dict[str, dict] = {}
for it in A_resp:
    e = por_estrato.setdefault(it.estrato, {"n": 0, "iguais": 0})
    e["n"] += 1
    if canonizar_spec(it.spec) == canonizar_spec(mb[it.id]):
        e["iguais"] += 1

saida = carimbar({
    "tipo": "concordancia_inter_anotador_MAQUINA_antt",
    "aviso": ("kappa de MAQUINA (2 LLMs), nao humano. A base da ANTT nao tem benchmark humano "
              "(falha registrada na Fase 0 de Dados); kappa humano segue no backlog."),
    "n_itens": len(ids), "sem_anotacao_b": [it.id for it in A if it.id not in mb],
    "decisao_respondivel_x_fora": {
        "n": len(ids), "acordo": acordo, "taxa": round(acordo / len(ids), 4),
        "cohen_kappa": cohen_kappa(dec_a, dec_b),
        "abstencoes_contestadas": abst_contestadas,
        "respondiveis_contestados": resp_contestados,
    },
    "concordancia_spec_respondiveis": rel,
    "por_estrato": {k: {**v, "taxa": round(v["iguais"] / v["n"], 4)}
                    for k, v in sorted(por_estrato.items())},
})
dest = REPO / "reports" / "fase12" / "concordancia_maquina_antt.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

d = saida["decisao_respondivel_x_fora"]
print(f"pareados: {len(ids)}")
print(f"DECISAO resp x fora: {d['acordo']}/{d['n']} = {d['taxa']:.1%} k={d['cohen_kappa']}")
print(f"  abstencoes contestadas: {abst_contestadas}")
print(f"  respondiveis contestados: {resp_contestados}")
print(f"SPEC (respondiveis n={rel['n_pares']}): bruta={rel['concordancia_spec_canonica']} "
      f"kappa_metrica={rel['cohen_kappa_metrica']}")
print(f"  discordantes: {rel['discordantes'][:14]}")
for k, v in saida["por_estrato"].items():
    print(f"  {k:20s} {v['iguais']:3d}/{v['n']:3d} ({v['taxa']:.0%})")
print(f"-> {dest}")
