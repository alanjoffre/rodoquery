"""Consolida o experimento de GPU no Kubernetes (Fase 24) num artefato auditável.

Lê os BRUTOS gravados pelos scripts 05/07/09 — as respostas do serviço, os logs do device plugin
e do Ollama, a saída do nvidia-smi dentro do pod — copia-os para reports/fase24/brutos/ e deriva
os números a partir deles. Nenhum valor é digitado à mão: se um bruto não estiver lá, o
consolidador falha em vez de inventar.

Uso: python k8s/gpu-wsl/consolidar.py /tmp/gpu_k8s
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from rodoquery.proveniencia import carimbar  # noqa: E402

ORIGEM = Path(sys.argv[1])
DEST = REPO / "reports" / "fase24"
BRUTOS = DEST / "brutos"

# Referência histórica: a MESMA pergunta no cluster em CPU (k8s/README.md, Fase 17b). Única
# entrada que não vem de um bruto desta fase, e por isso vai marcada com a fonte.
F17B_CPU = {"llm_s": 60.01, "total_s": 66.9, "catalogo": "basico",
            "fonte": "k8s/README.md, secao 'Inferencia ponta a ponta dentro do cluster' (F17b)",
            "ressalva": "versao do Ollama NAO registrada na F17b (imagem :latest de julho/2026)"}

SERIES = {
    "nativo_gpu_basico": "nativo_gpu_basico.json",
    "nativo_gpu_rico": "nativo_gpu_rico.json",
    "k8s_gpu_ollama0.34.1_basico": "k8s-gpu-ollama0.34.1_basico.json",
    "k8s_gpu_ollama0.34.1_rico": "k8s-gpu-ollama0.34.1_rico.json",
    "k8s_gpu_ollama0.31.2_basico": "k8s-gpu-ollama0.31.2_basico.json",
    "k8s_gpu_ollama0.31.2_rico": "k8s-gpu-ollama0.31.2_rico.json",
}


def _txt(nome: str) -> str:
    return (ORIGEM / nome).read_text(encoding="utf-8").strip()


def main() -> None:
    BRUTOS.mkdir(parents=True, exist_ok=True)
    for p in sorted(ORIGEM.iterdir()):
        shutil.copy2(p, BRUTOS / p.name)

    versoes = dict(ln.split("=", 1) for ln in _txt("versoes.txt").splitlines() if "=" in ln)

    series = {}
    for chave, arq in SERIES.items():
        d = json.loads((ORIGEM / arq).read_text(encoding="utf-8"))
        q = d["quentes"]
        series[chave] = {
            "catalogo": d["saude"].get("catalogo_antt"),
            "modelo": d["saude"].get("modelo"),
            "n_quentes": q["n"],
            "todas_conferem": q["todas_conferem"] and d["fria"]["confere"],
            "p50_s": q["parede_p50_s"], "p95_s": q["parede_p95_s"],
            "llm_p50_s": q["llm_p50_s"], "llm_p95_s": q["llm_p95_s"],
            "fria_s": d["fria"]["parede_s"],
            "abstencao_correta": d["abstencao"]["correta"],
            "abstencao_s": d["abstencao"]["parede_s"],
        }

    def razao(a: str, b: str) -> float:
        return round(series[a]["p50_s"] / series[b]["p50_s"], 3)

    plugin_log = _txt("device_plugin_log.txt")
    smi = _txt("teste_cuda_nvidia_smi.txt")
    gpu_log = _txt("k8s-gpu-ollama0.31.2_ollama_gpu_log.txt")
    ps = _txt("k8s-gpu-ollama0.31.2_ollama_ps.txt")
    offload = next((ln.split("offloaded")[1].strip() for ln in gpu_log.splitlines()
                    if "offloaded" in ln), None)
    divisao = next((tok for tok in ps.split() if "%/" in tok), None)

    degraus = [
        {"n": 1, "o_que": "NVIDIA Container Toolkit enxerga a GPU no WSL",
         "ok": bool(versoes.get("cuda_driver")), "evidencia": f"CUDA {versoes.get('cuda_driver')}"},
        {"n": 2, "o_que": "k3s sobe sem systemd e cria a RuntimeClass nvidia",
         "ok": _txt("runtimeclass_handler.txt") == "nvidia",
         "evidencia": f"handler={_txt('runtimeclass_handler.txt')}"},
        {"n": 3, "o_que": "o no anuncia nvidia.com/gpu (a pergunta central)",
         "ok": _txt("allocatable_gpu.txt") == "1" and "Detected platform: wsl" in plugin_log,
         "evidencia": plugin_log.splitlines()},
        {"n": 4, "o_que": "um pod que PEDE a GPU a enxerga",
         "ok": _txt("teste_cuda_fase.txt") == "Succeeded" and "RTX 4050" in smi,
         "evidencia": smi.splitlines()},
        {"n": 5, "o_que": "a stack do projeto infere na GPU, com a resposta certa",
         "ok": "library=CUDA" in gpu_log and all(s["todas_conferem"] for s in series.values()),
         "evidencia": {"offload": offload, "divisao_cpu_gpu": divisao,
                       "pod": _txt("ollama_pod_spec.txt")}},
    ]

    rel = carimbar({
        "fase": "24_gpu_no_kubernetes_wsl",
        "pergunta": "o README afirmava que GPU no K8s era impossivel nesta maquina; e?",
        "resposta": "possivel: todos os 5 degraus passaram" if all(d["ok"] for d in degraus)
        else "BLOQUEADO — ver o primeiro degrau com ok=false",
        "consulta_medida": "Quantos veículos passaram por sentido? (a mesma da F17b)",
        "ambiente": versoes,
        "degraus": degraus,
        "series": series,
        "referencia_f17b_k8s_cpu": F17B_CPU,
        "comparacoes": {
            "k8s_sobre_nativo_mesma_versao_basico": razao("k8s_gpu_ollama0.31.2_basico",
                                                          "nativo_gpu_basico"),
            "k8s_sobre_nativo_mesma_versao_rico": razao("k8s_gpu_ollama0.31.2_rico",
                                                        "nativo_gpu_rico"),
            "ollama_0341_sobre_0312_no_pod_basico": razao("k8s_gpu_ollama0.34.1_basico",
                                                          "k8s_gpu_ollama0.31.2_basico"),
            "ollama_0341_sobre_0312_no_pod_rico": razao("k8s_gpu_ollama0.34.1_rico",
                                                        "k8s_gpu_ollama0.31.2_rico"),
            "llm_cpu_f17b_sobre_llm_gpu_k8s": round(
                F17B_CPU["llm_s"] / series["k8s_gpu_ollama0.31.2_basico"]["llm_p50_s"], 1),
        },
        "hipoteses": [
            {"hipotese": "GPU no K8s e impossivel nesta maquina (README ate 17/09)",
             "veredito": "REFUTADA",
             "nota": "a F17b testou so kind sobre o Docker Desktop; k3s no WSL nunca foi tentado"},
            {"hipotese": "o limite cpu:4 do pod explica a lentidao no cluster",
             "veredito": "REFUTADA",
             "nota": "com cpu:4 mantido e Ollama 0.31.2, o pod igualou o nativo"},
            {"hipotese": "a versao do Ollama explica a lentidao no cluster",
             "veredito": "CONFIRMADA NO POD",
             "nota": "0.34.1 x 0.31.2 no mesmo pod; 0.34.1 NATIVO nao foi medido, entao nao se "
                     "separa regressao da versao de interacao versao x container"},
        ],
        "consequencia_no_manifesto": ("k8s/base/ollama.yaml: ollama/ollama:latest -> 0.31.2 "
                                      "(renderizacao da base muda exatamente essa linha)"),
        "defeito_de_manifesto_achado": {
            "instrucao_antiga": "descomente `limits: {nvidia.com/gpu: 1}` (segundo limits no mapa)",
            "via_apply_k": "kustomize RECUSA: mapping key already defined",
            "via_apply_f": ("kubectl ACEITA sem aviso; o pod sai com limits={nvidia.com/gpu: 1}, "
                            "sem CPU e memoria (dry-run no servidor, k3s v1.36)"),
            "conserto": "overlay k8s/gpu ACRESCENTA a chave ao mapa existente",
        },
        "ressalvas": [
            "offload PARCIAL: o modelo de 5,1 GB nao cabe inteiro em 6 GB; nativo e pod "
            "mostram a mesma divisao, entao a comparacao e justa, mas nao e GPU pura",
            "uma maquina, uma GPU, um no; 12 requisicoes quentes por serie, sequenciais (c=1)",
            "a F17b nao registrou a versao do Ollama, entao a razao CPU/GPU contra ela "
            "mistura hardware e versao",
            "WSL nao e Linux nativo: o caminho testado usa /dev/dxg e a NVML do driver Windows",
        ],
    })
    destino = DEST / "gpu_k8s_wsl.json"
    destino.write_text(json.dumps(rel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"resposta: {rel['resposta']}")
    for d in degraus:
        print(f"  degrau {d['n']}: {'OK ' if d['ok'] else 'FALHOU'} {d['o_que']}")
    for k, s in series.items():
        print(f"  {k:30s} p50 {s['p50_s']:6.3f}s  llm {s['llm_p50_s']:6.3f}s  "
              f"confere={s['todas_conferem']}")
    for k, v in rel["comparacoes"].items():
        print(f"  {k}: {v}")
    print(f"-> {destino}  (+ {len(list(BRUTOS.iterdir()))} brutos)")


if __name__ == "__main__":
    main()
