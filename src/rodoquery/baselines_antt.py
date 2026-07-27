"""Baseline `sql_cru` sobre o schema REAL da ANTT (Fase 12).

Mesmo SUT, mesma estrutura de prompt do baseline sintético — só muda o schema. A comparação
continua sendo **interface × interface**, não modelo × modelo.

Justiça (para não montar um espantalho): o prompt é generoso no COSMÉTICO — contrato de saída,
ordem das colunas, `date_trunc`, os valores exatos das colunas categóricas. O que ele NÃO entrega
é a regra de negócio que o Semantic Layer governa e o SQL cru precisa redescobrir sozinho:

  - a chave real da praça é (concessionaria, praca) — o nome sozinho se repete entre
    concessionárias, e agrupar por ele funde praças distintas em silêncio;
  - "taxa de automação" = volume com tipo_cobranca='Automática' ÷ volume total;
  - "participação de veículos comerciais" = volume Comercial ÷ volume total.

O schema mostra as colunas e os valores; não diz o que significa nenhuma dessas três coisas.
Se o baseline erra ISSO com todo o resto facilitado, o erro é semântico — que é a tese.
"""
from __future__ import annotations

from rodoquery.avaliacao import Predicao
from rodoquery.baselines import PROMPT, _chamar_ollama, _extrair_sql
from rodoquery.config import settings

SCHEMA_ANTT = """Tabelas disponíveis (DuckDB, schema `main`). SÓ estas podem ser consultadas:

fct_traffic_volume  — volume de veículos nas praças de pedágio federais (tabela fato).
                      Uma linha por praça × dia × sentido × cobrança × eixo × tipo de veículo.
  plaza_key VARCHAR        — identificador da praça no formato 'CONCESSIONARIA::PRACA'
  concessionaria VARCHAR   — nome da concessionária (30 valores, ex. 'RIOSP', 'ECOSUL')
  praca VARCHAR            — nome da praça (ex. 'NITEROÍ-1', 'P1', 'P4')
  data DATE                — data da passagem
  sentido VARCHAR          — valores: Crescente, Decrescente
  tipo_cobranca VARCHAR    — valores: Automática, Manual, OCR/PLACA
  categoria_eixo VARCHAR   — número de eixos do veículo, de '2' a '20'
  tipo_de_veiculo VARCHAR  — valores: Comercial, Passeio, Moto
  volume DOUBLE            — quantidade de veículos naquele grão

dim_date (date_key INTEGER, date_day DATE, ano INTEGER, mes INTEGER, dia INTEGER)"""

REGRAS_SAIDA = """Regras de SAÍDA (obrigatórias):
- Responda com UMA única query SELECT em DuckDB e MAIS NADA (sem explicação, sem ```).
- Ao agrupar, ponha a(s) coluna(s) de agrupamento PRIMEIRO e o valor agregado por ÚLTIMO.
- Para agrupar por tempo use date_trunc('day'|'week'|'month', data).
- Se a pergunta NÃO puder ser respondida com estas tabelas/colunas, responda EXATAMENTE a
  palavra: ABSTENHO"""

PROMPT_ANTT = PROMPT.split("Regras de SAÍDA")[0].replace(
    "numa concessionária de pedágio",
    "na agência reguladora de transportes terrestres (ANTT)",
) + REGRAS_SAIDA + "\n\nPergunta: {pergunta}"


def sql_cru_antt(pergunta: str, modelo: str | None = None,
                 temperatura: float | None = None, provedor=None) -> Predicao:
    """LLM escreve SQL direto sobre o schema da ANTT — o baseline que a tese precisa bater.

    `provedor=None` mantém o Ollama das Fases 12–16. O par (Tier-A, sql_cru) tem de rodar SEMPRE
    no mesmo provedor: comparar Tier-A na API contra baseline no Qwen mediria o modelo, não a
    interface — exatamente o confundimento que a tese existe para evitar.
    """
    modelo = modelo or settings.modelo_sut
    temp = settings.temperatura if temperatura is None else temperatura
    chamar = provedor or _chamar_ollama
    texto, tel = chamar(PROMPT_ANTT.format(schema=SCHEMA_ANTT, pergunta=pergunta), modelo, temp)
    if "ABSTENHO" in texto.upper():
        return Predicao.abster(modelo=modelo, raw=texto[:400], **tel)
    sql = _extrair_sql(texto)
    if not sql:
        return Predicao.abster(modelo=modelo, raw=texto[:400], falha_parse=True, **tel)
    return Predicao.com_sql(sql, modelo=modelo, raw=texto[:400], **tel)
