# Fase 24 — GPU no Kubernetes: "impossível nesta máquina" era mais do que tinha sido testado

Até 17/09/2026 o README dizia, sobre exercitar `nvidia.com/gpu` no cluster: *"nenhuma quantidade de
código resolve isto nesta máquina"*. A Fase 17b tinha testado **um** caminho — `kind` sobre o Docker
Desktop — e ele de fato não funciona (o Docker Desktop ignora `"default-runtime": "nvidia"`). A frase
generalizou esse único caminho para a máquina inteira.

Um caminho nunca tinha sido tentado: **k3s dentro do WSL**. E o WSL enxerga a GPU — `nvidia-smi`
mostra a RTX 4050, com `/dev/dxg` e `libcuda` presentes. Esta fase testa esse caminho.

## O desenho: degraus, parando no primeiro que falhar

Cada degrau só faz sentido se o anterior passou, e o experimento foi desenhado para que **qualquer**
resultado fechasse o item: se funcionasse, a GPU ficaria exercitada; se falhasse, o bloqueio exato
ficaria registrado e "impossível" viraria verdade medida.

| # | Pergunta | Resultado | Evidência |
|---|---|---|---|
| 1 | O NVIDIA Container Toolkit enxerga a GPU no WSL? | ✅ | `nvidia-container-cli info` → RTX 4050, driver 616.92, CUDA 13.4 |
| 2 | O k3s sobe sem systemd e reconhece o runtime da NVIDIA? | ✅ | `RuntimeClass nvidia` criada **sozinha** pelo k3s |
| 3 | **O nó anuncia `nvidia.com/gpu`?** — a pergunta central | ✅ | device plugin: `Detected platform: wsl`; `allocatable nvidia.com/gpu = 1` |
| 4 | Um pod que **pede** a GPU a recebe? | ✅ | `nvidia-smi` executado **dentro** do pod enxerga a placa |
| 5 | A stack do projeto infere na GPU, com a resposta certa? | ✅ | log do Ollama: `library=CUDA`, `offloaded 25/29 layers to GPU`; 72 de 72 respostas corretas |

Versões fixadas: k3s **v1.36.4+k3s1** (canal *stable*, binário conferido por sha256), NVIDIA
Container Toolkit **1.20.0**, device plugin **v0.20.0** (manifesto oficial vendorizado sem edição,
conferido contra a tag), containerd 2.3.4, kernel WSL 6.6.114.1.

**Sem `wsl --shutdown`.** Ligar o systemd para o k3s exigiria reiniciar o WSL e derrubar tudo que roda
nele. O k3s não precisa: o binário é o servidor, e roda como processo avulso com `setsid`.

## A medição

A mesma pergunta da F17b (*"Quantos veículos passaram por sentido?"*), para que os números
conversem. 1 requisição fria descartada, 12 quentes em sequência, e **uma latência só conta se a
resposta estiver certa**: a soma por sentido tem de dar 391.612.977, o total conferido contra SQL puro
na Fase 11. As 72 requisições quentes conferiram.

| Ambiente | Ollama | Catálogo | p50 | p95 | LLM (p50) |
|---|---|---|---:|---:|---:|
| K8s + **CPU** (F17b, histórico) | não registrada | básico | — | — | **60,01 s** |
| Nativo + GPU | 0.31.2 | básico | **1,99 s** | 2,16 s | 1,97 s |
| Nativo + GPU | 0.31.2 | rico | 2,02 s | 2,10 s | 2,01 s |
| **K8s + GPU** | 0.31.2 | básico | **2,05 s** | 2,34 s | 2,03 s |
| **K8s + GPU** | 0.31.2 | rico | 2,06 s | 2,24 s | 2,04 s |
| K8s + GPU | 0.34.1 (`:latest`) | básico | 3,97 s | 4,07 s | 3,95 s |
| K8s + GPU | 0.34.1 (`:latest`) | rico | 5,80 s | 5,90 s | 5,78 s |

