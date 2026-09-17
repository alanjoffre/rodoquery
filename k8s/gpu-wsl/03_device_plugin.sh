#!/usr/bin/env bash
# Degrau 3 — o nó anuncia `nvidia.com/gpu`? É a pergunta central do experimento.
#
# O device plugin é quem conversa com a NVML e registra o recurso no kubelet. No WSL a GPU não
# aparece como /dev/nvidia*, e sim como /dev/dxg — o plugin tem caminho de código próprio para
# isso desde a v0.16 ("wsl: report a single 'all' device", v0.19.1). Se este degrau falhar, o
# bloqueio é do plugin no WSL, e fica registrado com a mensagem exata.
set -euo pipefail
cd "$(dirname "$0")/device-plugin"
URL="https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.20.0/deployments/static/nvidia-device-plugin.yml"

if [ ! -f nvidia-device-plugin.yml ]; then
  curl -fsSL -o nvidia-device-plugin.yml "$URL"
  echo "vendorizado de $URL"
fi
# Confere que o arquivo local ainda e o da tag (nao foi editado a mao).
remoto="$(curl -fsSL "$URL" | sha256sum | awk '{print $1}')"
local_="$(sha256sum nvidia-device-plugin.yml | awk '{print $1}')"
[ "$remoto" = "$local_" ] || { echo "VENDORIZADO DIVERGE DA TAG: $local_ != $remoto"; exit 1; }
echo "manifesto vendorizado == tag v0.20.0 (sha256 ${local_:0:16}...)"

k3s kubectl apply -k .
echo "aguardando o pod do plugin..."
k3s kubectl -n kube-system rollout status ds/nvidia-device-plugin-daemonset --timeout=300s || true
k3s kubectl -n kube-system get pods -l name=nvidia-device-plugin-ds -o wide

echo "--- log do plugin ---"
k3s kubectl -n kube-system logs -l name=nvidia-device-plugin-ds --tail=25 2>&1 || true

echo "--- capacidade do no ---"
for _ in $(seq 1 30); do
  gpu="$(k3s kubectl get node -o jsonpath='{.items[0].status.allocatable.nvidia\.com/gpu}' 2>/dev/null)"
  [ -n "$gpu" ] && break
  sleep 2
done
echo "allocatable nvidia.com/gpu = ${gpu:-<AUSENTE>}"
