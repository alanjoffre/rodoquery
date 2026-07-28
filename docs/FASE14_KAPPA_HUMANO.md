# Fase 14 (#1) — κ humano: o instrumento, o roteiro e os dois defeitos

O κ humano é dívida declarada desde a Fase 2. Este documento é o que um anotador precisa para
quitá-la, e o registro do que quase impediu isso de funcionar.

## Por que existe um instrumento e não uma anotação

Eu **não posso produzir** o κ humano. Gerar specs e chamá-las de humanas seria fabricar evidência —
a fronteira que este projeto não cruza. O que dá para fazer é reduzir o item de "trabalho de
construção" para "~1h de um humano real clicando", e é isso que o `anotar_humano.py` é.

O `kappa` **se recusa a rodar** sem input humano:

```
$ python anotar_humano.py kappa
NENHUM item preenchido. O κ humano NÃO pode ser calculado por máquina —
este script se recusa a inventar. Preencha 'spec_humano' à mão primeiro.
```

O número sai com o **mesmo** `concordancia_mapeamento` do κ de máquina — então é comparável com o
0,977 da Fase 12 (qwen 7B × autor-modelo) e com o 0,992 do Opus 5 cego, não um cálculo ad-hoc.

## Como anotar

```bash
wsl -d Ubuntu-24.04
cd ~/rodoquery
.venv/bin/python anotar_humano.py anotar
```

O `.venv` existe só no WSL — o script não roda a partir do clone Windows.

A cada item aparece a pergunta, sozinha:

```
------------------------------------------------------------------------------
[1/40]

  PERGUNTA: Qual o número de veículos por praça de pedágio?

  ENTER p/ anotar | c=catálogo | p=pular | q=sair:
```

`c` mostra o catálogo inteiro (as 3 métricas, os tokens, os valores). Use à vontade nas primeiras
perguntas; depois decora.

Vêm até 4 perguntas, todas por número:

| # | Pergunta | Resposta |
|---|---|---|
| 1 | Métrica(s) | `1`, `2`, `3` ou `4` (=ABSTENHO). Várias: `1,2`. Se ABSTENHO, o item acaba aí. |
| 2 | `group_by` | números separados por vírgula, ou ENTER para nenhum |
| 3 | Filtro (`where`) | número da dimensão → número do valor, ou ENTER para nenhum |
| 4 | É ranking? | `s`/`n`. Se `s`: por qual campo, decrescente?, limite |

No fim ele mostra o JSON montado e pede `confirma? (s/n)`. Respondendo `n`, o item volta para a fila.

Nada é pré-selecionado em nenhum menu. Um default seria viés silencioso empurrando o anotador para
uma resposta — o oposto do que uma anotação cega deve fazer.

**Pausar e voltar:** `q` sai salvando; rodar o comando de novo continua de onde parou. `p` deixa um
item para depois. O arquivo é gravado a cada item confirmado.

## As regras de julgamento

São as mesmas regras que o autor-modelo recebeu no prompt. Dá-las ao anotador humano **não
contamina**: é a definição da tarefa, não a resposta. Sem elas, o κ mediria "o anotador adivinhou
minhas convenções?" em vez de "a label está certa?".

- **ABSTENHO** quando nenhuma métrica do catálogo responde. Receita, tarifa, multa, média, hora do
  dia, município, previsão — nada disso existe.
- **`group_by` só o que a pergunta pede explicitamente.** "volume por sentido" → `[plaza__sentido]`
  e mais nada.
- **Filtrar por um valor específico é `where`, nunca `group_by`.** "veículos comerciais" →
  `where tipo_de_veiculo='Comercial'`, `group_by=[]`. A regra prática: *"por X" agrupa, "dos X"
  filtra.*
- **"por dia/semana/mês"** → `group_by` de tempo.
- **Ranking só se a pergunta pedir explicitamente** — "o maior", "top 5", "que mais". "por mês" e
  "por praça" não são ranking.

## A única regra que não pode quebrar

**Não abra `golden/golden_test_antt.jsonl`.** É lá que estão as specs do autor-modelo. Se o anotador
as vir, o κ deixa de medir concordância independente e passa a medir quanto ele concorda com algo
que acabou de ler — que é informação zero.

E **não edite a folha `.jsonl` à mão**: ela carrega o campo `estrato` em cada linha e está gravada
agrupada por estrato. O caminho guiado esconde os dois; um editor de texto os devolve inteiros (ver
abaixo).

Em dúvida, anote sua melhor leitura e siga. **Discordância genuína é o sinal que estamos medindo** —
não é erro do anotador, e não deve ser evitada.

## Fechamento

