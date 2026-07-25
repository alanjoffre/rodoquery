"""Fase 15 — holdout de ABLAÇÃO fresco, disjunto de TUDO (golden_antt + robustez_antt).

Serve para medir, sem fitar a teste visto, os dois levers contra o resíduo de seleção de
métrica/dimensão: descrições melhores e SUT maior. Semente nova; specs inéditas verificadas contra
os dois conjuntos anteriores; inclui abstenções (o lever de descrição também mira a substituição
semântica).
"""
import collections
import json
from pathlib import Path

import gerar_autor_antt as gen

G = Path(__file__).resolve().parent
POR_ESTRATO = 6


def _assinaturas(arq):
    out = set()
    p = G / arq
    if not p.exists():
        return out
    for it in (json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()):
        s = it["spec"]
        out.add((tuple(s["metrics"]), tuple(s["group_by"]), s["where"], tuple(s["order_by"]),
                 s["limit"], bool(s["ordenado"])))
    return out


usadas = _assinaturas("autor_antt.jsonl") | _assinaturas("robustez_antt_autor.jsonl")
perguntas = set()
for arq in ("autor_antt.jsonl", "robustez_antt_autor.jsonl"):
    p = G / arq
    if p.exists():
        for it in (json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()):
            perguntas.add(it["pergunta_nl"].strip().lower())

gen.rng.seed(31337)
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
        itens.append({"id": f"{estrato}_abl_{n:02d}", "pergunta_nl": perg, "estrato": estrato,
                      "spec": spec, "revisado_humano": False})

# abstenções near-miss frescas (o lever de descrição mira a substituição semântica)
ABST = [
    "Qual a arrecadação de pedágio por concessionária?",
    "Qual o valor médio de tráfego por praça?",
    "Qual o pico de tráfego por hora?",
    "Quantos veículos únicos passaram?",
    "Qual a variação do tráfego versus o mês passado?",
    "Qual o tráfego por unidade da federação?",
]
for i, p in enumerate(ABST[:POR_ESTRATO], 1):
    if p.strip().lower() in perguntas:
        continue
    itens.append({"id": f"abstencao_abl_{i:02d}", "pergunta_nl": p, "estrato": "abstencao",
                  "spec": gen.sp([]), "revisado_humano": False})

dest = G / "ablacao_antt_autor.jsonl"
dest.write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in itens),
                encoding="utf-8")
c = collections.Counter(it["estrato"] for it in itens)
print(f"ablacao ANTT: {len(itens)} itens ineditos (disjuntos)  {dict(sorted(c.items()))}")
print(f"-> {dest}")
