# Fase 22 — o CI estava vermelho desde a Fase 6, e o badge dizia isso

Esta fase não mediu o sistema. Mediu **a mim**, e o resultado é o pior desta lista de fases.

## O número

Consultando a API do GitHub Actions, as 33 execuções do workflow desde que ele existe:

| | |
|---|---|
| Execuções totais | **33** |
| Execuções **verdes** | **1** |
| A única verde | `d5701540` — *"feat(fase5): MLOps — gate de regressão ativo"*, o commit que **criou** o CI |
| Vermelhas consecutivas | **32**, de 2026‑07‑22 a 2026‑08‑03 |
| Duração | **12 dias, 16 fases** |

O CI nasceu verde na Fase 5 e **morreu no commit seguinte**. Nunca mais rodou a suíte.

## A primeira causa

`tests/test_servico.py` chegou na Fase 6 e importa `fastapi`. O `fastapi` vive no extra
`[serve]`; o CI instalava `pip install -e ".[dev]"`. O pytest não falhava um teste — ele
**não conseguia coletar dois arquivos**, e coleta quebrada reprova o job inteiro.

Reproduzido antes de consertar, bloqueando os módulos que `[dev]` não instala:

```
OK      test_provedor.py
...
FALHA   test_servico.py           -> ModuleNotFoundError: No module named 'fastapi'
FALHA   test_servico_provedor.py  -> ModuleNotFoundError: No module named 'fastapi'
```

A data bate exatamente: a única execução verde é a **anterior** à chegada desses arquivos. Essa
causa fecha sem margem — mas ela **escondia uma segunda**, que só apareceu depois de consertada.

## Por que passou 12 dias despercebido

Nada aqui é culpa da ferramenta — **o CI funcionou perfeitamente**. Ele detectou, reportou e
estampou um badge vermelho no topo do README. Eu é que rodei `pytest` na minha máquina, onde os
cinco extras estão instalados, vi 216 verdes e **tratei "o workflow existe" como "o CI passa"**.

É o mesmo erro que a Fase 20 registra em outro contexto: *inferir consequência a partir do
mecanismo em vez de medir*. Ter pipeline não é ter pipeline verde. **A existência do artefato
não é evidência do comportamento do artefato** — e essa é justamente a disciplina que este
projeto inteiro afirma praticar.

## O conserto, e o que ele NÃO é

O remendo óbvio seria trocar a linha do YAML por `.[dev,serve,api,xlsx]`. Isso conserta hoje e
quebra de novo no próximo teste que precise de um extra.

**1. Um extra nomeado, no `pyproject.toml`**, que torna o acoplamento explícito e versionado:

```toml
test = ["rodoquery[dev,serve,api,xlsx]"]
```

O CI instala `.[test]`. Teste novo que exija um extra entra **aqui**, e o pipeline acompanha
sozinho — a dependência deixa de ser conhecimento tácito espalhado num arquivo de YAML.

**2. Uma trava de coleta** (`verificar_coleta.py`), que roda **antes** dos testes, porque o modo
de falha perigoso é o simétrico do que aconteceu. Se eu tivesse "consertado" com
`pytest.importorskip` nos dois arquivos, o build ficaria **verde com 26 testes a menos** e o badge
anunciaria sucesso sobre uma cobertura menor. **Verde com teste faltando é pior que vermelho** —
vermelho ao menos grita.

A trava afirma três coisas falseáveis:

1. a coleta não tem **nenhum** erro;
2. **todo** `tests/test_*.py` contribuiu com ≥ 1 teste (arquivo que colete zero é reprovação);
3. o total não caiu abaixo do piso declarado (**216**).

O piso é `>=`: acrescentar teste passa sozinho; só **remover** exige mexer no número — e mexer é
o ponto, porque aí a queda de cobertura vira decisão explícita, com autor e commit.

## A segunda causa, que a primeira escondia — e o falso negativo da minha trava

Com o conserto acima, o CI passou a **chegar** ao passo `Testes`. E falhou lá, por outro motivo:

```
tests/test_anotar_humano.py:21: import anotar_humano
E   ModuleNotFoundError: No module named 'anotar_humano'
```

`anotar_humano.py` é um script de **raiz**. Importá-lo exige a raiz no `sys.path`, e quem a
colocava lá era **o jeito de invocar**: eu rodo `python -m pytest` — e o `-m` põe o *cwd* no
`sys.path` sozinho —, o CI roda `pytest`, o console script, que **não** põe. A diferença entre a
minha máquina e o runner não era dependência nenhuma: era **uma letra de comando**.

Conserto: `pythonpath = ["."]` declarado no `[tool.pytest.ini_options]`. As duas invocações
passam a concordar, em vez de o resultado depender de como cada um digita.

