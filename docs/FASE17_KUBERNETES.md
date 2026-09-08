# Fase 17 e 17b — Kubernetes

> **O conteúdo desta fase vive em [`k8s/README.md`](../k8s/README.md)**, junto dos manifestos que
> ele descreve. Este arquivo existe só para fechar o padrão `docs/FASEnn_*.md` — a Fase 17 era a
> única sem entrada aqui, e quem varria o diretório concluía que ela não tinha documentação.

Manter o doc ao lado dos manifestos é deliberado: um README de deploy que mora longe do YAML
envelhece sem ninguém notar. O que se perde é a varredura por diretório, e é isso que este
ponteiro devolve.

## O que está lá

| | |
|---|---|
| **17** | `k8s/` com namespace, Deployment + Service + PDB, StatefulSet do Ollama, 2 NetworkPolicies e kustomization. Validado em cluster `kind` **efêmero** (criado, usado, destruído): 8/8 no `kubeconform -strict`, pod Ready, Service roteia, **MetricFlow compila com `readOnlyRootFilesystem: true`** — que era o risco real. |
| **17b** | As duas limitações da 17, resolvidas ou fechadas por evidência: inferência **ponta a ponta no cluster** (o resultado bate com a Fase 11, `391.612.977`, de nativo → Docker → K8s sem corromper) e a prova de que **GPU no `kind` é impossível no Docker Desktop/Windows** — testado, não presumido. |

## As duas decisões que valem a leitura

- **Não há HPA, de propósito.** A unidade de escala é a **GPU**, não a CPU: a Fase 6 mediu que c=4
  derruba a vazão para 0,75× e o p95 de 4,4 s para 43 s. Um HPA por CPU — com o pod apenas
  esperando I/O — criaria réplicas disputando a **mesma** GPU. A regra é **1 pod : 1 GPU**, e o
  semáforo + 503 já é a política de carga.
- **`/saude` serve de liveness *e* readiness.** Um health check que chamasse o LLM reprovaria o pod
  justamente sob carga — restart loop no pior momento possível.

E uma armadilha que só apareceu por testar de verdade: **`commonLabels` do Kustomize é depreciado e
injeta label no `selector`, que é imutável** — o `apply` seguinte falha com *"field is immutable"*.
Usar `labels` com `includeSelectors: false`.

## Reprodução

```bash
kubeconform -strict -summary k8s/*.yaml     # validação offline (não exige cluster)
kubectl apply -k k8s                        # precisa de um cluster
```

> `kubectl --dry-run=client --validate=true` **exige** um cluster; é por isso que a validação de
> schema usa `kubeconform`. O cluster do teste foi um `kind` efêmero, destruído depois — o Docker
> Desktop não tem Kubernetes habilitado nesta máquina.
