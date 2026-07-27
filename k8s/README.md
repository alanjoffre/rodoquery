# Kubernetes — e por que **não** há HPA aqui

```bash
kubectl apply -k k8s
kubectl -n rodoquery rollout status deployment/rodoquery
kubectl -n rodoquery port-forward svc/rodoquery 8077:80
```

## A decisão que define este deploy: a unidade de escala é a GPU, não a CPU

O reflexo padrão em Kubernetes seria pôr um HPA escalando por CPU. **Aqui isso estaria errado**, e
a Fase 6 tem o número:

| Concorrência | Vazão | p95 |
|---|---|---|
| c=1 | 1,00× | 4,4 s |
| c=2 | 1,11× | 8,2 s |
| c=4 | **0,75×** | **43 s** |
| c=8 | 0,76× | 43 s |

Em 1 GPU a inferência **não paraleliza**: a partir de c=4 a vazão *cai*. Um HPA vendo CPU baixa
(o pod passa o tempo esperando I/O do Ollama) escalaria réplicas — e cada réplica nova disputaria
a **mesma** GPU, piorando o p95 de todo mundo. Seria um autoscaler otimizando a métrica errada.

Por isso:

- `replicas: 1` no Deployment, com o comentário explicando a razão;
- a regra real é **1 pod : 1 GPU** — escalar o serviço exige escalar o `StatefulSet` do Ollama junto;
- o controle de admissão (semáforo 1 + `503`) já é a política de carga: o serviço **recusa** o
  excesso em vez de enfileirar, que é a degradação honesta.

Um HPA só faria sentido com métrica customizada (fila/latência do Ollama) e um pool de GPUs.

## Por que StatefulSet para o Ollama

O modelo tem 4,7 GB. Sem volume persistente, todo rollout re-baixa — e os 79 s de `load_duration`
medidos na Fase 16 viram o custo de cada restart, não só do primeiro request.

## Probes: `/saude` não mente

`/saude` não toca o LLM nem o banco — é liveness de verdade. Um health que chamasse o modelo
reprovaria o pod sempre que o Ollama estivesse ocupado, causando restart em loop justo quando o
sistema está sob carga.

A **readiness** usa o mesmo endpoint de propósito: se o serviço estiver saturado ele responde 503
por conta própria. Tirá-lo do balanceador nesse momento só empurraria a fila para o vizinho — que
divide a mesma GPU.

`startupProbe` com 120 s de margem cobre o cold start.

## Segurança: estrutural, como o resto do projeto

A tese do Tier-A é que a segurança é **estrutural** (vocabulário fechado ⇒ sem superfície de
injeção). A rede segue o mesmo princípio: em vez de confiar que o pod se comporta, o cluster limita
o que ele **alcança**.

- `readOnlyRootFilesystem: true`, `runAsNonRoot`, `drop: [ALL]`, `seccompProfile: RuntimeDefault`
- `NetworkPolicy`: egress do serviço **só** para o Ollama + DNS; ingress do Ollama **só** do serviço

## O que foi testado de verdade

Num cluster `kind` efêmero (criado, usado e **destruído**):

| Verificação | Resultado |
|---|---|
| `kubeconform -strict` (k8s 1.34) | ✅ 8/8 recursos válidos |
| `kubectl apply -k` do zero | ✅ 8 recursos criados |
| rollout do Deployment | ✅ `successfully rolled out` |
| pod Ready (probes passam) | ✅ 1/1 Running |
| Service roteia | ✅ `/saude` 200 via port-forward |
| **MetricFlow compila com rootfs read-only** | ✅ (era o risco real) |
| **DuckDB executa no pod** | ✅ 190.982.244 + 200.630.733 |
| **NetworkPolicy bloqueia egress** | ✅ ver abaixo |
| **inferência ponta a ponta no cluster** | ✅ modelo de 4,7 GB no pod, resposta correta |
| **abstenção no cluster** | ✅ 2,8 s, fora-do-catálogo recusado |

