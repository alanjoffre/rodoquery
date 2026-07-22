"""Fase 8 — split DEV/TEST do golden v2 e selo do TEST-v2 (pré-registro anti-vazamento).

**O TEST da v1 NÃO é tocado.** Ele é a evidência da Fase 4 e já foi consumido duas vezes (Fase 4 e
os deltas da Fase 7). Sobrescrevê-lo apagaria o histórico; misturá-lo aqui contaminaria a
replicação. A v2 vive em arquivos próprios, com selo próprio.

**frac_dev = 0.15** (contra 0.30 na v1): o sistema está CONGELADO desde a Fase 4 — não há mais
desenvolvimento para fazer, então quase todo item novo pode ir para o holdout. O DEV-v2 pequeno
serve só para inspecionar a qualidade do gerador sem olhar o TEST.
"""
import hashlib
from pathlib import Path

from rodoquery.golden import carregar, dividir_dev_test, resumo_estratos, salvar

G = Path(__file__).resolve().parent
itens = carregar(G / "golden_v2.jsonl")

dev, test = dividir_dev_test(itens, frac_dev=0.15, seed=42)
salvar(dev, G / "golden_dev_v2.jsonl")
salvar(test, G / "golden_test_v2.jsonl")

sha = hashlib.sha256((G / "golden_test_v2.jsonl").read_bytes()).hexdigest()
(G / "golden_test_v2.sha256").write_text(sha + "\n", encoding="utf-8")

print(f"v2 full : {len(itens)}  {resumo_estratos(itens)}")
print(f"DEV-v2  : {len(dev)}  {resumo_estratos(dev)}")
print(f"TEST-v2 : {len(test)}  {resumo_estratos(test)}")
print(f"\nTEST-v2 selado sha256 = {sha}")

abaixo = {e: n for e, n in resumo_estratos(test).items() if n < 25}
print(f"\nestratos abaixo de 25 no TEST-v2: {abaixo or 'nenhum'}")
