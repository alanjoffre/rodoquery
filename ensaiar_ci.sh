#!/usr/bin/env bash
# Ensaia o CI ANTES de empurrar — e o ensaio tem de divergir do runner em ZERO detalhes.
#
# Nasceu na Fase 22, depois de eu ensaiar errado tres vezes seguidas e cada vez passar aqui e
# falhar la:
#   1. rodei `python -m pytest` (o -m poe o cwd no sys.path); o CI roda `pytest`, que nao poe;
#   2. rodei na ARVORE DE TRABALHO, que tem arquivos gitignorados que o runner nao recebe;
#   3. clonei o HEAD com o conserto ainda so na arvore — ensaiei o codigo antigo.
# Toda vez que o ensaio diverge do alvo em um detalhe, ele passa e o alvo falha.
#
# Por isso aqui: CLONE do commit (so arquivos rastreados), VENV novo com o mesmo extra `[test]`,
# a fundacao de dados apontada para caminhos inexistentes (o runner nao tem DuckDB, MetricFlow
# nem chave de API) e o CONSOLE SCRIPT `pytest`, nunca `python -m pytest`.
#
# Uso: bash ensaiar_ci.sh            # ensaia o ultimo commit
#      bash ensaiar_ci.sh --negativo # + controle negativo: sem `pythonpath`, a trava DEVE reprovar
set -u
ORIGEM="$(cd "$(dirname "$0")" && pwd)"
ALVO=/tmp/ensaio_ci
NEG="${1:-}"

if [ -n "$(git -C "$ORIGEM" status --porcelain)" ]; then
  echo "AVISO: ha mudancas nao commitadas — o clone NAO as vera (foi o erro #3 da F22)."
  git -C "$ORIGEM" status --short
  echo
fi

rm -rf "$ALVO"
git clone -q "$ORIGEM" "$ALVO" || exit 9
cd "$ALVO" || exit 9
python3 -m venv .venv >/dev/null
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e ".[test]" || exit 9
export PATH="$ALVO/.venv/bin:$PATH"
export RODOQUERY_TOLL_DUCKDB=/nao/existe/t.duckdb
export RODOQUERY_ANTT_DUCKDB=/nao/existe/a.duckdb
export RODOQUERY_ANTT_SUITE_DIR=/nao/existe
export RODOQUERY_MF_BIN=/nao/existe/mf
unset ANTHROPIC_API_KEY
echo "ensaiando $(git log --oneline -1)"

if [ "$NEG" = "--negativo" ]; then
  echo
  echo "=== CONTROLE NEGATIVO: sem \`pythonpath\`, a trava de coleta DEVE reprovar ==="
  sed -i '/^pythonpath = \["\."\]$/d' pyproject.toml
  python verificar_coleta.py >/dev/null 2>&1
  rc=$?
  [ "$rc" -ne 0 ] && echo "  OK    trava reprovou (rc=$rc), como tem de reprovar" \
                  || echo "  FALHA trava APROVOU o estado quebrado — falso negativo"
  git checkout -q pyproject.toml
fi

falhou=0
passo() {  # passo "rotulo" comando...
  local rotulo="$1"; shift
  local saida; saida="$("$@" 2>&1)"; local rc=$?
  [ "$rc" -ne 0 ] && falhou=1
  printf '%-26s rc=%d\n' "$rotulo" "$rc"
  [ "$rc" -ne 0 ] && echo "$saida" | tail -20
  return 0
}

echo
echo "=== sequencia do .github/workflows/ci.yml ==="
passo "1. Lint (ruff)"        ruff check .
passo "2. Coleta completa"    python verificar_coleta.py
passo "3. Testes"             pytest -q
passo "4. Gate (nivel A)"     python gate_regressao.py

echo
[ "$falhou" -eq 0 ] && echo "ENSAIO VERDE — mas o veredito e a execucao do Actions, nao esta." \
                    || { echo "ENSAIO VERMELHO — nao empurre."; exit 1; }
