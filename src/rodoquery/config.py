"""Configuração central do RodoQuery (pydantic-settings).

Caminhos, seed e o modelo local. A fundação de dados (DuckDB + manifesto do dbt) vem da
plataforma toll-analytics-platform buildada; `TOLL_DUCKDB` e `TOLL_MANIFEST` apontam para lá.
Tudo sobrescrevível por variável de ambiente (prefixo RODOQUERY_).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
# A plataforma-fonte fica ao lado do repo (../toll-analytics-platform) por padrão.
_TOLL = REPO_ROOT.parent / "toll-analytics-platform" / "dbt-toll-analytics"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RODOQUERY_", extra="ignore")

    seed: int = 42
    # LLM local (SUT) — teto realista em 6GB de VRAM.
    modelo_sut: str = "qwen2.5-coder:7b"
    modelo_emb: str = "nomic-embed-text"
    temperatura: float = 0.0  # reprodutibilidade: nunca depender de sorte

    # Fundação de dados (toll-analytics buildado).
    toll_duckdb: Path = _TOLL / "toll_analytics.duckdb"
    toll_manifest: Path = _TOLL / "target" / "manifest.json"
    toll_semantic_manifest: Path = _TOLL / "target" / "semantic_manifest.json"

    reports_dir: Path = REPO_ROOT / "reports"


settings = Settings()
