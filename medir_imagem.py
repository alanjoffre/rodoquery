"""Mede o tamanho da imagem Docker e o que cada extra instala — e grava como ARTEFATO.

## Por que existe

O README afirmava **624 MB** de imagem (Fase 16), e esse era o **único número do README sem
artefato versionado**: medido uma vez, à mão, sem registro de *como* (o `docker image ls` e o
`docker image inspect` contam coisas diferentes, e o documento da F16 não diz qual foi usado).

Ele também travava uma limpeza: o extra `llm` (`httpx`, `ollama`) não é importado por nada desde a
F22, mas o `Dockerfile` o instalava, e os 624 MB incluíam esses pacotes. Removê-lo sem medir de novo
tornaria o número falso. Este script fecha as duas coisas: mede **antes e depois** da remoção, no
mesmo daemon, contra a mesma imagem base, e o delta passa a ser atribuível ao extra — não a outras
mudanças de 30 dias de código.

Só biblioteca padrão, de propósito: roda no Python do **Windows**, onde está o Docker Desktop, e
não pode depender do venv do projeto (que vive no WSL).

## Uso

  python medir_imagem.py construir --contexto DIR --tag T --rotulo antes --saida a.json
  python medir_imagem.py fumaca    --tag T --saida f.json
  python medir_imagem.py consolidar --antes a.json --depois b.json --fumaca f.json \
                                    --git-sha SHA --saida reports/fase16/imagem_docker.json
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MB = 1_000_000  # megabyte DECIMAL — é a unidade que o Docker exibe; declarado no artefato


def _rodar(cmd: list[str], **kw) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       **kw)
    if r.returncode != 0:
        raise SystemExit(f"FALHOU: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r.stdout.strip()


def _linha_pip(dockerfile: Path) -> str:
    return next(ln.strip() for ln in dockerfile.read_text(encoding="utf-8").splitlines()
                if "pip install" in ln and '".[' in ln)


def construir(a) -> None:
    ctx = Path(a.contexto)
    # A base precisa estar no image store LOCAL para ter digest registrável: com o containerd
    # snapshotter, o BuildKit baixa a base para o cache dele e `docker image inspect` não a vê.
    # Puxar antes faz o build usar exatamente esta imagem, e o `consolidar` confere que as duas
    # medições saíram da MESMA base — senão o delta mediria a troca da base, não o extra.
    _rodar(["docker", "pull", "python:3.12-slim"])
    t0 = time.monotonic()
    _rodar(["docker", "build", "-t", a.tag, str(ctx)])
    dur = round(time.monotonic() - t0, 1)

    tamanho_inspect = int(_rodar(["docker", "image", "inspect", a.tag, "--format", "{{.Size}}"]))
    tamanho_ls = _rodar(["docker", "image", "ls", a.tag, "--format", "{{.Size}}"])
    base = json.loads(_rodar(["docker", "image", "inspect", "python:3.12-slim"]))[0]
    freeze = _rodar(["docker", "run", "--rm", "--entrypoint", "pip", a.tag, "freeze",
                     "--all"]).splitlines()

    saida = {
        "rotulo": a.rotulo,
        "tag": a.tag,
        "linha_pip_install_do_dockerfile": _linha_pip(ctx / "Dockerfile"),
        "tamanho_bytes_image_inspect": tamanho_inspect,
        "tamanho_mb_image_inspect": round(tamanho_inspect / MB, 1),
        "tamanho_docker_image_ls": tamanho_ls,
        "base": {"imagem": "python:3.12-slim", "id": base["Id"],
                 "repo_digests": base.get("RepoDigests", [])},
        "pacotes_instalados": sorted(freeze, key=str.lower),
        "duracao_build_s": dur,
    }
    Path(a.saida).write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8",
                             newline="\n")
    print(f"[{a.rotulo}] inspect={saida['tamanho_mb_image_inspect']} MB | image ls={tamanho_ls} "
          f"| {len(freeze)} pacotes | build {dur}s")


def fumaca(a) -> None:
    """Prova que a imagem SEM o extra ainda faz o serviço inteiro, não só que ela constrói.

    Três níveis, do mais raso ao mais fundo: o processo sobe e responde /saude; o MetricFlow
    compila uma spec real dentro do container; o SQL executa no DuckDB assado e devolve o total
    que já foi conferido contra SQL puro na Fase 11 (391.612.977) — nativo, Docker e K8s bateram
    nesse mesmo número. Um total diferente aqui seria regressão, não detalhe.
    """
    nome = "rodoquery-fumaca"
    subprocess.run(["docker", "rm", "-f", nome], capture_output=True)
    _rodar(["docker", "run", "-d", "--name", nome, "-p", "18077:8077", a.tag])
    res: dict = {"tag": a.tag}
    try:
        saude = None
        for _ in range(60):
            try:
                with urllib.request.urlopen("http://localhost:18077/saude", timeout=3) as r:
                    saude = json.loads(r.read())
                    break
            except Exception:
                time.sleep(2)
        res["saude"] = saude
        res["saude_ok"] = bool(saude and saude.get("status") == "ok")

        codigo = (
            "import duckdb, json\n"
            "from rodoquery.gold import FUNDACAO_ANTT, Spec, compilar_spec\n"
            "from rodoquery.config import settings\n"
            "sql = compilar_spec(Spec(metrics=['traffic_volume'], group_by=['plaza__sentido']),"
            " fundacao=FUNDACAO_ANTT)\n"
            "con = duckdb.connect(str(settings.antt_duckdb), read_only=True)\n"
            "linhas = con.execute(sql).fetchall()\n"
            "print(json.dumps({'linhas': [[str(x) for x in l] for l in linhas],"
            " 'total': sum(int(l[-1]) for l in linhas)}))\n"
        )
        out = _rodar(["docker", "exec", nome, "python", "-c", codigo])
        comp = json.loads(out.splitlines()[-1])
        res["compilacao_e_execucao"] = comp
        res["total_esperado_fase11"] = 391_612_977
        res["total_confere"] = comp["total"] == 391_612_977

        imports = _rodar(["docker", "exec", nome, "python", "-c",
                          "import importlib.util as u; print([m for m in ('httpx','ollama') "
                          "if u.find_spec(m)])"])
        res["modulos_llm_presentes_na_imagem"] = imports
    finally:
        subprocess.run(["docker", "rm", "-f", nome], capture_output=True)

    Path(a.saida).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8",
                             newline="\n")
    print(f"/saude ok={res['saude_ok']} | total={res['compilacao_e_execucao']['total']} "
          f"confere={res['total_confere']} | modulos llm: {res['modulos_llm_presentes_na_imagem']}")
    if not (res["saude_ok"] and res["total_confere"]):
        raise SystemExit("FUMACA REPROVOU")


def consolidar(a) -> None:
    antes = json.loads(Path(a.antes).read_text(encoding="utf-8"))
    depois = json.loads(Path(a.depois).read_text(encoding="utf-8"))
    fum = json.loads(Path(a.fumaca).read_text(encoding="utf-8"))

    def _nomes(p):
        return {x.split("==")[0].split(" @ ")[0].lower() for x in p["pacotes_instalados"]}

    saiu = sorted(_nomes(antes) - _nomes(depois))
    entrou = sorted(_nomes(depois) - _nomes(antes))
    mesma_base = antes["base"]["id"] == depois["base"]["id"]

    rel = {
        "fase": "16b_imagem_docker_medida",
        "motivo": ("os 624 MB da F16 eram o unico numero do README sem artefato, e travavam a "
                   "remocao do extra `llm` (sem uso desde a F22)"),
        "unidade": "MB decimal (1 MB = 1.000.000 bytes), a mesma que o Docker exibe",
        "metodo": ("`docker image inspect --format {{.Size}}` e `docker image ls`, "
                   "no mesmo daemon, "
                   "mesma imagem base, antes e depois da mudanca de uma linha no Dockerfile"),
        "referencia_fase16": {
            "valor_afirmado": "624 MB",
            "metodo": "NAO REGISTRADO — o doc da F16 nao diz qual comando produziu o numero",
            "artefato": None,
        },
        "mesma_imagem_base_nas_duas_medicoes": mesma_base,
        "antes": {k: antes[k] for k in antes if k != "pacotes_instalados"},
        "depois": {k: depois[k] for k in depois if k != "pacotes_instalados"},
        "delta_bytes_image_inspect": depois["tamanho_bytes_image_inspect"]
        - antes["tamanho_bytes_image_inspect"],
        "delta_mb_image_inspect": round((depois["tamanho_bytes_image_inspect"]
                                         - antes["tamanho_bytes_image_inspect"]) / MB, 1),
        "pacotes_que_sairam": saiu,
        "pacotes_que_entraram": entrou,
        "n_pacotes": {"antes": len(antes["pacotes_instalados"]),
                      "depois": len(depois["pacotes_instalados"])},
        "fumaca_da_imagem_nova": fum,
        "_proveniencia": {
            "git_sha": a.git_sha,
            "docker_server": _rodar(["docker", "version", "--format", "{{.Server.Version}}"]),
            "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        },
    }
    # newline="\n" é obrigatório: este script roda no Python do WINDOWS e grava dentro do repo, que
    # é LF. Sem isto o write_text traduz \n -> \r\n e o artefato nasce com CRLF.
    destino = Path(a.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(rel, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    print(f"antes {antes['tamanho_mb_image_inspect']} MB -> depois "
          f"{depois['tamanho_mb_image_inspect']} MB (delta {rel['delta_mb_image_inspect']} MB)")
    print(f"sairam: {saiu}")
    print(f"entraram: {entrou or 'nenhum'} | mesma base: {mesma_base}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("construir")
    for arg in ("--contexto", "--tag", "--rotulo", "--saida"):
        c.add_argument(arg, required=True)
    f = sub.add_parser("fumaca")
    f.add_argument("--tag", required=True)
    f.add_argument("--saida", required=True)
    k = sub.add_parser("consolidar")
    for arg in ("--antes", "--depois", "--fumaca", "--git-sha", "--saida"):
        k.add_argument(arg, required=True)
    a = ap.parse_args()
    {"construir": construir, "fumaca": fumaca, "consolidar": consolidar}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