```bash
.venv/bin/python anotar_humano.py kappa
```

Grava `reports/fase14/kappa_humano.json`. Funciona com anotação parcial: calcula com o que tiver e
avisa quantos faltam. Com 40 itens o intervalo é decente; abaixo de ~20 fica largo demais para
concluir muita coisa.

## Os dois defeitos do instrumento (achados e corrigidos)

Ambos só apareceriam **depois** da hora de anotação. Foram encontrados ensaiando o caminho
`anotar` → `kappa` de ponta a ponta numa folha temporária, antes de qualquer humano sentar.

### 1. O κ estourava na discordância mais informativa

O `kappa` herdava o `estrato` do autor ao montar o lado B, e o `ItemGolden` impõe
`estrato=abstencao ⟹ metrics vazio`. É um invariante **correto para um golden** — mas aplicado a
uma segunda anotação ele levantava `ValueError` exatamente quando o humano **responde** um item que
o autor marcou como fora-de-escopo. Cinco dos 40 itens da amostra são desse estrato.

A falha era assimétrica: abster num item respondível funcionava; responder num item de abstenção
derrubava tudo. E o agravante é o conserto que a mensagem de erro convida a fazer depois de uma hora
de trabalho — editar a label do humano, o único conserto que invalidaria a medição.

Passou a usar a convenção que o `concordancia_opus5.py` já tinha fixado: **o estrato do lado B é o
julgamento de B**, não o rótulo do autor. O `concordancia_mapeamento` só lê `.id` e `.spec`.

### 2. O instrumento entregava parte da resposta

O `anotar` imprimia `estrato: <rótulo>` acima de cada pergunta. Os nomes dos estratos não são
metadado neutro — são metade da resposta:

| estrato | o que o nome entrega |
|---|---|
| `abstencao` | "não responda" |
| `ranking` | "é um ranking" |
| `grao_temporal` | "agrupe por tempo" |
| `valor_categorico` | "tem filtro" |

E a folha é escrita **agrupada por estrato**, em blocos de 5. A ordem sozinha carrega a mesma
informação: depois de abster quatro vezes seguidas, o quinto item se denuncia mesmo com o nome
escondido. Cegueira que o vizinho de linha desfaz não é cegueira.

Os dois juntos **inflam** o κ, que passaria a medir concordância com uma dica. Agora o estrato não é
impresso e a travessia é embaralhada com semente fixa (1337) — retomável e auditável.

### Contaminação declarada

Um item foi exposto fora do instrumento: um roteiro de uso entregue ao anotador mostrava
`estrato: abstencao` junto de *"Quantas multas foram aplicadas?"*. **Esse item não é cego.** É 1 em
40, e a resposta provavelmente seria ABSTENHO de qualquer forma — mas o artefato final deve dizer
isso em vez de afirmar que os 40 foram cegos.

### Guardas

Três testes de regressão em `tests/test_anotar_humano.py`: o κ com humano respondendo item de
abstenção, a ausência do estrato na tela, e a travessia fora da ordem do arquivo. Mais os que já
existiam contra drift do catálogo e contra preenchimento por máquina.

## Anotar em planilha (XLSX)

Quem não quiser o terminal anota em Excel. Mesmas garantias, e cada uma custou código:

```bash
.venv/bin/python anotar_humano.py xlsx [destino]        # exporta a planilha em branco
.venv/bin/python anotar_humano.py importar <planilha>   # lê de volta para a folha
```

A aba **Anotacao** tem uma linha por pergunta e listas suspensas em todas as colunas de resposta;
as abas **Catalogo** e **Instrucoes** evitam sair da planilha. Requer o extra:
`pip install -e .[xlsx]` (import tardio — quem anota no terminal não instala nada).

A coluna `codigo` é um sha1 truncado do `id`, **não** o `id`. Os ids do golden são prefixados pelo
estrato (`abstencao_antt_23`), então uma coluna de id entregaria a resposta tão bem quanto um
rótulo. O mapa `codigo → id` nunca aparece para quem anota.

O `importar` **revalida tudo** contra as mesmas listas do menu do terminal: validação de Excel é
conselho, não garantia — dá para colar por cima dela, e um token inválido que passasse viraria
ruído *dentro* do κ, indistinguível de discordância real. A rejeição é total: uma linha ruim aborta
o import inteiro, para a folha nunca ficar pela metade.

## Resultado — 28/07/2026

Um humano anotou os **40 itens**. Contra o autor-modelo:

