# Dados de terceiros — atribuição exigida

O [`LICENSE`](LICENSE) (MIT) cobre o **código**. Os **dados** usados no projeto seguem as suas
próprias licenças, listadas aqui.

> Este arquivo existe separado do `LICENSE` por um motivo prático: o detector de licenças do GitHub
> (`licensee`) não reconhece um texto MIT com seções extras anexadas, e passava a exibir o
> repositório como licença **"Other"**. O conteúdo é o mesmo que estava lá; só mudou de arquivo.

## 1. ANTT — Volume de Tráfego nas Praças de Pedágio · **Fases 11 em diante**

Agência Nacional de Transportes Terrestres, dados abertos sob **CC BY**.
<https://dados.antt.gov.br/dataset/volume-trafego-praca-pedagio>

1.534.142 linhas, 30 concessionárias, 241 praças, jan–mai/2026. **Sem dado pessoal** — o dado já
vem agregado por praça/dia/categoria.

O CSV de origem (143 MB) **não** está versionado aqui, e o `.duckdb` construído a partir dele
também não. A fundação que os transforma vive em
[alanjoffre/antt-foundation](https://github.com/alanjoffre/antt-foundation).

## 2. BIRD Mini-Dev · Fase 13 (calibração externa)

**CC BY-SA**. <https://bird-bench.github.io/>
Li et al., *"Can LLM Already Serve as A Database Interface?"* (NeurIPS 2023).

**Não versionado** neste repositório — baixado por script (~800 MB).

## 3. Dados sintéticos · Fases 0–10

Gerados pelo [toll-analytics-platform](https://github.com/alanjoffre/toll-analytics-platform)
(mesmo autor, MIT). Nenhum dado real.

---

**Nenhum dado de empregador, cliente ou terceiro privado foi usado em qualquer fase.**
