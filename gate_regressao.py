"""Gate de regressão — CLI. Sai com código != 0 se qualquer checagem falhar (é o que trava o CI).

Nível A (default): contrato — selo do golden + coerência do relatório + limiares. NÃO precisa de
GPU, banco ou LLM, então roda no CI de graça e **não flaka**.

Nível B (--replay): re-executa as predições CONGELADAS contra o gold e exige que o veredito
item-a-item seja IDÊNTICO ao do relatório commitado. Não usa LLM (não flaka), mas precisa de
DuckDB + MetricFlow — por isso roda na máquina da fundação, não no CI. Pega regressão em
canonização, scorer, gold ou nas variantes do test-suite.

Uso:
  python gate_regressao.py            # nível A (CI): contrato
  python gate_regressao.py --replay   # nível B: re-executa as predições congeladas
  python gate_regressao.py --margem   # margem medida p/ o gate live (nível C)
"""
import json
import sys
from pathlib import Path

from rodoquery.regressao import (
    Limiares,
    carregar_margem_medida,
    gate_contrato,
    verificar_selo,
)

REPO = Path(__file__).resolve().parent

# Limiares com FOLGA sobre o observado (Tier-A EX=0,976; vantagem +54,8pp): um gate colado no valor
# medido vira alarme falso. Estes pegam regressão real sem brigar com o ruído do SUT.
LIMIARES = Limiares(ex_minimo=0.90, abstencao_minima=0.90, vantagem_minima_pp=30.0)


def _replay() -> int:
    """Nível B: re-executa as predições congeladas e exige veredito idêntico ao relatório."""
    from rodoquery.avaliacao import avaliar_sistema, carregar_hashes_gold, vetor_correto
    from rodoquery.golden import carregar

    rel = json.loads(
        (REPO / "reports" / "fase4" / "resultado_test.json").read_text(encoding="utf-8"))
    itens = carregar(REPO / "golden" / "golden_test.jsonl")
    hashes = carregar_hashes_gold()
    dbs = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}

    ok_geral = True
    for nome in ("tier_a", "sql_cru"):
        fp = REPO / "reports" / "fase4" / f"predicoes_{nome}_test.json"
        preds = json.loads(fp.read_text(encoding="utf-8"))
        agora = vetor_correto(
            avaliar_sistema(itens, None, hashes, dbs, nome, predicoes=preds))
        antes = {r["id"]: r["correto"] for r in rel["resultados_por_item"][nome]}
        divergem = [i for i in antes if antes[i] != agora.get(i)]
        ok_geral &= not divergem
        print(f"{'OK  ' if not divergem else 'FALHA'} replay[{nome}]: "
              f"{len(antes) - len(divergem)}/{len(antes)} vereditos idênticos"
              f"{'  divergem: ' + ','.join(divergem[:5]) if divergem else ''}")
    print("\nGATE (replay):", "PASSOU" if ok_geral else "FALHOU")
    return 0 if ok_geral else 1


def main() -> int:
    if "--replay" in sys.argv:
        return _replay()
    if "--margem" in sys.argv:
        f = REPO / "reports" / "fase5" / "flakiness.json"
        print(f"margem de flakiness medida (ex_max - ex_min): {carregar_margem_medida(f)}")
        return 0

    relatorio = json.loads(
        (REPO / "reports" / "fase4" / "resultado_test.json").read_text(encoding="utf-8"))
    selo = verificar_selo(REPO / "golden" / "golden_test.jsonl",
                          REPO / "golden" / "golden_test.sha256")
    res = gate_contrato(relatorio, LIMIARES, selo)
    print(res.relatorio())
    print("\nGATE:", "PASSOU" if res.ok else "FALHOU")
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
