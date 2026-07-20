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
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from rodoquery.canonizacao import hash_resultado
from rodoquery.config import REPO_ROOT, settings
from rodoquery.estat import cohen_kappa
from rodoquery.gold import Spec, compilar_spec, executar_gold

# Os 7 mecanismos onde o SQL cru erra e o Semantic Layer acerta (itens RESPONDÍVEIS).
ESTRATOS_RESPONDIVEIS = (
    "metrica_filtrada", "coalesce_nulo", "join_grao", "metrica_derivada",
    "grao_temporal", "valor_categorico", "controle_trivial",
)
# 8º estrato = eixo DIFERENTE: a pergunta NÃO é respondível com o catálogo → o certo é ABSTER.
# É onde o vocabulário fechado do Semantic Layer vira vantagem (sabe dizer "não sei") e onde o SQL
# cru tende a alucinar. NÃO entra no EX; é medido como acurácia de abstenção.
ESTRATO_ABSTENCAO = "abstencao"
ESTRATOS = (*ESTRATOS_RESPONDIVEIS, ESTRATO_ABSTENCAO)

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
        # Item de abstenção = spec vazia (sem métrica): a resposta certa é NÃO responder.
        if self.estrato == ESTRATO_ABSTENCAO and self.spec.metrics:
            raise ValueError("item de abstenção deve ter spec.metrics vazio (é fora-de-escopo)")

    @property
    def eh_abstencao(self) -> bool:
        return self.estrato == ESTRATO_ABSTENCAO


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


def dividir_dev_test(
    itens: list[ItemGolden], frac_dev: float = 0.30, seed: int = 42,
) -> tuple[list[ItemGolden], list[ItemGolden]]:
    """Split DEV/TEST **estratificado e determinístico**.

    DEV (visível, ~`frac_dev`) é onde se desenvolve/inspeciona; TEST (selado, o resto) é o holdout
    cego — o sistema final é avaliado nele UMA vez. Estratifica por estrato para os dois lados
    conterem todos os mecanismos. `random.Random(seed)` → mesmo split toda vez (reprodutível)."""
    por_estrato: dict[str, list[ItemGolden]] = {}
    for it in itens:
        por_estrato.setdefault(it.estrato, []).append(it)
    rng = random.Random(seed)
    dev: list[ItemGolden] = []
    test: list[ItemGolden] = []
    for estrato in sorted(por_estrato):
        grupo = sorted(por_estrato[estrato], key=lambda x: x.id)  # ordem estável antes do shuffle
        rng.shuffle(grupo)
        k = max(1, round(len(grupo) * frac_dev))                 # ≥1 no DEV por estrato
        dev.extend(grupo[:k])
        test.extend(grupo[k:])
    dev.sort(key=lambda x: x.id)
    test.sort(key=lambda x: x.id)
    return dev, test


def resumo_estratos(itens: list[ItemGolden]) -> dict[str, int]:
    """Contagem por estrato — para checar balanceamento (alvo ≥25 por estrato p/ IC útil)."""
    out = dict.fromkeys(ESTRATOS, 0)
    for it in itens:
        out[it.estrato] += 1
    return out


def canonizar_spec(spec: Spec) -> str:
    """Forma canônica da spec (métricas/group-by ordenados) — para comparar dois mapeamentos.
    Ignora `ordenado`/`limit` (metadados de forma, não de conteúdo semântico)."""
    m = ",".join(sorted(spec.metrics))
    g = ",".join(sorted(spec.group_by))
    w = (spec.where or "").strip()
    return f"metrics=[{m}] group_by=[{g}] where={w}"


def validar_item(item: ItemGolden, duckdb_path: Path | None = None) -> tuple[bool, str]:
    """Um item é válido se a spec COMPILA no MetricFlow e o gold é NÃO-VAZIO (pergunta respondível).
    Roda na autoria para pegar spec inválida antes de selar o golden set.

    Item de abstenção é válido por construção (spec vazia): não há o que compilar — a resposta
    certa é NÃO responder. Aqui só checamos que ele é mesmo fora-de-escopo (metrics vazio)."""
    if item.eh_abstencao:
        return (True, "ok (abstenção)") if not item.spec.metrics else \
            (False, "abstenção não pode ter métrica")
    db = duckdb_path or settings.toll_duckdb
    try:
        sql = compilar_spec(item.spec)
    except Exception as e:
        return False, f"spec não compila: {str(e)[:120]}"
    linhas = executar_gold(sql, db)
    if not linhas:
        return False, "gold vazio (pergunta não-respondível nestes dados)"
    return True, "ok"


def concordancia_mapeamento(anotador_a: list[ItemGolden], anotador_b: list[ItemGolden]) -> dict:
    """κ do 2º anotador: dois humanos mapeiam as MESMAS perguntas → spec, independentes.

    Reporta concordância bruta (mesma spec canônica), κ de Cohen sobre a métrica primária e a
    concordância por campo. O especialista alertou: com marginais enviesadas (quase tudo cai em
    1-2 métricas), o κ deflaciona — por isso a concordância bruta também é reportada.
    """
    a = {it.id: it for it in anotador_a}
    b = {it.id: it for it in anotador_b}
    ids = sorted(set(a) & set(b))
    if not ids:
        raise SystemExit("nenhum id em comum entre os dois anotadores")

    spec_igual = [canonizar_spec(a[i].spec) == canonizar_spec(b[i].spec) for i in ids]
    metrica_a = [",".join(sorted(a[i].spec.metrics)) for i in ids]
    metrica_b = [",".join(sorted(b[i].spec.metrics)) for i in ids]
    gb_igual = [sorted(a[i].spec.group_by) == sorted(b[i].spec.group_by) for i in ids]
    where_igual = [(a[i].spec.where or "") == (b[i].spec.where or "") for i in ids]

    n = len(ids)
    metrica_igual = sum(x == y for x, y in zip(metrica_a, metrica_b, strict=True))
    return {
        "n_pares": n,
        "concordancia_spec_canonica": round(sum(spec_igual) / n, 4),
        "cohen_kappa_metrica": cohen_kappa(metrica_a, metrica_b),
        "concordancia_metrica": round(metrica_igual / n, 4),
        "concordancia_group_by": round(sum(gb_igual) / n, 4),
        "concordancia_where": round(sum(where_igual) / n, 4),
        "limiar_pre_registrado": {"cohen_kappa_metrica": 0.8, "concordancia_spec_canonica": 0.8},
        "discordantes": [i for i, ok in zip(ids, spec_igual, strict=True) if not ok],
    }


GOLD_ABSTER = "__ABSTER__"  # sentinela: a resposta certa é NÃO responder (item fora-de-escopo)


def gerar_respostas(itens: list[ItemGolden], dbs: dict[str, Path]) -> list[dict]:
    """Para cada item: compila a spec (1×) e faz o hash do resultado em CADA variante do test-suite.
    O gold é o conjunto de hashes por variante — o predito precisa bater em TODAS (Test-Suite EX,
    mata falso positivo de coincidência num único banco). `dbs` = {nome_variante: caminho}.

    Item de abstenção não tem gold executável: seu gold é o sentinela GOLD_ABSTER."""
    respostas = []
    for it in itens:
        if it.eh_abstencao:
            respostas.append({
                "id": it.id, "estrato": it.estrato, "sql_metricflow": None,
                "n_variantes": 0, "hashes_por_variante": {}, "gold": GOLD_ABSTER,
            })
            continue
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
