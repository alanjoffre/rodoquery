"""κ de MÁQUINA do golden v2 (Fase 8) — 2º anotador LLM cego às specs do autor.

Como na v1, é κ de MÁQUINA, não humano (backlog declarado). Duas diferenças em relação à v1:

1. **Os itens de abstenção entram no cálculo.** Na v1 o κ cobria só os respondíveis. Aqui a
   pergunta mais importante é justamente sobre as abstenções NEAR-MISS que autorei ("ticket médio",
   "taxa de estorno"): elas *soam* respondíveis. Se o anotador cego achar que são respondíveis, o
   item é ruim e precisa sair — senão eu estaria punindo o sistema por uma pergunta mal rotulada.
   Por isso reporto também a concordância na decisão binária respondível × fora-de-escopo.
2. O κ da métrica sobre respondíveis usa marginais bem menos enviesadas (7 métricas em uso contra
   praticamente 2 na v1), então aqui ele é mais informativo e menos deflacionado.
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

A = carregar(G / "golden_v2.jsonl")
meta = {it.id: it for it in A}

B: list[ItemGolden] = []
for ch in (1, 2, 3, 4):
    p = G / f"_v2_maquina_b_chunk{ch}.jsonl"
    for linha in p.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        d = json.loads(linha)
        if d["id"] not in meta:      # itens removidos pela regra anti-degenerado
            continue
        ref = meta[d["id"]]
        B.append(ItemGolden(id=d["id"], pergunta_nl=ref.pergunta_nl, estrato=ref.estrato,
                            spec=Spec(**d["spec"]), revisado_humano=False))

salvar(B, G / "kappa_maquina_v2_b.jsonl")
mb = {it.id: it for it in B}
faltando = [it.id for it in A if it.id not in mb]

# ---- eixo 1: decisão binária respondível × fora-de-escopo (vale para TODOS os itens) -----------
ids = [it.id for it in A if it.id in mb]
dec_a = ["fora" if not meta[i].spec.metrics else "respondivel" for i in ids]
dec_b = ["fora" if not mb[i].spec.metrics else "respondivel" for i in ids]
acordo_dec = sum(x == y for x, y in zip(dec_a, dec_b, strict=True))
# onde o autor disse ABSTER mas o cego achou respondível → abstenção suspeita (rótulo frágil)
abst_contestadas = [i for i, xa, xb in zip(ids, dec_a, dec_b, strict=True)
                    if xa == "fora" and xb == "respondivel"]
resp_contestados = [i for i, xa, xb in zip(ids, dec_a, dec_b, strict=True)
                    if xa == "respondivel" and xb == "fora"]

# ---- eixo 2: concordância de spec, só nos respondíveis ------------------------------------------
A_resp = [it for it in A if it.spec.metrics and it.id in mb]
B_resp = [mb[it.id] for it in A_resp]
rel = concordancia_mapeamento(A_resp, B_resp)

por_estrato: dict[str, dict] = {}
for it in A_resp:
    e = por_estrato.setdefault(it.estrato, {"n": 0, "iguais": 0})
    e["n"] += 1
    if canonizar_spec(it.spec) == canonizar_spec(mb[it.id].spec):
        e["iguais"] += 1

saida = carimbar({
    "tipo": "concordancia_inter_anotador_MAQUINA_v2",
    "aviso": ("2 anotadores = LLMs (autor + 2o anotador cego, so perguntas+catalogo). kappa de "
              "MAQUINA, nao humano. kappa humano segue no backlog declarado."),
    "anotador_a": "autor_modelo (golden/gerar_autor_v2.py)",
    "anotador_b": "2o_anotador_LLM_cego (4 subagents, chunks disjuntos, so perguntas+catalogo)",
    "n_itens": len(ids), "sem_anotacao_b": faltando,
    "decisao_respondivel_x_fora": {
        "n": len(ids), "acordo": acordo_dec, "taxa": round(acordo_dec / len(ids), 4),
        "cohen_kappa": cohen_kappa(dec_a, dec_b),
        "abstencoes_contestadas": abst_contestadas,
        "respondiveis_contestados": resp_contestados,
        "leitura": ("abstencoes_contestadas = o autor disse 'fora do catalogo' e o anotador cego "
                    "discordou; sao os rotulos frageis do estrato de abstencao."),
    },
    "concordancia_spec_respondiveis": rel,
    "por_estrato": {k: {**v, "taxa": round(v["iguais"] / v["n"], 4)}
                    for k, v in sorted(por_estrato.items())},
})
dest = REPO / "reports" / "fase8" / "concordancia_maquina_v2.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"itens pareados: {len(ids)}  (sem anotacao B: {len(faltando)})")
d = saida["decisao_respondivel_x_fora"]
print(f"\nDECISAO respondivel x fora: {d['acordo']}/{d['n']} = {d['taxa']:.1%}  "
      f"kappa={d['cohen_kappa']}")
print(f"  abstencoes contestadas ({len(abst_contestadas)}): {abst_contestadas}")
print(f"  respondiveis contestados ({len(resp_contestados)}): {resp_contestados}")
print(f"\nSPEC (respondiveis, n={rel['n_pares']}): bruta={rel['concordancia_spec_canonica']}  "
      f"kappa_metrica={rel['cohen_kappa_metrica']}")
print(f"  metrica={rel['concordancia_metrica']} group_by={rel['concordancia_group_by']} "
      f"where={rel['concordancia_where']}")
print("\npor estrato:")
for k, v in saida["por_estrato"].items():
    print(f"  {k:20s} {v['iguais']:3d}/{v['n']:3d}  ({v['taxa']:.0%})")
print(f"\n-> {dest}")
