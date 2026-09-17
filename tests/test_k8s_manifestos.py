"""Os manifestos Kubernetes não podem regredir para os dois defeitos que a Fase 24 achou.

Ambos passaram despercebidos por 7 fases porque ninguém tinha EXERCITADO a GPU no cluster:

1. **Chave duplicada.** A instrução no `ollama.yaml` mandava descomentar um segundo `limits:` logo
   abaixo do primeiro. Testado no k3s v1.36: pelo `kubectl apply -k` documentado, o kustomize
   recusa; mas `kubectl apply -f` no arquivo ACEITA sem aviso, e o pod sai só com
   `nvidia.com/gpu` — sem os limites de CPU e memória. O PyYAML também deixa a última vencer
   calado, e é por isso que o carregador abaixo precisa recusar a duplicata explicitamente.
2. **Imagem `:latest`.** O Ollama sem versão fixada resolveu para 0.34.1, que nesta máquina deixou
   a mesma consulta 1,9–2,8× mais lenta que a 0.31.2 — uma regressão de latência que nenhum commit
   causou e nenhum teste veria.

Tudo aqui é estático (lê os YAML), então roda no CI sem cluster nem GPU. A prova de que os overlays
funcionam de verdade está em reports/fase24/, não aqui — este arquivo só impede a volta.
"""
from pathlib import Path

import pytest
import yaml

K8S = Path(__file__).resolve().parents[1] / "k8s"


class _SemDuplicata(yaml.SafeLoader):
    """SafeLoader que RECUSA chave duplicada, em vez de deixar a última vencer calada."""


def _mapa_sem_duplicata(loader, node, deep=False):
    vistas = set()
    for chave_node, _ in node.value:
        chave = loader.construct_object(chave_node, deep=deep)
        if chave in vistas:
            raise yaml.constructor.ConstructorError(
                None, None, f"chave duplicada: {chave!r}", chave_node.start_mark)
        vistas.add(chave)
    return loader.construct_mapping(node, deep=deep)


_SemDuplicata.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa_sem_duplicata)

MANIFESTOS = sorted(p for p in K8S.rglob("*.y*ml") if p.suffix in (".yaml", ".yml"))


def test_ha_manifestos_para_conferir():
    """Sem esta guarda, um glob vazio sumiria com os testes e o build ficaria verde."""
    assert len(MANIFESTOS) >= 8


@pytest.mark.parametrize("arquivo", MANIFESTOS, ids=lambda p: str(p.relative_to(K8S)))
def test_nenhum_manifesto_tem_chave_duplicada(arquivo: Path):
    list(yaml.load_all(arquivo.read_text(encoding="utf-8"), Loader=_SemDuplicata))


def test_o_carregador_de_fato_pega_chave_duplicada():
    """Controle negativo: uma trava que nunca reprova o caso ruim não prova nada."""
    ruim = "resources:\n  limits: {cpu: '4'}\n  limits: {nvidia.com/gpu: 1}\n"
    with pytest.raises(yaml.constructor.ConstructorError, match="duplicada"):
        yaml.load(ruim, Loader=_SemDuplicata)  # noqa: S506 — é o SafeLoader com a checagem


def test_overlay_de_gpu_acrescenta_a_chave_sem_substituir_os_limites():
    kust = yaml.safe_load((K8S / "gpu" / "kustomization.yaml").read_text(encoding="utf-8"))
    ops = [op for p in kust["patches"] for op in yaml.safe_load(p["patch"])]
    gpu = [op for op in ops if op["path"].endswith("nvidia.com~1gpu")]
    assert gpu, "o overlay nao acrescenta nvidia.com/gpu"
    assert all(op["op"] == "add" for op in gpu)
    # Substituir o mapa `limits` inteiro reintroduziria o defeito por outro caminho.
    assert not any(op["path"].endswith("/resources/limits") for op in ops), (
        "o overlay substitui o mapa limits inteiro e apagaria os limites de CPU e memoria")


def test_base_continua_limitando_cpu_e_memoria_do_ollama():
    docs = yaml.safe_load_all((K8S / "base" / "ollama.yaml").read_text(encoding="utf-8"))
    sts = next(d for d in docs if d and d["kind"] == "StatefulSet")
    limites = sts["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]
    assert {"cpu", "memory"} <= set(limites)


def test_imagens_da_base_tem_versao_fixada():
    for arquivo in (K8S / "base").glob("*.yaml"):
        for doc in yaml.safe_load_all(arquivo.read_text(encoding="utf-8")):
            if not doc or doc.get("kind") not in ("Deployment", "StatefulSet"):
                continue
            for c in doc["spec"]["template"]["spec"]["containers"]:
                img = c["image"]
                assert ":" in img and not img.endswith(":latest"), (
                    f"{arquivo.name}: imagem sem versao fixada ({img}) — ver o comentario no "
                    "ollama.yaml sobre a regressao de latencia que isso escondeu")
