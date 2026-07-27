"""Fase 17 — a tese contra um SUT de fronteira (API da Anthropic).

**A pergunta que sobrou.** A Fase 12 mediu Tier-A 89,7% × sql_cru 26,7% (+63,0 pp, p≈0) com
`qwen2.5-coder:7b` nas duas pontas. A Fase 15 fechou o lado de baixo: um 9B generalista COLAPSA
(gemma2:9b, 5,6% — 23/39 specs com vocabulário inválido). Falta o lado de cima, e ele é o que
um cético perguntaria primeiro:

    o ganho do Semantic Layer é uma propriedade da INTERFACE, ou era compensação de um SUT fraco?

Se o gap encolher com um modelo de fronteira, a tese fica mais modesta e mais honesta: o Semantic
Layer vale MAIS quanto mais barato é o SUT. Se o gap persistir, a tese fica mais forte. Os dois
resultados são publicáveis; nenhum é fracasso. É por isso que vale medir.

**O par roda junto, sempre.** Tier-A e sql_cru usam o MESMO provedor na mesma execução. Comparar
Tier-A na API contra o baseline do Qwen mediria o modelo, não a interface — o confundimento exato
que este projeto existe para evitar.

## Uso — a API NUNCA dispara sem `--confirmar`

    python avaliar_fase17.py estimar                       # só a conta, zero chamadas
    python avaliar_fase17.py piloto --n 12 --confirmar     # mede o custo real numa amostra
    python avaliar_fase17.py completo --confirmar          # o TEST-ANTT inteiro

O `--teto-usd` (default 2,00) aborta ANTES de começar se a estimativa estourar, e aborta NO MEIO
se o gasto acumulado passar do teto. Um orçamento que só é verificado no fim não é um orçamento.
"""
import argparse
import json
import statistics as st
import sys
from pathlib import Path

from rodoquery.avaliacao import (
    Predicao,
    avaliar_sistema,
    predicao_de_dict,
    predicao_para_dict,
    vetor_correto,
)
from rodoquery.baselines_antt import sql_cru_antt
from rodoquery.config import settings
from rodoquery.estat import mcnemar
from rodoquery.gold import FUNDACAO_ANTT
from rodoquery.golden import carregar
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.provedor import PRECOS, ProvedorAnthropic, estimar_custo
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt import tier_a_antt

REPO = Path(__file__).resolve().parent
D12 = REPO / "reports" / "fase12"          # gold, catálogo e telemetria congelada do Qwen
D17 = REPO / "reports" / "fase17"
SISTEMAS = {"tier_a_antt": tier_a_antt, "sql_cru_antt": sql_cru_antt}

# O prefixo cacheável = tudo até "\nPergunta: ". Medido nos prompts reais, não estimado — ver
# `_medir_prefixos()`. Os dois sistemas têm prompts de tamanhos diferentes, então medimos os dois.


def _medir_prefixos() -> dict[str, int]:
    """Tokens do prefixo estável de cada sistema, aproximados por caracteres/4.

    Aproximação grosseira DE PROPÓSITO: ela só decide se o prefixo passa do mínimo de cache
    (512 no Opus 5) e alimenta a estimativa. O número que vale é o `cache_read_input_tokens`
    que a API devolve — e esse a gente mede no piloto, não chuta.
    """
    from rodoquery.baselines_antt import PROMPT_ANTT, SCHEMA_ANTT
    from rodoquery.sistema import PROMPT
    from rodoquery.sistema_antt import CATALOGO_ANTT

    p_tier = PROMPT.format(catalogo=CATALOGO_ANTT, pergunta="X")
    p_sql = PROMPT_ANTT.format(schema=SCHEMA_ANTT, pergunta="X")
    return {
        "tier_a_antt": len(p_tier[: p_tier.rfind("\nPergunta: ")]) // 4,
        "sql_cru_antt": len(p_sql[: p_sql.rfind("\nPergunta: ")]) // 4,
    }


