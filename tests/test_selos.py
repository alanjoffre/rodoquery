"""Os selos anti-vazamento têm de CONFERIR — e isso precisa ser uma trava, não um ritual.

Todo conjunto de medição deste projeto é selado com sha256 **antes** de qualquer sistema rodar:
é o que sustenta a afirmação "o número não foi obtido depois de olhar o teste". Só que, até aqui,
nada verificava os selos automaticamente — eles eram conferidos à mão, quando alguém lembrava.

Isso é a lição da Fase 22 outra vez, na sua forma mais pura: *a existência do artefato não é
evidência do comportamento do artefato*. Um selo que ninguém checa é decoração; se o `.jsonl`
mudasse por um merge desastrado ou por um script rodado duas vezes, o repositório seguiria
anunciando integridade e o CI seguiria verde.

Este teste roda no CI (só lê arquivos — sem GPU, sem banco, sem LLM).
"""
import hashlib
from pathlib import Path

import pytest

GOLDEN = Path(__file__).resolve().parents[1] / "golden"
SELOS = sorted(GOLDEN.glob("*.sha256"))


def test_ha_selos_para_conferir():
    """Guarda contra o pior modo de falha deste arquivo: passar por não achar nada.

    Se o glob voltasse vazio — diretório renomeado, teste rodado de outro cwd — os testes
    parametrizados abaixo simplesmente não existiriam, e a suíte ficaria verde sem ter conferido
    coisa alguma. Verde com teste faltando é pior que vermelho, porque vermelho ao menos grita."""
    assert len(SELOS) >= 9, f"esperava >= 9 conjuntos selados, achei {len(SELOS)}"


@pytest.mark.parametrize("selo", SELOS, ids=lambda p: p.stem)
def test_selo_confere(selo: Path):
    alvo = selo.with_suffix(".jsonl")
    assert alvo.exists(), f"{selo.name} não tem o .jsonl correspondente"
    atual = hashlib.sha256(alvo.read_bytes()).hexdigest()
    esperado = selo.read_text(encoding="utf-8").strip()
    assert atual == esperado, (
        f"{alvo.name} MUDOU depois de selado: {atual[:12]} != {esperado[:12]}. "
        "Se a mudança for legítima (defeito de rótulo removido), o conjunto tem de ser "
        "re-selado NO MESMO commit que a explica — nunca em silêncio.")