**Com a mesma versão do Ollama, o Kubernetes custa 2–3%** sobre o nativo (1,03× no catálogo básico,
1,02× no rico). Contra a F17b em CPU, a inferência no cluster ficou **29,6× mais rápida**.

## A primeira leitura estava errada, e a ablação mostrou por quê

A primeira medição no cluster usou o manifesto como estava, com `ollama/ollama:latest` — que resolveu
para **0.34.1**. Deu 3,97 s: **o dobro do nativo**. A conclusão fácil seria "o Kubernetes dobra a
latência". Havia duas variáveis diferentes entre os ambientes, e testei uma de cada vez:

1. **Limite de CPU do pod (`cpu: 4`).** Hipótese plausível: o modelo não cabe inteiro nos 6 GB, as 4
   camadas que sobram rodam na CPU, e no pod elas têm 4 núcleos contra 16 no nativo. O catálogo rico,
   de prompt mais longo, sofreu mais (5,80 s), o que combinava. **REFUTADA:** com o limite mantido e
   só a versão trocada, o pod igualou o nativo.
2. **Versão do Ollama.** Fixei o pod em **0.31.2**, a mesma do nativo, sem mexer em mais nada — mesmo
   pod, mesmo limite, mesmo modelo no mesmo volume. **CONFIRMADA:** 3,97 s → 2,05 s.

**A lentidão era da versão, não do Kubernetes.** A 0.34.1 foi 1,94× mais lenta no catálogo básico e
2,82× no rico, no mesmo pod.

**O que isso não prova:** não medi a 0.34.1 **nativa**. Então não sei separar "a 0.34.1 é mais lenta
em qualquer lugar" de "a 0.34.1 é mais lenta dentro de container". O que está medido é o efeito da
versão **no pod**.

### A consequência vai para o manifesto

O `:latest` não é só descuido de reprodutibilidade: aqui ele **dobrou a latência sem que nenhum commit
mudasse nada**. O `k8s/base/ollama.yaml` passou a fixar `ollama/ollama:0.31.2`, com o comentário de
por quê. A renderização da base muda **exatamente essa linha**, e aplicar o manifesto fixado sobre o
pod medido **não o recriou** (mesmo UID) — o manifesto versionado reproduz a configuração medida.

## Um defeito de manifesto que 7 fases não viram

O `ollama.yaml` trazia: *"Em nó com GPU, descomente: `limits: {nvidia.com/gpu: 1}`"*. Mas o container
já declara `limits: {cpu: "4", memory: 12Gi}` duas linhas acima. Descomentar cria uma segunda chave
`limits` no mesmo mapa.

Eu ia escrever que isso "faria o pod perder os limites em silêncio". **Testei antes de afirmar**, e é
mais sutil:

| Como se aplica | Resultado (k3s v1.36) |
|---|---|
| `kubectl apply -k` — o caminho documentado | o kustomize **recusa**: `mapping key "limits" already defined` |
| `kubectl apply -f` no arquivo | o kubectl **aceita sem aviso**; o pod sai com `limits: {nvidia.com/gpu: 1}` — **sem** CPU e memória |

Consertos:
- **Overlay em vez de "descomente"**: `kubectl apply -k k8s/gpu` *acrescenta* `nvidia.com/gpu` ao
  mapa de limites existente. A renderização confere: `cpu: 4`, `memory: 12Gi` **e** `nvidia.com/gpu: 1`.
- **`tests/test_k8s_manifestos.py`**: um carregador de YAML que **recusa** chave duplicada — o PyYAML
  padrão também deixa a última vencer calado — aplicado a todos os manifestos; mais a garantia de que o
  overlay acrescenta sem substituir o mapa, e de que a base tem imagens com versão fixada. **Controles
  negativos executados:** reintroduzir o `:latest` e a chave duplicada no manifesto real fez os testes
  reprovarem.

### Por que os manifestos mudaram de diretório

