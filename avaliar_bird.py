"""Fase 13 — calibração externa do SUT no BIRD Mini-Dev (500 perguntas HUMANAS).

**O que isto mede — e o que NÃO mede.** O BIRD não tem semantic layer: são 11 bancos SQLite
arbitrários. Logo o Tier-A (spec → MetricFlow) **não roda aqui** — não existe catálogo governado
para essas bases. O que roda é o caminho de **SQL cru**, que é o baseline.

Então o valor do BIRD para este projeto é **calibração**, e ela responde a uma objeção real:

> "O baseline de SQL cru vai mal (28,8% na ANTT) porque o modelo é fraco ou porque o prompt é
>  injusto?"

Se o mesmo SUT tirar um número compatível com o esperado para um 7B num benchmark público e
independente, então o desempenho fraco dele na ANTT **não é artefato do meu prompt** — é a
capacidade real do modelo escrevendo SQL cru. Isso sustenta a tese com evidência externa, e é a
única coisa aqui que não depende de nenhum artefato meu.

Protocolo do próprio BIRD (para o número ser comparável ao leaderboard):
  - o prompt inclui o `evidence` (conhecimento externo anotado por especialista);
  - o schema vem do CREATE TABLE real do SQLite;
  - Execution Accuracy: executa predito e gold no MESMO banco e compara o resultado canonizado
    (conjunto de linhas, ordem-insensível) — execução como oráculo, nunca LLM-juiz.

Uso: python avaliar_bird.py [n_itens]   (default: todos os 500)
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import sqlglot

from rodoquery.baselines import _chamar_ollama
from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.estat import wilson
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
BIRD = Path.home() / "bird" / "pacote" / "minidev" / "MINIDEV"
DBS = BIRD / "dev_databases"
D = REPO / "reports" / "fase13"
D.mkdir(parents=True, exist_ok=True)
LIMITE = int(sys.argv[1]) if len(sys.argv) > 1 else 0
TIMEOUT_S = 30.0

PROMPT = """Você é um especialista em SQLite. Escreva UMA query SQL que responda à pergunta.

Schema do banco:
{schema}

{evidence}Regras:
- Responda com UMA única query SELECT em SQLite e MAIS NADA (sem explicação, sem ```).
- Use exatamente os nomes de tabela e coluna do schema acima.

Pergunta: {pergunta}
SQL:"""


def schema_de(db_id: str) -> str:
    """CREATE TABLE reais do banco — o schema que o benchmark assume disponível."""
    con = sqlite3.connect(f"file:{DBS / db_id / f'{db_id}.sqlite'}?mode=ro", uri=True)
    try:
        linhas = con.execute(
            "select sql from sqlite_master where type='table' and sql is not null").fetchall()
    finally:
        con.close()
    return "\n\n".join(r[0] for r in linhas)


def executar(db_id: str, sql: str) -> list[tuple]:
    con = sqlite3.connect(f"file:{DBS / db_id / f'{db_id}.sqlite'}?mode=ro", uri=True)
    con.execute(f"pragma busy_timeout = {int(TIMEOUT_S * 1000)}")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def eh_select(sql: str) -> bool:
    """Fronteira de código, não de prompt: só SELECT single-statement roda."""
    try:
        sts = sqlglot.parse(sql, dialect="sqlite")
    except Exception:
        return False
    return len(sts) == 1 and sts[0] is not None and sts[0].key.lower() in ("select", "union")


def extrair(texto: str) -> str:
    t = texto.strip()
    if "```" in t:
        partes = t.split("```")
        for p in partes:
            p = p.removeprefix("sql").strip()
            if p.upper().startswith(("SELECT", "WITH")):
                return p
    i = max(t.upper().find("SELECT"), t.upper().find("WITH"))
    return t[i:].strip().rstrip(";") if i >= 0 else ""


itens = json.load(open(BIRD / "mini_dev_sqlite.json", encoding="utf-8"))
if LIMITE:
    itens = itens[:LIMITE]
print(f"[BIRD Mini-Dev] {len(itens)} perguntas humanas, "
      f"{len({x['db_id'] for x in itens})} bancos", flush=True)

cache_schema: dict[str, str] = {}
fp = D / "predicoes_sut_bird.json"
preds = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}
if preds:
    print(f"  {len(preds)} predições congeladas reusadas", flush=True)

