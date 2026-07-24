"""FASE 0 DE DADOS — crivo de aptidão da base, com go/no-go, ANTES de construir qualquer coisa.

Existe porque no RodoQuery os problemas mais caros (métricas ambíguas entre si, itens de gold
degenerados, ausência de anotação humana) só apareceram nas Fases 8 e 9 — depois de tudo pronto.
Eram problemas DA BASE E DO CATÁLOGO, não do agente. Este script é a porta de entrada que faltava.

Os 6 checks (ver a memória `validacao-dados-inicio-projeto`):
  1. Licença e PII declaradas
  2. Existe benchmark humano de perguntas para esta base?
  3. O catálogo tem métricas ambíguas ENTRE SI? (mesma grandeza em unidades diferentes)
  4. Filtros embutidos em métrica conflitam com filtros naturais das perguntas?
  5. Riqueza dimensional (tempo + categóricas + entidades)
  6. Um resultado varia com os dados? (se é constante, não protege contra falso positivo)

Uso: python fase0_dados.py <arquivo.csv> [--sep ';'] [--encoding latin1]
Saída: reports/fase0_dados/<nome>.json + veredito legível no terminal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parent
MIN_ENTIDADES = 2          # ao menos 2 dimensões de entidade para o join valer alguma coisa
MIN_CARD_ENTIDADE = 5      # entidade com <5 valores não exercita fan-out
MAX_CARD_CATEGORICA = 50   # acima disso é identificador, não categoria


def perfilar(csv: str, sep: str, encoding: str) -> dict:
    con = duckdb.connect()
    rel = (f"read_csv('{csv}', delim='{sep}', header=true, encoding='{encoding}', "
           f"sample_size=-1, ignore_errors=true)")
    colunas = con.execute(f"describe select * from {rel}").fetchall()
    n = con.execute(f"select count(*) from {rel}").fetchone()[0]
    perfil = []
    for nome, tipo, *_ in colunas:
        q = con.execute(
            f'select count(distinct "{nome}"), count(*) filter (where "{nome}" is null) from {rel}'
        ).fetchone()
        # Medida guardada como texto? (vírgula decimal brasileira: "213,00"). Precisa de cast no
        # staging — e não pode ser confundida com dimensão só por ser VARCHAR.
        texto_numerico = False
        if "VARCHAR" in tipo.upper():
            amostra = con.execute(
                f'select "{nome}" from {rel} where "{nome}" is not null limit 200').fetchall()
            vals = [str(v[0]).strip() for v in amostra]
            if vals:
                conv = sum(1 for v in vals if v.replace(".", "").replace(",", ".")
                           .lstrip("-").replace(".", "", 1).isdigit())
                texto_numerico = conv / len(vals) > 0.95
        perfil.append({"coluna": nome, "tipo": tipo, "distintos": q[0], "nulos": q[1],
                       "pct_nulo": round(q[1] / n * 100, 2) if n else None,
                       "texto_numerico": texto_numerico})
    con.close()
    return {"n_linhas": n, "colunas": perfil}


def classificar(perfil: dict) -> dict:
    """Separa colunas em medida / tempo / entidade / categórica — o esqueleto do semantic layer.

    Duas armadilhas que a 1ª versão deste script caiu, na base real da ANTT:
      - `categoria_eixo` é BIGINT mas tem 19 valores em 1,5 M de linhas: é CATEGÓRICA, não medida.
        Tipo numérico não é sinal de medida; **cardinalidade** é.
      - `volume_total` é VARCHAR (vírgula decimal brasileira, "213,00") mas É a medida. Medida
        guardada como texto é um problema de qualidade a resolver no staging, não um motivo para
        classificá-la como dimensão.
    """
    medidas, tempos, entidades, categoricas, suspeitas = [], [], [], [], []
    n = max(perfil["n_linhas"], 1)
    for c in perfil["colunas"]:
        nome, tipo, d = c["coluna"], c["tipo"].upper(), c["distintos"]
        numerico = any(t in tipo for t in ("BIGINT", "DOUBLE", "DECIMAL", "INTEGER", "FLOAT"))
        temporal = any(t in tipo for t in ("DATE", "TIMESTAMP"))
        # medida = valor contínuo: numérico (ou texto numérico) COM cardinalidade alta
        if (numerico or c.get("texto_numerico")) and d > MAX_CARD_CATEGORICA:
            medidas.append(nome)
        elif temporal:
            tempos.append(nome)
        elif d > MAX_CARD_CATEGORICA:
            (entidades if d < n * 0.5 else suspeitas).append(nome)
        elif d > 1:
            categoricas.append(nome)
        else:
            suspeitas.append(nome)
    return {"medidas": medidas, "tempo": tempos, "entidades": entidades,
            "categoricas": categoricas, "suspeitas_de_id_ou_constante": suspeitas}


def checar(perfil: dict, papeis: dict, meta: dict) -> list[dict]:
    ok = []
    ok.append({"check": "1_licenca_e_pii",
               "passou": bool(meta.get("licenca")) and meta.get("tem_pii") is False,
               "detalhe": f"licenca={meta.get('licenca')!r}, tem_pii={meta.get('tem_pii')}"})
    ok.append({"check": "2_benchmark_humano_existente",
               "passou": bool(meta.get("benchmark_humano")),
               "detalhe": meta.get("benchmark_humano")
               or "NAO existe -> golden set sera de maquina; declarar kappa humano como backlog",
               "bloqueante": False})
    # 3 e 4 dependem do catálogo, que ainda não existe: viram AVISOS de desenho
    ok.append({"check": "3_metricas_ambiguas_entre_si",
               "passou": None,
               "detalhe": ("a decidir no desenho do catalogo: NUNCA expor a mesma grandeza em duas "
                           "unidades (foi o gargalo do RodoQuery). Uma metrica por conceito."),
               "bloqueante": False})
    ok.append({"check": "4_filtro_embutido_x_filtro_da_pergunta",
               "passou": None,
               "detalhe": ("a decidir no desenho: contagem filtrada deve ser `where`, nao metrica "
                           "propria — senao gera itens degenerados (gold constante)."),
               "bloqueante": False})
    rico = (len(papeis["medidas"]) >= 1 and len(papeis["tempo"]) >= 1
            and len(papeis["entidades"]) + len(papeis["categoricas"]) >= 3)
    ok.append({"check": "5_riqueza_dimensional", "passou": rico,
               "detalhe": (f"medidas={papeis['medidas']} tempo={papeis['tempo']} "
                           f"entidades={papeis['entidades']} categoricas={papeis['categoricas']}")})
    ok.append({"check": "6_resultado_varia_com_os_dados", "passou": perfil["n_linhas"] > 1000,
               "detalhe": f"{perfil['n_linhas']} linhas; agregados por dimensao devem variar. "
                          f"Confirmar por item na geracao do gold (regra anti-degenerado)."})
    # 7: dívida de staging que a base real expôs — medida como texto, categórica como número.
    txt = [c["coluna"] for c in perfil["colunas"] if c.get("texto_numerico")]
    num_cat = [c["coluna"] for c in perfil["colunas"]
               if any(t in c["tipo"].upper() for t in ("BIGINT", "INTEGER"))
               and c["distintos"] <= MAX_CARD_CATEGORICA]
    ok.append({"check": "7_divida_de_staging", "passou": not (txt or num_cat),
               "bloqueante": False,
               "detalhe": (f"medida(s) guardada(s) como TEXTO (precisa cast): {txt or 'nenhuma'}; "
                           f"coluna(s) numerica(s) que sao CATEGORICAS: {num_cat or 'nenhuma'}")})
    return ok


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    csv = sys.argv[1]
    sep = sys.argv[sys.argv.index("--sep") + 1] if "--sep" in sys.argv else ";"
    enc = sys.argv[sys.argv.index("--encoding") + 1] if "--encoding" in sys.argv else "utf-8"
    meta_p = REPO / "fase0_meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}

    print(f"perfilando {csv} (sep={sep!r}, encoding={enc})...", flush=True)
    perfil = perfilar(csv, sep, enc)
    papeis = classificar(perfil)
    checks = checar(perfil, papeis, meta)

    bloqueantes = [c for c in checks if c["passou"] is False and c.get("bloqueante", True)]
    veredito = "NO-GO" if bloqueantes else "GO"

    rel = {"arquivo": csv, "meta_declarada": meta, "perfil": perfil, "papeis": papeis,
           "checks": checks, "veredito": veredito,
           "bloqueantes": [c["check"] for c in bloqueantes]}
    dest = REPO / "reports" / "fase0_dados" / f"{Path(csv).stem}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nlinhas: {perfil['n_linhas']:,}")
    for c in perfil["colunas"]:
        print(f"  {c['coluna']:22s} {c['tipo']:12s} distintos={c['distintos']:>8,} "
              f"nulos={c['pct_nulo']}%")
    print("\npapeis inferidos:")
    for k, v in papeis.items():
        print(f"  {k:28s} {v}")
    print("\nchecks:")
    for c in checks:
        s = {True: "OK  ", False: "FALHA", None: "AVISO"}[c["passou"]]
        print(f"  [{s}] {c['check']}: {c['detalhe'][:96]}")
    print(f"\nVEREDITO: {veredito}")
    print(f"-> {dest}")
    return 0 if veredito == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
