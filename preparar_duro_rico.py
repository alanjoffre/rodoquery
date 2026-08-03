"""Fase 21 — re-sela o conjunto duro sob o catálogo ENRIQUECIDO.

**Trocar o catálogo muda o gabarito, e isso não é trapaça — é a definição de "respondível".**
Uma pergunta é abstenção porque o catálogo não tem como respondê-la; se o catálogo passa a ter,
ela vira respondível e o gold dela **tem de ser gerado**. Fingir que o conjunto antigo ainda se
aplica é que seria errado.

Das 12 abstenções near-miss da Fase 20, exatamente **4** viram respondíveis:

    "Qual a proporção de cobrança manual?"          -> manual_share
    "Que percentual do tráfego usa OCR/PLACA?"      -> ocr_share
    "Qual a participação de motos no tráfego?"      -> motorcycle_share
    "Qual a proporção de veículos de passeio?"      -> passenger_share

As outras 8 **continuam abstenção**, e é isso que torna o experimento informativo em vez de
tautológico — se todas virassem respondíveis, eu teria só movido a régua:

    percentual por eixo / por sentido       -> partição NÃO completada (regra declarada)
    razão comercial ÷ passeio               -> denominador arbitrário, não é share sobre o total
    "cobrança não automatizada"             -> Manual+OCR juntos não é uma métrica
    participação de cada concessionária     -> share por entidade não existe
    percentual de PRAÇAS com automática     -> grão de entidade, não de tráfego
    comercial ÷ total de motos              -> denominador arbitrário

Guardas idênticas às da Fase 20 (G0 anti-degenerado, G4 ranking, G5 razão viva).
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import settings
from rodoquery.gold import FUNDACAO_ANTT, Spec, compilar_spec, executar_gold
from rodoquery.golden import ItemGolden, carregar, salvar
from rodoquery.proveniencia import carimbar

REPO = Path(__file__).resolve().parent
G = REPO / "golden"
D = REPO / "reports" / "fase21"
D.mkdir(parents=True, exist_ok=True)
DBS = {f"p{v}": settings.antt_suite_dir / f"antt_p{v}.duckdb" for v in range(3)}
RAZOES = ("_rate", "_share")

# id -> métrica que o catálogo enriquecido passa a oferecer. Fora daqui, segue abstenção.
VIRAM_RESPONDIVEIS = {
    "abstencao_duro_01": "manual_share",       # proporção de cobrança manual
    "abstencao_duro_02": "ocr_share",          # percentual que usa OCR/PLACA
    "abstencao_duro_03": "motorcycle_share",   # participação de motos
    "abstencao_duro_04": "passenger_share",    # proporção de veículos de passeio
}


def _sem_limit(s: Spec) -> Spec:
    return Spec(metrics=s.metrics, group_by=s.group_by, where=s.where,
                order_by=s.order_by, limit=None, ordenado=s.ordenado)


def main() -> None:
    base = carregar(G / "duro_antt.jsonl")
    itens = []
    for it in base:
        nova = VIRAM_RESPONDIVEIS.get(it.id)
        if nova is None:
            itens.append(it)
            continue
        # vira respondível: estrato novo + spec com a métrica que passou a existir
        itens.append(ItemGolden(id=it.id.replace("abstencao_", "particao_"),
                                pergunta_nl=it.pergunta_nl, estrato="metrica_derivada",
                                spec=Spec(metrics=[nova]), revisado_humano=False))
    print(f"itens: {len(itens)}  (viraram respondiveis: {len(VIRAM_RESPONDIVEIS)})", flush=True)

    validos, respostas, descartados = [], [], []
    for it in itens:
        if it.eh_abstencao:
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
            descartados.append({"id": it.id, "motivo": "resultado vazio"})
            continue
        if len(set(hashes.values())) == 1:
            descartados.append({"id": it.id, "motivo": "gold constante entre variantes (G0)"})
            continue
        idx = [i for i, m in enumerate(it.spec.metrics) if m.endswith(RAZOES)]
        if idx and len(linhas0) > 1:
            desloc = len(linhas0[0]) - len(it.spec.metrics)
            if any(len({round(float(r[desloc + i]), 9) for r in linhas0}) == 1 for i in idx):
                descartados.append({"id": it.id, "motivo": "razao constante (G5)"})
                continue
        if it.spec.ordenado and it.spec.limit:
            vals = [r[-1] for r in executar_gold(
                compilar_spec(_sem_limit(it.spec), fundacao=FUNDACAO_ANTT), DBS["p0"])]
            n = it.spec.limit
            if len(vals) < n or (len(vals) > n and vals[n - 1] == vals[n]):
                descartados.append({"id": it.id, "motivo": "G4 ranking"})
                continue
        validos.append(it)
        respostas.append({"id": it.id, "estrato": it.estrato, "sql_metricflow": sql,
                          "n_variantes": len(DBS), "hashes_por_variante": hashes})

    dest = G / "duro_rico_antt.jsonl"
    salvar(validos, dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    (G / "duro_rico_antt.sha256").write_text(sha + "\n", encoding="utf-8")
    (D / "gold_duro_rico.json").write_text(json.dumps(carimbar({
        "tipo": "gold_conjunto_duro_catalogo_ENRIQUECIDO",
        "derivado_de": "duro_antt.jsonl (Fase 20)",
        "viraram_respondiveis": VIRAM_RESPONDIVEIS,
        "n_validos": len(validos), "n_descartados": len(descartados),
        "descartados": descartados, "sha256": sha, "respostas": respostas,
    }), ensure_ascii=False, indent=2), encoding="utf-8")

    n_abs = sum(1 for i in validos if i.eh_abstencao)
    print(f"\nvalidos: {len(validos)}  (abstencoes: {n_abs}, respondiveis: {len(validos)-n_abs})")
    for d in descartados:
        print(f"  - {d['id']}: {d['motivo']}")
    print("\npor estrato:")
    for e, n in sorted(Counter(i.estrato for i in validos).items()):
        print(f"  {e:18s} {n}")
    print(f"\nselado: {sha[:16]}...  -> {dest}")


if __name__ == "__main__":
    main()
