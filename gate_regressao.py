"""Gate de regressão — CLI. Sai com código != 0 se qualquer checagem falhar (é o que trava o CI).

Nível A (default): contrato — selo do golden + coerência do relatório + limiares. NÃO precisa de
GPU, banco ou LLM, então roda no CI de graça e **não flaka**.

Nível B (--replay): re-executa as predições CONGELADAS contra o gold e exige que o veredito
item-a-item seja IDÊNTICO ao do relatório commitado. Não usa LLM (não flaka), mas precisa de
DuckDB + MetricFlow — por isso roda na máquina da fundação, não no CI. Pega regressão em
canonização, scorer, gold ou nas variantes do test-suite.

## Por que há TRÊS alvos, e não um

Até a Fase 22 este gate lia **um** relatório: `reports/fase4/resultado_test.json` — a tese na
fundação **sintética**, medida 18 fases atrás. A tese que o README exibe no topo vive na ANTT
(F12 com o SUT local, F18 com o SUT de fronteira). O efeito prático: **uma regressão no caminho
ANTT passava verde**, porque o gate não tinha como olhá-la.

É o análogo exato da lição da Fase 22 — *ter pipeline não é ter pipeline no alvo certo* — com um
agravante: aqui o gate estava comprovadamente **ativo** (pega 6/6 regressões injetadas, F5), o que
o fazia parecer prova. Um gate ativo apontado para o alvo errado é a forma mais convincente de
falsa segurança que este projeto produziu.

O conserto **não** é trocar o alvo: é cobrir todos os que o README sustenta. A F4 continua sendo
uma afirmação viva do repositório (a tabela de fases a exibe), então ela permanece — só deixou de
ser a única.

Uso:
  python gate_regressao.py            # nível A (CI): contrato, nos 3 alvos
  python gate_regressao.py --replay   # nível B: re-executa as predições congeladas
  python gate_regressao.py --margem   # margem medida p/ o gate live (nível C)
"""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rodoquery.regressao import (
    Limiares,
    carregar_margem_medida,
    gate_contrato,
    verificar_selo,
)

REPO = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Alvo:
    """Uma afirmação do README que o gate protege."""
    rotulo: str
    relatorio: Path
    golden: Path
    sha: Path
    sistema: str
    baseline: str
    limiares: Limiares
    # Nível B: de onde vêm as predições congeladas e contra qual fundação re-pontuar.
    gold_hashes: Path | None = None          # None = gold da Fase 2 (sintético)
    dbs: dict[str, Path] = field(default_factory=dict)
    catalogo: Path | None = None             # None = allowlist da fundação sintética
    fundacao_antt: bool = False
    normalizar_specs: bool = False           # normalizadores F9/F10 (só no caminho ANTT)


# Limiares com FOLGA sobre o observado: um gate colado no valor medido vira alarme falso.
#
# Quanta folga? Derivada de uma variação MEDIDA, não de chute: o MESMO conjunto ANTT foi
# re-pontuado três vezes ao longo do projeto (F12 86,9% -> F14 88,7% -> F15 89,7%) conforme
# defeitos de gold saíam, uma amplitude de 2,8 pp. Os limiares abaixo ficam ~8 pp sob o medido —
# cerca de 3x a maior deriva já observada numa re-pontuação. Pegam regressão real sem brigar com
# correção legítima de rótulo.
ALVOS = [
    Alvo(
        rotulo="F4 · fundação SINTÉTICA (qwen2.5-coder:7b)",
        relatorio=REPO / "reports" / "fase4" / "resultado_test.json",
        golden=REPO / "golden" / "golden_test.jsonl",
        sha=REPO / "golden" / "golden_test.sha256",
        sistema="tier_a", baseline="sql_cru",
        # Inalterados desde a Fase 5, de propósito: mexer aqui mudaria o significado de 18 fases.
        limiares=Limiares(ex_minimo=0.90, abstencao_minima=0.90, vantagem_minima_pp=30.0),
        dbs={f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb"
             for s in (1, 2, 3)},
    ),
    Alvo(
        rotulo="F12 · dado real ANTT (qwen2.5-coder:7b)",
        relatorio=REPO / "reports" / "fase12" / "resultado_test_antt.json",
        golden=REPO / "golden" / "golden_test_antt.jsonl",
        sha=REPO / "golden" / "golden_test_antt.sha256",
        sistema="tier_a_antt", baseline="sql_cru_antt",
        # Medido: EX 89,7% · abstenção 88,0% · vantagem +63,0 pp.
        # A abstenção de 88% é o motivo de este alvo NÃO poder herdar os limiares da F4: com
        # `abstencao_minima=0.90` o gate reprovaria a própria tese que deve proteger.
        limiares=Limiares(ex_minimo=0.82, abstencao_minima=0.80, vantagem_minima_pp=45.0),
        gold_hashes=REPO / "reports" / "fase12" / "gold_respostas_antt.json",
        dbs={f"p{v}": Path.home() / "antt_suite" / f"antt_p{v}.duckdb" for v in range(3)},
        catalogo=REPO / "reports" / "fase12" / "catalog_antt.json",
        fundacao_antt=True,
        normalizar_specs=True,
    ),
    Alvo(
        rotulo="F18 · dado real ANTT (claude-opus-5)",
        relatorio=REPO / "reports" / "fase18" / "resultado_test_antt_api.json",
        golden=REPO / "golden" / "golden_test_antt.jsonl",
        sha=REPO / "golden" / "golden_test_antt.sha256",
        sistema="tier_a_antt", baseline="sql_cru_antt",
        # Medido: EX 100% · abstenção 96,0% · vantagem +55,5 pp. O EX saturado é justamente o
        # motivo de o limiar NÃO ser 1,0: um gate colado no teto reprova qualquer item que ceda.
        limiares=Limiares(ex_minimo=0.92, abstencao_minima=0.88, vantagem_minima_pp=40.0),
        gold_hashes=REPO / "reports" / "fase12" / "gold_respostas_antt.json",
        dbs={f"p{v}": Path.home() / "antt_suite" / f"antt_p{v}.duckdb" for v in range(3)},
        catalogo=REPO / "reports" / "fase12" / "catalog_antt.json",
        fundacao_antt=True,
        normalizar_specs=True,
    ),
]