def _telemetria_qwen() -> dict[str, dict]:
    """Média de tokens por item, medida nas predições congeladas da Fase 12 (Qwen)."""
    out = {}
    for nome in SISTEMAS:
        fp = D12 / f"predicoes_{nome}_test.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        tp = [v["meta"]["tokens_prompt"] for v in d.values()]
        ts = [v["meta"]["tokens_saida"] for v in d.values()]
        out[nome] = {"n": len(tp), "prompt_medio": st.mean(tp), "saida_media": st.mean(ts)}
    return out


def cmd_estimar(args) -> None:
    """A conta ANTES de gastar. Zero chamadas de API."""
    tel, pref = _telemetria_qwen(), _medir_prefixos()
    print("Telemetria medida (Fase 12, qwen2.5-coder:7b):")
    for n, t in tel.items():
        print(f"  {n:14s} n={t['n']}  prompt~{t['prompt_medio']:.0f}  "
              f"saída~{t['saida_media']:.0f}  prefixo~{pref[n]} tok")

    print(f"\nEstimativa para o PAR completo ({tel['tier_a_antt']['n']} itens × 2 sistemas),")
    print("com fator 1,35× de segurança para o tokenizer da Claude:\n")
    print(f"  {'modelo':18s} {'cacheia?':>9s} {'custo USD':>10s}")
    for modelo in PRECOS:
        total, caches = 0.0, []
        for n, t in tel.items():
            e = estimar_custo(modelo, t["n"], t["prompt_medio"], t["saida_media"], pref[n],
                              args.fator)
            total += e["custo_usd_estimado"]
            caches.append(e["cacheia"])
        marca = "sim" if all(caches) else ("parcial" if any(caches) else "não")
        print(f"  {modelo:18s} {marca:>9s} {total:>10.2f}")
    print("\n(Estes números são um TETO. O piloto mede o custo real e reduz a incerteza.)")


