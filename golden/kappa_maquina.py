"""κ de MÁQUINA (Fase 2): concordância inter-anotador entre o autor (modelo) e um 2º anotador-LLM
independente, cego às specs do autor. NÃO é κ humano — está rotulado como máquina, de propósito.
O κ humano fica como backlog declarado (docs/GUIA_GOLDEN.md).

Gera: golden/kappa_maquina_b.jsonl (specs do 2º anotador, enriquecidas c/ estrato+pergunta)
      reports/fase2/concordancia_maquina.json (métricas de concordância + carimbo de proveniência)
"""
import json
from pathlib import Path

from rodoquery.gold import Spec
from rodoquery.golden import (
    ItemGolden,
    canonizar_spec,
    carregar,
    concordancia_mapeamento,
    salvar,
)
from rodoquery.proveniencia import carimbar

REPO = Path.home() / "rodoquery"
A = carregar(REPO / "golden" / "golden.jsonl")                     # anotador A = autor (modelo)
meta = {it.id: it for it in A}

# 2º anotador (máquina): só {id, spec}; herda estrato+pergunta do golden por id (metadados só).
B: list[ItemGolden] = []
for linha in (REPO / "golden" / "_maquina_b_raw.jsonl").read_text(encoding="utf-8").splitlines():
    if not linha.strip():
        continue
    d = json.loads(linha)
    ref = meta[d["id"]]
    B.append(ItemGolden(id=d["id"], pergunta_nl=ref.pergunta_nl, estrato=ref.estrato,
                        spec=Spec(**d["spec"]), revisado_humano=False))

salvar(B, REPO / "golden" / "kappa_maquina_b.jsonl")

rel = concordancia_mapeamento(A, B)

# por estrato: onde os dois anotadores-LLM divergem?
por_estrato: dict[str, dict] = {}
mb = {it.id: it for it in B}
for it in A:
    e = por_estrato.setdefault(it.estrato, {"n": 0, "iguais": 0})
    e["n"] += 1
    if canonizar_spec(it.spec) == canonizar_spec(mb[it.id].spec):
        e["iguais"] += 1

saida = carimbar({
    "tipo": "concordancia_inter_anotador_MAQUINA",
    "aviso": ("2 anotadores = LLMs (autor + 2o anotador independente, cego). "
              "kappa de MAQUINA, nao humano. kappa humano = backlog declarado."),
    "anotador_a": "autor_modelo (golden/gerar_autor.py)",
    "anotador_b": "2o_anotador_LLM_cego (general-purpose subagent, so perguntas+catalogo)",
    "n_itens": len(A),
    "concordancia": rel,
    "por_estrato": {k: {**v, "taxa": round(v["iguais"] / v["n"], 4)}
                    for k, v in sorted(por_estrato.items())},
})

destino = REPO / "reports" / "fase2" / "concordancia_maquina.json"
destino.parent.mkdir(parents=True, exist_ok=True)
destino.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(rel, ensure_ascii=False, indent=2))
print("\npor estrato:")
for k, v in saida["por_estrato"].items():
    print(f"  {k:20s} {v['iguais']}/{v['n']}  ({v['taxa']:.0%})")
print(f"\n-> {destino}")
