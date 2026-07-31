"""Fase 20 — valida, aplica as guardas e SELA o conjunto duro.

Mesmo crivo do `rodar_robustez_antt.py` da Fase 14, com uma guarda a mais que só faz sentido aqui.
Um item só entra se passar em TODAS:

  compila      — o MetricFlow gera SQL a partir da spec do autor (anti-circularidade)
  não-vazio    — a consulta devolve linhas nas 3 variantes
  G0 anti-degenerado — os hashes das 3 variantes NÃO podem ser iguais. Gold constante não falseia
                 nada: uma spec errada que devolva o mesmo valor em toda parte "acerta" nas três.
  G4 ranking   — `limit` menor que a cardinalidade, e o corte não pode cair num EMPATE (na Fase 14
                 isso produziu 10 itens onde a spec correta "errava" por LIMIT não-determinístico)
  G5 razão viva (NOVA) — se a spec tem métrica de razão, a coluna não pode ser constante entre as
                 linhas. É a versão medida da guarda G1: em vez de eu julgar se o filtro colide
                 com a definição da métrica, o dado decide. Pega a armadilha da Fase 15
                 (`commercial_share` filtrada por `categoria_eixo='6'` = 1,0 em tudo) mesmo em
                 combinações que eu não previ.

O selo (`sha256`) é gravado ANTES de qualquer sistema rodar — pré-registro anti-vazamento.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT, Spec, compilar_spec, executar_gold
from rodoquery.golden import carregar, salvar
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
D = REPO / "reports" / "fase20"
D.mkdir(parents=True, exist_ok=True)
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
RAZOES = ("_rate", "_share")


def _sem_limit(s: Spec) -> Spec:
    return Spec(metrics=s.metrics, group_by=s.group_by, where=s.where,
                order_by=s.order_by, limit=None, ordenado=s.ordenado)


def main() -> None:
    itens = carregar(G / "duro_antt_autor.jsonl")
    print(f"autorados: {len(itens)}", flush=True)

    validos, respostas, descartados = [], [], []
    for it in itens:
        if it.eh_abstencao:                       # não tem gold: a resposta certa é não responder
            validos.append(it)
            continue
        try:
            sql = compilar_spec(it.spec, fundacao=FUNDACAO_ANTT)
        except Exception as e:                                        # noqa: BLE001
            descartados.append({"id": it.id, "motivo": f"nao compila: {type(e).__name__}"})
            continue

        hashes, linhas0, vazio = {}, None, False
        for nome, db in DBS.items():
            linhas = executar_gold(sql, db)
            linhas0 = linhas if linhas0 is None else linhas0
            vazio = vazio or not linhas
            hashes[nome] = hash_resultado(linhas, ordenado=it.spec.ordenado)

        if vazio:
            descartados.append({"id": it.id, "motivo": "resultado vazio em alguma variante"})
            continue
        if len(set(hashes.values())) == 1:
            descartados.append({"id": it.id, "motivo": "gold constante entre variantes (G0)"})
            continue

        # G5 — razão viva: coluna de razão constante = filtro colidindo com a definição
        idx_razao = [i for i, m in enumerate(it.spec.metrics) if m.endswith(RAZOES)]
        if idx_razao:
            desloc = len(linhas0[0]) - len(it.spec.metrics)     # colunas de group_by vêm antes
            constante = any(
                len({round(float(r[desloc + i]), 9) for r in linhas0}) == 1 for i in idx_razao)
            if constante and len(linhas0) > 1:
                descartados.append({"id": it.id, "motivo": "razao constante (G5) — filtro colide"})
                continue

        # G4 — ranking: limite < cardinalidade e corte fora de empate
        if it.spec.ordenado and it.spec.limit:
            vals = [r[-1] for r in executar_gold(
                compilar_spec(_sem_limit(it.spec), fundacao=FUNDACAO_ANTT), DBS["p0"])]
            n = it.spec.limit
            if len(vals) < n:
                descartados.append({"id": it.id,
                                    "motivo": f"limit {n} > cardinalidade {len(vals)}"})
                continue
            if len(vals) > n and vals[n - 1] == vals[n]:
                descartados.append({"id": it.id, "motivo": "empate na zona de corte (G4)"})
                continue

        validos.append(it)
        respostas.append({"id": it.id, "estrato": it.estrato, "sql_metricflow": sql,
                          "n_variantes": len(DBS), "hashes_por_variante": hashes})

    dest = G / "duro_antt.jsonl"
    salvar(validos, dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    (G / "duro_antt.sha256").write_text(sha + "\n", encoding="utf-8")
    (D / "gold_duro.json").write_text(json.dumps(carimbar({
        "tipo": "gold_conjunto_duro",
        "anti_circularidade": "gold via MetricFlow a partir da spec do autor; nunca SQL a mao",
        "guardas": ["compila", "nao-vazio", "G0 anti-degenerado", "G4 ranking", "G5 razao viva"],
        "n_autorados": len(itens), "n_validos": len(validos), "n_descartados": len(descartados),
        "descartados": descartados, "sha256": sha, "respostas": respostas,
    }), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nvalidos: {len(validos)}  descartados: {len(descartados)}")
    for d in descartados:
        print(f"  - {d['id']}: {d['motivo']}")
    print("\npor estrato:")
    for e, n in sorted(Counter(i.estrato for i in validos).items()):
        print(f"  {e:18s} {n}")
    print(f"\nselado: {sha[:16]}...  -> {dest}")


if __name__ == "__main__":
    main()
