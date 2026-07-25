"""Fase 14 (#2, parte 1) — remove itens de RANKING com empate na zona de corte: defeito de gold.

Achado ao diagnosticar o resíduo de 72%: alguns itens de ranking pedem "as N praças com maior X"
onde as N primeiras têm o MESMO valor de X. Com empate, `LIMIT N` sem desempate total devolve um
conjunto de linhas NÃO-DETERMINÍSTICO — qualquer subconjunto das empatadas é uma resposta válida,
mas o gold foi congelado de UMA execução. Resultado: o modelo produz a spec IDÊNTICA ao gold e
mesmo assim "erra", porque a ordem entre iguais mudou.

Isso é a mesma família da regra anti-degenerado (Fase 8): um item cujo gold não é determinado pelos
dados não pertence ao conjunto. Aqui a não-determinação é na ORDEM, não no valor.

Critério (propriedade do GOLD, independente de qualquer sistema): item ordenado com `limit=N` em
que o valor da métrica na posição N é igual ao da posição N+1 (ou há menos de N valores distintos
na coluna ordenada) — o corte cai no meio de um empate.

Aplica a TODOS os itens de ranking do golden ANTT (dev+test), não só às falhas — senão eu estaria
escolhendo quais remover olhando o resultado.
"""
import hashlib
import json
from pathlib import Path

from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT, Spec, compilar_spec, executar_gold
from rodoquery.golden import carregar

G = Path("golden")
DBS = [settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)]
CH = ("metrics", "group_by", "where", "order_by", "limit", "ordenado")


def empate_no_corte(spec: Spec) -> bool:
    """O corte do LIMIT cai dentro de um empate, em QUALQUER variante?"""
    if not (spec.ordenado and spec.limit):
        return False
    sql = compilar_spec(spec, fundacao=FUNDACAO_ANTT)
    for db in DBS:
        linhas = executar_gold(sql, db)
        if len(linhas) < spec.limit:
            return True                       # menos linhas que o limite = corte instável
        vals = [r[-1] for r in linhas]        # a métrica é a última coluna
        # valor na posição limit-1 empata com o próximo? (precisa olhar 1 além do corte)
        # como o SQL já veio com LIMIT, recompilamos sem limit para ver o vizinho
    # olhar 1 além do corte exige a query sem limit:
    s2 = Spec(metrics=spec.metrics, group_by=spec.group_by, where=spec.where,
              order_by=spec.order_by, limit=None, ordenado=spec.ordenado)
    sql2 = compilar_spec(s2, fundacao=FUNDACAO_ANTT)
    for db in DBS:
        linhas = executar_gold(sql2, db)
        vals = [r[-1] for r in linhas]
        n = spec.limit
        if len(vals) > n and vals[n - 1] == vals[n]:
            return True                       # posição N empata com N+1 → corte no meio do empate
        if len(set(vals[:n])) < min(n, len(vals)):
            return True                       # empate dentro do top-N
    return False


for split in ("test", "dev", ""):
    nome = f"golden_{split}_antt.jsonl" if split else "golden_antt.jsonl"
    caminho = G / nome
    if not caminho.exists():
        continue
    itens = carregar(caminho)
    ranking = [it for it in itens if it.estrato == "ranking"]
    ruins = [it for it in ranking if empate_no_corte(it.spec)]
    ids_ruins = {it.id for it in ruins}
    mant = [it for it in itens if it.id not in ids_ruins]
    caminho.write_text(
        "".join(json.dumps({"id": it.id, "pergunta_nl": it.pergunta_nl, "estrato": it.estrato,
                            "spec": {k: getattr(it.spec, k) for k in CH},
                            "revisado_humano": it.revisado_humano}, ensure_ascii=False) + "\n"
                for it in mant), encoding="utf-8")
    print(f"{nome}: {len(itens)} -> {len(mant)}  (removidos {len(ids_ruins)} rankings com empate)")
    for it in ruins:
        print(f"   - {it.id}: {it.pergunta_nl[:60]}")
    if split == "test":
        sha = hashlib.sha256(caminho.read_bytes()).hexdigest()
        (G / "golden_test_antt.sha256").write_text(sha + "\n", encoding="utf-8")
        print(f"   TEST re-selado: {sha[:16]}...")
