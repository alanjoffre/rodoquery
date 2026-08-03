# Fase 21 — o defeito era do catálogo, e a conta do conserto

Esta fase fecha os sete itens que restavam no backlog. Quatro deles eram **um problema só**.

## O diagnóstico da Fase 20 estava incompleto

A Fase 20 mediu a abstenção cair para 50% num conjunto de near-miss, com um mecanismo uniforme:
**pedem proporção, o modelo responde contagem**. Registrei como *"rebaixamento de tipo"* — um
defeito do modelo.

Olhando o catálogo, o defeito é dele, e é de **assimetria**:

```
tipo_cobranca   = {Automática, Manual, OCR/PLACA}   → só automation_rate exposta
tipo_de_veiculo = {Comercial, Passeio, Moto}        → só commercial_share exposta
```

Quem vê *"taxa de automação"* espera, com razão, que *"proporção de cobrança manual"* exista. O
modelo não estava inventando: estava diante de uma pergunta legítima cuja resposta o catálogo
escondia, e devolveu o mais próximo que tinha.

## A regra: completar a partição, não expor tudo

Só entram os **irmãos de partições onde um membro já estava exposto**:

| Dimensão | Valores | Entra? | Por quê |
|---|---|---|---|
| `tipo_cobranca` | 3 | ✅ | um membro já exposto → assimetria real |
| `tipo_de_veiculo` | 3 | ✅ | idem |
| `sentido` | 2 | ❌ | **nenhum** membro exposto — sem assimetria, sem armadilha |
| `categoria_eixo` | 19 | ❌ | 19 shares recriariam a ambiguidade da Fase 10 |

Catálogo: **3 → 7 métricas**. A regra é falseável e tem prova: as duas partições **somam
exatamente 1,0** (verificado no dado, não presumido; teste `test_particoes_somam_um`).

O catálogo enriquecido é um **sistema novo** (`sistema_antt_rico.py`), não uma edição do
congelado — trocar `CATALOGO_ANTT` mudaria o SUT das Fases 11–20 de uma vez e nenhum número
anterior poderia ser comparado com nenhum posterior. **O PROMPT é byte a byte o mesmo.** Se este
sistema for melhor, o mérito é do catálogo.

## O resultado: uma troca, não um ganho grátis

Mesmas 47 perguntas, mesmo SUT (`claude-opus-5`), muda só o catálogo:

| | Catálogo de 3 (F20) | Catálogo de 7 (F21) |
|---|---|---|
| Respondíveis | 35/35 (100%) | 38/39 (97,4%) |
| Abstenção | 6/12 (50%) | **6/8 (75%)** |
| **Rebaixamento de tipo** | **6 de 6 falhas** | **1 de 8** |
| **Total dos 47 itens** | 41/47 | **44/47** |

O gabarito muda em 4 itens, e **tem** de mudar: uma pergunta é abstenção porque o catálogo não
pode respondê-la. Os outros 8 near-miss **seguem abstenção** — é o que impede o experimento de
ser tautológico. Custo: US$ 0,142.

### A regressão, que é o preço

Um item que acertava passou a errar:

> *"Quais as 5 praças com maior **volume** de motos no sentido crescente?"*
> gold `traffic_volume` + filtro · catálogo de 7 respondeu **`motorcycle_share`**

Com o share disponível, o modelo confundiu **contagem de X** com **proporção de X**. É a
ambiguidade que a Fase 10 mediu, num vizinho novo — e é o argumento honesto contra catálogos
grandes. **A troca líquida é +3 itens em 47**, e ela vem com este custo, não sem.

## O que a auditoria adversarial achou

Método da Fase 15 (o crítico **vê** a spec e só procura erro — mais forte que re-anotação cega,
e mais adequado que κ de máquina, que aqui mediria a incompetência do anotador nas formas duras).

**44/47 corretas (93,6%)**, 3 defeitos, todos da mesma categoria — `abstencao_errada`:

| Item | Argumento do crítico |
|---|---|
| *"razão entre tráfego comercial e de passeio?"* | `commercial_share ÷ passenger_share` = comercial/passeio |
| *"taxa de cobrança não automatizada?"* | `manual_share + ocr_share` |
| *"participação de cada concessionária?"* | `traffic_volume` por concessionária "permite calcular" |

Os dois primeiros são fortes: **completar a partição tornou perguntas respondíveis por
COMPOSIÇÃO**, e o meu gold não antecipou isso. O terceiro é fraco — devolver contagens não é
devolver a participação; é exatamente o rebaixamento de tipo com outro nome.

