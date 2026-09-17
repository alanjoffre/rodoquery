#!/usr/bin/env bash
# Degrau 1 — NVIDIA Container Toolkit no WSL, versão FIXADA.
#
# No WSL o driver da GPU vive no WINDOWS; o Linux só vê /dev/dxg e as bibliotecas em
# /usr/lib/wsl/lib. Nada de driver é instalado aqui — só o runtime que injeta esses dois
# pontos nos containers. É o mesmo pacote que a documentação da NVIDIA usa para Docker nativo
# no WSL; o que este experimento testa é se ele serve também ao containerd do k3s.
set -euo pipefail
VERSAO="1.20.0-1"

if dpkg -s nvidia-container-toolkit >/dev/null 2>&1; then
  echo "toolkit ja instalado: $(dpkg-query -W -f='${Version}' nvidia-container-toolkit 2>/dev/null || dpkg -s nvidia-container-toolkit | grep ^Version)"
else
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
  sudo apt-get update -qq
  # SEM `| head`: com `set -o pipefail`, o head fecha o pipe cedo, o apt-cache morre de SIGPIPE
  # (rc 141) e o `set -e` encerra o script calado. Foi exatamente o que aconteceu na 1a execucao.
  echo "versao fixada disponivel: $(apt-cache madison nvidia-container-toolkit | awk -v v="$VERSAO" '$3==v{print $3}')"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    "nvidia-container-toolkit=${VERSAO}" "nvidia-container-toolkit-base=${VERSAO}" \
    "libnvidia-container-tools=${VERSAO}" "libnvidia-container1=${VERSAO}"
fi

echo "--- verificacao ---"
nvidia-ctk --version | head -1
command -v nvidia-container-runtime
# O que o runtime enxerga no WSL: se isto nao listar a GPU, os degraus seguintes nao tem chance.
nvidia-container-cli info 2>&1 | head -8 || echo "nvidia-container-cli info FALHOU (esperado em alguns modos WSL; o CDI e a alternativa)"