**Mas o pior está aqui.** A trava de coleta que eu tinha acabado de escrever **passou nesse mesmo
job**, com "216 testes, 0 arquivos vazios, COLETA OK", enquanto o passo seguinte morria de erro de
coleta. Ela rodava `pytest.main()` **in-process**, chamada por `python verificar_coleta.py` — e o
interpretador põe o diretório do script (a raiz) no `sys.path` **de graça**. A trava criada para
impedir falsa segurança produziu falsa segurança, sobre exatamente a classe de defeito que ela
existe para pegar.

Agora ela invoca o **mesmo executável `pytest`**, do mesmo diretório, com os mesmos argumentos que
o CI usa, em **subprocesso**. Medido no estado quebrado: rc=2 e **176** itens coletados, não 216 —
ela reprova onde antes aprovava.

> **Uma trava que não reproduz a invocação do alvo não é trava — é uma segunda fonte de falsa
> segurança**, e mais perigosa que a primeira, porque parece prova.

## Ensaiei errado três vezes seguidas

Vale registrar porque o padrão é sempre o mesmo, e é o mesmo do resto do projeto:

| # | Como ensaiei | Por que passou aqui e falhou lá |
|---|---|---|
| 1 | `python -m pytest` | o `-m` põe o *cwd* no `sys.path`; o CI usa `pytest` |
| 2 | na **árvore de trabalho** | ela tem arquivos *gitignorados* que o runner não recebe |
| 3 | clone do **HEAD** | o conserto ainda estava só na árvore — ensaiei o código **antigo** |

O erro nº 3 produziu o resultado mais confuso do dia: a trava aprovava e o `pytest` falhava
*"mesmo com o conserto"*. Não havia contradição — não havia conserto no clone. O que desfez a
confusão foi rodar **o comando exato** e ler o resultado, em vez de continuar deduzindo.

**Toda vez que o ensaio diverge do alvo em um único detalhe, ele passa e o alvo falha.** Por isso
o ensaio virou ferramenta versionada — [`ensaiar_ci.sh`](../ensaiar_ci.sh) —, com os três erros
escritos no cabeçalho e um **controle negativo** (`--negativo`): remove o `pythonpath` e **exige**
que a trava reprove. Se ela aprovar, o próprio ensaio grita.

## Verificação

Ensaio fiel — clone do commit, venv novo, `pytest` console script, fundação apontada para
caminhos inexistentes (o runner não tem DuckDB, nem MetricFlow, nem chave de API):

```
=== CONTROLE NEGATIVO: sem `pythonpath`, a trava DEVE reprovar ===
  OK    trava reprovou (rc=1), como tem de reprovar

=== sequencia do .github/workflows/ci.yml ===
1. Lint (ruff)             rc=0
2. Coleta completa         rc=0
3. Testes                  rc=0
4. Gate (nivel A)          rc=0
```

E o **veredito que vale**, que não é a minha máquina:

```
✓ main CI · 30807927479        ✓ qualidade in 23s
```

A **2ª execução verde em 34** — a primeira em 12 dias e 17 fases. Os 2 *skips* da suíte são os
testes que exigem a fundação ANTT; pulam por marcador declarado, e a trava os conta como
**coletados**, que é o que importa aqui.

## O que isto custou e o que devolveu

Custou 12 dias de badge vermelho num repositório de portfólio — **exatamente o artefato que um
recrutador abre primeiro**. Devolveu a única evidência que faltava para a afirmação "CI/CD real":
não é ter o arquivo `ci.yml`, é ter o histórico do Actions verde e uma trava que impede a
cobertura de encolher em silêncio.

## Um achado de brinde, e por que ele NÃO foi consertado agora

Auditando os extras, o `llm` (`httpx`, `ollama`) **não é importado por nada**: o cliente do Ollama
fala HTTP por `urllib` da stdlib. É metadado de empacotamento que não corresponde ao código.

Não removi. O `Dockerfile` instala `.[serve,llm]`, e os **624 MB** de imagem medidos na Fase 16
**incluem** esses pacotes — tirá-los sem reconstruir e re-medir tornaria aquele número falso, o
que seria trocar um defeito de metadado por um defeito de evidência. Fica no backlog para sair no
**mesmo commit** que re-mede a imagem.

## Limitações declaradas

- **O CI continua rodando só o nível A** do gate (contrato). Os níveis B (replay contra o gold) e
  C (live, com o LLM) seguem na máquina com fundação/GPU — um CI que depende de GPU flaka, e gate
  que flaka é gate que o time ignora. Isso é decisão da Fase 5, não consequência desta.
- **O piso de 216 é manual.** Ele impede queda silenciosa, não garante qualidade dos testes.
- **Nada aqui testa o caminho de API** de verdade: o `anthropic` é instalado para a coleta, mas
  nenhuma chamada paga roda no CI — e nem deve.
