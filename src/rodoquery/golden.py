"""Golden set governado — o núcleo da Fase 2 (e o risco existencial do projeto).

**Regra anti-circularidade** (auditoria staff): o *gold* de cada item é o RESULTADO de uma spec
compilada pelo MetricFlow — nunca SQL escrito à mão. O humano escreve só a **pergunta em NL** e o
**mapeamento** pergunta→spec; um 2º anotador refaz o mapeamento independente (κ de Cohen ≥ 0,8).

Estratos (pré-registrados) = os MECANISMOS pelos quais o SQL cru erra e o Semantic Layer acerta:
  - `metrica_filtrada`  — a métrica embute filtro (revenue só conta COMPLETED e valor > 0)
  - `coalesce_nulo`     — dias/grupos sem atividade viram 0, não somem (join_to_timespine)
  - `join_grao`         — grão/fan-out de join (1:N) — o SQL cru duplica
  - `metrica_derivada`  — ratio/derivada (suspect_rate: denominador certo; revenue: /100 no fim)
  - `grao_temporal`     — dia/semana/mês (truncamento correto)
  - `valor_categorico`  — valor exato de dimensão (status/audit_flag)
  - `controle_trivial`  — count numa tabela só: AMBOS devem acertar (guarda contra scorer viciado)

Split DEV (visível) / TEST (selado): o `sha256` do TEST é commitado ANTES de rodar qualquer
sistema (pré-registro — não dá pra editar depois). O agente nunca vê a spec: só a pergunta + o
catálogo.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import REPO_ROOT
from rodoquery.gold import Spec, compilar_spec, executar_gold

ESTRATOS = (
    "metrica_filtrada", "coalesce_nulo", "join_grao", "metrica_derivada",
    "grao_temporal", "valor_categorico", "controle_trivial",
)

GOLDEN_DIR = REPO_ROOT / "golden"


@dataclass(frozen=True)
class ItemGolden:
    id: str
    pergunta_nl: str
    estrato: str
    spec: Spec
    revisado_humano: bool = False  # True só após revisão cega + κ do 2º anotador

    def __post_init__(self) -> None:
        if self.estrato not in ESTRATOS:
            raise ValueError(f"estrato inválido: {self.estrato}")


def _item_de_dict(d: dict) -> ItemGolden:
    return ItemGolden(
        id=d["id"], pergunta_nl=d["pergunta_nl"], estrato=d["estrato"],
        spec=Spec(**d["spec"]), revisado_humano=d.get("revisado_humano", False),
    )


def carregar(caminho: Path) -> list[ItemGolden]:
    """Lê um .jsonl de itens do golden set."""
    itens = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            itens.append(_item_de_dict(json.loads(linha)))
    return itens


def salvar(itens: list[ItemGolden], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as fh:
        for it in itens:
            fh.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def selar(caminho_test: Path) -> str:
    """sha256 do arquivo de TEST — commitado ANTES de rodar sistemas (pré-registro anti-vazamento).
    Se o TEST mudar depois, o hash muda e o diff denuncia."""
    return hashlib.sha256(caminho_test.read_bytes()).hexdigest()


def resumo_estratos(itens: list[ItemGolden]) -> dict[str, int]:
    """Contagem por estrato — para checar balanceamento (alvo ≥25 por estrato p/ IC útil)."""
    out = dict.fromkeys(ESTRATOS, 0)
    for it in itens:
        out[it.estrato] += 1
    return out


def gerar_respostas(itens: list[ItemGolden], dbs: dict[str, Path]) -> list[dict]:
    """Para cada item: compila a spec (1×) e faz o hash do resultado em CADA variante do test-suite.
    O gold é o conjunto de hashes por variante — o predito precisa bater em TODAS (Test-Suite EX,
    mata falso positivo de coincidência num único banco). `dbs` = {nome_variante: caminho}."""
    respostas = []
    for it in itens:
        sql = compilar_spec(it.spec)                      # data-independente → 1 compilação só
        hashes = {}
        for nome, db in dbs.items():
            linhas = executar_gold(sql, db)
            hashes[nome] = hash_resultado(linhas, ordenado=it.spec.ordenado)
        respostas.append({
            "id": it.id,
            "estrato": it.estrato,
            "sql_metricflow": sql,
            "n_variantes": len(hashes),
            "hashes_por_variante": hashes,
        })
    return respostas