| | valor | limiar pré-registrado |
|---|---|---|
| concordância de spec canônica | **1,0** (40/40) | 0,8 |
| κ de Cohen da métrica | **1,0** | 0,8 |
| concordância de `group_by` | **1,0** | — |
| concordância de `where` | **1,0** | — |
| κ respondível × fora-de-escopo | **1,0** | — |
| discordantes | **nenhum** | — |

`reports/fase14/kappa_humano.json` · IC95 exato (Clopper-Pearson) para 40/40: **[0,912; 1,000]** —
o resultado exclui concordância abaixo de ~91%, não prova igualdade perfeita na população.

**Onde ficou na escala do projeto:** κ de máquina 0,977 (Fase 12, qwen 7B × autor) → Opus 5 cego
0,9921 (n=171, 1 discordante) → **humano 1,0** (n=40). Concordância quase perfeita já era o padrão
estabelecido neste golden; com ~0,6% de discordância por item, o número esperado de discordâncias em
40 itens é 0,23. **Zero é o desfecho mais provável, não uma anomalia** — mas também é o menos
informativo: um κ perfeito não localiza nenhum candidato a defeito de label, que é o subproduto mais
útil dessas auditorias.

### O que este 1,0 cobre — e o que não cobre

**Não cobre `order_by`.** O `canonizar_spec` ignora `order_by`/`limit`/`ordenado` por decisão de
projeto (metadados de forma, não de conteúdo semântico), e o κ é calculado sobre métrica,
`group_by` e `where`. Conferindo os campos ignorados: em **14 dos 40 itens** o autor traz
`order_by: ['metric_time__day']` e o humano traz `[]`.

Isso **não é discordância** — é limitação do instrumento. Tanto o anotador guiado quanto a planilha
só perguntam `order_by` quando a resposta a "é ranking?" é sim. Ordenar uma série temporal fora de
ranking é convenção de apresentação do autor, e a pergunta nunca foi feita ao humano. Não é que
concordaram: é que ninguém perguntou. Fica registrado como limitação, não como sinal.

**Cobre bem os rankings.** Nos 5 itens de ranking o humano bateu `order_by`, `limit` e `ordenado`
**exatamente** com o autor, inclusive os limites. É o estrato mais difícil, e ali o instrumento
pergunta tudo.

**Abstenções coincidem item a item.** Os 5 itens em que o humano absteve são os mesmos 5 que o autor
marcou fora-de-escopo — não apenas a mesma contagem.

### A evidência de que foi anotação, e não cópia

A objeção óbvia a um κ = 1,0 é que o anotador pode ter visto a resposta. A cegueira do processo é
argumento; isto aqui é medição.

As 40 specs humanas são **canonicamente idênticas** às do autor — mas apenas **26 são idênticas
byte a byte**. As outras 14 escrevem a mesma coisa de outro jeito (campos em ordem diferente,
`order_by` ausente onde o autor traz um token de tempo, `limit: null` explícito × omitido).

Cópia produz 40/40 byte a byte. Concordância genuína produz o que apareceu: **mesmo significado,
superfície diferente** — que é também o motivo de o κ ser calculado sobre a forma canônica. É o
único sinal disponível que separa as duas hipóteses sem depender da palavra de ninguém.

### Duas ressalvas honestas

**A amostra vem do golden SELADO, já limpo.** As Fases 14 e 15 removeram 10 rankings com empate na
zona de corte e 7 labels defeituosas achadas por auditoria adversarial. Amostrar de lá é a decisão
certa — anotar contra referência que já sabemos errada mediria defeito conhecido, não discordância —
mas significa que este 1,0 é **concordância sobre o golden sobrevivente**, não sobre o golden como
foi originalmente construído. Os itens com maior chance de gerar discordância já tinham saído.

**Um item não foi cego.** *"Quantas multas foram aplicadas?"* apareceu com o rótulo
`estrato: abstencao` num roteiro de uso entregue ao anotador. Excluindo-o: 39/39, IC95
**[0,910; 1,000]**. A conclusão não muda — mas o número honesto é "39 cegos + 1 contaminado", não
"40 cegos".

## Status

| | |
|---|---|
| Instrumento | pronto, verificado, dois caminhos (terminal e XLSX) |
| Folha | 40 itens estratificados, **40 anotados** |
| `reports/fase14/kappa_humano.json` | **existe** — κ = 1,0 (n=40) |
| Item #1 do backlog | **FECHADO** — dívida da Fase 2 quitada |

Sobre a proveniência do artefato: `git_dirty: true` porque `carimbar` usa `git status --porcelain`,
que conta arquivos não rastreados — e o próprio artefato é um deles no momento em que é escrito. O
`git_sha` (`0375910`) fixa o código que o produziu, commitado e com a árvore limpa antes de rodar.
