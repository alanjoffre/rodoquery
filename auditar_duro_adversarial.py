"""Fase 21 (#4) — auditoria ADVERSARIAL do conjunto duro.

## Por que auditoria adversarial e não κ de 2º anotador

O conjunto duro foi autorado por mim, que também escrevi as guardas. Um κ de segundo anotador
de máquina teria um problema: nas formas duras (filtro composto, métrica mista) um 7B erra por
incompetência, e a discordância mediria a competência do anotador, não a qualidade do rótulo.
Usar o Opus 5 como anotador B seria pior — é o próprio SUT.

A Fase 15 já resolveu isso com um método mais forte: o crítico **vê a spec do autor** e só
procura ERRO. Não é re-anotação cega; é tentativa de refutação. Lá achou **7 defeitos em 60**
que três rodadas de κ de máquina não tinham achado.

## O que conta como defeito

O crítico recebe a pergunta, a spec e o catálogo, e responde se a spec responde a pergunta.
Categorias que a história do projeto mostrou serem reais:

    ambiguidade      — a pergunta admite duas leituras legítimas
    metrica_errada   — existe métrica melhor no catálogo
    filtro_espurio   — filtra o que a pergunta não pede (ou deixa de filtrar)
    grao_errado      — group_by a mais ou a menos
    ranking          — ordem/limite não batem com o enunciado
    abstencao_errada — marcada como fora-de-escopo, mas o catálogo responde

Uso: python auditar_duro_adversarial.py --confirmar [--teto-usd 0.40]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from rodoquery.golden import carregar
from rodoquery.provedor import ProvedorAnthropic
from rodoquery.proveniencia import carimbar
from rodoquery.sistema_antt_rico import CATALOGO_ANTT_RICO

REPO = Path(__file__).resolve().parent
D = REPO / "reports" / "fase21"
D.mkdir(parents=True, exist_ok=True)

# A parte VARIÁVEL fica no fim, depois do marcador `\nPergunta: ` — o mesmo que o
# `ProvedorAnthropic._partir` usa para cortar o prefixo cacheável. Na 1ª versão eu escrevi
# `PERGUNTA:` em maiúscula: o marcador não casou, nada cacheou e a auditoria custou 3x mais
# (US$ 0,37 queimados num abort). Marcador de cache é contrato, não formatação.
PROMPT_CRITICO = """Você é um revisor CÉTICO de um conjunto de avaliação de Text-to-SQL.

Sua tarefa NÃO é responder a pergunta. É procurar ERRO na spec de referência. Assuma que ela
pode estar errada e tente demonstrar isso. Se, depois de tentar, ela estiver correta, diga.

{catalogo}

Responda com UM objeto JSON e nada mais:
{{"defeito": <true|false>,
  "categoria": "ambiguidade"|"metrica_errada"|"filtro_espurio"|"grao_errado"
               |"ranking"|"abstencao_errada"|null,
  "justificativa": "<uma frase; se defeito=false, diga por que a spec responde a pergunta>"}}

Regras:
- `metrics: []` significa ABSTENÇÃO (a pergunta não é respondível com este catálogo).
- Marque `abstencao_errada` se a spec abstém mas o catálogo TEM como responder.
- Não invente métrica: só existe o que está no catálogo acima.
- Ser rigoroso é o trabalho; apontar defeito onde não há também é erro.

