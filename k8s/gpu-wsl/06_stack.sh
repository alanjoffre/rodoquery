#!/usr/bin/env bash
# Degrau 5b — a stack do RodoQuery no k3s, com o Ollama pedindo `nvidia.com/gpu`.
#
# A imagem `rodoquery:dev` vem do Docker Desktop (onde é construída) e é importada no containerd
# do k3s — os dois não compartilham image store. O modelo de 4,7 GB é baixado DENTRO do pod, como
# na Fase 17b: é o que um cluster de verdade faria, sem atalho de volume do host.
set -uo pipefail
TAR="${1:?caminho do rodoquery_dev.tar}"
cd "$HOME/rodoquery"

if ! sudo k3s ctr -n k8s.io images ls -q | grep -q "rodoquery:dev"; then
  echo "--- importando rodoquery:dev no containerd do k3s ---"
  sudo k3s ctr -n k8s.io images import "$TAR" 2>&1 | tail -1
fi

k3s kubectl apply -k k8s/gpu-wsl/stack

# Espera o OBJETO existir antes de esperar a condição: `kubectl wait` num pod que o StatefulSet
# ainda não criou falha na hora com NotFound — foi o que aconteceu na 1a execução deste script.
echo "--- aguardando o pod do Ollama existir e ficar Ready ---"
for _ in $(seq 1 120); do
  k3s kubectl -n rodoquery get pod ollama-0 >/dev/null 2>&1 && break
  sleep 2
done
k3s kubectl -n rodoquery wait --for=condition=Ready pod/ollama-0 --timeout=1800s || {
  k3s kubectl -n rodoquery describe pod ollama-0 | tail -20; exit 1; }
k3s kubectl -n rodoquery get pod ollama-0 \
  -o jsonpath='runtimeClass={.spec.runtimeClassName} limits={.spec.containers[0].resources.limits}{"\n"}'
echo "ollama no pod: $(k3s kubectl -n rodoquery exec ollama-0 -- ollama --version 2>&1 | tail -1)"

echo "--- baixando o modelo DENTRO do pod ---"
t0=$(date +%s)
k3s kubectl -n rodoquery exec ollama-0 -- ollama pull qwen2.5-coder:7b 2>&1 | tail -1
echo "pull: $(( $(date +%s) - t0 )) s"
k3s kubectl -n rodoquery exec ollama-0 -- ollama list

echo "--- aguardando o RodoQuery ---"
k3s kubectl -n rodoquery rollout status deploy/rodoquery --timeout=600s
k3s kubectl -n rodoquery get pods -o wide
