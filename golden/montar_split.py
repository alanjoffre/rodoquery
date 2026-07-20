"""Fase 3a — monta o golden completo (respondíveis + abstenção), valida, faz o split DEV/TEST
estratificado e sela o TEST (pré-registro anti-vazamento).

Saídas:
  golden/golden_full.jsonl   — 76 itens (61 respondíveis + 15 abstenção), todos válidos
  golden/golden_dev.jsonl    — ~30% visível (desenvolvimento/inspeção)
  golden/golden_test.jsonl   — ~70% holdout cego
  golden/golden_test.sha256  — selo do TEST (commitado ANTES de rodar sistemas)
"""
import hashlib
from pathlib import Path

from rodoquery.golden import (
    carregar,
    dividir_dev_test,
    resumo_estratos,
    salvar,
    validar_item,
)

REPO = Path.home() / "rodoquery"
G = REPO / "golden"

respondiveis = carregar(G / "golden.jsonl")       # 61, já validados na Fase 2
abstencao = carregar(G / "abstencao.jsonl")        # 15
itens = respondiveis + abstencao

# valida o lote de abstenção (respondíveis já passaram; revalidar abstenção é barato)
for it in abstencao:
    ok, motivo = validar_item(it)
    assert ok, f"abstenção inválida {it.id}: {motivo}"

salvar(itens, G / "golden_full.jsonl")

dev, test = dividir_dev_test(itens, frac_dev=0.30, seed=42)
salvar(dev, G / "golden_dev.jsonl")
salvar(test, G / "golden_test.jsonl")

sha = hashlib.sha256((G / "golden_test.jsonl").read_bytes()).hexdigest()
(G / "golden_test.sha256").write_text(sha + "\n", encoding="utf-8")

print(f"full : {len(itens)}  {resumo_estratos(itens)}")
print(f"DEV  : {len(dev)}  {resumo_estratos(dev)}")
print(f"TEST : {len(test)}  {resumo_estratos(test)}")
print(f"\nTEST selado sha256 = {sha}")
