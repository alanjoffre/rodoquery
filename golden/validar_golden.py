"""Valida cada item do golden do autor (compila no mf + gold não-vazio) e salva só os válidos."""
from pathlib import Path

from rodoquery.golden import ItemGolden, carregar, resumo_estratos, salvar, validar_item

itens = carregar(Path("golden/autor.jsonl"))
validos: list[ItemGolden] = []
for it in itens:
    ok, motivo = validar_item(it)
    if ok:
        validos.append(it)
    else:
        print(f"X  {it.id}: {motivo}  ::  {it.pergunta_nl}")

salvar(validos, Path("golden/golden.jsonl"))
print(f"\nvalidos: {len(validos)}/{len(itens)}")
print("por estrato:", resumo_estratos(validos))
