#!/usr/bin/env bash
# Para o k3s e desfaz o que ele criou na REDE do WSL — mantendo os DADOS (modelo de 4,7 GB,
# imagens, volumes), para o cluster voltar em segundos com `02_k3s.sh` em vez de re-baixar tudo.
#
# O k3s foi instalado SEM o script oficial (binário conferido por sha256), então o `k3s-killall.sh`
# não existe aqui. Isto reproduz a parte dele que importa: processos, montagens, interfaces de rede
# e regras de iptables com prefixo KUBE-/CNI-/flannel. Sem limpar a rede, interfaces e regras
# órfãs ficariam no WSL depois de o processo morrer.
#
# Remoção COMPLETA (apaga modelo e imagens):  --apagar-dados
set -uo pipefail
APAGAR="${1:-}"

echo "--- parando o k3s ---"
sudo pkill -f "k3s server" 2>/dev/null
for _ in $(seq 1 30); do pgrep -f "k3s server" >/dev/null || break; sleep 1; done
# Os containers sobrevivem ao servidor: os shims são processos próprios.
sudo pkill -f "containerd-shim-runc" 2>/dev/null
sleep 3
# Contagem sem falso positivo NEM falso negativo, e as duas formas ingênuas falham:
#   - `pgrep -f 'containerd-shim'` casa com a linha de comando de QUEM CHAMOU o script;
#   - `pgrep -x containerd-shim-runc-v2` nunca casa: o nome tem mais de 15 caracteres, e o `-x`
#     compara com /proc/PID/comm, que é truncado nesse limite (o próprio pgrep avisa).
# Ancorar no caminho do binário resolve: nenhum chamador tem isso na linha de comando.
echo "processos k3s restantes: $(( $(pgrep -xc k3s-server || true) + $(pgrep -cf '^/var/lib/rancher/k3s/data/.*containerd-shim' || true) ))"

echo "--- montagens ---"
# /var/lib/kubelet ENTRA na lista, e por último: o kubelet monta o diretório sobre si mesmo (para
# ter propagação compartilhada), então ele fica "Device or resource busy" mesmo vazio, e o
# `rm -rf` do final falha sem isso. Ordem inversa (`sort -r`) desmonta os filhos primeiro.
for alvo in /run/k3s /var/lib/kubelet/pods /var/lib/kubelet/plugins /run/netns/cni- /var/lib/kubelet; do
  awk -v a="$alvo" '$2 ~ "^"a {print $2}' /proc/self/mounts | sort -r | xargs -r -n1 sudo umount -l 2>/dev/null
done

echo "--- rede ---"
ip netns show 2>/dev/null | awk '/^cni-/{print $1}' | xargs -r -n1 sudo ip netns delete
ip -o link show 2>/dev/null | awk -F': ' '/master cni0/{sub(/@.*/,"",$2); print $2}' | xargs -r -n1 sudo ip link delete
for iface in cni0 flannel.1 flannel-v6.1 kube-ipvs0 flannel-wg flannel-wg-v6; do
  ip link show "$iface" >/dev/null 2>&1 && sudo ip link delete "$iface" && echo "removida: $iface"
done
sudo rm -rf /var/lib/cni/
for t in iptables ip6tables; do
  if command -v "${t}-save" >/dev/null; then
    sudo "${t}-save" | grep -v KUBE- | grep -v CNI- | grep -iv flannel | sudo "${t}-restore"
    echo "$t: regras KUBE-/CNI-/flannel removidas"
  fi
done

if [ "$APAGAR" = "--apagar-dados" ]; then
  # /etc/rancher/node guarda a credencial do nó — some junto, senão fica um segredo órfão.
  sudo rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/rancher/node /var/lib/kubelet
  # `rmdir` e não `rm -rf`: só remove se estiver vazio. Se outra coisa usar estes diretórios, eles
  # ficam — apagar o pai por hábito é como se perde dado de terceiro.
  sudo rmdir /var/lib/rancher /etc/rancher 2>/dev/null
  echo "dados do k3s apagados"
  for d in /var/lib/rancher/k3s /etc/rancher/k3s /var/lib/kubelet; do
    [ -e "$d" ] && echo "AINDA EXISTE: $d"
  done
else
  echo "dados mantidos: $(sudo du -sh /var/lib/rancher/k3s 2>/dev/null | cut -f1) em /var/lib/rancher/k3s"
  echo "para apagar tudo: bash $0 --apagar-dados"
fi
echo "GPU livre? VRAM em uso: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
