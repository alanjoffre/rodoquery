"""Latência de ponta a ponta do /consulta, com a resposta CONFERIDA a cada requisição.

Existe porque o `load_test.py` da Fase 6 não serve para esta comparação: ele grava por cima de
`reports/fase6/load_test.json` e as perguntas dele são do catálogo SINTÉTICO, enquanto a imagem e o
cluster servem a ANTT. Aqui a pergunta é a MESMA que a Fase 17b usou no cluster em CPU
("Quantos veículos passaram por sentido?"), o que faz os três números serem comparáveis:

  K8s + CPU (F17b, histórico)  ×  nativo + GPU (hoje)  ×  K8s + GPU (hoje)

Protocolo:
  1. /saude — registra modelo, fundação e catálogo que DE FATO estão respondendo;
  2. 1 requisição FRIA (inclui a carga do modelo na VRAM e a 1ª compilação) — reportada à parte;
  3. N requisições QUENTES da mesma pergunta — p50/p95 do total e do componente LLM;
  4. 1 pergunta de ABSTENÇÃO (o caminho curto: o modelo recusa antes de compilar).

Uma latência só conta se a resposta estiver certa: a soma por sentido tem de dar 391.612.977 (o
total conferido contra SQL puro na F11). Velocidade com resposta errada não é resultado.

Só biblioteca padrão.

Uso: python medir_consulta.py --base http://127.0.0.1:18077 --rotulo k8s-gpu --n 12 --saida x.json
"""
import argparse
import datetime as dt
import json
import statistics as st
import time
import urllib.request
from pathlib import Path

PERGUNTA = "Quantos veículos passaram por sentido?"
ABSTENCAO = "Qual foi a receita de pedágio arrecadada?"
TOTAL_ESPERADO = 391_612_977


def _get(base: str, rota: str) -> dict:
    with urllib.request.urlopen(f"{base}{rota}", timeout=30) as r:
        return json.loads(r.read())


def _consultar(base: str, pergunta: str) -> tuple[dict, float]:
    req = urllib.request.Request(
        f"{base}/consulta", data=json.dumps({"pergunta": pergunta}).encode(),
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    return d, round(time.perf_counter() - t0, 3)


def _confere(d: dict) -> bool:
    if d.get("tipo") != "resposta" or not d.get("linhas"):
        return False
    return round(sum(float(linha[-1]) for linha in d["linhas"])) == TOTAL_ESPERADO


def _pct(v: list[float], p: float) -> float:
    s = sorted(v)
    return round(s[min(len(s) - 1, int(len(s) * p))], 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--rotulo", required=True)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()

    saude = _get(a.base, "/saude")
    fria, parede_fria = _consultar(a.base, PERGUNTA)
    quentes = []
    for _ in range(a.n):
        d, parede = _consultar(a.base, PERGUNTA)
        quentes.append({"parede_s": parede, "latencia_s": d.get("latencia_s", {}),
                        "confere": _confere(d)})
    abst, parede_abst = _consultar(a.base, ABSTENCAO)

    tot = [q["parede_s"] for q in quentes]
    llm = [q["latencia_s"].get("llm", 0.0) for q in quentes]
    rel = {
        "rotulo": a.rotulo,
        "pergunta": PERGUNTA,
        "saude": saude,
        "fria": {"parede_s": parede_fria, "latencia_s": fria.get("latencia_s"),
                 "confere": _confere(fria), "spec": fria.get("spec"),
                 "linhas": fria.get("linhas")},
        "quentes": {
            "n": len(quentes),
            "todas_conferem": all(q["confere"] for q in quentes),
            "parede_p50_s": _pct(tot, 0.50), "parede_p95_s": _pct(tot, 0.95),
            "parede_media_s": round(st.mean(tot), 3),
            "llm_p50_s": _pct(llm, 0.50), "llm_p95_s": _pct(llm, 0.95),
            "amostras": quentes,
        },
        "abstencao": {"pergunta": ABSTENCAO, "tipo": abst.get("tipo"),
                      "correta": abst.get("tipo") == "abstencao", "parede_s": parede_abst},
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }
    destino = Path(a.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(rel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                       newline="\n")
    q = rel["quentes"]
    print(f"[{a.rotulo}] modelo={saude.get('modelo')} catalogo={saude.get('catalogo_antt')}")
    print(f"  fria : {parede_fria}s (confere={rel['fria']['confere']})")
    print(f"  quente n={q['n']}: p50 {q['parede_p50_s']}s  p95 {q['parede_p95_s']}s  "
          f"| llm p50 {q['llm_p50_s']}s  | todas conferem={q['todas_conferem']}")
    print(f"  abstencao: {rel['abstencao']['tipo']} em {parede_abst}s")


if __name__ == "__main__":
    main()
