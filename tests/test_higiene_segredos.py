"""Nenhum segredo pode estar rastreado pelo git. Trava, não promessa.

O README afirma "sem segredos — `.env` no `.gitignore` desde sempre; a chave de API nunca foi
versionada". Era verdade, e mesmo assim quase deixou de ser: o `.gitignore` cobria o nome **exato**
`.env`, e o `nano` cria vizinhos que carregam o mesmo segredo (`.env.save`, backup de emergência).
Um `git add -A` capturou um desses, e o **commit foi criado com ele dentro** — `git add`, `git
status` e `git commit` rodaram no mesmo comando, então não houve revisão entre o staging e o
commit. Só foi notado na saída, **depois** do commit e **antes** do push, e removido com amend.
Nada foi publicado. Mas quem segurou foi a sorte da ordem das operações e uma leitura posterior,
não uma trava — e isso é exatamente o que não escala.

Este arquivo troca a atenção por uma trava, e é a mesma lição da Fase 22 aplicada a segredo:
*a existência da regra não é evidência do comportamento da regra.*

Roda no CI (só lê o índice do git — sem GPU, banco ou rede).
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Famílias de arquivo que carregam credencial. `.env.example` é a exceção declarada: ele existe
# para ser público e só contém placeholders comentados (há teste abaixo garantindo isso).
PADROES_PROIBIDOS = (
    re.compile(r"^\.env$"),
    re.compile(r"^\.env\.(?!example$).+"),
    re.compile(r".*\.(pem|key|p12|pfx)$"),
    re.compile(r"^.*id_(rsa|ed25519)$"),
    re.compile(r"^\.aws/credentials$"),
)

# Formatos de credencial que não podem aparecer no CONTEÚDO de arquivo rastreado.
# São procurados como prefixo + corpo longo, para não casar com a própria documentação
# (o README e o .env.example citam `sk-ant-...`, com reticências, e devem continuar podendo).
SEGREDOS_NO_CONTEUDO = (
    ("chave da Anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("chave da OpenAI", re.compile(r"sk-[A-Za-z0-9]{40,}")),
    ("token do GitHub", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("chave da AWS", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("chave privada", re.compile(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----")),
)


def _rastreados() -> list[str]:
    if shutil.which("git") is None:
        # Falha ABERTA, de propósito: sem git esta trava não consegue fazer o seu trabalho, e
        # pular em silêncio deixaria o build verde sem ter conferido nada.
        pytest.fail("git não encontrado — esta trava não pode ser verificada, e pular seria pior")
    saida = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True,
                           text=True, check=True).stdout
    return [x for x in saida.split("\0") if x]


def test_ha_arquivos_rastreados_para_conferir():
    """Guarda contra o pior modo de falha: passar por não achar nada que conferir."""
    assert len(_rastreados()) > 50


def test_nenhum_arquivo_de_segredo_esta_rastreado():
    rastreados = _rastreados()
    ofensores = [f for f in rastreados
                 for p in PADROES_PROIBIDOS if p.match(Path(f).name) or p.match(f)]
    assert not ofensores, (
        f"arquivo de credencial rastreado pelo git: {ofensores}. "
        "Remova do índice (`git rm --cached`), acrescente ao .gitignore e, se já houve push, "
        "considere a chave COMPROMETIDA e rotacione-a.")


def test_nenhuma_credencial_no_conteudo_dos_arquivos_rastreados():
    achados = []
    for rel in _rastreados():
        caminho = REPO / rel
        if not caminho.is_file():
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binário: não é onde uma chave em texto se esconde
        for nome, padrao in SEGREDOS_NO_CONTEUDO:
            if padrao.search(texto):
                achados.append(f"{rel}: possível {nome}")
    assert not achados, f"credencial em arquivo rastreado: {achados}"


def test_o_env_example_e_so_placeholder():
    """A exceção precisa continuar sendo exceção: exemplo com chave real seria o pior caso."""
    exemplo = REPO / ".env.example"
    assert exemplo.exists(), ".env.example sumiu — o README manda o usuário copiá-lo"
    texto = exemplo.read_text(encoding="utf-8")
    for linha in texto.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#"):
            continue
        # Toda linha não-comentada tem de ser uma atribuição VAZIA (ex.: `RODOQUERY_X=`).
        assert "=" in limpa, f"linha inesperada no exemplo: {limpa!r}"
        assert not limpa.split("=", 1)[1].strip(), (
            f".env.example traz VALOR em {limpa.split('=', 1)[0]!r} — ele deve ser só placeholder")
