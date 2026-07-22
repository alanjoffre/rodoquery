"""Prova que o gate está ATIVO (métrica dura da Fase 5) — não basta ele ficar verde.

Um gate que nunca reprova é decoração. Aqui pego o relatório REAL da Fase 4 e injeto, uma a uma,
regressões plausíveis. O gate tem de reprovar TODAS e aprovar o relatório íntegro.

Gera: reports/fase5/gate_ativo.json (evidência auditável).
"""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from rodoquery.proveniencia import carimbar
from rodoquery.regressao import Limiares, gate_contrato, verificar_selo

REPO = Path(__file__).resolve().parent
LIM = Limiares(ex_minimo=0.90, abstencao_minima=0.90, vantagem_minima_pp=30.0)
BASE = json.loads((REPO / "reports" / "fase4" / "resultado_test.json").read_text(encoding="utf-8"))
SELO_OK = verificar_selo(REPO / "golden" / "golden_test.jsonl",
                         REPO / "golden" / "golden_test.sha256")


def _com(mut) -> dict:
    r = copy.deepcopy(BASE)
    mut(r)
    return r


def _queda_ex(r):
    r["sistemas"]["tier_a"]["execution_accuracy_respondiveis"]["taxa"] = 0.62


def _agregado_adulterado(r):
    # alguém "melhora" o número no topo sem mexer nos itens
    r["sistemas"]["tier_a"]["execution_accuracy_respondiveis"]["acertos"] = 42


def _perde_vantagem(r):
    r["sistemas"]["sql_cru"]["execution_accuracy_respondiveis"]["taxa"] = 0.95


def _perde_significancia(r):
    r["mcnemar_tier_a_vs_sql_cru_respondiveis"]["p_valor"] = 0.31


def _abstencao_desaba(r):
    r["sistemas"]["tier_a"]["acuracia_abstencao"]["taxa"] = 0.40


CENARIOS = [
    ("integro (deve PASSAR)", BASE, True),
    ("EX do Tier-A despenca", _com(_queda_ex), False),
    ("agregado adulterado (nao bate com os itens)", _com(_agregado_adulterado), False),
    ("baseline alcanca o sistema (vantagem some)", _com(_perde_vantagem), False),
    ("McNemar deixa de ser significante", _com(_perde_significancia), False),
    ("abstencao desaba (passa a alucinar)", _com(_abstencao_desaba), False),
]

linhas, todos_ok = [], True
for nome, rel, esperado_ok in CENARIOS:
    res = gate_contrato(rel, LIM, SELO_OK)
    acertou = res.ok == esperado_ok
    todos_ok &= acertou
    falhas = [c["nome"] for c in res.checagens if not c["ok"]]
    linhas.append({"cenario": nome, "gate_passou": res.ok, "esperado": esperado_ok,
                   "gate_se_comportou": acertou, "checagens_que_falharam": falhas})
    print(f"{'✓' if acertou else '✗'} {nome:48s} gate={'PASSOU' if res.ok else 'FALHOU'}"
          f"{'  <- ' + ','.join(falhas) if falhas else ''}")

# selo: adultera o arquivo do golden num tmp e confirma que o gate percebe
with tempfile.TemporaryDirectory() as d:
    alvo, sha = Path(d) / "g.jsonl", Path(d) / "g.sha256"
    alvo.write_text("original\n", encoding="utf-8")
    sha.write_text(hashlib.sha256(alvo.read_bytes()).hexdigest(), encoding="utf-8")
    ok_antes = verificar_selo(alvo, sha)["ok"]
    alvo.write_text("golden editado depois do pre-registro\n", encoding="utf-8")
    ok_depois = verificar_selo(alvo, sha)["ok"]
sel_ok = ok_antes and not ok_depois
todos_ok &= sel_ok
linhas.append({"cenario": "golden TEST editado apos o selo", "gate_passou": ok_depois,
               "esperado": False, "gate_se_comportou": sel_ok, "checagens_que_falharam":
               [] if ok_depois else ["selo_golden_test"]})
print(f"{'✓' if sel_ok else '✗'} {'golden TEST editado apos o selo':48s} "
      f"gate={'PASSOU' if ok_depois else 'FALHOU'}")

saida = carimbar({
    "fase": "5_gate_ativo",
    "proposito": "provar que o gate REPROVA regressoes reais (gate que so fica verde e decoracao)",
    "limiares": {"ex_minimo": LIM.ex_minimo, "abstencao_minima": LIM.abstencao_minima,
                 "vantagem_minima_pp": LIM.vantagem_minima_pp},
    "cenarios": linhas,
    "gate_ativo_comprovado": bool(todos_ok),
})
dest = REPO / "reports" / "fase5" / "gate_ativo.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\ngate_ativo_comprovado = {todos_ok}\n-> {dest}")
raise SystemExit(0 if todos_ok else 1)
