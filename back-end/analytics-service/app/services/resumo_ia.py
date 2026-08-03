"""
Geração do resumo executivo do dashboard via LLM (Groq) — mesmo padrão já
validado em `tutor_llm.py` no Learning Service: o LLM recebe métricas JÁ
CALCULADAS (contagens, agregações) e só as narra em linguagem natural para
o admin. Nunca inventa números novos, nunca decide nada — só traduz dado
estruturado em texto legível para um dashboard.

Se a chamada ao Groq falhar por qualquer motivo (sem API key, timeout,
rate limit), cai automaticamente em `gerar_resumo_fallback` — um template
determinístico. O campo `resumo_executivo` na resposta de
`GET /analytics/resumo-executivo` nunca é nulo.
"""

from groq import AsyncGroq

from app.config import settings

_client: AsyncGroq | None = None

MODELO = "llama-3.1-8b-instant"

PROMPT_SISTEMA = (
    "Você escreve resumos executivos curtos (3 a 5 frases) para o painel "
    "administrativo de uma plataforma educacional com marketplace "
    "integrado. Você recebe métricas JÁ CALCULADAS de um período e "
    "resume em linguagem natural, direta e profissional — sem "
    "saudação, sem markdown.\n\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Use APENAS os números fornecidos — nunca invente métricas ou "
    "compare com períodos que não estejam nos dados.\n"
    "2. Destaque o que mais chama atenção (maior contagem, alguma "
    "métrica zerada ou incomum), mas sem especular a causa.\n"
    "3. Se houver ocorrências não resolvidas, mencione isso como ponto "
    "de atenção.\n"
    "4. Responda em português do Brasil."
)


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key, timeout=8.0)
    return _client


def _montar_prompt_usuario(contexto: dict) -> str:
    linhas = [f"Período: últimos {contexto['periodo_dias']} dias", ""]

    linhas.append(f"Pedidos criados: {contexto['pedidos_criados']}")
    if contexto["pedidos_por_status"]:
        linhas.append("Pedidos por status:")
        for status, total in contexto["pedidos_por_status"].items():
            linhas.append(f"  - {status}: {total}")

    linhas.append(f"Ocorrências abertas: {contexto['ocorrencias_abertas']}")
    linhas.append(f"Ocorrências resolvidas: {contexto['ocorrencias_resolvidas']}")

    if contexto["diagnosticos_por_acao"]:
        linhas.append("Diagnósticos concluídos por ação:")
        for acao, total in contexto["diagnosticos_por_acao"].items():
            linhas.append(f"  - {acao}: {total}")

    return "\n".join(linhas)


async def gerar_resumo_executivo(contexto: dict) -> str | None:
    """Retorna o resumo gerado pelo LLM, ou None se a chamada falhar —
    o chamador DEVE tratar None com `gerar_resumo_fallback`."""
    if not settings.groq_api_key:
        return None

    try:
        client = _get_client()
        resposta = await client.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": PROMPT_SISTEMA},
                {"role": "user", "content": _montar_prompt_usuario(contexto)},
            ],
            temperature=0.5,
            max_tokens=220,
        )
        texto = resposta.choices[0].message.content
        return texto.strip() if texto else None
    except Exception:
        return None


def gerar_resumo_fallback(contexto: dict) -> str:
    """Template determinístico, usado quando o Groq não está configurado
    ou a chamada falha — garante que `resumo_executivo` nunca fica vazio."""
    partes = [
        f"Nos últimos {contexto['periodo_dias']} dias foram registrados "
        f"{contexto['pedidos_criados']} pedidos."
    ]

    if contexto["ocorrencias_abertas"] > 0:
        partes.append(
            f"Há {contexto['ocorrencias_abertas']} ocorrência(s) ainda aguardando decisão do aluno."
        )
    else:
        partes.append("Não há ocorrências em aberto no momento.")

    if contexto["diagnosticos_por_acao"]:
        total_diagnosticos = sum(contexto["diagnosticos_por_acao"].values())
        partes.append(f"Foram concluídos {total_diagnosticos} diagnósticos no período.")

    return " ".join(partes)
