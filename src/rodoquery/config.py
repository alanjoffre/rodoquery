"""Configuração central do RodoQuery (pydantic-settings).

Caminhos, seed e o modelo local. A fundação de dados (DuckDB + manifesto do dbt) vem da
plataforma toll-analytics-platform buildada; `TOLL_DUCKDB` e `TOLL_MANIFEST` apontam para lá.
Tudo sobrescrevível por variável de ambiente (prefixo RODOQUERY_).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
# Fundação buildada em filesystem WSL-NATIVO (não /mnt/d — lá o dbt/mf ficam lentos e flaky por
# I/O 9P). Ver docs/FUNDACAO.md. Sobrescrevível por env (RODOQUERY_TOLL_*).
_TOLL = Path.home() / "toll-foundation" / "dbt-toll-analytics"
_ANTT_RAIZ = Path.home() / "antt-foundation"
_ANTT = _ANTT_RAIZ / "dbt-antt"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RODOQUERY_", extra="ignore")

    seed: int = 42
    # LLM local (SUT) — teto realista em 6GB de VRAM.
    modelo_sut: str = "qwen2.5-coder:7b"
    modelo_emb: str = "nomic-embed-text"
    temperatura: float = 0.0  # reprodutibilidade: nunca depender de sorte

    # Fundação de dados SINTÉTICA (toll-analytics buildado) — a das Fases 0–10.
    toll_duckdb: Path = _TOLL / "toll_analytics.duckdb"
    toll_manifest: Path = _TOLL / "target" / "manifest.json"
    toll_semantic_manifest: Path = _TOLL / "target" / "semantic_manifest.json"

    # Fundação de dados REAL (ANTT, CC-BY) — a partir da Fase 11. Projeto dbt SEPARADO de
    # propósito: mexer no sintético invalidaria a reprodutibilidade das fases anteriores.
    # Reusa o binário `mf` do venv da fundação sintética (mesmo dbt/MetricFlow).
    antt_dbt_dir: Path = _ANTT
    antt_duckdb: Path = _ANTT_RAIZ / "antt_analytics.duckdb"
    antt_manifest: Path = _ANTT / "target" / "manifest.json"
    antt_semantic_manifest: Path = _ANTT / "target" / "semantic_manifest.json"
    antt_suite_dir: Path = Path.home() / "antt_suite"

    # Binário do MetricFlow. O default é o venv da fundação sintética (como sempre foi); num
    # container o `mf` está no PATH do sistema, então isto precisa ser sobrescrevível —
    # caminho de venv hardcoded é o que impedia empacotar o serviço (RODOQUERY_MF_BIN).
    mf_bin: Path = _TOLL / ".venv" / "bin" / "mf"

    # Qual fundação o SERVIÇO expõe: "sintetica" (Fases 0–10) ou "antt" (dado real).
    # Default sintética para não mudar o comportamento de nada que já foi medido.
    fundacao_ativa: str = "sintetica"

    # Endpoint do Ollama. Era hardcoded em `localhost` — num container o LLM vive noutro host
    # (RODOQUERY_OLLAMA_URL=http://ollama:11434/api/generate).
    ollama_url: str = "http://localhost:11434/api/generate"

    reports_dir: Path = REPO_ROOT / "reports"


settings = Settings()
