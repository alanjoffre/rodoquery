"""Harness de avaliação (Fase 3) — mede um SISTEMA contra o golden set, com honestidade estrita.

Um **sistema** é qualquer `Callable[[str], Predicao]`: recebe a pergunta em NL, devolve ou um SQL
para executar, ou uma ABSTENÇÃO. O harness cuida do resto: valida no sandbox, executa em TODAS as
variantes do test-suite e compara com o gold (Test-Suite Execution Accuracy).

Dois eixos DISTINTOS de acerto (não os misture num número só — seria desonesto):
  - **EX (respondíveis):** o SQL predito bate o gold em TODAS as variantes? Abster aqui = ERRO
    (abstenção indevida).
  - **Abstenção (fora-de-escopo):** a pergunta é irrespondível com o catálogo; acerto = ABSTER.
    Responder com SQL aqui = ERRO (alucinação).

Regra de ouro: na dúvida, conta como ERRO. Nunca inflar. Um SQL que o sandbox rejeita, que dá erro
de execução, ou que bate o gold em 2 de 3 variantes → ERRADO.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import REPO_ROOT
from rodoquery.estat import wilson
from rodoquery.gold import Spec, compilar_spec, executar_gold
from rodoquery.golden import ESTRATOS_RESPONDIVEIS, ItemGolden
from rodoquery.sandbox import carregar_allowlist, executar


@dataclass(frozen=True)
class Predicao:
    """O que um sistema devolve para uma pergunta.

    Três formas, refletindo a arquitetura:
      - `sql`    → SQL cru (Tier-B / baseline): passa pelo SANDBOX (não-confiável).
      - `spec`   → spec do Semantic Layer (Tier-A): o LLM NUNCA escreve SQL; o MetricFlow gera.
                   Roda pelo caminho GOVERNADO (compilar_spec), sem sandbox (sem injeção).
      - `abster` → não responde.
    """
    tipo: str                       # "sql" | "spec" | "abster"
    sql: str | None = None
    spec: Spec | None = None
    meta: dict = field(default_factory=dict)   # latência, texto cru, etc.

    @classmethod
    def abster(cls, **meta) -> Predicao:
        return cls("abster", None, None, meta)

    @classmethod
    def com_sql(cls, sql: str, **meta) -> Predicao:
        return cls("sql", sql, None, meta)

    @classmethod
    def com_spec(cls, spec: Spec, **meta) -> Predicao:
        return cls("spec", None, spec, meta)


Sistema = Callable[[str], Predicao]


def predicao_para_dict(p: Predicao) -> dict:
    return {"tipo": p.tipo, "sql": p.sql,
            "spec": asdict(p.spec) if p.spec else None, "meta": p.meta}


def predicao_de_dict(d: dict) -> Predicao:
    spec = Spec(**d["spec"]) if d.get("spec") else None
    return Predicao(d["tipo"], d.get("sql"), spec, d.get("meta", {}))


def coletar_predicoes(itens: list[ItemGolden], sistema: Sistema) -> dict[str, dict]:
    """Roda o sistema UMA vez e CONGELA as predições (o SUT é estocástico; isto torna o número
    reprodutível e auditável — o scoring vira determinístico a partir daqui)."""
    return {it.id: predicao_para_dict(sistema(it.pergunta_nl)) for it in itens}


def carregar_hashes_gold(caminho: Path | None = None) -> dict[str, dict[str, str]]:
    """{id: {variante: hash}} dos itens RESPONDÍVEIS, do gold da Fase 2."""
    cam = caminho or (REPO_ROOT / "reports" / "fase2" / "gold_respostas.json")
    dados = json.loads(cam.read_text(encoding="utf-8"))
    return {r["id"]: r["hashes_por_variante"] for r in dados["respostas"]
            if r.get("hashes_por_variante")}


def avaliar_item(
    item: ItemGolden,
    pred: Predicao,
    hashes_gold: dict[str, str],
    dbs: dict[str, Path],
    allowlist: set[str],
) -> dict:
    """Avalia UMA predição. Devolve um dict-resultado auditável (por que acertou/errou)."""
    base = {"id": item.id, "estrato": item.estrato, "abstencao": item.eh_abstencao,
            "predicao": pred.tipo, "meta": pred.meta}

    if item.eh_abstencao:
        correto = pred.tipo == "abster"
        motivo = "absteve (correto)" if correto else "respondeu pergunta fora-de-escopo (alucinou)"
        return {**base, "correto": correto, "motivo": motivo}

    # item respondível
    if pred.tipo == "abster":
        return {**base, "correto": False, "motivo": "absteve numa pergunta respondível"}

    # Executa o predito em cada variante e coleta o hash canônico. Dois caminhos:
    #   spec (Tier-A) → compila no MetricFlow e roda no caminho GOVERNADO (confiável, sem sandbox);
    #   sql (Tier-B)  → passa pelo SANDBOX (não-confiável).
    # Em ambos, canoniza com o `ordenado` do GOLD (a pergunta define se a ordem é resposta).
    hashes_pred: dict[str, str] = {}
    if pred.tipo == "spec":
        try:
            sql = compilar_spec(pred.spec)
        except Exception as e:
            return {**base, "correto": False, "motivo": f"spec não compila: {str(e)[:100]}"}
        for nome, db in dbs.items():
            linhas = executar_gold(sql, db)
            hashes_pred[nome] = hash_resultado(linhas, ordenado=item.spec.ordenado)
    else:  # pred.tipo == "sql"
        for nome, db in dbs.items():
            v, linhas = executar(pred.sql, allowlist, db)
            if not v:
                return {**base, "correto": False, "motivo": f"sandbox: {v.motivo}",
                        "sql": pred.sql}
            hashes_pred[nome] = hash_resultado(linhas, ordenado=item.spec.ordenado)

    # Test-Suite EX: tem de bater em TODAS as variantes
    bateram = {n: hashes_pred[n] == hashes_gold.get(n) for n in dbs}
    correto = all(bateram.values())
    n_bate = sum(bateram.values())
    motivo = "EX em todas as variantes" if correto else f"bateu {n_bate}/{len(dbs)} variantes"
    return {**base, "correto": correto, "motivo": motivo,
            "sql": pred.sql, "variantes_batem": bateram}


def _bloco_metricas(resultados: list[dict]) -> dict:
    n = len(resultados)
    ac = sum(r["correto"] for r in resultados)
    lo, hi = wilson(ac, n) if n else (0.0, 0.0)
    return {"n": n, "acertos": ac, "taxa": round(ac / n, 4) if n else None,
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


def avaliar_sistema(
    itens: list[ItemGolden],
    sistema: Sistema | None,
    hashes_gold: dict[str, dict[str, str]],
    dbs: dict[str, Path],
    nome_sistema: str = "sistema",
    predicoes: dict[str, dict] | None = None,
) -> dict:
    """Roda o sistema em todos os itens e agrega — separando os dois eixos e por estrato.

    Se `predicoes` (congeladas) for dado, usa-as em vez de chamar o sistema → scoring 100%
    determinístico e reprodutível (o SUT é estocástico; ver `coletar_predicoes`)."""
    allowlist = carregar_allowlist()
    resultados: list[dict] = []
    for it in itens:
        pred = (predicao_de_dict(predicoes[it.id]) if predicoes is not None
                else sistema(it.pergunta_nl))
        resultados.append(avaliar_item(it, pred, hashes_gold.get(it.id, {}), dbs, allowlist))

    respondiveis = [r for r in resultados if not r["abstencao"]]
    abstencoes = [r for r in resultados if r["abstencao"]]

    por_estrato = {}
    for e in ESTRATOS_RESPONDIVEIS:
        grupo = [r for r in respondiveis if r["estrato"] == e]
        if grupo:
            por_estrato[e] = _bloco_metricas(grupo)

    # abstenção indevida = respondível onde o sistema absteve
    abst_indevida = sum(1 for r in respondiveis if r["predicao"] == "abster")

    return {
        "sistema": nome_sistema,
        "n_total": len(resultados),
        "execution_accuracy_respondiveis": _bloco_metricas(respondiveis),
        "acuracia_abstencao": _bloco_metricas(abstencoes),
        "ex_por_estrato": por_estrato,
        "abstencao_indevida_em_respondiveis": abst_indevida,
        "resultados": resultados,
    }


def vetor_correto(avaliacao: dict) -> dict[str, bool]:
    """{id: correto} — para testes pareados (McNemar) entre dois sistemas."""
    return {r["id"]: r["correto"] for r in avaliacao["resultados"]}
