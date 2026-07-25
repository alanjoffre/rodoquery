"""Exporta uma amostra do golden ANTT para AUDITORIA ADVERSARIAL de labels (Fase 15).

Diferente do κ de máquina (2º anotador cego que RE-anota): aqui o crítico VÊ a spec do autor e tem
uma única missão — encontrar labels ERRADAS. É um teste mais forte para qualidade de rótulo, ainda
que de máquina (não substitui o κ humano; complementa)."""
import json
import random
from pathlib import Path

G = Path(__file__).resolve().parent
xs = [json.loads(x) for x in (G / "golden_antt.jsonl").read_text(encoding="utf-8").splitlines()
      if x.strip()]
random.Random(11).shuffle(xs)
sel = xs[:60]
CH = ("metrics", "group_by", "where", "order_by", "limit", "ordenado")
with (G / "_auditoria_labels.jsonl").open("w", encoding="utf-8") as f:
    for x in sel:
        s = x["spec"]
        f.write(json.dumps({"id": x["id"], "estrato": x["estrato"], "pergunta": x["pergunta_nl"],
                            "spec_autor": {k: s[k] for k in CH}}, ensure_ascii=False) + "\n")
print(f"exportados {len(sel)} itens -> {G / '_auditoria_labels.jsonl'}")
