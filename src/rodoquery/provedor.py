"""Provedor de LLM plugável: Ollama local (default) ou API da Anthropic (Fase 17).

**Por que isto existe.** Até a Fase 16 o SUT era sempre `qwen2.5-coder:7b` via Ollama em
`localhost`. Isso amarrava a tese a um modelo de 7B rodando numa RTX 4050 — e deixava aberta a
pergunta que a Fase 15 só respondeu pelo lado de baixo: o ganho de +63,0 pp do Semantic Layer é
uma propriedade da **interface**, ou era compensação de um SUT fraco? A Fase 15 mostrou que um 9B
generalista COLAPSA (gemma2:9b, 5,6%). Falta o lado de cima.

**O contrato.** Um provedor é `(prompt, modelo, temperatura) -> (texto, telemetria)` — exatamente
a assinatura de `_chamar_ollama`, para que `sistema_antt` e `baselines_antt` não precisem saber
qual está em uso. A telemetria tem as MESMAS chaves nos dois casos (`tokens_prompt`,
`tokens_saida`, `latencia_s`, ...), então o congelamento de predições e o relatório de custo da
Fase 5 continuam funcionando sem alteração.

**O default NUNCA muda.** `obter_provedor()` sem argumento devolve o Ollama, com o mesmo corpo de
requisição byte a byte das Fases 0–16. Nada aqui altera um número já medido.

## Três decisões de método que valem ser declaradas

1. **Sem structured outputs.** A API da Anthropic sabe forçar um JSON Schema
   (`output_config.format`), o que garantiria spec bem-formada de graça. **Não uso de propósito.**
   Metade do que o Tier-A mede é justamente "o modelo consegue emitir uma spec válida a partir de
   um vocabulário fechado?". Forçar o schema responderia essa pergunta por decreto e tornaria o
   número incomparável com o do Qwen. O contrato de saída é texto livre, idêntico ao local.

2. **Determinismo é MAIS FRACO aqui, e isso é declarado.** O caminho Ollama fixa
   `temperature=0, seed=42, top_k=1` — a Fase 5 mediu amplitude 0,0 pp em 5 execuções. Os modelos
   Claude a partir do Opus 4.7 **rejeitam** `temperature`/`top_p`/`top_k` com HTTP 400; não existe
   seed. Logo a execução via API **não é bit-reproduzível**. A mitigação é a que o projeto já usa
   desde a Fase 4: as predições são CONGELADAS em disco e o scoring roda sobre elas. O número
   publicado é reprodutível; a coleta que o gerou, não. Dizer isso é o ponto.

3. **`<thinking>` vazado é consertado em código, não no prompt.** Com o thinking desligado, os
   modelos Claude ocasionalmente escrevem tags internas no texto visível. Eu poderia pedir no
   prompt para não fazer isso — mas aí o prompt deixaria de ser byte a byte o mesmo que o Qwen
   recebeu, e a comparação morre. Então normalizo na borda de transporte (`_limpar_tags`), que é
   a mesma lição da Fase 9/15: **falha mecânica se conserta em código, não em prosa no prompt.**
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from rodoquery.baselines import _chamar_ollama


# --------------------------------------------------------------------------------------------
# Preços (USD por milhão de tokens). Fonte: tabela oficial da Anthropic, consultada em 2026-07-27.
# Ficam aqui explícitos porque o relatório de custo precisa ser auditável — um número de gasto sem
# a tabela que o gerou é tão pouco verificável quanto um EX sem o gold.
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Preco:
    entrada: float           # USD / 1M tokens de entrada
    saida: float             # USD / 1M tokens de saída
    minimo_cache: int        # prefixo mínimo (tokens) para o cache pegar; abaixo disso NÃO cacheia

    # Multiplicadores do prompt caching (iguais para todos os modelos):
    #   escrita = 1,25x o preço de entrada | leitura = 0,10x
    def custo(self, entrada: int, saida: int, cache_w: int = 0, cache_r: int = 0) -> float:
        return (
            entrada * self.entrada
            + cache_w * self.entrada * 1.25
            + cache_r * self.entrada * 0.10
            + saida * self.saida
        ) / 1_000_000


PRECOS: dict[str, Preco] = {
    "claude-opus-5":     Preco(entrada=5.00, saida=25.00, minimo_cache=512),
    "claude-opus-4-8":   Preco(entrada=5.00, saida=25.00, minimo_cache=1024),
    # Sonnet 5 está em preço introdutório ($2/$10) até 2026-08-31; uso o preço CHEIO para não
    # subestimar o custo — errar para cima num orçamento apertado é a direção segura.
    "claude-sonnet-5":   Preco(entrada=3.00, saida=15.00, minimo_cache=1024),
    "claude-haiku-4-5":  Preco(entrada=1.00, saida=5.00,  minimo_cache=4096),
}

MODELO_API_PADRAO = "claude-opus-5"

# Tags internas que podem vazar no texto visível quando o thinking está desligado. Removidas na
# borda de transporte — ver decisão (3) no docstring do módulo.
_TAGS_INTERNAS = re.compile(r"<(thinking|antml:thinking)>.*?</\1>", re.DOTALL | re.IGNORECASE)


def _limpar_tags(texto: str) -> str:
    return _TAGS_INTERNAS.sub("", texto).strip()


class Provedor(Protocol):
    """`(prompt, modelo, temperatura) -> (texto, telemetria)` — o contrato do `_chamar_ollama`."""

    nome: str

    def __call__(self, prompt: str, modelo: str,
                 temperatura: float) -> tuple[str, dict]: ...


# --------------------------------------------------------------------------------------------
# Ollama — o caminho das Fases 0–16, intocado
# --------------------------------------------------------------------------------------------
@dataclass
class ProvedorOllama:
    """Delegação pura para `_chamar_ollama`. Existe para dar uma interface, não comportamento."""

    nome: str = "ollama"

    def __call__(self, prompt: str, modelo: str, temperatura: float) -> tuple[str, dict]:
        return _chamar_ollama(prompt, modelo, temperatura)


# --------------------------------------------------------------------------------------------
# Anthropic API
# --------------------------------------------------------------------------------------------
def _carregar_env(caminho: Path | None = None) -> None:
    """Lê `.env` para `os.environ` sem depender de python-dotenv.

    O `Settings` do projeto usa `env_prefix='RODOQUERY_'` e ignora tudo mais, então a chave da
    Anthropic não passaria por lá. O SDK lê `ANTHROPIC_API_KEY` do ambiente — este helper só
    garante que o `.env` (gitignorado) chegue nele. Variável já exportada TEM precedência.
    """
    env = caminho or (Path(__file__).resolve().parents[2] / ".env")
    if not env.exists():
        return
    for linha in env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip("'\""))


@dataclass
class ProvedorAnthropic:
    """SUT via API da Anthropic, com prompt caching e contabilidade de custo por chamada.

    **O corte do prompt não é cosmético.** O `PROMPT` congelado do projeto termina em
    `Pergunta: {pergunta}\\nJSON:` — instrução + catálogo formam um prefixo IDÊNTICO nas 186
    chamadas e só os últimos ~38 tokens variam. Mando o prefixo em `system` com
    `cache_control` e a pergunta no turno do usuário: a concatenação é byte a byte o mesmo texto
    que o Ollama recebeu, mas o prefixo passa a custar 0,10x a partir da 2ª chamada. Medido na
    telemetria congelada: ~750 dos ~788 tokens de cada prompt são esse prefixo.

    Se o corte falhar (marcador ausente), mando o prompt inteiro como turno de usuário — mais
    caro, nunca errado. Prefiro degradar o custo a degradar a fidelidade do prompt.
    """

    nome: str = "anthropic"
    modelo_padrao: str = MODELO_API_PADRAO
    # `disabled` + effort baixo mantém o custo no orçamento (a tarefa é extração estruturada de
    # vocabulário fechado, não raciocínio aberto). Configurável porque é uma hipótese a testar,
    # não um dogma: `pensar=True` liga o adaptive thinking.
    pensar: bool = False
    esforco: str = "low"
    max_tokens: int = 512     # a spec mais longa medida no Qwen tem 93 tokens; 512 é folga 5x
    _cliente: object | None = field(default=None, repr=False)
    # Acumuladores da execução inteira — é o que fecha o relatório de custo no fim.
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tokens_cache_escrita: int = 0
    tokens_cache_leitura: int = 0
    custo_usd: float = 0.0
    chamadas: int = 0

    _MARCADOR = "\nPergunta: "

    def __post_init__(self) -> None:
        if self._cliente is None:
            _carregar_env()
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError(
                    "ANTHROPIC_API_KEY ausente. Coloque a chave em ~/rodoquery/.env "
                    "(gitignorado) na forma ANTHROPIC_API_KEY=sk-ant-... ou exporte-a."
                )
            import anthropic  # import tardio: o caminho Ollama não deve exigir o SDK
            self._cliente = anthropic.Anthropic()

    def _partir(self, prompt: str) -> tuple[str, str]:
        """(prefixo estável p/ cache, sufixo variável). Concatenados == prompt original."""
        i = prompt.rfind(self._MARCADOR)
        if i == -1:
            return "", prompt
        return prompt[:i], prompt[i:]

    def __call__(self, prompt: str, modelo: str, temperatura: float) -> tuple[str, dict]:
        # `temperatura` é aceita e IGNORADA: Claude >= 4.7 rejeita o parâmetro com HTTP 400.
        # Não é omissão — é a decisão (2) do módulo, e o chamador não precisa saber disso.
        modelo = modelo if modelo in PRECOS else self.modelo_padrao
        prefixo, sufixo = self._partir(prompt)

        corpo: dict = {
            "model": modelo,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": sufixo}],
        }
        if prefixo:
            corpo["system"] = [{
                "type": "text", "text": prefixo,
                "cache_control": {"type": "ephemeral"},
            }]
        if self.pensar:
            corpo["thinking"] = {"type": "adaptive"}
            corpo["output_config"] = {"effort": self.esforco}
        else:
            # `disabled` só é aceito com effort <= high no Opus 5; `low` está dentro.
            corpo["thinking"] = {"type": "disabled"}
            corpo["output_config"] = {"effort": self.esforco}

        t0 = time.perf_counter()
        resp = self._cliente.messages.create(**corpo)
        latencia = round(time.perf_counter() - t0, 3)

        texto = _limpar_tags(
            "".join(b.text for b in resp.content if getattr(b, "type", None) == "text"))

        u = resp.usage
        ent = u.input_tokens or 0
        sai = u.output_tokens or 0
        c_w = getattr(u, "cache_creation_input_tokens", 0) or 0
        c_r = getattr(u, "cache_read_input_tokens", 0) or 0
        custo = PRECOS[modelo].custo(ent, sai, c_w, c_r)

        self.tokens_entrada += ent
        self.tokens_saida += sai
        self.tokens_cache_escrita += c_w
        self.tokens_cache_leitura += c_r
        self.custo_usd += custo
        self.chamadas += 1

        telemetria = {
            "latencia_s": latencia,
            # MESMAS chaves do Ollama: `tokens_prompt` soma tudo que foi processado como entrada
            # (fresco + escrita + leitura de cache), senão o total do relatório mentiria para menos.
            "tokens_prompt": ent + c_w + c_r,
            "tokens_saida": sai,
            "eval_s": latencia,
            "carga_modelo_s": 0.0,
            # extras do caminho API (o Ollama não tem equivalente)
            "tokens_cache_escrita": c_w,
            "tokens_cache_leitura": c_r,
            "custo_usd": round(custo, 6),
            "stop_reason": resp.stop_reason,
        }
        return texto, telemetria

    def relatorio(self) -> dict:
        """Fecha a conta da execução. É o que vai para o report e para a decisão de gastar mais."""
        return {
            "provedor": self.nome,
            "modelo": self.modelo_padrao,
            "chamadas": self.chamadas,
            "tokens_entrada_frescos": self.tokens_entrada,
            "tokens_cache_escrita": self.tokens_cache_escrita,
            "tokens_cache_leitura": self.tokens_cache_leitura,
            "tokens_saida": self.tokens_saida,
            "custo_usd": round(self.custo_usd, 4),
            "custo_usd_por_chamada": round(self.custo_usd / self.chamadas, 6)
            if self.chamadas else 0.0,
        }


def obter_provedor(nome: str | None = None, **kw) -> Provedor:
    """`None` ou 'ollama' → o caminho local intocado. 'anthropic' → API (exige chave).

    O default é deliberadamente o local: nenhum caminho de código gasta crédito por acidente.
    """
    nome = (nome or "ollama").lower()
    if nome == "ollama":
        return ProvedorOllama()
    if nome == "anthropic":
        return ProvedorAnthropic(**kw)
    raise ValueError(f"provedor desconhecido: {nome!r} (use 'ollama' ou 'anthropic')")


def estimar_custo(modelo: str, n_itens: int, tokens_prompt_medio: float,
                  tokens_saida_medio: float, tokens_prefixo: int,
                  fator_tokenizer: float = 1.35) -> dict:
    """Estimativa ANTES de gastar, a partir da telemetria congelada do Qwen.

    `fator_tokenizer` converte tokens do Qwen para tokens da Claude. 1,35 é o pior caso
    documentado pela Anthropic para o tokenizer novo — margem de segurança, não previsão.
    """
    p = PRECOS[modelo]
    prefixo = round(tokens_prefixo * fator_tokenizer)
    variavel = round((tokens_prompt_medio - tokens_prefixo) * fator_tokenizer)
    saida = round(tokens_saida_medio * fator_tokenizer)
    cacheia = prefixo >= p.minimo_cache

    if cacheia:
        custo = p.custo(entrada=variavel * n_itens, saida=saida * n_itens,
                        cache_w=prefixo, cache_r=prefixo * (n_itens - 1))
    else:
        custo = p.custo(entrada=(prefixo + variavel) * n_itens, saida=saida * n_itens)

    return {
        "modelo": modelo, "n_itens": n_itens,
        "tokens_prefixo_claude": prefixo, "cacheia": cacheia,
        "minimo_cache": p.minimo_cache,
        "custo_usd_estimado": round(custo, 4),
        "fator_tokenizer": fator_tokenizer,
    }
