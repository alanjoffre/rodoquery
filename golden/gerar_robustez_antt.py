"""Fase 14 (#4) — conjunto de ROBUSTEZ dedicado, DISJUNTO do TEST-ANTT.

A Fase 7 mediu robustez reusando o TEST sintético — cada reuso erode um holdout. Esta fase resolve
isso: um conjunto próprio, gerado com semente diferente, cujas specs são INÉDITAS contra o golden
ANTT inteiro (dev+test). O TEST-ANTT não é tocado.

Reusa os candidatos do gerador principal (mesmas guardas G1–G4), mas:
  - semente nova (7777) → outras escolhas;
  - filtra contra as assinaturas JÁ usadas no golden_antt → disjunção verificada;
  - ~6 por estrato respondível → conjunto enxuto (a robustez é medida por delta pareado, não por
    EX absoluto, então N menor ainda dá sinal).

Roda: python golden/gerar_robustez_antt.py  → golden/robustez_antt_autor.jsonl
"""
import collections
import json
from pathlib import Path

import gerar_autor_antt as gen

G = Path(__file__).resolve().parent
POR_ESTRATO = 6

# assinaturas já usadas no golden ANTT (dev+test+removidos) — o conjunto de robustez é disjunto
usadas = set()
for it in (json.loads(x) for x in (G / "autor_antt.jsonl").read_text(encoding="utf-8").splitlines()
           if x.strip()):
    s = it["spec"]
    usadas.add((tuple(s["metrics"]), tuple(s["group_by"]), s["where"], tuple(s["order_by"]),
                s["limit"], bool(s["ordenado"])))
perguntas = {it["pergunta_nl"].strip().lower()
             for it in (json.loads(x) for x in
                        (G / "autor_antt.jsonl").read_text(encoding="utf-8").splitlines()
                        if x.strip())}

gen.rng.seed(7777)                          # semente nova → escolhas diferentes
itens = []
for estrato, fn in gen.PLANO:
    cands = fn()
    gen.rng.shuffle(cands)
    n = 0
    for spec, perg in cands:
        if n >= POR_ESTRATO:
            break
        s = gen.sig(spec)
        if s in usadas or perg.strip().lower() in perguntas:
            continue
        usadas.add(s)
        perguntas.add(perg.strip().lower())
        n += 1
        itens.append({"id": f"{estrato}_rob_{n:02d}", "pergunta_nl": perg, "estrato": estrato,
                      "spec": spec, "revisado_humano": False})

dest = G / "robustez_antt_autor.jsonl"
dest.write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in itens),
                encoding="utf-8")
c = collections.Counter(it["estrato"] for it in itens)
print(f"robustez ANTT: {len(itens)} itens INÉDITOS (disjuntos)  {dict(sorted(c.items()))}")
print(f"-> {dest}")
