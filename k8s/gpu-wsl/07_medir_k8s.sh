#!/usr/bin/env bash
# Degrau 5c — mede o RodoQuery DENTRO do cluster, com o Ollama na GPU, nos dois catálogos.
#
# Acesso por port-forward ao Service (não ao pod): é o caminho que um cliente do cluster usaria.
# Depois de cada série, registra a PROVA de que a inferência foi na GPU — `ollama ps` dentro do
# pod mostra a divisão CPU/GPU, e o log do Ollama diz quantas camadas foram para a placa.
set -uo pipefail
SAIDA="${1:?diretorio de saida}"; ROTULO="${2:?rotulo, ex.: k8s-gpu-ollama0.34.1}"
mkdir -p "$SAIDA"
cd "$HOME/rodoquery"
source .venv/bin/activate
NS=rodoquery

encaminhar() {
  pkill -f "port-forward -n $NS svc/rodoquery" 2>/dev/null; sleep 1
  setsid nohup k3s kubectl port-forward -n $NS svc/rodoquery 18077:80 \
    > /tmp/port_forward.log 2>&1 < /dev/null &
  for _ in $(seq 1 60); do curl -fs http://127.0.0.1:18077/saude >/dev/null && return 0; sleep 1; done
  echo "port-forward nao respondeu"; cat /tmp/port_forward.log; return 1
}

catalogo() {
  if [ "$1" = "rico" ]; then
    k3s kubectl -n $NS set env deploy/rodoquery RODOQUERY_CATALOGO_ANTT-
  else
    k3s kubectl -n $NS set env deploy/rodoquery RODOQUERY_CATALOGO_ANTT="$1"
  fi
  k3s kubectl -n $NS rollout status deploy/rodoquery --timeout=300s
}

for cat in basico rico; do
  catalogo "$cat" >/dev/null || exit 1
  encaminhar || exit 1
  python k8s/gpu-wsl/medir_consulta.py --base http://127.0.0.1:18077 \
    --rotulo "$ROTULO-$cat" --n 12 --saida "$SAIDA/${ROTULO}_$cat.json"
  echo "  divisao CPU/GPU no pod: $(k3s kubectl -n $NS exec ollama-0 -- ollama ps 2>/dev/null | awk 'NR==2{print $4, $5}')"
done
pkill -f "port-forward -n $NS svc/rodoquery" 2>/dev/null

echo "--- prova no log do Ollama do pod ---"
k3s kubectl -n $NS logs ollama-0 2>/dev/null | grep -Ei "offload|inference compute|library=cuda|total vram" | tail -6
k3s kubectl -n $NS exec ollama-0 -- ollama --version 2>&1 | tail -1 > "$SAIDA/${ROTULO}_ollama_versao.txt"
k3s kubectl -n $NS logs ollama-0 2>/dev/null | grep -Ei "offload|inference compute|library=cuda|total vram" \
  > "$SAIDA/${ROTULO}_ollama_gpu_log.txt"
k3s kubectl -n $NS exec ollama-0 -- ollama ps > "$SAIDA/${ROTULO}_ollama_ps.txt" 2>&1
