"""Auditoria de FIDELIDADE: cada número afirmado na documentação existe no relatório?

Um README bonito com número errado é pior que nenhum. Este script lê os artefatos em
`reports/**` e confere contra o que o README/docs afirmam. Ele NÃO conserta nada — só denuncia.

Regra: se um número aparece no README, ou ele sai daqui, ou é retratado.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
R = REPO / "reports"
ok = falhas = 0


def _j(rel: str):
    p = R / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def checa(rotulo: str, obtido, esperado, tol=0.0):
    global ok, falhas
    if obtido is None:
        print(f"  AUSENTE  {rotulo:52s} (artefato nao encontrado)")
        falhas += 1
        return
    bate = (abs(float(obtido) - float(esperado)) <= tol
            if isinstance(esperado, (int, float)) else obtido == esperado)
    if bate:
        print(f"  OK       {rotulo:52s} {obtido}")
        ok += 1
    else:
        print(f"  DIVERGE  {rotulo:52s} doc={esperado}  artefato={obtido}")
        falhas += 1


print("=== TESE: numeros do cabecalho do README ===")
f18 = _j("fase18/resultado_test_antt_api.json")
if f18:
    s = f18["sistemas"]
    checa("F18 tier_a EX (README diz 100%)",
          s["tier_a_antt"]["execution_accuracy_respondiveis"]["taxa"], 1.0)
    checa("F18 sql_cru EX (README diz 44,5%)",
          s["sql_cru_antt"]["execution_accuracy_respondiveis"]["taxa"], 0.4452, 0.0001)
    checa("F18 n respondiveis (README diz 146)",
          s["tier_a_antt"]["execution_accuracy_respondiveis"]["n"], 146)
    checa("F18 custo (README diz US$ 0,96)", f18["custo"]["custo_usd"], 0.9627, 0.0001)

# O artefato da F12 guarda o valor RE-PONTUADO (as F14/15 corrigiram gold e re-scoraram as
# mesmas predicoes: 86,9 -> 88,7 -> 89,7). O README cita 86,9% na linha da fase COM nota de
# rodape explicando isso, e 89,7% na tabela da tese. Aqui conferimos o que o artefato de fato tem.
f12 = _j("fase12/resultado_test_antt.json")
if f12:
    checa("F12 artefato = valor RE-PONTUADO (README explica em nota)",
          f12["sistemas"]["tier_a_antt"]["execution_accuracy_respondiveis"]["taxa"], 0.8973, 0.001)

print("\n=== FASE 19 ===")
f19 = _j("fase19/robustez_schema_opaco_api.json")
if f19:
    e = f19["execution_accuracy"]
    checa("F19 original (README diz 100%)", e["original"]["taxa"], 1.0)
    checa("F19 opaco (README diz 100%)", e["schema_opaco"]["taxa"], 1.0)
    checa("F19 delta (README diz 0,00 pp)", e["delta_pp"], 0.0)
    checa("F19 custo (README diz US$ 0,19)", f19["custo_usd"], 0.1925, 0.0001)
    checa("F19 previsao registrada (doc diz -9 pp)",
          f19["previsao_registrada"]["delta_pp"], -9.0)
    checa("F19 previsao acertou? (doc diz REFUTADA)",
          f19["veredito"]["dentro_da_faixa_prevista"], False)

f14r = _j("fase14/robustez_schema_opaco.json")
if f14r:
    checa("F14 delta do Qwen (README diz -29,4 pp)",
          f14r["execution_accuracy"]["delta_pp"], -29.41, 0.01)

print("\n=== FASE 20 ===")
f20 = _j("fase20/resultado_duro.json")
if f20:
    s = f20["sistemas"]
    checa("F20 tier_a respondiveis (README diz 35/35)",
          s["tier_a_antt"]["execution_accuracy_respondiveis"]["acertos"], 35)
    checa("F20 n respondiveis", s["tier_a_antt"]["execution_accuracy_respondiveis"]["n"], 35)
    checa("F20 tier_a abstencao (README diz 50%)",
          s["tier_a_antt"]["acuracia_abstencao"]["taxa"], 0.5)
    checa("F20 sql_cru abstencao (README diz 0%)",
          s["sql_cru_antt"]["acuracia_abstencao"]["taxa"], 0.0)
    checa("F20 custo (README diz US$ 0,30)", f20["custo_usd"], 0.2965, 0.0001)
g20 = _j("fase20/gold_duro.json")
if g20:
    checa("F20 itens selados (doc diz 47)", g20["n_validos"], 47)
    checa("F20 descartados (doc diz 1)", g20["n_descartados"], 1)

print("\n=== FASE 21 ===")
f21 = _j("fase21/resultado_duro_rico.json")
if f21:
    ex, ab = f21["execution_accuracy_respondiveis"], f21["acuracia_abstencao"]
    checa("F21 respondiveis (README diz 38/39)", ex["acertos"], 38)
    checa("F21 n respondiveis (README diz 39)", ex["n"], 39)
    checa("F21 abstencao (README diz 6/8 = 75%)", ab["taxa"], 0.75)
    checa("F21 rebaixamento remanescente (doc diz 1)",
          f21["rebaixamento_de_tipo_remanescente"], 1)
    checa("F21 custo (doc diz US$ 0,142)", f21["custo_usd"], 0.1424, 0.0001)
g21 = _j("fase21/gold_duro_rico.json")
if g21:
    checa("F21 itens selados (doc diz 47)", g21["n_validos"], 47)
    checa("F21 viraram respondiveis (doc diz 4)", len(g21["viraram_respondiveis"]), 4)
aud = _j("fase21/auditoria_adversarial.json")
if aud:
    checa("F21 auditoria corretas (README diz 44/47)", aud["n"] - aud["n_defeitos"], 44)
    checa("F21 taxa correta (doc diz 93,6%)", aud["taxa_correta"], 0.9362, 0.001)
    checa("F21 defeitos (doc diz 3)", aud["n_defeitos"], 3)
cc = _j("fase21/concorrencia_api.json")
if cc:
    checa("F21 vazao relativa em c=8 (doc diz 5,74x)", cc["vazao_relativa"]["8"], 5.74, 0.01)
    checa("F21 melhor nivel (doc diz 8)", cc["melhor_nivel"], 8)
    checa("F21 criterio pre-declarado atendido", cc["escala"], True)

print("\n=== FASE 22 (historico do CI) ===")
# SNAPSHOT congelado no dia do conserto (03/08/2026). O README afirma o passado — "1 verde em 33"
# — entao a fonte tem de ser o snapshot, nao uma nova consulta: re-medir depois do conserto daria
# outro numero e o README, que fala de antes, pareceria mentir. Regravar so com
# `medir_historico_ci.py`, e de proposito.
ci = _j("fase22/historico_ci.json")
if ci:
    checa("F22 execucoes ate o conserto (README diz 33)", ci["n_execucoes"], 33)
    checa("F22 verdes (README diz 1)", ci["n_verdes"], 1)
    checa("F22 vermelhas seguidas (README diz 32)",
          ci["vermelhas_consecutivas_ate_a_ultima"], 32)
    checa("F22 dias vermelho (doc diz 12)", ci["dias_vermelho"], 12)
    checa("F22 unica verde = commit que criou o CI (F5)",
          ci["primeira_verde"]["sha"], "d5701540")
    checa("F22 quebrou no commit da F6 (serving/FastAPI)",
          ci["primeira_vermelha"]["sha"], "528387c9")

print("\n=== KAPPA HUMANO ===")
kh = _j("fase14/kappa_humano.json")
if kh:
    checa("kappa humano (README diz 1,0)", kh["concordancia_spec"]["cohen_kappa_metrica"], 1.0)
    checa("n anotados (README diz 40)", kh["n_anotados_por_humano"], 40)
co = _j("fase18/concordancia_opus5_x_autor.json")
if co:
    checa("Opus5 cego x autor (README diz 0,992)",
          co["concordancia_spec"]["cohen_kappa_metrica"], 0.9921, 0.0001)
    checa("discordantes (doc diz 1)", len(co["concordancia_spec"]["discordantes"]), 1)

print("\n=== BIRD / calibracao externa ===")
b = _j("fase13/resultado_bird.json") or _j("fase13/bird_minidev.json")
if b is None:
    for p in sorted((R / "fase13").glob("*.json")) if (R / "fase13").exists() else []:
        d = json.loads(p.read_text(encoding="utf-8"))
        if "execution_accuracy" in json.dumps(d)[:2000]:
            b = d
            print(f"  (usando {p.name})")
            break
if b:
    txt = json.dumps(b)
    m = re.search(r'"taxa":\s*(0\.4\d+)', txt)
    checa("BIRD EX (README diz 43,4%)", float(m.group(1)) if m else None, 0.434, 0.002)

print("\n=== CUSTO TOTAL DE API ===")
total = 0.0
for p in sorted(R.glob("fase*/*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    c = d.get("custo_usd")
    if c is None and isinstance(d.get("custo"), dict):
        c = d["custo"].get("custo_usd")
    if isinstance(c, (int, float)):
        total += c
        print(f"  {p.parent.name}/{p.name:38s} US$ {c:.4f}")
print(f"  {'TOTAL':50s} US$ {total:.4f}")

print(f"\n{'=' * 70}\nOK: {ok}   DIVERGENCIAS/AUSENTES: {falhas}")
raise SystemExit(1 if falhas else 0)
