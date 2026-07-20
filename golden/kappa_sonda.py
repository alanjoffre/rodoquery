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
A = carregar(REPO / "golden" / "sonda_ambiguidade.jsonl")
meta = {it.id: it for it in A}

B = []
for linha in (REPO / "golden" / "_sonda_b_raw.jsonl").read_text(encoding="utf-8").splitlines():
    if not linha.strip():
        continue
    d = json.loads(linha)
    ref = meta[d["id"]]
    B.append(ItemGolden(id=d["id"], pergunta_nl=ref.pergunta_nl, estrato=ref.estrato,
                        spec=Spec(**d["spec"])))
salvar(B, REPO / "golden" / "sonda_kappa_maquina_b.jsonl")

rel = concordancia_mapeamento(A, B)
mb = {it.id: it for it in B}
print(json.dumps(rel, ensure_ascii=False, indent=2))
print("\nDIVERGENCIAS (spec canonica):")
for it in A:
    ca, cb = canonizar_spec(it.spec), canonizar_spec(mb[it.id].spec)
    if ca != cb:
        print(f"  {it.id}  <{it.pergunta_nl}>")
        print(f"     autor : {ca}")
        print(f"     2o LLM: {cb}")

saida = carimbar({
    "tipo": "sonda_ambiguidade_kappa_MAQUINA",
    "proposito": "estressar o kappa com perguntas ambiguas — verificar que a metrica discrimina",
    "n_itens": len(A),
    "concordancia": rel,
})
dest = REPO / "reports" / "fase2" / "sonda_ambiguidade_maquina.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n-> {dest}")