def _carregar_hashes(alvo: Alvo) -> dict:
    from rodoquery.avaliacao import carregar_hashes_gold
    if alvo.gold_hashes is None:
        return carregar_hashes_gold()
    dados = json.loads(alvo.gold_hashes.read_text(encoding="utf-8"))
    return {r["id"]: r["hashes_por_variante"] for r in dados["respostas"]
            if r.get("hashes_por_variante")}


def _predicoes(alvo: Alvo, nome: str) -> dict:
    """As congeladas ficam ao lado do relatório, com o mesmo sufixo de split."""
    return json.loads(
        (alvo.relatorio.parent / f"predicoes_{nome}_test.json").read_text(encoding="utf-8"))


def _replay_alvo(alvo: Alvo) -> bool:
    from rodoquery.avaliacao import (
        Predicao,
        avaliar_sistema,
        predicao_de_dict,
        predicao_para_dict,
        vetor_correto,
    )
    from rodoquery.gold import FUNDACAO_ANTT
    from rodoquery.golden import carregar
    from rodoquery.normalizacao_spec import normalizar_spec

    rel = json.loads(alvo.relatorio.read_text(encoding="utf-8"))
    itens = carregar(alvo.golden)
    hashes = _carregar_hashes(alvo)
    fundacao = FUNDACAO_ANTT if alvo.fundacao_antt else None

    ok_geral = True
    for nome in (alvo.sistema, alvo.baseline):
        preds = _predicoes(alvo, nome)
        # Os normalizadores das F9/F10 rodam ANTES do scoring no caminho ANTT — o relatório
        # commitado foi produzido com eles. Replay sem esta etapa divergiria por construção, e o
        # gate acusaria uma regressão que não existe.
        if alvo.normalizar_specs and nome == alvo.sistema:
            norm = {}
            for id_, d in preds.items():
                p = predicao_de_dict(d)
                if p.tipo == "spec" and p.spec is not None:
                    ns = normalizar_spec(p.spec)
                    if ns != p.spec:
                        p = Predicao.com_spec(ns, **p.meta)
                norm[id_] = predicao_para_dict(p)
            preds = norm
        agora = vetor_correto(avaliar_sistema(
            itens, None, hashes, alvo.dbs, nome, predicoes=preds,
            fundacao=fundacao, catalogo=alvo.catalogo))
        antes = {r["id"]: r["correto"] for r in rel["resultados_por_item"][nome]}
        divergem = [i for i in antes if antes[i] != agora.get(i)]
        ok_geral &= not divergem
        print(f"  {'OK  ' if not divergem else 'FALHA'} replay[{nome}]: "
              f"{len(antes) - len(divergem)}/{len(antes)} vereditos idênticos"
              f"{'  divergem: ' + ','.join(divergem[:5]) if divergem else ''}")
    return ok_geral


def _replay() -> int:
    """Nível B: re-executa as predições congeladas e exige veredito idêntico ao relatório."""
    ok_geral = True
    for alvo in ALVOS:
        print(f"\n--- {alvo.rotulo} ---")
        if not alvo.relatorio.exists():
            print("  PULADO: relatório ausente")
            continue
        faltando = [p for p in alvo.dbs.values() if not p.exists()]
        if faltando:
            # Falha ABERTA: o nível B precisa da fundação em disco, e fingir que passou seria
            # exatamente o "verde com teste faltando" que a Fase 22 declarou pior que vermelho.
            print(f"  FALHA: fundação ausente ({faltando[0]}) — o nível B não pode ser verificado")
            ok_geral = False
            continue
        ok_geral &= _replay_alvo(alvo)
    print("\nGATE (replay):", "PASSOU" if ok_geral else "FALHOU")
    return 0 if ok_geral else 1


def main() -> int:
    if "--replay" in sys.argv:
        return _replay()
    if "--margem" in sys.argv:
        f = REPO / "reports" / "fase5" / "flakiness.json"
        print(f"margem de flakiness medida (ex_max - ex_min): {carregar_margem_medida(f)}")
        return 0

    ok_geral = True
    for alvo in ALVOS:
        print(f"\n--- {alvo.rotulo} ---")
        relatorio = json.loads(alvo.relatorio.read_text(encoding="utf-8"))
        selo = verificar_selo(alvo.golden, alvo.sha)
        res = gate_contrato(relatorio, alvo.limiares, selo,
                            nome_sistema=alvo.sistema, nome_baseline=alvo.baseline)
        print(res.relatorio())
        ok_geral &= res.ok
    print("\nGATE:", "PASSOU" if ok_geral else "FALHOU")
    return 0 if ok_geral else 1


if __name__ == "__main__":
    raise SystemExit(main())
