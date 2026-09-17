#!/usr/bin/env bash
# Coleta as evidências de CADA degrau enquanto o cluster ainda está no ar, em arquivos de texto
# que o consolidar.py lê. Cópia do que o cluster DISSE, não resumo do que eu lembro.
set -uo pipefail
SAIDA="${1:?diretorio de saida}"
mkdir -p "$SAIDA"
K="k3s kubectl"

{
  echo "driver_windows=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader)"
  echo "gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader)"
  echo "vram_total=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader)"
  echo "cuda_driver=$(nvidia-container-cli info 2>/dev/null | awk -F: '/CUDA version/{gsub(/ /,"",$2); print $2}')"
  echo "toolkit=$(nvidia-ctk --version 2>/dev/null | head -1 | awk '{print $NF}')"
  echo "k3s=$(k3s --version | head -1 | awk '{print $3}')"
  echo "containerd=$($K get node -o jsonpath='{.items[0].status.nodeInfo.containerRuntimeVersion}')"
  echo "kernel=$(uname -r)"
  echo "device_plugin_imagem=$($K -n kube-system get ds nvidia-device-plugin-daemonset -o jsonpath='{.spec.template.spec.containers[0].image}')"
} > "$SAIDA/versoes.txt"

$K get node -o jsonpath='{.items[0].status.allocatable.nvidia\.com/gpu}' > "$SAIDA/allocatable_gpu.txt"
$K -n kube-system logs -l name=nvidia-device-plugin-ds --tail=200 2>/dev/null \
  | grep -E "Detected platform|discovery strategy|Registered device plugin" > "$SAIDA/device_plugin_log.txt"
$K logs teste-cuda > "$SAIDA/teste_cuda_nvidia_smi.txt" 2>&1
$K get pod teste-cuda -o jsonpath='{.status.phase}' > "$SAIDA/teste_cuda_fase.txt"
$K get runtimeclass nvidia -o jsonpath='{.handler}' > "$SAIDA/runtimeclass_handler.txt"
$K -n rodoquery get pod ollama-0 \
  -o jsonpath='{.spec.runtimeClassName} {.spec.containers[0].resources.limits}' > "$SAIDA/ollama_pod_spec.txt"
ls -la "$SAIDA"
cat "$SAIDA/versoes.txt"
