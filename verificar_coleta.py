"""Trava de COLETA: nenhum teste pode sumir em silêncio.

Por que existe. O CI instalava `.[dev]`, mas `tests/test_servico*.py` importam `fastapi`, que
vive no extra `[serve]`. A coleta do pytest quebrava, o build ficava vermelho — e ficou por oito
execuções seguidas sem ninguém ler o log. O modo de falha PERIGOSO é o simétrico: se aqueles dois
arquivos tivessem um `pytest.importorskip`, a suíte ficaria VERDE com 26 testes a menos, e o badge
diria "passando" sobre uma cobertura menor. Verde com teste faltando é pior que vermelho.

Esta trava afirma três coisas, todas falseáveis:
  1. a coleta não tem erro nenhum;
  2. TODO arquivo `tests/test_*.py` contribuiu com pelo menos um teste;
  3. o total não caiu abaixo do piso declarado abaixo.

O piso é `>=`: acrescentar teste passa sozinho, só a REMOÇÃO exige mexer aqui — e mexer é o
ponto, porque aí a queda vira decisão explícita, com autor e commit.
"""
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent
# Piso medido em 2026-08-03 (Fase 22). Só desça este número deliberadamente, no mesmo commit que
# remove os testes, explicando no corpo da mensagem por quê.
PISO_TOTAL = 216


class _Coletor:
    def __init__(self):
        self.itens: list[str] = []
        self.erros: list[str] = []

    def pytest_collection_modifyitems(self, items):
        self.itens = [i.nodeid for i in items]

    def pytest_collectreport(self, report):
        if report.failed:
            self.erros.append(f"{report.nodeid}: {report.longreprtext.strip().splitlines()[-1]}")


def main() -> int:
    c = _Coletor()
    pytest.main(["--collect-only", "-q", "--no-header", "-p", "no:cacheprovider"], plugins=[c])

    arquivos = sorted(p.name for p in (REPO / "tests").glob("test_*.py"))
    por_arquivo = Counter(n.split("::")[0].split("/")[-1] for n in c.itens)
    vazios = [a for a in arquivos if por_arquivo[a] == 0]

    print(f"\narquivos de teste no disco: {len(arquivos)}    testes coletados: {len(c.itens)}")
    for a in arquivos:
        print(f"  {'OK   ' if por_arquivo[a] else 'VAZIO'}  {a:34s} {por_arquivo[a]:4d}")

    problemas = []
    if c.erros:
        problemas += [f"erro de coleta -> {e}" for e in c.erros]
    if vazios:
        problemas += [f"arquivo coletou ZERO testes (extra faltando?) -> {a}" for a in vazios]
    if len(c.itens) < PISO_TOTAL:
        problemas.append(f"total {len(c.itens)} abaixo do piso declarado {PISO_TOTAL}")

    if problemas:
        print("\nCOLETA REPROVADA:")
        for p in problemas:
            print(f"  - {p}")
        return 1
    print(f"\nCOLETA OK — {len(c.itens)} testes, piso {PISO_TOTAL}, 0 arquivos vazios.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
