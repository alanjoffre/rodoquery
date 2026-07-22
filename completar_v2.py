"""Fase 8 — aplica a regra anti-degenerado ao golden v2 e repõe o estrato que ficou curto.

**A regra, declarada antes de olhar qualquer resultado de sistema:** um item cujo gold é IDÊNTICO
nas 3 variantes de seed não oferece proteção de Test-Suite EX. O resultado não depende dos dados,
então uma spec ERRADA que produza o mesmo valor (tipicamente 0 ou 1.0) "acerta" em todas as
variantes. Esses itens inflam o EX e saem da avaliação.

Onde isso aparece: combinações em que o filtro da pergunta conflita com o filtro EMBUTIDO na
métrica — `revenue` (só COMPLETED) filtrado por FAILED/REVERSED dá sempre 0; `suspect_rate`
filtrado por uma flag de auditoria dá sempre 1.0 ou 0.0.

Dropar os degenerados derruba `valor_categorico` abaixo da meta de 25, então geramos candidatos
adicionais DO MESMO estrato e ficamos com os que sobrevivem à regra. Note que a reposição é
escolhida por uma propriedade do GOLD (varia com os dados?), nunca por desempenho de sistema
nenhum — os sistemas ainda não rodaram.
"""
import json
import random
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.gold import Spec, compilar_spec, executar_gold
from rodoquery.golden import ItemGolden, carregar, salvar
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
DBS = {f"seed{s}": Path.home() / "rodoquery_suite" / f"toll_seed{s}.duckdb" for s in (1, 2, 3)}
ALVO = 34
rng = random.Random(777)

# Helpers duplicados de golden/gerar_autor_v2.py de propósito: aquele arquivo é um script com
# efeito colateral (escreve autor_v2.jsonl) e importá-lo aqui o re-executaria.
METRICAS = ["transactions", "suspect_transactions", "revenue", "revenue_cents",
            "revenue_leakage_brl", "revenue_leakage_cents", "suspect_rate"]
VALORES = {
    "transaction__status": ["COMPLETED", "FAILED", "REVERSED"],
    "transaction__payment_method": ["AUTOMATIC_TAG", "CARD", "CASH"],
    "transaction__audit_flag": ["OK", "COBRANCA_EM_FALHA", "TARIFA_DIVERGENTE",
                                "POSSIVEL_DUPLICIDADE", "VALOR_INVALIDO"],
}
VAL_LABEL = {
    "COMPLETED": "concluídas", "FAILED": "que falharam", "REVERSED": "estornadas",
    "AUTOMATIC_TAG": "pagas com tag automática", "CARD": "pagas com cartão",
    "CASH": "pagas em dinheiro", "OK": "sem apontamento de auditoria",
    "COBRANCA_EM_FALHA": "com cobrança em falha", "TARIFA_DIVERGENTE": "com tarifa divergente",
    "POSSIVEL_DUPLICIDADE": "com possível duplicidade", "VALOR_INVALIDO": "com valor inválido",
}


def frase_filtro(m, label):
    if m == "transactions":
        return f"Quantas transações {label} houve?"
    if m == "suspect_transactions":
        return f"Quantas transações suspeitas {label} houve?"
    if m == "revenue":
        return rng.choice([f"Qual foi a receita das transações {label}?",
                           f"Qual o faturamento das transações {label}?"])
    if m == "revenue_cents":
        return f"Qual a receita em centavos das transações {label}?"
    if m == "revenue_leakage_brl":
        return rng.choice([f"Qual o vazamento de receita das transações {label}?",
                           f"Qual a perda de receita das transações {label}?"])
    if m == "revenue_leakage_cents":
        return f"Qual o vazamento de receita em centavos das transações {label}?"
    if m == "suspect_rate":
        return f"Qual a taxa de suspeita das transações {label}?"
    raise ValueError(m)


def sig(s: Spec):
    return (tuple(s.metrics), tuple(s.group_by), s.where, tuple(s.order_by), s.limit,
            bool(s.ordenado))


def gold_de(spec: Spec):
    """(hashes por variante, degenerado?) — degenerado = vazio OU constante entre variantes."""
    sql = compilar_spec(spec)
    hashes, vazio = {}, False
    for nome, db in DBS.items():
        linhas = executar_gold(sql, db)
        if not linhas:
            vazio = True
        hashes[nome] = hash_resultado(linhas, ordenado=spec.ordenado)
    return sql, hashes, (vazio or len(set(hashes.values())) == 1)