O kustomize recusa uma overlay **dentro** do diretório da base que ela referencia (`cycle detected`).
Base e overlays passaram a ser irmãs: `k8s/base/`, `k8s/gpu/`, `k8s/gpu-wsl/stack/`. O comando
documentado continua `kubectl apply -k k8s`, e a mudança só foi aceita depois de provar que a
renderização saiu **idêntica, byte a byte**, à de antes (`sha256 a2ece65c…` nos dois lados).

## Dois overlays, não um

| Overlay | O que faz | Vale para |
|---|---|---|
| `k8s/gpu` | acrescenta `nvidia.com/gpu: 1` ao Ollama | qualquer cluster com o device plugin |
| `k8s/gpu-wsl/stack` | o anterior + `runtimeClassName: nvidia` | k3s (o runtime da NVIDIA não é o padrão) |

A `runtimeClassName` fica fora do overlay portável de propósito: em clusters gerenciados o runtime da
NVIDIA costuma ser o padrão, e pedir uma RuntimeClass que não existe impede o pod de agendar.

## Limitações declaradas

- **Offload parcial.** O modelo de 5,1 GB não cabe inteiro em 6 GB: 25 de 29 camadas vão para a GPU,
  e o `ollama ps` mostra 18% CPU / 82% GPU — **igual no nativo e no pod**. A comparação é justa, mas
  não é inferência 100% em GPU.
- **Uma máquina, uma GPU, um nó.** 12 requisições quentes por série, em sequência (c=1). Não mede
  concorrência, e a Fase 6 já mostrou que 1 GPU não paraleliza.
- **A razão contra a F17b mistura hardware e versão.** A F17b não registrou a versão do Ollama (imagem
  `:latest` de julho). Os 29,6× são direcionais.
- **WSL não é Linux nativo.** O caminho testado usa `/dev/dxg` e a NVML do driver Windows. Em Linux
  nativo o device plugin segue outro caminho de código — não exercitado aqui.

## Reprodução

Em ordem, no WSL (os scripts param no primeiro erro e dizem por quê):

```bash
bash k8s/gpu-wsl/01_toolkit.sh                 # toolkit 1.20.0 + nvidia-container-cli info
bash k8s/gpu-wsl/02_k3s.sh                     # k3s v1.36.4 (sha256 conferido), sem systemd
bash k8s/gpu-wsl/03_device_plugin.sh           # device plugin v0.20.0 -> allocatable nvidia.com/gpu
bash k8s/gpu-wsl/04_teste_cuda.sh              # nvidia-smi DENTRO de um pod que pede a GPU
bash k8s/gpu-wsl/05_referencia_nativa.sh /tmp/gpu_k8s   # nativo + GPU, ANTES do cluster
bash k8s/gpu-wsl/06_stack.sh rodoquery_dev.tar # stack com GPU; modelo baixado dentro do pod
bash k8s/gpu-wsl/07_medir_k8s.sh /tmp/gpu_k8s k8s-gpu-ollama0.31.2
bash k8s/gpu-wsl/09_evidencias.sh /tmp/gpu_k8s
python k8s/gpu-wsl/consolidar.py /tmp/gpu_k8s  # -> reports/fase24/gpu_k8s_wsl.json
bash k8s/gpu-wsl/99_desmontar.sh               # para o k3s e limpa a rede (mantém os dados)
```

A ablação de versão é `08_versao_ollama.sh 0.34.1` / `0.31.2` seguida de `07_medir_k8s.sh`. A imagem
`rodoquery:dev` é construída no Docker Desktop (`docker build` + `docker save`) e importada no
containerd do k3s, porque os dois não compartilham *image store*.

Artefato: `reports/fase24/gpu_k8s_wsl.json`, com os **brutos** em `reports/fase24/brutos/` — respostas
do serviço, logs do device plugin e do Ollama, `nvidia-smi` do pod e a prova da chave duplicada. Os
números do artefato são derivados dos brutos pelo `consolidar.py`; nenhum foi digitado.