def _amostra_estratificada(itens, n: int):
    """Metade respondíveis, metade abstenção — determinístico.

    Amostrar só respondíveis inflaria o custo/item extrapolado (spec longa vs 'ABSTENHO'), e só
    abstenções o subestimaria. O piloto só serve se a mistura espelhar a corrida cheia.
    """
    resp = [i for i in itens if not i.eh_abstencao]
    abst = [i for i in itens if i.eh_abstencao]
    k = max(1, n // 2)
    return resp[:k] + abst[: n - k]


def _coletar(itens, fn, provedor, teto: float, rotulo: str) -> dict:
    """Coleta com trava de orçamento verificada A CADA item, não no fim."""
    preds = {}
    for i, it in enumerate(itens, 1):
        if provedor.custo_usd > teto:
            # Código de saída EXPLÍCITO: `sys.exit("texto")` sai com 0 neste ambiente, e um
            # abort de orçamento que devolve sucesso é pior do que não ter trava nenhuma —
            # qualquer script em volta trataria o estouro como corrida bem-sucedida.
            print(f"\nABORTADO: gasto acumulado ${provedor.custo_usd:.4f} passou do teto "
                  f"${teto:.2f} no item {i}/{len(itens)} de {rotulo}. "
                  f"{len(preds)} predições coletadas ficam salvas.", file=sys.stderr)
            raise SystemExit(2)
        preds[it.id] = predicao_para_dict(fn(it.pergunta_nl, provedor=provedor))
        if i % 10 == 0 or i == len(itens):
            print(f"    {rotulo}: {i}/{len(itens)}  ${provedor.custo_usd:.4f}", flush=True)
    return preds


def _rodar(args, itens, sufixo: str) -> tuple[dict, dict]:
    """Roda o par (Tier-A, sql_cru) no MESMO provedor. Devolve (predições, relatório de custo)."""
    D17.mkdir(parents=True, exist_ok=True)
    prov = ProvedorAnthropic(modelo_padrao=args.modelo, pensar=args.pensar, esforco=args.esforco)
    preds = {}
    for nome, fn in SISTEMAS.items():
        fp = D17 / f"predicoes_{nome}_{sufixo}.json"
        if fp.exists() and not args.refazer:
            preds[nome] = json.loads(fp.read_text(encoding="utf-8"))
            print(f"  {nome}: congeladas reusadas (não gastou)", flush=True)
            continue
        print(f"  {nome}: coletando via API...", flush=True)
        preds[nome] = _coletar(itens, fn, prov, args.teto_usd, nome)
        fp.write_text(json.dumps(preds[nome], ensure_ascii=False, indent=2), encoding="utf-8")
    return preds, prov.relatorio()


def cmd_piloto(args) -> None:
    itens = _amostra_estratificada(carregar(REPO / "golden" / "golden_test_antt.jsonl"), args.n)
    print(f"[PILOTO] {len(itens)} itens × 2 sistemas, modelo={args.modelo}, teto=${args.teto_usd}")
    _, custo = _rodar(args, itens, f"piloto{args.n}")

    n_total = len(carregar(REPO / "golden" / "golden_test_antt.jsonl"))
    por_chamada = custo["custo_usd_por_chamada"]
    # Extrapolação DEFENSIVA: o piloto paga a escrita do cache uma vez e amortiza sobre poucas
    # leituras, então seu custo/chamada é um TETO do custo/chamada da corrida cheia.
    projecao = por_chamada * n_total * 2

    (D17 / f"custo_piloto{args.n}.json").write_text(
        json.dumps(carimbar({"custo_piloto": custo, "n_total_par": n_total * 2,
                             "projecao_completo_usd": round(projecao, 4)}),
                   ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n== CUSTO MEDIDO (piloto) ==")
    for k, v in custo.items():
        print(f"  {k:26s} {v}")
    print(f"\n  projeção p/ o par completo ({n_total * 2} chamadas): "
          f"${projecao:.2f}  [teto — o cache amortiza mais na corrida longa]")
    print("\nSe o número couber no orçamento: python avaliar_fase17.py completo --confirmar")


def cmd_completo(args) -> None:
    itens = carregar(REPO / "golden" / "golden_test_antt.jsonl")
    print(f"[COMPLETO] {len(itens)} itens × 2 sistemas, modelo={args.modelo}, "
          f"teto=${args.teto_usd}", flush=True)
    preds, custo = _rodar(args, itens, "test")

    # Normalizadores das Fases 9/10 — parte do sistema em serving; medir sem eles mediria uma
    # versão que não existe mais.
    tocadas, norm = 0, {}
    for id_, d in preds["tier_a_antt"].items():
        p: Predicao = predicao_de_dict(d)
        if p.tipo == "spec" and p.spec is not None:
            ns = normalizar_spec(p.spec)
            if ns != p.spec:
                tocadas += 1
                p = Predicao.com_spec(ns, **p.meta)
        norm[id_] = predicao_para_dict(p)
    preds["tier_a_antt"] = norm
    print(f"  normalizadores (F9/F10) tocaram {tocadas} specs", flush=True)

    gold = json.loads((D12 / "gold_respostas_antt.json").read_text(encoding="utf-8"))
    hashes = {r["id"]: r["hashes_por_variante"] for r in gold["respostas"]
              if r.get("hashes_por_variante")}
    dbs = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}

    # `fundacao` e `catalogo` são OBRIGATÓRIOS aqui: sem eles o gold compila contra o projeto
    # sintético (0/N) e a allowlist do sandbox bloqueia o baseline inteiro (0/N) — dois bugs de
    # harness que INFLARIAM a tese a nosso favor. Foi o que aconteceu na Fase 12.
    avals = {n: avaliar_sistema(itens, None, hashes, dbs, n, predicoes=preds[n],
                                fundacao=FUNDACAO_ANTT, catalogo=D12 / "catalog_antt.json")
             for n in SISTEMAS}
    ids_resp = [it.id for it in itens if not it.eh_abstencao]
    va, vb = vetor_correto(avals["tier_a_antt"]), vetor_correto(avals["sql_cru_antt"])
    mc = mcnemar([vb[i] for i in ids_resp], [va[i] for i in ids_resp])

    rel = carimbar({
        "fase": "17_tese_contra_sut_de_fronteira",
        "sut": args.modelo, "provedor": "anthropic_api",
        "pensar": args.pensar, "esforco": args.esforco,
        "comparacao": "MESMO SUT nas duas pontas; muda só a interface (spec governada × SQL cru).",
        "determinismo": ("MAIS FRACO que o local: a API rejeita temperature/seed. Predições "
                         "congeladas em disco — o número é reprodutível, a coleta não."),
        "sem_structured_outputs": ("de propósito: forçar JSON Schema responderia por decreto "
                                   "metade do que o Tier-A mede."),
        "referencia_fase12_qwen7b": {"tier_a_ex": 0.897, "sql_cru_ex": 0.267, "delta_pp": 63.0},
        "custo": custo,
        "n": len(itens), "n_variantes": len(dbs), "specs_normalizadas": tocadas,
        "sistemas": {n: {k: v for k, v in avals[n].items() if k != "resultados"}
                     for n in SISTEMAS},
        "mcnemar_sqlcru_vs_tiera_respondiveis": mc,
        "resultados_por_item": {n: avals[n]["resultados"] for n in SISTEMAS},
    })
    dest = D17 / "resultado_test_antt_api.json"
    dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n== TEST-ANTT com {args.modelo} ==")
    for n in SISTEMAS:
        ex, ab = avals[n]["execution_accuracy_respondiveis"], avals[n]["acuracia_abstencao"]
        print(f"  {n:14s} EX={ex['taxa']} IC{ex['wilson_ic95']} ({ex['acertos']}/{ex['n']})"
              f"  | abstenção={ab['taxa']} ({ab['acertos']}/{ab['n']})")
    d_api = (avals["tier_a_antt"]["execution_accuracy_respondiveis"]["taxa"]
             - avals["sql_cru_antt"]["execution_accuracy_respondiveis"]["taxa"]) * 100
    print(f"  McNemar: {mc}")
    print(f"\n  delta Tier-A − sql_cru:  {d_api:+.1f} pp  (Qwen 7B na Fase 12: +63,0 pp)")
    print(f"  custo total: ${custo['custo_usd']:.4f}")
    print(f"\n-> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def comuns(p, confirmar=True):
        p.add_argument("--modelo", default="claude-opus-5", choices=sorted(PRECOS))
        p.add_argument("--teto-usd", type=float, default=2.00,
                       help="aborta antes de começar E durante a corrida (default: 2.00)")
        p.add_argument("--pensar", action="store_true",
                       help="liga adaptive thinking (mais caro; default: desligado)")
        p.add_argument("--esforco", default="low", choices=["low", "medium", "high"])
        p.add_argument("--refazer", action="store_true",
                       help="ignora predições congeladas e gasta de novo")
        if confirmar:
            p.add_argument("--confirmar", action="store_true",
                           help="OBRIGATÓRIO: sem isto, nenhuma chamada de API é feita")

    pe = sub.add_parser("estimar", help="a conta, sem gastar nada")
    pe.add_argument("--fator", type=float, default=1.35)
    pe.set_defaults(func=cmd_estimar)

    pp = sub.add_parser("piloto", help="amostra pequena; mede o custo real")
    pp.add_argument("--n", type=int, default=12)
    comuns(pp)
    pp.set_defaults(func=cmd_piloto)

    pc = sub.add_parser("completo", help="TEST-ANTT inteiro, os dois sistemas")
    comuns(pc)
    pc.set_defaults(func=cmd_completo)

    args = ap.parse_args()
    if args.cmd != "estimar" and not args.confirmar:
        print("Recusado: '--confirmar' é obrigatório para gastar crédito da API.\n"
              "Rode `python avaliar_fase17.py estimar` primeiro para ver a conta.",
              file=sys.stderr)
        raise SystemExit(2)      # explícito: ver comentário em `_coletar`
    args.func(args)


if __name__ == "__main__":
    main()