# ---------------------------------------------------------------- 1) dropar degenerados
itens = carregar(G / "golden_v2.jsonl")
_GOLD_V2 = REPO / "reports" / "fase8" / "gold_respostas_v2.json"
rel = json.loads(_GOLD_V2.read_text(encoding="utf-8"))
respostas = {r["id"]: r for r in rel["respostas"]}
degenerados = set(rel["gold_constante_entre_variantes"]["ids"])

mantidos = [it for it in itens if it.id not in degenerados]
removidos = [{"id": it.id, "estrato": it.estrato, "pergunta_nl": it.pergunta_nl,
              "motivo": "gold constante entre as 3 variantes (sem protecao de test-suite)"}
             for it in itens if it.id in degenerados]
print(f"removidos por gold constante: {len(removidos)}")

usados = {sig(it.spec) for it in mantidos if not it.eh_abstencao}
usados |= {sig(it.spec) for it in carregar(G / "golden_full.jsonl") if not it.eh_abstencao}
perguntas = {it.pergunta_nl.strip().lower() for it in mantidos}

# ---------------------------------------------------------------- 2) repor valor_categorico
n_vc = sum(1 for it in mantidos if it.estrato == "valor_categorico")
print(f"valor_categorico apos o drop: {n_vc} (alvo {ALVO})")

cands = [(m, dim, v) for dim, vals in VALORES.items() for v in vals for m in METRICAS]
rng.shuffle(cands)
novos, tentados, descartados_novos = [], 0, []
# Sufixo `_r<N>` (reposto) em vez de continuar a numeração: um id removido libera o número, e
# reaproveitá-lo faria a anotação cega do item ANTIGO ser pareada com o item NOVO — κ corrompido.
prox = 1

for m, dim, v in cands:
    if n_vc + len(novos) >= ALVO:
        break
    spec = Spec(metrics=[m], group_by=[], where=f"{{{{ Dimension('{dim}') }}}} = '{v}'")
    perg = frase_filtro(m, VAL_LABEL[v])
    if sig(spec) in usados or perg.strip().lower() in perguntas:
        continue
    tentados += 1
    try:
        sql, hashes, degen = gold_de(spec)
    except Exception as e:
        descartados_novos.append({"spec": str(spec), "motivo": f"nao compila: {str(e)[:80]}"})
        continue
    if degen:
        descartados_novos.append({"pergunta": perg, "motivo": "gold degenerado (vazio/constante)"})
        continue
    usados.add(sig(spec))
    perguntas.add(perg.strip().lower())
    it = ItemGolden(id=f"valor_categorico_v2_r{prox:02d}", pergunta_nl=perg,
                    estrato="valor_categorico", spec=spec, revisado_humano=False)
    prox += 1
    novos.append(it)
    respostas[it.id] = {"id": it.id, "estrato": it.estrato, "sql_metricflow": sql,
                        "n_variantes": len(hashes), "hashes_por_variante": hashes}

print(f"repostos: {len(novos)} (de {tentados} candidatos testados; "
      f"{len(descartados_novos)} degenerados)")

# ---------------------------------------------------------------- 3) gravar
final = mantidos + novos
salvar(final, G / "golden_v2.jsonl")

saida = carimbar({
    "tipo": "gold_golden_v2_fase8_final",
    "regra_anti_degenerado": ("item cujo gold e IDENTICO nas 3 variantes sai: o resultado nao "
                              "depende dos dados, entao uma spec ERRADA que produza o mesmo valor "
                              "acerta em todas as variantes e infla o EX."),
    "removidos_por_gold_constante": removidos,
    "repostos_no_estrato_valor_categorico": [it.id for it in novos],
    "descartados_na_reposicao": descartados_novos,
    "n_final": len(final),
    "variantes": list(DBS),
    "respostas": [respostas[it.id] for it in final],
})
dest = REPO / "reports" / "fase8" / "gold_respostas_v2.json"
dest.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")

import collections  # noqa: E402

c = collections.Counter(it.estrato for it in final)
print(f"\nv2 final: {len(final)}  {dict(sorted(c.items()))}")
print(f"-> {dest}")
