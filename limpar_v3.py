"""Fase 9 — remove do TEST-v3 os itens AMBÍGUOS por construção, antes de qualquer sistema rodar.

**Origem do sinal (não fui eu que percebi).** Dois dos anotadores cegos, de forma independente,
sinalizaram o mesmo problema no relatório final: há itens que filtram por uma dimensão e **agrupam
por ela mesma** ("entre as transações estornadas, ... por status"). Aí duas leituras são
defensáveis — a dimensão fica só no `where`, ou aparece nos dois — e a discordância mede
*convenção*, não capacidade. É o mesmo tipo de aviso que fez três paráfrases serem excluídas na
Fase 7, e a resposta é a mesma: excluir antes de medir.

Um gerador melhor não produziria esses itens; o de `valor_categorico` já tinha a guarda
(`if d == dim: continue`), os de `ranking` e `metrica_derivada` não tinham.
"""
import collections
import hashlib
import json
import re
from pathlib import Path

from rodoquery.golden import carregar, salvar

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
_DIM = re.compile(r"Dimension\('([^']+)'\)")

itens = carregar(G / "golden_test_v3.jsonl")
manter, ambiguos = [], []
for it in itens:
    dims_where = set(_DIM.findall(it.spec.where or ""))
    if dims_where & set(it.spec.group_by):
        ambiguos.append({"id": it.id, "estrato": it.estrato, "pergunta_nl": it.pergunta_nl,
                         "motivo": "filtra e agrupa pela MESMA dimensao (leitura ambigua)"})
    else:
        manter.append(it)

salvar(manter, G / "golden_test_v3.jsonl")
sha = hashlib.sha256((G / "golden_test_v3.jsonl").read_bytes()).hexdigest()
(G / "golden_test_v3.sha256").write_text(sha + "\n", encoding="utf-8")

p = REPO / "reports" / "fase9" / "gold_respostas_v3.json"
rel = json.loads(p.read_text(encoding="utf-8"))
ids = {it.id for it in manter}
rel["respostas"] = [r for r in rel["respostas"] if r["id"] in ids]
rel["removidos_por_ambiguidade"] = ambiguos
rel["origem_do_sinal"] = ("2 anotadores cegos sinalizaram, de forma independente, que itens que "
                          "filtram e agrupam pela mesma dimensao admitem duas leituras. Removidos "
                          "ANTES de qualquer sistema rodar.")
rel["n_validos"] = len(manter)
rel["sha256_test_v3"] = sha
p.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

c = collections.Counter(it.estrato for it in manter)
print(f"removidos por ambiguidade: {len(ambiguos)}")
for a in ambiguos[:8]:
    print(f"   {a['id']}: {a['pergunta_nl'][:70]}")
print(f"\nTEST-v3 final: {len(manter)}  {dict(sorted(c.items()))}")
print(f"selo sha256 = {sha}")
