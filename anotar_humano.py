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
  python anotar_humano.py anotar          # anotador GUIADO (recomendado — só digitar números)
  python anotar_humano.py kappa           # calcula κ depois que o humano preencheu a folha

**O que o `anotar` faz e o que ele NÃO faz.** Ele monta o JSON a partir de escolhas numeradas,
salva a cada item (é retomável) e nunca pré-seleciona nada — não há opção "sugerida", porque um
default seria um viés silencioso empurrando o anotador. Ele **não** vê nem mostra a spec do
autor-modelo: a cegueira é o que faz o κ medir concordância independente em vez de quanto o
humano concorda com algo que acabou de ler.
"""
import json
import random
import sys
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
from rodoquery.sistema_antt import CATALOGO_ANTT

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
D = REPO / "reports" / "fase14"
FOLHA = G / "anotacao_humana_antt.jsonl"          # o humano PREENCHE o campo "spec_humano"
D.mkdir(parents=True, exist_ok=True)

MODELO_SPEC = ('{"metrics": [...], "group_by": [...], "where": <str|null>, '
               '"order_by": [...], "limit": <int|null>, "ordenado": <bool>}  '
               '# metrics:[] = ABSTENHO')


def _golden_selado() -> list[ItemGolden]:
    """O golden SELADO ATUAL (test + dev), não o pool bruto `golden_antt.jsonl`.

    Por quê: o pool ainda contém itens que as Fases 14 e 15 **removeram** — 10 rankings com
    empate na zona de corte (gold não-determinístico) e 7 labels defeituosas achadas por
    auditoria adversarial. Amostrar de lá faria o anotador humano gastar tempo em itens cuja
    referência **já sabemos estar errada**, e o κ mediria defeito conhecido em vez de
    discordância genuína. A 1ª folha (25/07) tinha 3 desses em 40.
    """
    itens, vistos = [], set()
    for nome in ("golden_test_antt.jsonl", "golden_dev_antt.jsonl"):
        for it in carregar(G / nome):
            if it.id not in vistos:
                vistos.add(it.id)
                itens.append(it)
    return itens


def amostra(n: int) -> None:
    itens = _golden_selado()
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


# ---------------------------------------------------------------------------------------------
# Anotador guiado
#
# O vocabulário fica explícito aqui (e não parseado do catálogo) porque parsear texto livre é
# frágil. O preço disso é risco de DRIFT: se o catálogo mudar e estas listas não, o anotador
# ofereceria tokens que não existem mais. `tests/test_anotar_humano.py` trava isso — cada item
# abaixo tem de aparecer literalmente em CATALOGO_ANTT.
# ---------------------------------------------------------------------------------------------
METRICAS = ["traffic_volume", "automation_rate", "commercial_share"]
GROUP_BY = ["metric_time__day", "metric_time__week", "metric_time__month",
            "plaza__praca", "plaza__concessionaria", "plaza__sentido",
            "plaza__tipo_cobranca", "plaza__categoria_eixo", "plaza__tipo_de_veiculo"]
VALORES = {
    "plaza__tipo_cobranca": ["Automática", "Manual", "OCR/PLACA"],
    "plaza__tipo_de_veiculo": ["Comercial", "Passeio", "Moto"],
    "plaza__sentido": ["Crescente", "Decrescente"],
    "plaza__categoria_eixo": [str(i) for i in range(2, 21)],
}


def _menu(titulo: str, opcoes: list[str], multi: bool, permite_vazio: bool) -> list[str]:
    """Escolha numerada. NUNCA há opção pré-selecionada — default seria viés silencioso."""
    print(f"\n  {titulo}")
    for i, o in enumerate(opcoes, 1):
        print(f"    {i}. {o}")
    dica = "números separados por vírgula" if multi else "um número"
    dica += ", ENTER para nenhum" if permite_vazio else ""
    while True:
        cru = input(f"  > ({dica}): ").strip()
        if not cru:
            if permite_vazio:
                return []
            print("    ! obrigatório")
            continue
        try:
            idx = [int(x) for x in cru.replace(" ", "").split(",") if x]
            if not multi and len(idx) != 1:
                print("    ! escolha só um")
                continue
            if any(not 1 <= i <= len(opcoes) for i in idx):
                print(f"    ! fora do intervalo 1..{len(opcoes)}")
                continue
            return [opcoes[i - 1] for i in idx]
        except ValueError:
            print("    ! digite números")


def _sim(pergunta: str) -> bool:
    while True:
        r = input(f"  {pergunta} (s/n): ").strip().lower()
        if r in ("s", "sim"):
            return True
        if r in ("n", "nao", "não"):
            return False


def _montar_where() -> str | None:
    """Monta a sintaxe do MetricFlow, que é chata de digitar à mão e fácil de errar."""
    dims = sorted(VALORES)
    escolha = _menu("FILTRO (where) — dimensão:", [*dims, "(nenhum filtro)"], False, True)
    if not escolha or escolha[0] == "(nenhum filtro)":
        return None
    d = escolha[0]
    v = _menu(f"valor de {d}:", VALORES[d], False, False)[0]
    return f"{{{{ Dimension('{d}') }}}} = '{v}'"


def anotar() -> None:
    """Coleta a spec do HUMANO item a item. Salva a cada resposta — retomável."""
    if not FOLHA.exists():
        raise SystemExit("folha ausente — rode `python anotar_humano.py amostra` primeiro")
    texto = FOLHA.read_text(encoding="utf-8")
    cab = [x for x in texto.splitlines() if x.startswith("#")]
    linhas = [json.loads(x) for x in texto.splitlines() if x.strip() and not x.startswith("#")]

    def salvar() -> None:
        FOLHA.write_text("\n".join(cab) + "\n"
                         + "\n".join(json.dumps(d, ensure_ascii=False) for d in linhas) + "\n",
                         encoding="utf-8")

    # Ordem EMBARALHADA (semente fixa → retomável e auditável). A folha é escrita agrupada por
    # estrato, e a ordem sozinha entrega o rótulo do autor: depois de abster 4 vezes seguidas, o
    # 5º item se denuncia. Cegueira que o vizinho de linha desfaz não é cegueira.
    ordem = list(range(len(linhas)))
    random.Random(1337).shuffle(ordem)
    pendentes = [i for i in ordem if not linhas[i].get("spec_humano")]
    if not pendentes:
        print("Todos os itens já estão anotados. Rode: python anotar_humano.py kappa")
        return

    print(f"\n{'=' * 78}\nANOTACAO HUMANA — {len(pendentes)} de {len(linhas)} pendentes")
    print("Você vê apenas a pergunta e o catálogo. A spec do autor-modelo NÃO é mostrada:")
    print("é a cegueira que faz o κ medir concordância independente.")
    print("A qualquer momento:  c = ver catálogo   p = pular item   q = sair (salva)")
    print("=" * 78)

    for n, i in enumerate(pendentes, 1):
        d = linhas[i]
        # O estrato NÃO é impresso: `abstencao` diz "não responda", `ranking` diz "é um ranking",
        # `grao_temporal` diz "agrupe por tempo". É a classificação do autor — metade da resposta.
        # Mostrá-la infla o κ, que passa a medir concordância com uma dica.
        print(f"\n{'-' * 78}\n[{n}/{len(pendentes)}]")
        print(f"\n  PERGUNTA: {d['pergunta_nl']}\n")
        acao = input("  ENTER p/ anotar | c=catálogo | p=pular | q=sair: ").strip().lower()
        while acao == "c":
            print("\n" + CATALOGO_ANTT + "\n")
            acao = input("  ENTER p/ anotar | p=pular | q=sair: ").strip().lower()
        if acao == "q":
            salvar()
            print(f"\nSalvo. {sum(1 for x in linhas if x.get('spec_humano'))}/{len(linhas)} "
                  "anotados. Rode de novo para continuar.")
            return
        if acao == "p":
            continue

        met = _menu("MÉTRICA(S) — ou 'ABSTENHO' se nada no catálogo responde:",
                    [*METRICAS, "ABSTENHO (nenhuma métrica responde)"], True, False)
        if any(m.startswith("ABSTENHO") for m in met):
            spec = {"metrics": [], "group_by": [], "where": None,
                    "order_by": [], "limit": None, "ordenado": False}
        else:
            gb = _menu("AGRUPAR POR (group_by) — só o que a pergunta pede explicitamente:",
                       GROUP_BY, True, True)
            where = _montar_where()
            ordenado, order_by, limite = False, [], None
            if _sim("É RANKING? (a pergunta pede 'o maior', 'top N', 'que mais')"):
                ordenado = True
                campo = _menu("ordenar por:", [*met, *gb], False, False)[0]
                order_by = [f"-{campo}" if _sim("decrescente (do maior p/ o menor)?")
                            else campo]
                cru = input("  limite (número, ENTER p/ nenhum): ").strip()
                limite = int(cru) if cru.isdigit() else None
            spec = {"metrics": met, "group_by": gb, "where": where,
                    "order_by": order_by, "limit": limite, "ordenado": ordenado}

        print(f"  → {json.dumps(spec, ensure_ascii=False)}")
        if _sim("confirma?"):
            linhas[i]["spec_humano"] = spec
            salvar()
        else:
            print("  (descartado — o item fica pendente)")

    salvar()
    feitos = sum(1 for x in linhas if x.get("spec_humano"))
    print(f"\n{'=' * 78}\n{feitos}/{len(linhas)} anotados.")
    print("Agora: python anotar_humano.py kappa")


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

    autor = {it.id: it for it in _golden_selado()}
    # Guarda: um item fora do golden selado teria referência que as Fases 14/15 já descartaram.
    # Falhar alto é melhor que publicar um κ silenciosamente contaminado.
    orfaos = [d["id"] for d in preenchidos if d["id"] not in autor]
    if orfaos:
        raise SystemExit(
            f"{len(orfaos)} item(ns) anotados NÃO estão no golden selado atual: {orfaos[:5]}\n"
            "A folha é antiga (anterior às limpezas das Fases 14/15). Regenere com "
            "`python anotar_humano.py amostra` e anote a nova — o κ contra referência "
            "descartada mediria defeito conhecido, não discordância.")
    A, B = [], []
    for d in preenchidos:
        ref = autor[d["id"]]
        A.append(ref)
        spec = Spec(**d["spec_humano"])
        # O `estrato` do lado B é o julgamento DO HUMANO, não o rótulo do autor. O `ItemGolden`
        # impõe "estrato=abstencao ⟹ spec vazia" — invariante correto para um GOLDEN, mas herdar
        # `ref.estrato` aqui faria o κ ESTOURAR justamente quando o humano responde um item que o
        # autor marcou como fora-de-escopo: a discordância mais informativa da amostra (5 dos 40
        # itens são do estrato `abstencao`). Mesma convenção de `concordancia_opus5.py`;
        # `concordancia_mapeamento` só lê `.id` e `.spec`.
        estrato_b = ESTRATO_ABSTENCAO if not spec.metrics else (
            ref.estrato if ref.estrato != ESTRATO_ABSTENCAO else ESTRATOS_RESPONDIVEIS[0])
        B.append(ItemGolden(id=d["id"], pergunta_nl=ref.pergunta_nl, estrato=estrato_b,
                            spec=spec, revisado_humano=True))
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
    elif cmd == "anotar":
        anotar()
    elif cmd == "kappa":
        kappa()
    else:
        print(__doc__)