t0 = time.perf_counter()
for i, x in enumerate(itens, 1):
    k = str(x["question_id"])
    if k in preds:
        continue
    if x["db_id"] not in cache_schema:
        cache_schema[x["db_id"]] = schema_de(x["db_id"])
    ev = f"Conhecimento externo: {x['evidence']}\n\n" if x.get("evidence") else ""
    texto, tel = _chamar_ollama(
        PROMPT.format(schema=cache_schema[x["db_id"]], evidence=ev, pergunta=x["question"]),
        settings.modelo_sut, settings.temperatura)
    preds[k] = {"sql": extrair(texto), "raw": texto[:300], **tel}
    if i % 25 == 0:
        fp.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {i}/{len(itens)} ({time.perf_counter() - t0:.0f}s)", flush=True)
fp.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")

print("pontuando (execução como oráculo)...", flush=True)
resultados = []
for x in itens:
    k = str(x["question_id"])
    sql = preds[k]["sql"]
    base = {"question_id": x["question_id"], "db_id": x["db_id"],
            "difficulty": x.get("difficulty"), "pergunta": x["question"]}
    if not sql:
        resultados.append({**base, "correto": False, "motivo": "sem SQL na resposta"})
        continue
    if not eh_select(sql):
        resultados.append({**base, "correto": False, "motivo": "não é SELECT single-statement"})
        continue
    try:
        h_gold = hash_resultado(executar(x["db_id"], x["SQL"]), ordenado=False)
    except Exception as e:
        resultados.append({**base, "correto": False,
                           "motivo": f"GOLD do benchmark não executa: {str(e)[:60]}"})
        continue
    try:
        h_pred = hash_resultado(executar(x["db_id"], sql), ordenado=False)
    except Exception as e:
        resultados.append({**base, "correto": False,
                           "motivo": f"predito não executa: {type(e).__name__}: {str(e)[:60]}"})
        continue
    ok = h_pred == h_gold
    resultados.append({**base, "correto": ok,
                       "motivo": "resultado bate o gold" if ok else "resultado difere do gold"})


def bloco(rs):
    ac = sum(r["correto"] for r in rs)
    lo, hi = wilson(ac, len(rs)) if rs else (0, 0)
    return {"n": len(rs), "acertos": ac, "taxa": round(ac / len(rs), 4) if rs else None,
            "wilson_ic95": [round(lo, 4), round(hi, 4)]}


por_dif = {d: bloco([r for r in resultados if r["difficulty"] == d])
           for d in ("simple", "moderate", "challenging")}
import collections  # noqa: E402

motivos = collections.Counter(r["motivo"][:44] for r in resultados if not r["correto"])

rel = carimbar({
    "fase": "13_calibracao_externa_bird",
    "benchmark": "BIRD Mini-Dev (SQLite), CC BY-SA 4.0 — perguntas e SQL-gold HUMANOS",
    "o_que_mede": ("capacidade do SUT escrevendo SQL CRU num benchmark publico independente. O "
                   "Tier-A nao roda aqui: o BIRD nao tem semantic layer."),
    "protocolo": "prompt inclui o `evidence` do benchmark; EX por execucao, ordem-insensivel.",
    "n": len(resultados),
    "execution_accuracy": bloco(resultados),
    "por_dificuldade": por_dif,
    "motivos_de_erro": dict(motivos.most_common(8)),
    "resultados": resultados,
})
(D / "resultado_bird.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2),
                                       encoding="utf-8")

ex = rel["execution_accuracy"]
print(f"\n== BIRD Mini-Dev — {settings.modelo_sut} ==")
print(f"  EX = {ex['taxa']} IC{ex['wilson_ic95']}  ({ex['acertos']}/{ex['n']})")
for d, v in por_dif.items():
    print(f"    {d:12s} {v['acertos']:3d}/{v['n']:3d} = {v['taxa']}")
print("\n  motivos de erro:")
for m, n in motivos.most_common(6):
    print(f"    {n:3d}  {m}")
print(f"\n-> {D / 'resultado_bird.json'}")
