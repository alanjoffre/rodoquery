#!/usr/bin/env bash
# Degrau 4 — roda teste-cuda.yaml e mostra o nvidia-smi executado DENTRO do pod.
set -uo pipefail
cd "$(dirname "$0")"
k3s kubectl delete pod teste-cuda --ignore-not-found >/dev/null
k3s kubectl apply -f teste-cuda.yaml
fase=""
for _ in $(seq 1 200); do
  fase="$(k3s kubectl get pod teste-cuda -o jsonpath='{.status.phase}' 2>/dev/null)"
  case "$fase" in Succeeded|Failed) break ;; esac
  sleep 3
done
echo "fase final: $fase"
echo "--- nvidia-smi DENTRO do pod ---"
k3s kubectl logs teste-cuda 2>&1
echo "--- recurso pedido ---"
k3s kubectl get pod teste-cuda -o jsonpath='{.spec.containers[0].resources.limits}'; echo
if [ "$fase" != "Succeeded" ]; then
  echo "--- eventos (diagnostico) ---"
  k3s kubectl describe pod teste-cuda | tail -15
fi
