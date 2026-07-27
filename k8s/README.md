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

## Limitações declaradas

- Testado em `kind` (control-plane único, **sem GPU**). O bloco `nvidia.com/gpu` está comentado e
  **não foi exercitado** — requer o NVIDIA device plugin no cluster.
- O Ollama subiu no cluster mas **sem o modelo baixado**: a inferência ponta a ponta foi validada
  no Docker (Fase 16), não aqui. O que este teste prova é o *deploy*, não a latência.
- `image: rodoquery:dev` é local (carregada via `kind load`). Para um cluster real, publique numa
  registry e troque a tag.
