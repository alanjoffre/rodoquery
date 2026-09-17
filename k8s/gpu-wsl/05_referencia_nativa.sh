#!/usr/bin/env bash
# Degrau 5a — referência NATIVA + GPU, medida HOJE, na mesma máquina e com a mesma pergunta.
#
# Sem isto, o número do cluster só poderia ser comparado com a Fase 6, que mediu outra fundação
# (sintética), outras perguntas e outra versão do Ollama. Roda ANTES de subir o Ollama do cluster:
# os dois disputariam os 6 GB de VRAM e a comparação mediria a disputa, não o Kubernetes.
set -uo pipefail
cd "$HOME/rodoquery"
source .venv/bin/activate
SAIDA="${1:?diretorio de saida}"
mkdir -p "$SAIDA"

pgrep -x ollama >/dev/null || { setsid nohup ollama serve > /tmp/ollama_nativo.log 2>&1 < /dev/null & }
for _ in $(seq 1 60); do curl -fs http://127.0.0.1:11434/ >/dev/null && break; sleep 1; done
echo "ollama nativo: $(ollama --version 2>/dev/null | tail -1)"

subir_servico() {
  pkill -f "uvicorn rodoquery.servico:app" 2>/dev/null; sleep 2
  RODOQUERY_FUNDACAO_ATIVA=antt RODOQUERY_CATALOGO_ANTT="$1" DO_NOT_TRACK=1 \
    setsid nohup uvicorn rodoquery.servico:app --host 127.0.0.1 --port 8077 \
    > "/tmp/uvicorn_nativo_$1.log" 2>&1 < /dev/null &
  for _ in $(seq 1 60); do curl -fs http://127.0.0.1:8077/saude >/dev/null && return 0; sleep 1; done
  echo "servico nao subiu"; tail -20 "/tmp/uvicorn_nativo_$1.log"; return 1
}

for cat in basico rico; do
  subir_servico "$cat" || exit 1
  python k8s/gpu-wsl/medir_consulta.py --base http://127.0.0.1:8077 \
    --rotulo "nativo-gpu-$cat" --n 12 --saida "$SAIDA/nativo_gpu_$cat.json"
done
echo "--- uso da GPU pelo Ollama nativo ---"
ollama ps
nvidia-smi --query-gpu=memory.used --format=csv,noheader

# Libera a GPU para o degrau seguinte.
pkill -f "uvicorn rodoquery.servico:app"
ollama stop qwen2.5-coder:7b 2>/dev/null
pkill -x ollama; sleep 3
echo "VRAM apos liberar: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
