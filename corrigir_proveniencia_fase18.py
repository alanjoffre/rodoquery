"""Conserta `meta['modelo']` nas predições congeladas da Fase 18 — e deixa rastro de que consertou.

## O bug

A 1ª corrida completa gravou as 342 predições com `modelo: "qwen2.5-coder:7b"`. Causa: em
`tier_a_antt`/`sql_cru_antt`, `modelo = modelo or settings.modelo_sut` resolve para o default
LOCAL, e o `ProvedorAnthropic` trocava para `claude-opus-5` só internamente, sem reportar de
volta. O EX não depende desse campo — mas quem abrisse `reports/fase18/` concluiria que um 7B
local fez 146/146. **Artefato que mente sobre a própria proveniência é pior que artefato ausente.**

Corrigido na fonte (`provedor.py` passou a emitir `modelo_efetivo`; os dois sistemas passaram a
gravá-lo). Este script existe para os arquivos que já estavam em disco.

## Por que corrigir em vez de recoletar

Recoletar custaria outros US$ 0,96 e produziria predições DIFERENTES — a API não aceita
`temperature`/`seed`, então a coleta não é bit-reproduzível (ver docs/FASE18_PROVEDOR.md). Trocar
um artefato real por outro real só para consertar um rótulo seria pior: perderia o vínculo com o
resultado já auditado.

## Por que isto não é falsificar o artefato

Só o RÓTULO muda. `spec`, `sql` e `raw` — tudo que o modelo de fato produziu e sobre o que o EX
foi calculado — ficam intocados, e há uma asserção para isso. E a correção só é aplicada a
registros que carregam PROVA INDEPENDENTE de origem na API:

  - `custo_usd` presente (o caminho Ollama nunca produz esse campo), E
  - `carga_modelo_s == 0` (o Ollama reporta tempo de carga real; a API não tem equivalente).

Um registro sem essas duas marcas é deixado como está — se o script não consegue provar a origem,
ele não reescreve.

Uso:  python corrigir_proveniencia_fase18.py [--aplicar]   (sem --aplicar: só relata)
"""
import argparse
import json
from collections import Counter
from pathlib import Path

MODELO_CORRETO = "claude-opus-5"
D18 = Path(__file__).resolve().parent / "reports" / "fase18"


def veio_da_api(meta: dict) -> bool:
    """Prova independente de que este registro nasceu na API, não no Ollama."""
    return "custo_usd" in meta and not meta.get("carga_modelo_s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="sem isto, apenas relata")
    args = ap.parse_args()

    for fp in sorted(D18.glob("predicoes_*.json")):
        d = json.loads(fp.read_text(encoding="utf-8"))
        antes = Counter(v["meta"].get("modelo") for v in d.values())
        alvos = [k for k, v in d.items()
                 if veio_da_api(v["meta"]) and v["meta"].get("modelo") != MODELO_CORRETO]
        sem_prova = [k for k, v in d.items() if not veio_da_api(v["meta"])]

        print(f"\n{fp.name}  (n={len(d)})")
        print(f"  modelo antes        : {dict(antes)}")
        print(f"  a corrigir          : {len(alvos)}")
        print(f"  sem prova de origem : {len(sem_prova)}  (deixados intactos)")

        if not args.aplicar or not alvos:
            continue

        # A carga útil não pode mudar — só o rótulo.
        assinatura = {k: (json.dumps(v.get("spec"), sort_keys=True), v.get("sql"),
                          v["meta"].get("raw")) for k, v in d.items()}
        for k in alvos:
            d[k]["meta"]["modelo"] = MODELO_CORRETO
            d[k]["meta"]["modelo_efetivo"] = MODELO_CORRETO
            d[k]["meta"]["proveniencia_corrigida"] = (
                "rotulo reescrito por corrigir_proveniencia_fase18.py; "
                "spec/sql/raw intocados (ver docstring)")
        depois = {k: (json.dumps(v.get("spec"), sort_keys=True), v.get("sql"),
                      v["meta"].get("raw")) for k, v in d.items()}
        assert assinatura == depois, "REGRESSAO: a carga util mudou — abortado sem gravar"

        fp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> corrigido ({len(alvos)} registros); spec/sql/raw verificados intactos")

    if not args.aplicar:
        print("\n(dry-run — rode com --aplicar para gravar)")


if __name__ == "__main__":
    main()
