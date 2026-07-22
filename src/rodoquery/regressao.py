"""Gate de regressão (Fase 5) — em 3 níveis, projetado para o SUT ser FLAKY.

**O problema real** (achado da Fase 4, quantificado em `reports/fase5/flakiness.json`): o SUT tem
variância run-a-run mesmo greedy+seed (float não-associativo na GPU). Um gate ingênuo colado no EX
observado (`falha se EX < 0.976`) alterna verde/vermelho sozinho — e um gate que crê-lobo é pior que
gate nenhum: o time aprende a ignorá-lo.

**A resposta:** separar o que é determinístico do que é estocástico, e dar ao estocástico uma margem
derivada da variância MEDIDA (não chutada).

| Nível | O que checa | Precisa de | Flaky? |
|---|---|---|---|
| **A · contrato** | selo do golden; agregados batem com os itens; limiares | só os JSON | **não** |
| **B · replay** | re-executa predições congeladas vs gold | DuckDB + mf | **não** |
| **C · live** | roda o sistema de verdade num smoke set | GPU + LLM | sim → usa margem |

O nível A é o que roda no CI (sem GPU). B roda na máquina da fundação. C roda agendado, com margem.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Limiares:
    """Limiares do gate. `margem_flaky` DEVE vir da variância medida, não de chute."""
    ex_minimo: float = 0.90            # EX mínimo aceitável do sistema (Tier-A)
    abstencao_minima: float = 0.90
    vantagem_minima_pp: float = 30.0   # Tier-A tem de bater o sql_cru por N pontos
    margem_flaky: float = 0.0          # subtraída dos mínimos no gate LIVE (nível C)


@dataclass(frozen=True)
class Resultado:
    ok: bool
    checagens: list[dict]

    def relatorio(self) -> str:
        linhas = [f"{'OK  ' if c['ok'] else 'FALHA'} {c['nome']}: {c['detalhe']}"
                  for c in self.checagens]
        return "\n".join(linhas)


def _chk(nome: str, ok: bool, detalhe: str) -> dict:
    return {"nome": nome, "ok": bool(ok), "detalhe": detalhe}


def verificar_selo(caminho_test: Path, caminho_sha: Path) -> dict:
    """O golden TEST não pode ter mudado depois do pré-registro — senão o número não vale nada."""
    atual = hashlib.sha256(caminho_test.read_bytes()).hexdigest()
    esperado = caminho_sha.read_text(encoding="utf-8").strip()
    detalhe = ("sha256 confere" if atual == esperado
               else f"MUDOU: {atual[:12]} != {esperado[:12]}")
    return _chk("selo_golden_test", atual == esperado, detalhe)


def _agregar(resultados: list[dict]) -> tuple[int, int, int, int]:
    """(acertos_respondiveis, n_respondiveis, acertos_abstencao, n_abstencao)"""
    resp = [r for r in resultados if not r["abstencao"]]
    abst = [r for r in resultados if r["abstencao"]]
    return (sum(r["correto"] for r in resp), len(resp),
            sum(r["correto"] for r in abst), len(abst))


def gate_contrato(relatorio: dict, limiares: Limiares, selo: dict | None = None) -> Resultado:
    """Nível A (CI, sem GPU): coerência interna do relatório + limiares + selo.

    Recomputa os agregados A PARTIR dos itens: se alguém editar só o número bonito no topo do JSON,
    o gate pega. É barato e não flaka."""
    checagens = [selo] if selo else []
    sistemas = relatorio["sistemas"]
    por_item = relatorio["resultados_por_item"]

    for nome, bloco in sistemas.items():
        ac, n, ac_a, n_a = _agregar(por_item[nome])
        ex_rep = bloco["execution_accuracy_respondiveis"]
        ab_rep = bloco["acuracia_abstencao"]
        coerente = (ex_rep["acertos"] == ac and ex_rep["n"] == n
                    and ab_rep["acertos"] == ac_a and ab_rep["n"] == n_a)
        checagens.append(_chk(
            f"coerencia[{nome}]", coerente,
            f"relatorio {ex_rep['acertos']}/{ex_rep['n']} vs itens {ac}/{n}"))

    ex_sis = sistemas["tier_a"]["execution_accuracy_respondiveis"]["taxa"]
    ab_sis = sistemas["tier_a"]["acuracia_abstencao"]["taxa"]
    ex_base = sistemas["sql_cru"]["execution_accuracy_respondiveis"]["taxa"]
    vantagem_pp = (ex_sis - ex_base) * 100

    checagens += [
        _chk("ex_minimo", ex_sis >= limiares.ex_minimo,
             f"EX={ex_sis:.4f} (min {limiares.ex_minimo})"),
        _chk("abstencao_minima", ab_sis >= limiares.abstencao_minima,
             f"abstencao={ab_sis:.4f} (min {limiares.abstencao_minima})"),
        _chk("vantagem_sobre_baseline", vantagem_pp >= limiares.vantagem_minima_pp,
             f"+{vantagem_pp:.1f}pp (min {limiares.vantagem_minima_pp}pp)"),
    ]
    mc = relatorio.get("mcnemar_tier_a_vs_sql_cru_respondiveis", {})
    if mc:
        checagens.append(_chk("mcnemar_significante", mc.get("p_valor", 1.0) < 0.05,
                              f"p={mc.get('p_valor')}"))
    return Resultado(all(c["ok"] for c in checagens), checagens)


def gate_live(ex_observado: float, referencia: float, limiares: Limiares) -> Resultado:
    """Nível C (com LLM): só falha se cair ABAIXO da referência descontada a margem MEDIDA.

    Sem a margem, este gate acusaria regressão por puro ruído de GPU."""
    piso = max(limiares.ex_minimo, referencia - limiares.margem_flaky)
    ok = ex_observado >= piso
    return Resultado(ok, [_chk(
        "ex_live_com_margem", ok,
        f"EX={ex_observado:.4f} vs piso={piso:.4f} "
        f"(ref {referencia:.4f} - margem {limiares.margem_flaky:.4f})")])


def carregar_margem_medida(caminho: Path, n_respondiveis: int | None = None) -> float:
    """Margem do gate live, derivada da MEDIÇÃO (nunca de chute).

    Margem = max(amplitude observada, 1 item).

    O piso de 1 item é deliberado e honesto: a medição observou amplitude 0 em K runs, mas **K runs
    pequenos não provam variância zero** — só dizem que ela é baixa. Sem piso, um único item que
    virasse reprovaria o build; com o piso, o gate só acusa regressão de verdade (≥ 2 itens)."""
    d = json.loads(caminho.read_text(encoding="utf-8"))
    amplitude = d["ex_max"] - d["ex_min"]
    piso = 1.0 / n_respondiveis if n_respondiveis else 0.0
    return round(max(amplitude, piso), 4)