Pergunta: {pergunta}
SPEC DE REFERÊNCIA: {spec}
JSON:"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirmar", action="store_true")
    ap.add_argument("--teto-usd", type=float, default=0.40)
    ap.add_argument("--modelo", default="claude-opus-5")
    args = ap.parse_args()
    if not args.confirmar:
        print("Recusado: '--confirmar' e obrigatorio.", file=sys.stderr)
        raise SystemExit(2)

    itens = carregar(REPO / "golden" / "duro_rico_antt.jsonl")
    print(f"[AUDITORIA] {len(itens)} itens, critico={args.modelo}", flush=True)

    fp = D / "auditoria_adversarial.json"
    # RETOMÁVEL. A 1ª execução abortou no teto e perdeu 46 vereditos já pagos — abort que
    # descarta trabalho pago é pior que não ter teto. Agora cada veredito é salvo na hora.
    parciais = D / "_auditoria_parcial.json"
    vereditos = json.loads(parciais.read_text(encoding="utf-8")) if parciais.exists() else []
    feitos = {v["id"] for v in vereditos}
    if feitos:
        print(f"  retomando: {len(feitos)} vereditos ja em disco", flush=True)

    prov = ProvedorAnthropic(modelo_padrao=args.modelo)
    for i, it in enumerate(itens, 1):
        if it.id in feitos:
            continue
        if prov.custo_usd > args.teto_usd:
            parciais.write_text(json.dumps(vereditos, ensure_ascii=False), encoding="utf-8")
            print(f"\nABORTADO em {i}/{len(itens)} — {len(vereditos)} vereditos SALVOS; "
                  "rode de novo para continuar.", file=sys.stderr)
            raise SystemExit(2)
        spec = {"metrics": it.spec.metrics, "group_by": it.spec.group_by,
                "where": it.spec.where, "order_by": it.spec.order_by,
                "limit": it.spec.limit, "ordenado": it.spec.ordenado}
        texto, _ = prov(PROMPT_CRITICO.format(catalogo=CATALOGO_ANTT_RICO,
                                              pergunta=it.pergunta_nl,
                                              spec=json.dumps(spec, ensure_ascii=False)),
                        args.modelo, 0.0)
        try:
            ini, fim = texto.find("{"), texto.rfind("}")
            v = json.loads(texto[ini:fim + 1])
        except Exception:                                             # noqa: BLE001
            v = {"defeito": None, "categoria": "falha_parse", "justificativa": texto[:200]}
        v.update({"id": it.id, "pergunta": it.pergunta_nl, "estrato": it.estrato, "spec": spec})
        vereditos.append(v)
        parciais.write_text(json.dumps(vereditos, ensure_ascii=False), encoding="utf-8")
        if i % 10 == 0 or i == len(itens):
            print(f"    {i}/{len(itens)}  ${prov.custo_usd:.4f}", flush=True)
    parciais.unlink(missing_ok=True)

    defeitos = [v for v in vereditos if v.get("defeito") is True]
    cat = Counter(v.get("categoria") for v in defeitos)
    fp.write_text(json.dumps(carimbar({
        "tipo": "auditoria_adversarial_conjunto_duro",
        "metodo": "critico VE a spec e so procura erro (mais forte que re-anotacao cega)",
        "critico": args.modelo, "n": len(itens),
        "n_defeitos": len(defeitos), "taxa_correta": round(1 - len(defeitos) / len(itens), 4),
        "categorias": dict(cat), "custo_usd": round(prov.custo_usd, 4),
        "NAO_CORRIGIDO": ("o conjunto esta SELADO e a auditoria veio depois de medir; "
                          "defeitos ficam DECLARADOS para a proxima revisao (disciplina F8)"),
        "defeitos": defeitos, "vereditos": vereditos,
    }), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n== AUDITORIA ADVERSARIAL ==\n  corretas: {len(itens) - len(defeitos)}/{len(itens)} "
          f"({(1 - len(defeitos) / len(itens)) * 100:.1f}%)")
    print(f"  categorias: {dict(cat)}")
    for v in defeitos:
        print(f"\n  [{v['id']}] {v.get('categoria')}")
        print(f"    {v['pergunta']}")
        print(f"    spec: {v['spec']['metrics']}")
        print(f"    -> {v.get('justificativa', '')[:160]}")
    print(f"\n  custo: ${prov.custo_usd:.4f}\n-> {fp}")


if __name__ == "__main__":
    main()
