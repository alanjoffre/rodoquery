"""Mede o histórico REAL do CI na API do GitHub Actions e persiste como artefato.

Existe porque o README afirma "1 verde em 33 execuções". Número afirmado no README ou sai de um
artefato, ou é retratado — a regra vale também quando o número é contra mim.

Uso: python medir_historico_ci.py  (API pública, sem token; repositório é público)
"""
import json
import urllib.request
from datetime import date
from pathlib import Path

REPO_GH = "alanjoffre/rodoquery"
SAIDA = Path(__file__).resolve().parent / "reports" / "fase22" / "historico_ci.json"


def main() -> int:
    url = f"https://api.github.com/repos/{REPO_GH}/actions/runs?per_page=100"
    req = urllib.request.Request(url, headers={"User-Agent": "rodoquery-auditoria"})
    with urllib.request.urlopen(req, timeout=30) as r:
        bruto = json.load(r)

    runs = sorted(bruto["workflow_runs"], key=lambda x: x["created_at"])
    concluidas = [x for x in runs if x["conclusion"] is not None]
    verdes = [x for x in concluidas if x["conclusion"] == "success"]

    # maior sequência de vermelhas TERMINANDO na última execução concluída
    seguidas = 0
    for x in reversed(concluidas):
        if x["conclusion"] == "success":
            break
        seguidas += 1

    d0 = date.fromisoformat(concluidas[-seguidas]["created_at"][:10]) if seguidas else None
    d1 = date.fromisoformat(concluidas[-1]["created_at"][:10]) if seguidas else None

    art = {
        "medido_em": concluidas[-1]["created_at"],
        "repositorio": REPO_GH,
        "n_execucoes": len(concluidas),
        "n_verdes": len(verdes),
        "n_vermelhas": len(concluidas) - len(verdes),
        "vermelhas_consecutivas_ate_a_ultima": seguidas,
        "dias_vermelho": (d1 - d0).days if seguidas else 0,
        "primeira_verde": (
            {"sha": verdes[0]["head_sha"][:8], "em": verdes[0]["created_at"],
             "titulo": verdes[0]["display_title"]} if verdes else None
        ),
        "primeira_vermelha": (
            {"sha": concluidas[-seguidas]["head_sha"][:8],
             "em": concluidas[-seguidas]["created_at"],
             "titulo": concluidas[-seguidas]["display_title"]} if seguidas else None
        ),
        "execucoes": [
            {"em": x["created_at"][:16], "conclusao": x["conclusion"],
             "sha": x["head_sha"][:8], "titulo": x["display_title"]}
            for x in concluidas
        ],
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"execucoes concluidas : {art['n_execucoes']}")
    print(f"verdes               : {art['n_verdes']}")
    print(f"vermelhas seguidas   : {art['vermelhas_consecutivas_ate_a_ultima']} "
          f"({art['dias_vermelho']} dias)")
    if art["primeira_verde"]:
        print(f"primeira verde       : {art['primeira_verde']['sha']} "
              f"{art['primeira_verde']['em'][:10]}  {art['primeira_verde']['titulo'][:44]}")
    if art["primeira_vermelha"]:
        print(f"quebrou em           : {art['primeira_vermelha']['sha']} "
              f"{art['primeira_vermelha']['em'][:10]}  {art['primeira_vermelha']['titulo'][:44]}")
    print(f"\nartefato: {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
