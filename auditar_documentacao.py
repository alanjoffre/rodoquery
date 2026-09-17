"""Auditoria de FIDELIDADE: cada número afirmado na documentação existe no relatório?

Um README bonito com número errado é pior que nenhum. Este script lê os artefatos em
`reports/**` e confere contra o que o README/docs afirmam. Ele NÃO conserta nada — só denuncia.

Regra: se um número aparece no README, ou ele sai daqui, ou é retratado.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
R = REPO / "reports"
ok = falhas = 0


def _j(rel: str):
    p = R / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def checa(rotulo: str, obtido, esperado, tol=0.0):
    global ok, falhas
    if obtido is None:
        print(f"  AUSENTE  {rotulo:52s} (artefato nao encontrado)")
        falhas += 1
        return
    bate = (abs(float(obtido) - float(esperado)) <= tol
            if isinstance(esperado, (int, float)) else obtido == esperado)
    if bate:
        print(f"  OK       {rotulo:52s} {obtido}")
        ok += 1
    else:
        print(f"  DIVERGE  {rotulo:52s} doc={esperado}  artefato={obtido}")
        falhas += 1


print("=== TESE: numeros do cabecalho do README ===")
f18 = _j("fase18/resultado_test_antt_api.json")
if f18:
    s = f18["sistemas"]
    checa("F18 tier_a EX (README diz 100%)",
          s["tier_a_antt"]["execution_accuracy_respondiveis"]["taxa"], 1.0)
    checa("F18 sql_cru EX (README diz 44,5%)",
          s["sql_cru_antt"]["execution_accuracy_respondiveis"]["taxa"], 0.4452, 0.0001)
    checa("F18 n respondiveis (README diz 146)",
          s["tier_a_antt"]["execution_accuracy_respondiveis"]["n"], 146)
    checa("F18 custo (README diz US$ 0,96)", f18["custo"]["custo_usd"], 0.9627, 0.0001)

# O artefato da F12 guarda o valor RE-PONTUADO (as F14/15 corrigiram gold e re-scoraram as
# mesmas predicoes: 86,9 -> 88,7 -> 89,7). O README cita 86,9% na linha da fase COM nota de
# rodape explicando isso, e 89,7% na tabela da tese. Aqui conferimos o que o artefato de fato tem.
f12 = _j("fase12/resultado_test_antt.json")
if f12:
    checa("F12 artefato = valor RE-PONTUADO (README explica em nota)",
          f12["sistemas"]["tier_a_antt"]["execution_accuracy_respondiveis"]["taxa"], 0.8973, 0.001)

# =====================================================================================
# FASES 1-10 e 15 — a fundação SINTÉTICA.
#
# Estas travas nasceram do P2.3 do levantamento de pendências: o README prometia conferir
# "cada valor citado aqui", e o auditor lia só 8 fases (12, 13, 14, 18–22). Os números das
# fases antigas ficavam sem lastro automático — justamente os que ninguém reabre, e por isso
# os mais fáceis de apodrecer. Promessa e trava passam a coincidir.
#
# Os artefatos já estavam todos em disco: nenhuma medição nova foi feita para escrever isto.
# =====================================================================================
print("\n=== FASE 1 (sandbox) ===")
f1 = _j("fase1/security_redteam.json")
if f1:
    checa("F1 attack-block (README diz 100%)", f1["attack_block_rate"], 1.0)
    checa("F1 bloqueados (README diz 39/39)", f1["n_bloqueados"], 39)
    checa("F1 n ataques (README diz 39)", f1["n_ataques"], 39)
    checa("F1 falso-positivo (README diz 0%)", f1["falso_positivo_rate"], 0.0)
    checa("F1 legitimas passam (README diz 10/10)", f1["n_passaram"], 10)

print("\n=== FASE 3 (baselines) ===")
f3 = _j("fase3/baselines.json")
if f3:
    ex3 = f3["sistemas"]["sql_cru"]["execution_accuracy_respondiveis"]
    checa("F3 sql_cru EX no DEV (README diz 26,3%)", ex3["taxa"], 0.2632, 0.0001)
    checa("F3 n respondiveis no DEV", ex3["n"], 19)
    # O piso "sempre abster" existe para provar que o EX nao e artefato do denominador.
    checa("F3 piso sempre_abster EX (doc diz 0%)",
          f3["sistemas"]["sempre_abster"]["execution_accuracy_respondiveis"]["taxa"], 0.0)

print("\n=== FASE 4 (tese na fundacao sintetica) ===")
f4 = _j("fase4/resultado_test.json")
if f4:
    s4 = f4["sistemas"]
    m4 = f4["mcnemar_tier_a_vs_sql_cru_respondiveis"]
    checa("F4 tier_a EX (README diz 97,6%)",
          s4["tier_a"]["execution_accuracy_respondiveis"]["taxa"], 0.9762, 0.0001)
    checa("F4 sql_cru EX (README diz 42,9%)",
          s4["sql_cru"]["execution_accuracy_respondiveis"]["taxa"], 0.4286, 0.0001)
    checa("F4 vantagem (README diz +54,8 pp)", m4["delta_acuracia"], 0.5476, 0.0001)
    checa("F4 McNemar b (README diz 23)", m4["b_only"], 23)
    checa("F4 McNemar c (README diz 0)", m4["c_only"], 0)
    checa("F4 n do TEST selado (doc diz 53)", f4["n"], 53)

print("\n=== FASE 5 (MLOps: o gate reprova de verdade?) ===")
f5g = _j("fase5/gate_ativo.json")
if f5g:
    # 7 cenarios = 1 integro (deve passar) + 6 regressoes injetadas (devem reprovar).
    injetadas = [c for c in f5g["cenarios"] if not c["esperado"]]
    checa("F5 regressoes injetadas (README diz 6)", len(injetadas), 6)
    checa("F5 gate pegou todas (README diz 6/6)",
          sum(1 for c in injetadas if c["gate_se_comportou"]), 6)
    checa("F5 gate ativo comprovado", f5g["gate_ativo_comprovado"], True)
f5f = _j("fase5/flakiness.json")
if f5f:
    checa("F5 latencia p50 (README diz 4,5 s)", f5f["latencia_s"]["p50"], 4.507, 0.001)
    checa("F5 latencia p95 (README diz 7,9 s)", f5f["latencia_s"]["p95"], 7.935, 0.001)
    # O achado honesto da fase: a flakiness PREVISTA nao se confirmou.
    checa("F5 amplitude entre 5 runs (doc diz 0,0 pp)", f5f["amplitude_pp"], 0.0)

print("\n=== FASE 6 (serving + SLO) ===")
f6s = _j("fase6/slo.json")
if f6s:
    checa("F6 p95 em c=1 (README diz 4,36 s)", f6s["medido"]["p95_c1_s"], 4.36, 0.001)
    checa("F6 capacidade (README diz ~0,25 req/s)",
          f6s["medido"]["vazao_c1_req_s"], 0.251, 0.001)
    checa("F6 SLO atendido", f6s["slo_atendido"], True)
f6c = _j("fase6/canario.json")
if f6c:
    checa("F6 canario (README diz 10/10)", f6c["acertos"], 10)
    checa("F6 canario n", f6c["n"], 10)
f6l = _j("fase6/load_test.json")
if f6l:
    # A hipotese "6 GB serializa": em c=4 a vazao CAI. E o que justifica o semaforo 1 e a
    # ausencia de HPA na Fase 17 — um numero que sustenta uma decisao de arquitetura.
    checa("F6 vazao relativa em c=4 (doc diz 0,75x)",
          f6l["ganho_de_vazao_vs_c1"]["4"], 0.75, 0.01)
    checa("F6 hipotese 'serializa' confirmada", f6l["hipotese_confirmada"], True)

print("\n=== FASE 7 (robustez na fundacao sintetica) ===")
f7p = _j("fase7/heldout_parafrase.json")
if f7p:
    checa("F7 parafrase delta (README diz -7,7 pp)",
          f7p["execution_accuracy"]["delta_pp"], -7.7, 0.01)
    checa("F7 parafrase p (README diz 0,375 = NAO significativo)",
          f7p["mcnemar_original_vs_parafrase"]["p_valor"], 0.375, 0.001)
f7s = _j("fase7/perturbacao_schema.json")
if f7s:
    checa("F7 schema opaco delta (README diz -14,3 pp)",
          f7s["execution_accuracy"]["delta_pp"], -14.29, 0.01)
    checa("F7 schema opaco p (README diz 0,031)",
          f7s["mcnemar_reais_vs_opaco"]["p_valor"], 0.0312, 0.0001)

print("\n=== FASE 8 (poder estatistico: o 97,6% replica?) ===")
f8 = _j("fase8/resultado_test_v2.json")
if f8:
    checa("F8 n do TEST-v2 selado (README diz 223)", f8["n"], 223)
a8 = _j("fase8/analise.json")
if a8:
    r8 = a8["replicacao_7_estratos_originais"]
    checa("F8 valor original da F4 (README diz 97,6%)",
          r8["fase4_v1"]["tier_a"]["execution_accuracy"]["taxa"], 0.9762, 0.0001)
    checa("F8 replicacao nos MESMOS 7 estratos (README diz 73,7%)",
          r8["fase8_v2"]["tier_a"]["execution_accuracy"]["taxa"], 0.7365, 0.0001)
    checa("F8 vantagem no v2 (README diz +58,7 pp)", r8["fase8_v2"]["delta_pp"], 58.68, 0.01)

print("\n=== FASE 9 (conserto: prompt x codigo) ===")
f9p = _j("fase9/resultado_test_v3.json")
if f9p:
    # Resultado NEGATIVO documentado: reescrever o prompt EMPATOU.
    checa("F9 prompt v2 empatou (README diz p=0,89)",
          f9p["execution_accuracy"]["mcnemar"]["p_valor"], 0.8877, 0.0001)
f9n = _j("fase9/resultado_normalizador_v3.json")
if f9n:
    e9 = f9n["execution_accuracy"]
    checa("F9 EX antes do normalizador (doc diz 66,9%)", e9["cru"]["taxa"], 0.6685, 0.0001)
    checa("F9 EX depois (doc diz 71,8%)", e9["com_normalizador"]["taxa"], 0.7182, 0.0001)
    checa("F9 ganho (README diz +5 pp)", e9["mcnemar"]["delta_acuracia"], -0.0497, 0.0001)
    checa("F9 p (README diz 0,004)", e9["mcnemar"]["p_valor"], 0.0039, 0.0001)
    checa("F9 zero regressoes (README diz zero)", e9["mcnemar"]["b_only"], 0)

print("\n=== FASE 10 (catalogo: hipotese refutada + o gargalo real) ===")
f10c = _j("fase10/resultado_catalogo_limpo.json")
if f10c:
    # Minha hipotese foi REFUTADA e o numero fica travado igual aos que deram certo.
    checa("F10 limpar catalogo empatou (README diz p=1,0)",
          f10c["execution_accuracy"]["mcnemar"]["p_valor"], 1.0)
f10n = _j("fase10/resultado_normalizador_groupby.json")
if f10n:
    e10 = f10n["execution_accuracy"]
    checa("F10 EX antes (doc diz 71,8%)", e10["so_ordem"]["taxa"], 0.7182, 0.0001)
    checa("F10 EX depois (doc diz 84,5%)", e10["ordem_e_groupby"]["taxa"], 0.8453, 0.0001)
    checa("F10 ganho (README diz +12,7 pp)", e10["mcnemar"]["delta_acuracia"], -0.1271, 0.0001)
    checa("F10 zero regressoes", e10["mcnemar"]["b_only"], 0)

print("\n=== FASE 15 (ablacao: o maior ganho isolado do projeto) ===")
f15 = _j("fase15/resultado_ablacao.json")
if f15:
    e15 = f15["execution_accuracy"]
    checa("F15 A baseline (doc diz 47,2%)", e15["A_baseline_normF10"]["taxa"], 0.4722, 0.0001)
    checa("F15 B normalizador corrigido (doc diz 80,6%)",
          e15["B_norm_corrigido"]["taxa"], 0.8056, 0.0001)
    # +33,3 pp, nao +33,4: sao 12 itens em 36 = 1/3 exato. O README dizia 33,4 porque a conta
    # foi feita sobre as taxas JA arredondadas (0,8056 - 0,4722). Achado ao escrever esta trava.
    checa("F15 ganho B vs A (README diz +33,3 pp)",
          f15["mcnemar_vs_baseline"]["B_norm_corrigido"]["delta_acuracia"], -0.3333, 0.0001)
    checa("F15 B zero regressoes", f15["mcnemar_vs_baseline"]["B_norm_corrigido"]["b_only"], 0)
    checa("F15 SUT 9B colapsa (README diz 5,6%)", e15["D_sut_gemma9b"]["taxa"], 0.0556, 0.0001)
    checa("F15 gemma perde em 15 itens, ganha em 0",
          f15["mcnemar_vs_baseline"]["D_sut_gemma9b"]["c_only"], 0)

print("\n=== FASE 16 (imagem Docker, re-medida) ===")
# Os 624 MB da F16 eram o unico numero do README sem artefato (medido a mao, metodo nao
# registrado). Re-medido antes e depois da remocao do extra `llm`, no mesmo daemon e mesma base.
img = _j("fase16/imagem_docker.json")
if img:
    checa("F16 imagem com extra llm (doc diz 637,4 MB)",
          img["antes"]["tamanho_mb_image_inspect"], 637.4, 0.05)
    checa("F16 imagem sem extra llm (README diz 635 MB)",
          img["depois"]["tamanho_mb_image_inspect"], 635.1, 0.05)
    checa("F16 delta atribuivel ao extra (doc diz -2,2 MB)", img["delta_mb_image_inspect"], -2.2)
    checa("F16 mesma imagem base nas duas medicoes", img["mesma_imagem_base_nas_duas_medicoes"],
          True)
    checa("F16 pacotes que sairam (doc diz httpcore, httpx, ollama)",
          img["pacotes_que_sairam"], ["httpcore", "httpx", "ollama"])
    checa("F16 nenhum pacote entrou", img["pacotes_que_entraram"], [])
    checa("F16 fumaca: total da Fase 11 confere na imagem nova (391.612.977)",
          img["fumaca_da_imagem_nova"]["total_confere"], True)

# A auditoria adversarial de labels da F15 nao vive em reports/ — o veredito e o proprio
# arquivo que `aplicar_auditoria.py` consome para remover os itens do golden. E versionado,
# entao e travavel: e o unico numero desta lista cuja fonte fica fora de reports/.
ver15 = REPO / "golden" / "_auditoria_veredito.jsonl"
checa("F15 defeitos de label achados (README diz 7)",
      len([x for x in ver15.read_text(encoding="utf-8").splitlines() if x.strip()])
      if ver15.exists() else None, 7)

print("\n=== FASE 19 ===")
f19 = _j("fase19/robustez_schema_opaco_api.json")
if f19:
    e = f19["execution_accuracy"]
    checa("F19 original (README diz 100%)", e["original"]["taxa"], 1.0)
    checa("F19 opaco (README diz 100%)", e["schema_opaco"]["taxa"], 1.0)
    checa("F19 delta (README diz 0,00 pp)", e["delta_pp"], 0.0)
    checa("F19 custo (README diz US$ 0,19)", f19["custo_usd"], 0.1925, 0.0001)
    checa("F19 previsao registrada (doc diz -9 pp)",
          f19["previsao_registrada"]["delta_pp"], -9.0)
    checa("F19 previsao acertou? (doc diz REFUTADA)",
          f19["veredito"]["dentro_da_faixa_prevista"], False)

f14r = _j("fase14/robustez_schema_opaco.json")
if f14r:
    checa("F14 delta do Qwen (README diz -29,4 pp)",
          f14r["execution_accuracy"]["delta_pp"], -29.41, 0.01)

print("\n=== FASE 20 ===")
f20 = _j("fase20/resultado_duro.json")
if f20:
    s = f20["sistemas"]
    checa("F20 tier_a respondiveis (README diz 35/35)",
          s["tier_a_antt"]["execution_accuracy_respondiveis"]["acertos"], 35)
    checa("F20 n respondiveis", s["tier_a_antt"]["execution_accuracy_respondiveis"]["n"], 35)
    checa("F20 tier_a abstencao (README diz 50%)",
          s["tier_a_antt"]["acuracia_abstencao"]["taxa"], 0.5)
    checa("F20 sql_cru abstencao (README diz 0%)",
          s["sql_cru_antt"]["acuracia_abstencao"]["taxa"], 0.0)
    checa("F20 custo (README diz US$ 0,30)", f20["custo_usd"], 0.2965, 0.0001)
g20 = _j("fase20/gold_duro.json")
if g20:
    checa("F20 itens selados (doc diz 47)", g20["n_validos"], 47)
    checa("F20 descartados (doc diz 1)", g20["n_descartados"], 1)

print("\n=== FASE 21 ===")
f21 = _j("fase21/resultado_duro_rico.json")
if f21:
    ex, ab = f21["execution_accuracy_respondiveis"], f21["acuracia_abstencao"]
    checa("F21 respondiveis (README diz 38/39)", ex["acertos"], 38)
    checa("F21 n respondiveis (README diz 39)", ex["n"], 39)
    checa("F21 abstencao (README diz 6/8 = 75%)", ab["taxa"], 0.75)
    checa("F21 rebaixamento remanescente (doc diz 1)",
          f21["rebaixamento_de_tipo_remanescente"], 1)
    checa("F21 custo (doc diz US$ 0,142)", f21["custo_usd"], 0.1424, 0.0001)
g21 = _j("fase21/gold_duro_rico.json")
if g21:
    checa("F21 itens selados (doc diz 47)", g21["n_validos"], 47)
    checa("F21 viraram respondiveis (doc diz 4)", len(g21["viraram_respondiveis"]), 4)
aud = _j("fase21/auditoria_adversarial.json")
if aud:
    checa("F21 auditoria corretas (README diz 44/47)", aud["n"] - aud["n_defeitos"], 44)
    checa("F21 taxa correta (doc diz 93,6%)", aud["taxa_correta"], 0.9362, 0.001)
    checa("F21 defeitos (doc diz 3)", aud["n_defeitos"], 3)
cc = _j("fase21/concorrencia_api.json")
if cc:
    checa("F21 vazao relativa em c=8 (doc diz 5,74x)", cc["vazao_relativa"]["8"], 5.74, 0.01)
    checa("F21 melhor nivel (doc diz 8)", cc["melhor_nivel"], 8)
    checa("F21 criterio pre-declarado atendido", cc["escala"], True)

print("\n=== FASE 23 (catalogo rico no benchmark principal) ===")
f23 = _j("fase23/resultado_rico_test_antt.json")
if f23:
    ex23 = f23["execution_accuracy_respondiveis"]
    checa("F23 rico EX (doc diz 145/146)", ex23["acertos"], 145)
    checa("F23 n respondiveis (mesmos 146 da F18)", ex23["n"], 146)
    checa("F23 rico abstencao (doc diz 25/25 = 100%)",
          f23["acuracia_abstencao_NAO_COMPARAVEL"]["taxa"], 1.0)
    mc23 = f23["mcnemar_vs_fase18_respondiveis"]
    checa("F23 McNemar b (doc diz 1)", mc23["b_only"], 1)
    checa("F23 McNemar c (doc diz 0)", mc23["c_only"], 0)
    checa("F23 p (doc diz 1,0 = NAO significativo)", mc23["p_valor"], 1.0)
    checa("F23 regressoes (doc diz 1)", len(f23["regressoes"]), 1)
    checa("F23 ganhos (doc diz 0)", len(f23["ganhos"]), 0)
    # A precaucao metodologica que se mostrou desnecessaria — e que so se sabe medindo.
    checa("F23 abstencoes que viraram respondiveis (doc diz 0)",
          f23["abstencoes_respondidas_com_metrica_nova"], 0)
    checa("F23 custo (doc diz US$ 0,4632)", f23["custo_usd"], 0.4632, 0.0001)

print("\n=== FASE 24 (GPU no Kubernetes, k3s no WSL) ===")
g24 = _j("fase24/gpu_k8s_wsl.json")
if g24:
    checa("F24 os 5 degraus passaram", all(d["ok"] for d in g24["degraus"]), True)
    s24 = g24["series"]
    checa("F24 nativo GPU p50 basico (doc diz 1,99 s)",
          s24["nativo_gpu_basico"]["p50_s"], 1.988, 0.001)
    checa("F24 K8s GPU mesma versao p50 basico (doc diz 2,05 s)",
          s24["k8s_gpu_ollama0.31.2_basico"]["p50_s"], 2.048, 0.001)
    checa("F24 K8s GPU com :latest p50 basico (doc diz 3,97 s)",
          s24["k8s_gpu_ollama0.34.1_basico"]["p50_s"], 3.971, 0.001)
    checa("F24 todas as series com resposta conferida",
          all(s["todas_conferem"] for s in s24.values()), True)
    c24 = g24["comparacoes"]
    checa("F24 custo do K8s sobre o nativo, mesma versao (doc diz 1,03x)",
          c24["k8s_sobre_nativo_mesma_versao_basico"], 1.03, 0.001)
    checa("F24 efeito da versao no pod, rico (doc diz 2,8x)",
          c24["ollama_0341_sobre_0312_no_pod_rico"], 2.817, 0.001)
    checa("F24 LLM CPU (F17b) sobre LLM GPU (doc diz 29,6x)",
          c24["llm_cpu_f17b_sobre_llm_gpu_k8s"], 29.6, 0.05)
    checa("F24 hipotese do limite de CPU (doc diz REFUTADA)",
          g24["hipoteses"][1]["veredito"], "REFUTADA")

print("\n=== FASE 22 (historico do CI) ===")
# SNAPSHOT congelado no dia do conserto (03/08/2026). O README afirma o passado — "1 verde em 33"
# — entao a fonte tem de ser o snapshot, nao uma nova consulta: re-medir depois do conserto daria
# outro numero e o README, que fala de antes, pareceria mentir. Regravar so com
# `medir_historico_ci.py`, e de proposito.
ci = _j("fase22/historico_ci.json")
if ci:
    checa("F22 execucoes ate o conserto (README diz 33)", ci["n_execucoes"], 33)
    checa("F22 verdes (README diz 1)", ci["n_verdes"], 1)
    checa("F22 vermelhas seguidas (README diz 32)",
          ci["vermelhas_consecutivas_ate_a_ultima"], 32)
    checa("F22 dias vermelho (doc diz 12)", ci["dias_vermelho"], 12)
    checa("F22 unica verde = commit que criou o CI (F5)",
          ci["primeira_verde"]["sha"], "d5701540")
    checa("F22 quebrou no commit da F6 (serving/FastAPI)",
          ci["primeira_vermelha"]["sha"], "528387c9")

print("\n=== KAPPA HUMANO ===")
kh = _j("fase14/kappa_humano.json")
if kh:
    checa("kappa humano (README diz 1,0)", kh["concordancia_spec"]["cohen_kappa_metrica"], 1.0)
    checa("n anotados (README diz 40)", kh["n_anotados_por_humano"], 40)
co = _j("fase18/concordancia_opus5_x_autor.json")
if co:
    checa("Opus5 cego x autor (README diz 0,992)",
          co["concordancia_spec"]["cohen_kappa_metrica"], 0.9921, 0.0001)
    checa("discordantes (doc diz 1)", len(co["concordancia_spec"]["discordantes"]), 1)

print("\n=== BIRD / calibracao externa ===")
b = _j("fase13/resultado_bird.json") or _j("fase13/bird_minidev.json")
if b is None:
    for p in sorted((R / "fase13").glob("*.json")) if (R / "fase13").exists() else []:
        d = json.loads(p.read_text(encoding="utf-8"))
        if "execution_accuracy" in json.dumps(d)[:2000]:
            b = d
            print(f"  (usando {p.name})")
            break
if b:
    txt = json.dumps(b)
    m = re.search(r'"taxa":\s*(0\.4\d+)', txt)
    checa("BIRD EX (README diz 43,4%)", float(m.group(1)) if m else None, 0.434, 0.002)

print("\n=== CUSTO TOTAL DE API ===")
total = 0.0
for p in sorted(R.glob("fase*/*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    c = d.get("custo_usd")
    if c is None and isinstance(d.get("custo"), dict):
        c = d["custo"].get("custo_usd")
    if isinstance(c, (int, float)):
        total += c
        print(f"  {p.parent.name}/{p.name:38s} US$ {c:.4f}")
print(f"  {'TOTAL':50s} US$ {total:.4f}")

print(f"\n{'=' * 70}\nOK: {ok}   DIVERGENCIAS/AUSENTES: {falhas}")
raise SystemExit(1 if falhas else 0)
