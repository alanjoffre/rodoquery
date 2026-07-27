#!/usr/bin/env bash
# Prepara o contexto de build: a fundação (projeto dbt + DuckDB) vive FORA do repositório
# (~/antt-foundation), e o Docker não copia de fora do contexto. Este script a materializa em
# docker/_contexto/ (gitignorado), de forma explícita e reproduzível.
#
# Por que assar o DuckDB na imagem em vez de montar do host: são 27 MB de dado PÚBLICO (ANTT,
# CC-BY). Assado, `docker compose up` funciona em qualquer máquina — que é o ponto de existir a
# imagem. Montado, só funcionaria na minha.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FUND="${ANTT_FOUNDATION:-$HOME/antt-foundation}"
DEST="$RAIZ/docker/_contexto"

[ -d "$FUND/dbt-antt" ] || { echo "ERRO: projeto dbt não encontrado em $FUND/dbt-antt"; exit 1; }
[ -f "$FUND/antt_analytics.duckdb" ] || { echo "ERRO: DuckDB não encontrado em $FUND"; exit 1; }

rm -rf "$DEST"
mkdir -p "$DEST"

# projeto dbt SEM artefatos de build (o `dbt parse` roda dentro da imagem, garantindo que o
# manifesto corresponde ao código que foi copiado — e não a um build velho da minha máquina).
cp -r "$FUND/dbt-antt" "$DEST/dbt-antt"
rm -rf "$DEST/dbt-antt/target" "$DEST/dbt-antt/dbt_packages" "$DEST/dbt-antt/logs"

cp "$FUND/antt_analytics.duckdb" "$DEST/antt_analytics.duckdb"

echo "contexto pronto em $DEST"
du -sh "$DEST"/* | sed 's/^/  /'
