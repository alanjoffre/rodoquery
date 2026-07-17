"""Test-suite de bancos — mata os FALSOS POSITIVOS do Execution Accuracy (Fase 0).

**O problema.** Num único banco sintético, uma query ERRADA pode devolver o mesmo resultado da
gold por coincidência (ex.: um filtro a mais que, *nestes dados*, não muda nada). Isso **infla** o
EX. Um revisor staff pergunta isso em 10 segundos.

**A solução (estilo Spider Test-Suite).** Como os dados são sintéticos e o gerador aceita `--seed`,
geramos **N bancos variantes** e só contamos acerto se o predito bater a gold em **TODOS**. Uma
coincidência raramente sobrevive a várias distribuições diferentes.

Reusa o pipeline real da plataforma (mesmo padrão do `scripts/benchmark.sh`):
    generate_data.py --seed S --out <landing_S>   →  dlt (TOLL_LANDING_DIR, DBT_DUCKDB_PATH)
    →  dbt build  →  <db_S>.duckdb

Uso:  python -m rodoquery.suite_dbs --seeds 1 2 3 --escala 5000
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from rodoquery.config import REPO_ROOT, settings
from rodoquery.proveniencia import carimbar

# Raiz da plataforma-fonte (o dbt-toll-analytics fica dentro dela).
PLATAFORMA = settings.toll_duckdb.parent.parent
INGESTAO = PLATAFORMA / "ingestion-toll-analytics"
DBT = PLATAFORMA / "dbt-toll-analytics"


def _rodar(cmd: list[str], cwd: Path, env_extra: dict[str, str] | None = None) -> None:
    import os

    env = {**os.environ, **(env_extra or {})}
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"falhou: {' '.join(cmd)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")


def construir_variante(seed: int, escala: int, destino: Path) -> Path:
    """Gera dados com `seed`, ingere e roda o dbt build → devolve o caminho do .duckdb."""
    landing = destino / f"landing_seed{seed}"
    db = destino / f"toll_seed{seed}.duckdb"
    for p in (db, Path(str(db) + ".wal")):
        p.unlink(missing_ok=True)

    _rodar(
        [str(INGESTAO / ".venv/bin/python"), "generate_data.py",
         "--scale", str(escala), "--out", str(landing), "--seed", str(seed)],
        cwd=INGESTAO,
    )
    _rodar(
        [str(INGESTAO / ".venv/bin/python"), "toll_ingestion.py"],
        cwd=INGESTAO,
        env_extra={"TOLL_LANDING_DIR": str(landing), "DBT_DUCKDB_PATH": str(db)},
    )
    _rodar(
        [str(DBT / ".venv/bin/dbt"), "build", "--exclude", "tag:observability",
         "--no-partial-parse", "--profiles-dir", "."],
        cwd=DBT,
        env_extra={"DBT_DUCKDB_PATH": str(db)},
    )
    return db


def construir_suite(seeds: list[int], escala: int, destino: Path) -> dict:
    destino.mkdir(parents=True, exist_ok=True)
    variantes, t0 = [], time.time()
    for seed in seeds:
        t = time.time()
        db = construir_variante(seed, escala, destino)
        variantes.append({
            "seed": seed,
            "duckdb": str(db),
            "bytes": db.stat().st_size,
            "segundos": round(time.time() - t, 1),
        })
        print(f"  seed {seed}: {db.name} ({variantes[-1]['segundos']}s)")
    return carimbar({
        "proposito": ("bancos variantes p/ Test-Suite Execution Accuracy: acerto só conta se o "
                      "predito bate a gold em TODAS as variantes (mata falso positivo)"),
        "escala_transacoes": escala,
        "n_variantes": len(variantes),
        "variantes": variantes,
        "segundos_total": round(time.time() - t0, 1),
    })


def main() -> int:
    ap = argparse.ArgumentParser(description="Gera os bancos variantes do test-suite.")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--escala", type=int, default=5_000, help="nº de transações por variante")
    ap.add_argument("--destino", default="/tmp/rodoquery_suite")
    args = ap.parse_args()

    print(f"construindo {len(args.seeds)} variantes (escala={args.escala})...")
    res = construir_suite(args.seeds, args.escala, Path(args.destino))
    saida = REPO_ROOT / "reports" / "fase0" / "suite_dbs.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"suite pronta em {res['segundos_total']}s -> {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
