"""Carimbo de reprodutibilidade em todo report (herdado do RodoIA, adaptado).

Além de seed/git_sha/versões, carimba o que torna um número de LLM reproduzível e que é
frequentemente esquecido: o **digest do modelo** (pull de modelo muda o número) e o **hash do
template de prompt** (a versão do prompt é parâmetro de experimento). Sem isso, o gate de CI
seria uma farsa.
"""
from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

from rodoquery.config import REPO_ROOT, settings

_PACOTES = ("duckdb", "sqlglot", "numpy", "pydantic-settings")


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        return ""


def _git_dirty() -> tuple[bool, str]:
    porcelain = _git("status", "--porcelain")
    dirty = bool(porcelain)
    diff_sha1 = hashlib.sha1(porcelain.encode()).hexdigest()[:12] if dirty else ""
    return dirty, diff_sha1


def hash_texto(texto: str) -> str:
    """Hash curto e estável de um texto (ex.: template de prompt)."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _versoes() -> dict[str, str]:
    out = {}
    for p in _PACOTES:
        try:
            out[p] = version(p)
        except PackageNotFoundError:
            out[p] = "n/d"
    return out


def carimbar(payload: dict) -> dict:
    """Anexa `_proveniencia` a um dict de resultado, sem mutar o original."""
    dirty, diff_sha1 = _git_dirty()
    return {
        **payload,
        "_proveniencia": {
            "seed": settings.seed,
            "modelo_sut": settings.modelo_sut,
            "temperatura": settings.temperatura,
            "git_sha": _git("rev-parse", "--short", "HEAD"),
            "git_dirty": dirty,
            "git_diff_sha1": diff_sha1,
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "versoes": _versoes(),
        },
    }
