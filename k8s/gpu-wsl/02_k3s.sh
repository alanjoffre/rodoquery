#!/usr/bin/env bash
# Degrau 2 — k3s dentro do WSL, versão FIXADA, binário conferido por sha256, SEM systemd.
#
# Por que sem systemd: o systemd está desligado neste WSL, e ligá-lo exige editar /etc/wsl.conf
# e `wsl --shutdown`, o que derruba tudo que roda na distro. O k3s não precisa dele: o binário é
# o servidor. Roda como processo avulso com `setsid`, a mesma lição do Ollama neste projeto
# (processo filho do shell do wsl.exe morre quando o shell fecha).
#
# Por que não `curl https://get.k3s.io | sh`: executar script remoto sem conferir é exatamente o
# risco de cadeia de suprimentos que um repositório público não deveria ensinar. Aqui baixa-se o
# binário e o arquivo de checksums da MESMA release, e só instala se conferir.
set -euo pipefail
VERSAO="v1.36.4+k3s1"
URL="https://github.com/k3s-io/k3s/releases/download/${VERSAO/+/%2B}"
TMP="$(mktemp -d)"

if command -v k3s >/dev/null && k3s --version | grep -qF "${VERSAO}"; then
  echo "k3s ${VERSAO} ja instalado"
else
  curl -fsSL -o "$TMP/k3s" "$URL/k3s"
  curl -fsSL -o "$TMP/sha256sum-amd64.txt" "$URL/sha256sum-amd64.txt"
  esperado="$(awk '$2=="k3s"{print $1}' "$TMP/sha256sum-amd64.txt")"
  obtido="$(sha256sum "$TMP/k3s" | awk '{print $1}')"
  [ -n "$esperado" ] && [ "$esperado" = "$obtido" ] || { echo "CHECKSUM NAO CONFERE: $obtido != $esperado"; exit 1; }
  echo "checksum confere: ${obtido:0:16}..."
  sudo install -m 0755 "$TMP/k3s" /usr/local/bin/k3s
fi
rm -rf "$TMP"
k3s --version | head -1

if pgrep -x k3s-server >/dev/null || pgrep -f "k3s server" >/dev/null; then
  echo "k3s server ja em execucao"
else
  # traefik e metrics-server desligados: nao participam do teste e so disputariam portas com o
  # Windows (networkingMode=mirrored compartilha as portas do host).
  sudo setsid nohup k3s server --write-kubeconfig-mode 644 \
    --disable traefik --disable metrics-server \
    > /tmp/k3s.log 2>&1 < /dev/null &
  echo "k3s server iniciado (log em /tmp/k3s.log)"
fi

echo "aguardando o no ficar Ready..."
for _ in $(seq 1 90); do
  if k3s kubectl get nodes 2>/dev/null | grep -q " Ready "; then break; fi
  sleep 2
done
k3s kubectl get nodes -o wide

echo "--- o k3s detectou o runtime da NVIDIA? ---"
CFG=/var/lib/rancher/k3s/agent/etc/containerd/config.toml
sudo grep -n -A3 'nvidia' "$CFG" | head -12 || echo "NVIDIA NAO aparece em $CFG"
echo "--- RuntimeClasses ---"
k3s kubectl get runtimeclass 2>&1
