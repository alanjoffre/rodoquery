#!/usr/bin/env bash
# Ablação 1 — a lentidão no cluster é da VERSÃO do Ollama?
#
# A base usa `ollama/ollama:latest`, que hoje resolve para 0.34.1; o Ollama nativo desta máquina é
# 0.31.2. Com versões diferentes, "K8s é 2x mais lento que o nativo" misturaria duas causas. Aqui
# o pod é fixado na MESMA versão do nativo e nada mais muda (mesmo limite de CPU, mesmo modelo no
# mesmo volume). Se a diferença sumir, era a versão; se ficar, não era.
set -uo pipefail
VERSAO="${1:?versao do ollama, ex.: 0.31.2}"
NS=rodoquery
k3s kubectl -n $NS set image statefulset/ollama ollama="ollama/ollama:${VERSAO}"
k3s kubectl -n $NS rollout status statefulset/ollama --timeout=1800s
k3s kubectl -n $NS wait --for=condition=Ready pod/ollama-0 --timeout=600s
echo "ollama no pod: $(k3s kubectl -n $NS exec ollama-0 -- ollama --version 2>&1 | tail -1)"
k3s kubectl -n $NS exec ollama-0 -- ollama list
