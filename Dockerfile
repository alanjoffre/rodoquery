# RodoQuery — imagem do serviço (Tier-A sobre o Semantic Layer da ANTT, dado real CC-BY).
#
# O que vai dentro: o pacote, o dbt/MetricFlow (o serviço COMPILA specs em runtime, via `mf`) e a
# fundação (projeto dbt + DuckDB de 27 MB). Antes de buildar: `bash docker/preparar_contexto.sh`.
#
# O `dbt parse` roda no BUILD, não no runtime: o manifesto semântico é determinístico e assá-lo
# tira ~10 s do primeiro request. Compilar spec→SQL é data-independente (invariante que sustenta o
# Test-Suite EX), então o `mf` não precisa do banco para gerar SQL — só a execução precisa.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DO_NOT_TRACK=1 \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false

WORKDIR /app

# dbt + MetricFlow nas versões que geraram os resultados publicados (reprodutibilidade).
RUN pip install --no-cache-dir \
        "dbt-core==1.11.12" \
        "dbt-duckdb==1.10.1" \
        "dbt-metricflow==0.13.0"

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir ".[serve,llm]"

# Fundação: projeto dbt + banco (materializados por docker/preparar_contexto.sh).
COPY docker/_contexto/dbt-antt/ /fundacao/dbt-antt/
COPY docker/_contexto/antt_analytics.duckdb /fundacao/antt_analytics.duckdb

ENV DBT_PROFILES_DIR=/fundacao/dbt-antt \
    DBT_DUCKDB_PATH=/fundacao/antt_analytics.duckdb

# Gera target/semantic_manifest.json — é o que o `mf query --explain` lê.
RUN cd /fundacao/dbt-antt && dbt parse

# Aponta o pacote para a fundação de dentro da imagem. Estes eram caminhos HARDCODED
# (venv do dbt, /home/alan/...) — o que impedia empacotar o serviço.
ENV RODOQUERY_FUNDACAO_ATIVA=antt \
    RODOQUERY_MF_BIN=/usr/local/bin/mf \
    RODOQUERY_ANTT_DBT_DIR=/fundacao/dbt-antt \
    RODOQUERY_ANTT_DUCKDB=/fundacao/antt_analytics.duckdb \
    RODOQUERY_ANTT_MANIFEST=/fundacao/dbt-antt/target/manifest.json \
    RODOQUERY_ANTT_SEMANTIC_MANIFEST=/fundacao/dbt-antt/target/semantic_manifest.json \
    RODOQUERY_OLLAMA_URL=http://ollama:11434/api/generate

# Não roda como root; o banco é aberto read-only pelo serviço.
RUN useradd --create-home --uid 10001 rodo && chown -R rodo:rodo /fundacao
USER rodo

EXPOSE 8077

# /saude não toca o LLM nem o banco — é liveness de verdade, não um health que mente.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8077/saude', timeout=4).status==200 else 1)"

CMD ["uvicorn", "rodoquery.servico:app", "--host", "0.0.0.0", "--port", "8077"]