O total por sentido fecha em **391.612.977** — exatamente o número que verifiquei contra SQL puro
na Fase 11. O dado atravessa Docker → Kubernetes sem se corromper.

**A NetworkPolicy foi testada por diferença, não por suposição:** um pod *sem* policy conecta a
`1.1.1.1:443`; o pod do RodoQuery, com a policy, dá timeout. A diferença isola a policy como causa
— um timeout sozinho não provaria nada (poderia ser ausência de rota).

## Uma armadilha que o teste pegou

A primeira versão usava `commonLabels` (depreciado no Kustomize). Ele injeta o label **também no
`selector`** — que é **imutável**. Resultado: o `apply` seguinte falhou com
`field is immutable`, e a correção só entra recriando os objetos. Trocado por `labels` com
`includeSelectors: false`.

## Inferência ponta a ponta **dentro do cluster**

O primeiro teste provou o *deploy*, não o sistema. Refiz com o modelo de verdade: baixei o
`qwen2.5-coder:7b` (4,7 GB) dentro do pod do Ollama e consultei pelo Service.

```
POST /consulta  {"pergunta": "Quantos veículos passaram por sentido?"}
→ spec: {metrics:[traffic_volume], group_by:[plaza__sentido]}
→ Decrescente 200.630.733 · Crescente 190.982.244
→ latencia: llm 60,01s · compilacao 6,90s · execucao 0,03s · total 66,9s
```

**200.630.733 + 190.982.244 = 391.612.977** — o mesmo total que verifiquei contra SQL puro na
Fase 11. O número atravessa nativo → Docker → Kubernetes sem se corromper.

A abstenção também foi exercitada no cluster: *"Qual foi a receita de pedágio arrecadada?"* →
`abstencao` em 2,8 s (o catálogo da ANTT não tem métrica de dinheiro). O caminho curto — o modelo
recusa antes de compilar qualquer coisa — funciona igual em K8s.

### Latência: 66,9 s, e por quê

| Ambiente | LLM | Compilação | Total |
|---|---|---|---|
| Nativo + GPU (Fase 6) | — | 2,72 s | **4,5 s** |
| Docker + GPU do host (Fase 16) | 7,3 s | 0,00 s (cache) | **7,3 s** |
| **Kubernetes, CPU** | **60,0 s** | 6,90 s | **66,9 s** |

Os 60 s são **inferência em CPU** — o `kind` roda sem GPU (ver abaixo). Isso **não** é um número de
serving; é a prova de que a cadeia funciona. O SLO da Fase 6 continua valendo só para GPU nativo, e
segue não herdado.

## GPU: por que continua sem ser exercitada (testado, não presumido)

Tentei e documento onde parou:

1. `docker run --gpus all …` → **funciona**: a RTX 4050 (6141 MiB) aparece dentro do container.
2. O runtime `nvidia` **está registrado** no daemon (`nvidia-container-runtime`).
3. Mas o `kind` cria o nó **sem** `--gpus`, então o nó só vê GPU se o runtime nvidia for o
   **padrão**. Configurei `"default-runtime": "nvidia"` no `~/.docker/daemon.json` e reiniciei.
4. **O Docker Desktop ignora essa chave**: o arquivo tinha a mudança, `docker info` continuou
   reportando `runc`, e um container sem `--gpus` não achou o `nvidia-smi`.

Conclusão honesta: **é limitação do Docker Desktop no Windows**, não do manifesto. O bloco
`nvidia.com/gpu` segue comentado e **não exercitado** — exercitá-lo exige um cluster com
NVIDIA device plugin (k3s/kubeadm em Linux nativo, ou um managed com node pool de GPU). A config do
daemon foi **restaurada ao original** depois do teste.

## Outras limitações

- `image: rodoquery:dev` é local (carregada via `kind load`). Para um cluster real, publique numa
  registry e troque a tag.
- Control-plane único: `PodDisruptionBudget` e `RollingUpdate` estão declarados mas um cluster de
  um nó não exercita drain/rebalance de verdade.
