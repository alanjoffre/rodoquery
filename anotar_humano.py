"""Fase 14 (#1) — INSTRUMENTO de anotação humana para o κ humano do golden RodoQuery.

**Por que isto e não uma anotação pronta.** O κ humano é dívida declarada desde a Fase 2. Eu NÃO
posso produzi-lo: gerar specs e chamá-las de humanas seria fabricar evidência — a fronteira que
este projeto não cruza. O que EU posso entregar é o instrumento que reduz o κ humano de "trabalho
de construção" a "~1h de um humano real clicando". É isso aqui.

O anotador humano vê APENAS a pergunta + o catálogo (cego às specs do autor-modelo), mapeia cada
uma, e este script:
  1. amostra estratificada de N itens do golden (determinística, para ser reproduzível);
  2. apresenta pergunta + catálogo, coleta a spec do humano num formato simples;
  3. ao final, calcula o κ humano × autor-modelo com o MESMO `concordancia_mapeamento` usado no
     κ de máquina — então o número é comparável, não um cálculo ad-hoc.

Status honesto enquanto ninguém rodou: `reports/fase14/kappa_humano.json` NÃO existe, e o README/
docs dizem "instrumento pronto, aguardando anotador humano". Nada é preenchido por máquina aqui.

Uso:
  python anotar_humano.py amostra [N]     # gera a folha de anotação (default 40 itens)
  python anotar_humano.py kappa           # calcula κ depois que o humano preencheu a folha
"""
import json
import random
import sys
from pathlib import Path

from rodoquery.estat import cohen_kappa
from rodoquery.gold import Spec
from rodoquery.golden import ItemGolden, carregar, concordancia_mapeamento
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt import CATALOGO_ANTT

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
D = REPO / "reports" / "fase14"
FOLHA = G / "anotacao_humana_antt.jsonl"          # o humano PREENCHE o campo "spec_humano"
D.mkdir(parents=True, exist_ok=True)

MODELO_SPEC = ('{"metrics": [...], "group_by": [...], "where": <str|null>, '
               '"order_by": [...], "limit": <int|null>, "ordenado": <bool>}  '
               '# metrics:[] = ABSTENHO')


def amostra(n: int) -> None:
    itens = carregar(G / "golden_antt.jsonl")
    porestrato: dict[str, list] = {}
    for it in itens:
        porestrato.setdefault(it.estrato, []).append(it)
    rng = random.Random(42)
    escolha = []
    por = max(1, n // len(porestrato))
    for _, grupo in sorted(porestrato.items()):
        rng.shuffle(grupo)
        escolha += grupo[:por]
    linhas = []
    for it in escolha:
        linhas.append(json.dumps({
            "id": it.id, "estrato": it.estrato, "pergunta_nl": it.pergunta_nl,
            "spec_humano": None,          # <<< O HUMANO PREENCHE ISTO
        }, ensure_ascii=False))
    cab = (f"# FOLHA DE ANOTACAO HUMANA — {len(escolha)} itens\n"
           f"# Preencha 'spec_humano' em cada linha, cego as specs do autor. Formato:\n"
           f"#   {MODELO_SPEC}\n"
           f"# CATALOGO (o unico contexto permitido):\n"
           + "".join(f"#   {ln}\n" for ln in CATALOGO_ANTT.splitlines()))
    FOLHA.write_text(cab + "\n".join(linhas) + "\n", encoding="utf-8")
    print(f"folha gerada: {len(escolha)} itens estratificados -> {FOLHA}")
    print("Preencha 'spec_humano' em cada linha (cego), depois rode: python anotar_humano.py kappa")


def kappa() -> None:
    if not FOLHA.exists():
        raise SystemExit("folha ausente — rode `python anotar_humano.py amostra` primeiro")
    linhas = [json.loads(x) for x in FOLHA.read_text(encoding="utf-8").splitlines()
              if x.strip() and not x.startswith("#")]
    preenchidos = [d for d in linhas if d.get("spec_humano")]
    if not preenchidos:
        raise SystemExit(
            "NENHUM item preenchido. O κ humano NÃO pode ser calculado por máquina — "
            "este script se recusa a inventar. Preencha 'spec_humano' à mão primeiro.")
    if len(preenchidos) < len(linhas):
        print(f"AVISO: {len(preenchidos)}/{len(linhas)} preenchidos; κ parcial.")

    autor = {it.id: it for it in carregar(G / "golden_antt.jsonl")}
    A, B = [], []
    for d in preenchidos:
        ref = autor[d["id"]]
        A.append(ref)
        sh = d["spec_humano"]
        B.append(ItemGolden(id=d["id"], pergunta_nl=ref.pergunta_nl, estrato=ref.estrato,
                            spec=Spec(**sh), revisado_humano=True))
    rel = concordancia_mapeamento(A, B)
    dec_a = ["fora" if not a.spec.metrics else "resp" for a in A]
    dec_b = ["fora" if not b.spec.metrics else "resp" for b in B]
    saida = carimbar({
        "tipo": "concordancia_HUMANO_x_autor_modelo",
        "n_anotados_por_humano": len(preenchidos),
        "decisao_respondivel_x_fora_kappa": cohen_kappa(dec_a, dec_b),
        "concordancia_spec": rel,
    })
    (D / "kappa_humano.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    print(f"κ humano (n={len(preenchidos)}): spec bruta={rel['concordancia_spec_canonica']} "
          f"kappa_metrica={rel['cohen_kappa_metrica']}")
    print(f"-> {D / 'kappa_humano.json'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "amostra"
    if cmd == "amostra":
        amostra(int(sys.argv[2]) if len(sys.argv) > 2 else 40)
    elif cmd == "kappa":
        kappa()
    else:
        print(__doc__)
