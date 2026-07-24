"""Fase 11 — canário: o agente responde perguntas reais sobre a base da ANTT?

Sinal OPERACIONAL (poucas perguntas, escritas à mão), não medida científica. A avaliação com
golden set estratificado, gold via MetricFlow e Test-Suite EX é a próxima etapa. O que este script
prova é que o caminho inteiro fecha sobre DADO REAL: pergunta → spec → MetricFlow → SQL → número.

Inclui perguntas fora do catálogo de propósito — a base é agregada e não tem receita nem hora do
dia, então o certo é ABSTER. É onde a Fase 8 mostrou que o modelo troca a métrica por um vizinho.
"""
from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT, compilar_spec, executar_gold
from rodoquery.normalizacao_spec import normalizar_spec
from rodoquery.sistema_antt import tier_a_antt

PERGUNTAS = [
    ("Quantos veículos passaram no total?", False),
    ("Qual o volume de tráfego por mês?", False),
    ("Qual a taxa de automação por concessionária?", False),
    ("Quais as 5 praças com maior volume de tráfego?", False),
    ("Quantos veículos comerciais passaram em cada praça?", False),
    ("Qual o volume de tráfego em cada dia na cobrança automática?", False),
    ("Qual a participação de veículos comerciais por sentido?", False),
    # fora do catálogo — o certo é ABSTER
    ("Qual foi a receita de pedágio arrecadada?", True),
    ("Qual o volume médio de veículos por praça?", True),
    ("Quantos veículos passaram por hora do dia?", True),
    ("Qual a receita por concessionária?", True),
    ("Quantos veículos distintos passaram?", True),
]

acertos = 0
for pergunta, deve_abster in PERGUNTAS:
    pred = tier_a_antt(pergunta)
    if pred.tipo == "abster":
        ok = deve_abster
        print(f"[{'OK ' if ok else 'ERRO'}] ABSTEVE  | {pergunta}")
    else:
        spec = normalizar_spec(pred.spec)
        try:
            sql = compilar_spec(spec, fundacao=FUNDACAO_ANTT)
            linhas = executar_gold(sql, settings.antt_duckdb)
            ok = not deve_abster and len(linhas) > 0
            amostra = linhas[0] if linhas else None
            print(f"[{'OK ' if ok else 'ERRO'}] {len(linhas):>4} linhas | {pergunta}")
            print(f"        m={spec.metrics} gb={spec.group_by} -> {amostra}")
        except Exception as e:
            ok = False
            print(f"[ERRO] não compila | {pergunta}\n        {type(e).__name__}: {str(e)[:90]}")
    acertos += ok

print(f"\ncanário ANTT: {acertos}/{len(PERGUNTAS)}")