Consequência que muda a leitura do número: na medição, o SUT respondeu *"taxa de cobrança não
automatizada"* com `[manual_share, ocr_share]` e **foi contado como erro**. Pela auditoria, a
resposta é defensável. **A abstenção de 6/8 é um piso, não uma estimativa.**

**Nada foi corrigido.** O conjunto está selado e a auditoria veio depois de medir; ajustar agora
seria fitar (disciplina da Fase 8). Os 3 ficam declarados para a próxima revisão.

## Concorrência da API: medida, e o default estava certo

O semáforo do serving era 1 por medição (Fase 6: *uma GPU não paraleliza*). No caminho de API o
default virou 8 **por raciocínio**, e `/saude` admitia isso em `concorrencia_medida: false`.

Critério declarado **antes** de olhar: manter 8 só se a vazão em c=8 passasse de 1,5× a de c=1.

| c | API (vazão relativa) | p95 API | GPU local (F6) |
|---|---|---|---|
| 1 | 1,00× | 4,6 s | 1,00× |
| 2 | 1,94× | 3,4 s | 1,11× |
| 4 | 3,10× | 3,2 s | **0,75×** |
| 8 | **5,74×** | 3,3 s | 0,76× |

Escala quase linear **e o p95 fica plano** — o oposto exato da GPU local, onde a vazão colapsa e
o p95 vai a 43 s. O 8 é conservador, não agressivo. `CONCORRENCIA_MEDIDA` agora é `True` nos dois
caminhos. Custo: US$ 0,064.

## As duas decisões

**Catálogo v2 ao serving — não promover, e o item está superado.** Ele foi um experimento sobre
o catálogo de 3 métricas (+5,5 pp no Qwen), e a lei da Fase 18 prevê que esse ganho evapora num
SUT forte — como os normalizadores (+17,7 pp → 0) e a fragilidade lexical (−29,4 pp → 0). O
caminho adiante é o **catálogo enriquecido desta fase**, que ataca um defeito medido em vez de
uma diferença de redação. Promover o v2 custaria a comparabilidade de 15 fases por um ganho que a
própria evidência do projeto diz que não sobrevive.

**GPU no Kubernetes — bloqueado por hardware, e fica assim.** Não é falta de trabalho: está
**diagnosticado** (Fase 17b). `docker run --gpus all` funciona e o runtime `nvidia` está
registrado, mas o `kind` cria o nó sem `--gpus`, e o **Docker Desktop ignora
`"default-runtime": "nvidia"`** no `daemon.json` — testado, com a config restaurada depois.
Exercitar `nvidia.com/gpu` exige k3s/kubeadm em Linux nativo ou um cluster gerenciado com node
pool de GPU. **Nenhuma quantidade de código resolve isto nesta máquina**, e o bloco no manifesto
segue comentado e declarado como não exercitado.

## Um erro meu que custou dinheiro

A primeira execução da auditoria adversarial gastou **US$ 0,37 e não salvou nada**: abortou no
teto em 46/47 e descartou 46 vereditos já pagos. Duas causas, ambas minhas:

1. **O prompt do crítico começava com `PERGUNTA:`** em maiúscula, mas o marcador de corte do
   prompt caching é `\nPergunta: `. Não casou, nada cacheou, e cada chamada custou ~3× o
   necessário. *Marcador de cache é contrato, não formatação.*
2. **O teto abortava sem persistir.** Trava de orçamento que joga fora trabalho já pago é pior
   que não ter trava.

Consertados: o prompt passou a ter a parte variável no fim, com o marcador correto, e a auditoria
virou **retomável** (salva cada veredito na hora). A re-execução custou **US$ 0,159 para 47
itens** — 2,4× mais barata que os 46 anteriores.

O gasto rastreado nos artefatos (**US$ 1,82**) **não inclui** esses US$ 0,37 queimados, porque
nenhum artefato foi produzido. Fica registrado aqui.

## Limitações declaradas

- **n pequeno na abstenção** (8 itens): o valor está no **mecanismo** — o rebaixamento de tipo
  caiu de 6/6 para 1/8 —, não na taxa pontual.
- **Os 3 defeitos da auditoria não foram corrigidos**, por disciplina de selo.
- **A concorrência foi medida no provedor, não via HTTP**: subir o uvicorn acrescentaria FastAPI,
  semáforo e rede à medição, e o semáforo é justamente o que se queria dimensionar.
- **A vazão absoluta depende do tier da conta e do horário.** O que se afirma aqui é a **forma da
  curva** (escala vs. colapsa), que é o que decide o parâmetro.
