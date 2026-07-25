"""Fase 15 — aplica o veredito da AUDITORIA ADVERSARIAL de labels ao golden ANTT.

O auditor (crítico forte, com acesso à spec do autor e missão única de achar erro) encontrou 7
defeitos em 60 itens. Cada um tem mecanismo verificável; removo todos, do golden e dos splits, e
re-selo o TEST — mesmo protocolo das paráfrases da Fase 7 e dos ambíguos da Fase 9: label ruim sai
ANTES de qualquer nova medição.

Duas classes eram invisíveis às guardas existentes e ficam registradas para o gerador:
  - degeneração por dimensão CORRELACIONADA: `commercial_share` filtrada por `categoria_eixo='6'`
    é constante 1,0 porque todo veículo de 6 eixos é comercial. A G1 só olhava a dimensão que a
    métrica usa DIRETAMENTE.
  - "classe de veículo" é termo ambíguo no domínio (tipo × categoria tarifária por eixos).
"""
import hashlib
import json
from pathlib import Path

G = Path(__file__).resolve().parent / "golden"
ver = [json.loads(x) for x in (G / "_auditoria_veredito.jsonl").read_text(encoding="utf-8")
       .splitlines() if x.strip()]
remover = {d["id"] for d in ver}
print(f"veredito da auditoria: {len(remover)} defeitos")
for d in ver:
    print(f"  [{d['gravidade']:5s}] {d['id']}: {d['tipo_defeito']}")

for nome in ("golden_antt.jsonl", "golden_dev_antt.jsonl", "golden_test_antt.jsonl",
             "autor_antt.jsonl"):
    p = G / nome
    if not p.exists():
        continue
    linhas = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    mant = [x for x in linhas if json.loads(x)["id"] not in remover]
    p.write_text("\n".join(mant) + "\n", encoding="utf-8")
    print(f"{nome}: {len(linhas)} -> {len(mant)}")
    if nome == "golden_test_antt.jsonl":
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        (G / "golden_test_antt.sha256").write_text(sha + "\n", encoding="utf-8")
        print(f"  TEST re-selado: {sha[:16]}...")
