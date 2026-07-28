"""Terceira camada de auditoria de label: Opus 5 (CEGO) × autor-modelo. Fase 18b.

## O que isto é — e o que NÃO é

**NÃO é o κ humano.** É máquina auditando máquina, e o arquivo de saída diz isso no nome e no
campo `tipo`. `reports/fase14/kappa_humano.json` continua não existindo, e o item segue aberto.

**É a camada mais forte de auditoria de máquina que este projeto consegue produzir**, e por um
motivo específico: o κ de máquina existente (0,977, Fase 12) é `qwen2.5-coder:7b` × autor-modelo
— dois modelos fracos concordando, que é a forma mais frágil de concordância. O Opus 5 acabou de
fazer **100% de EX** neste mesmo golden (Fase 18), então quando ELE discorda do autor, a hipótese
mais provável não é incompetência do anotador: é **label suspeita**.

## Por que custa zero

As predições do Opus 5 já estão congeladas em `reports/fase18/`. Elas foram produzidas do jeito
exato de uma anotação cega: o modelo viu **apenas pergunta + catálogo** (o `PROMPT` congelado),
nunca a spec do autor. Recomprá-las seria pagar de novo por evidência que já existe em disco.

## O que a discordância significa aqui

EX e concordância de spec medem coisas diferentes: **specs estruturalmente distintas podem
produzir o mesmo número**. O Opus 5 acertou 146/146 no EX — logo, toda discordância de spec aqui
é um caso em que **os dois caminhos dão a mesma resposta certa**. Isso torna cada discordante um
candidato a uma destas três coisas:

  1. ambiguidade genuína da pergunta (dois mapeamentos legítimos),
  2. convenção do gold que o catálogo não documenta,
  3. label do autor mais frágil do que parecia.

Nenhuma delas é erro do modelo — e é exatamente isso que faz a lista de discordantes valer mais
que o número agregado.
"""
import json
from collections import Counter
from pathlib import Path

from rodoquery.estat import cohen_kappa
from rodoquery.gold import Spec
from rodoquery.golden import (
    ESTRATO_ABSTENCAO,
    ESTRATOS_RESPONDIVEIS,
    ItemGolden,
    carregar,
    concordancia_mapeamento,
)
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
D18 = REPO / "reports" / "fase18"
PRED = D18 / "predicoes_tier_a_antt_test.json"


def main() -> None:
    autor = carregar(REPO / "golden" / "golden_test_antt.jsonl")
    preds = json.loads(PRED.read_text(encoding="utf-8"))

    modelos = {v["meta"].get("modelo") for v in preds.values()}
    if modelos != {"claude-opus-5"}:
        raise SystemExit(f"proveniencia inesperada nas predicoes: {modelos}")

    b: list[ItemGolden] = []
    for it in autor:
        p = preds.get(it.id)
        if p is None:
            continue
        # Abstenção do modelo = spec vazia, que é a MESMA convenção do golden para "fora do
        # catálogo" (`metrics: []`). Sem isso, as 25 abstenções sairiam da comparação e o número
        # cobriria só o eixo de acerto — perdendo justamente o eixo que ainda discrimina.
        spec = Spec(**p["spec"]) if p["tipo"] == "spec" and p["spec"] else Spec(metrics=[])
        # O `estrato` do lado B é o julgamento DE B, não o rótulo do golden. O `ItemGolden`
        # impõe "estrato=abstencao ⟹ spec vazia" — invariante correto para um GOLDEN, mas
        # aplicá-lo a uma segunda anotação tornaria IMPOSSÍVEL registrar que o anotador
        # respondeu um item que o autor marcou como fora-de-escopo, que é precisamente a
        # discordância mais interessante. `concordancia_mapeamento` só lê `.id` e `.spec`.
        estrato_b = ESTRATO_ABSTENCAO if not spec.metrics else (
            it.estrato if it.estrato != ESTRATO_ABSTENCAO else ESTRATOS_RESPONDIVEIS[0])
        b.append(ItemGolden(id=it.id, pergunta_nl=it.pergunta_nl, estrato=estrato_b,
                            spec=spec, revisado_humano=False))

    a = [it for it in autor if it.id in {x.id for x in b}]
    rel = concordancia_mapeamento(a, b)

    dec_a = ["fora" if not x.spec.metrics else "resp" for x in a]
    dec_b = ["fora" if not x.spec.metrics else "resp" for x in b]

    por_estrato = Counter(x.estrato for x in a)
    disc_por_estrato = Counter(next(y.estrato for y in a if y.id == i)
                               for i in rel["discordantes"])

    # A lista de discordantes vale mais que o agregado — cada um é candidato a defeito de label.
    # Fica no artefato com pergunta e as DUAS specs, para poder ser julgado sem rodar nada.
    ia = {x.id: x for x in a}
    ib = {x.id: x for x in b}
    detalhe = [{
        "id": i,
        "pergunta_nl": ia[i].pergunta_nl,
        "estrato_autor": ia[i].estrato,
        "spec_autor": {"metrics": ia[i].spec.metrics, "group_by": ia[i].spec.group_by,
                       "where": ia[i].spec.where},
        "spec_opus5": {"metrics": ib[i].spec.metrics, "group_by": ib[i].spec.group_by,
                       "where": ib[i].spec.where},
    } for i in rel["discordantes"]]

    saida = carimbar({
        "tipo": "concordancia_MAQUINA_opus5_x_autor_modelo",
        "discordantes_detalhe": detalhe,
        "NAO_AJUSTADO_APOS_VER_O_RESULTADO": (
            "O TEST esta selado e os discordantes foram inspecionados DEPOIS de medir. "
            "Corrigir label agora seria fitar (disciplina da Fase 8). Defeitos candidatos "
            "ficam DECLARADOS aqui para a proxima revisao de golden, e os numeros das "
            "Fases 12/15/18 seguem intactos."),
        "NAO_E_KAPPA_HUMANO": ("maquina auditando maquina. O kappa humano segue ABERTO; "
                               "reports/fase14/kappa_humano.json nao existe de proposito."),
        "anotador_b": "claude-opus-5 (cego: viu apenas pergunta + catalogo)",
        "custo_usd": 0.0,
        "fonte": "predicoes congeladas da Fase 18 (nenhuma chamada nova de API)",
        "n_pares": rel["n_pares"],
        "decisao_respondivel_x_fora_kappa": cohen_kappa(dec_a, dec_b),
        "concordancia_spec": rel,
        "discordantes_por_estrato": dict(disc_por_estrato),
        "itens_por_estrato": dict(por_estrato),
        "referencia_kappa_maquina_qwen_fase12": 0.977,
    })
    dest = D18 / "concordancia_opus5_x_autor.json"
    dest.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"n = {rel['n_pares']} pares  (custo US$ 0,00 — predicoes ja congeladas)")
    print(f"  spec canonica identica : {rel['concordancia_spec_canonica']}")
    print(f"  kappa da metrica       : {rel['cohen_kappa_metrica']}")
    print(f"  concordancia metrica   : {rel['concordancia_metrica']}")
    print(f"  concordancia group_by  : {rel['concordancia_group_by']}")
    print(f"  concordancia where     : {rel['concordancia_where']}")
    print(f"  kappa respondivel/fora : {cohen_kappa(dec_a, dec_b)}")
    print(f"\n  discordantes: {len(rel['discordantes'])}")
    for e, n in sorted(disc_por_estrato.items(), key=lambda x: -x[1]):
        print(f"    {e:20s} {n:3d}/{por_estrato[e]:3d}")
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
