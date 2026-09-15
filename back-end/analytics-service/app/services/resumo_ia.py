"""
Geração do resumo executivo do dashboard via LLM (Groq) — mesmo padrão já
validado em `tutor_llm.py` no Learning Service: o LLM recebe métricas JÁ
CALCULADAS (contagens, agregações) e só as narra em linguagem natural para
o admin. Nunca inventa números novos, nunca decide nada — só traduz dado
estruturado em texto legível para um dashboard.

Se a chamada ao Groq falhar por qualquer motivo (sem API key, timeout,
rate limit), cai automaticamente em `gerar_resumo_fallback` — um template
determinístico. O campo `resumo_executivo` na resposta de
`GET /analytics/executive-summary` nunca é nulo.
"""

from groq import AsyncGroq

from app.config import settings

_client: AsyncGroq | None = None

# `llama-3.1-8b-instant` saiu do Groq (404 `model_not_found` em 2026-09-13).
# `gpt-oss-20b` é modelo de raciocínio: a chamada passa
# `reasoning_effort="low"`, senão o raciocínio consome o `max_tokens` e o
# conteúdo volta vazio.
MODELO = "openai/gpt-oss-20b"

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
    '4. Use a palavra "ocorrência" só para as ocorrências abertas e '
    "resolvidas. As passagens por etapa são pedidos chegando a uma etapa "
    "do fluxo, não ocorrências — e não as compare com os pedidos criados.\n"
    "5. Responda em português do Brasil."
)


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key, timeout=8.0)
    return _client


# O modelo repete no texto o que recebe: código cru no prompt vira código cru
# no painel. Código desconhecido passa como veio, em vez de sumir.
ROTULO_STATUS = {
    "CRIADO": "Criado",
    "CONFIRMADO": "Pagamento confirmado",
    "AGUARDANDO_SEPARACAO": "Aguardando separação",
    "EM_SEPARACAO": "Em separação",
    "AGUARDANDO_SUBSTITUICAO": "Aguardando decisão do aluno sobre substituição",
    "SEPARADO": "Separado",
    "AGUARDANDO_COLETA": "Aguardando coleta",
    "EM_TRANSITO": "Em trânsito",
    "ENTREGUE": "Entregue",
    "CANCELADO": "Cancelado",
}

ROTULO_ACAO = {
    "estudar": "Estudar o tema de novo",
    "avancar": "Avançar para o próximo tema",
    "retroceder": "Voltar ao tema anterior",
}


def _montar_prompt_usuario(contexto: dict) -> str:
    linhas = [f"Período: últimos {contexto['periodo_dias']} dias", ""]

    linhas.append(f"Pedidos criados: {contexto['pedidos_criados']}")
    if contexto["pedidos_por_status"]:
        # A contagem vem de `order.status_changed` no período: um pedido conta
        # em cada etapa por onde passou, de novo se voltar a ela (a separação
        # depois de uma substituição), e conta mesmo tendo sido criado antes
        # do período. Não é "pedidos por status" nem se compara com criados.
        linhas.append(
            "Passagens de pedidos por etapa no período (um pedido conta em cada etapa "
            "por onde passou, e quem volta a ela conta de novo; inclui pedidos "
            "criados antes do período):"
        )
        for status, total in contexto["pedidos_por_status"].items():
            linhas.append(f"  - {ROTULO_STATUS.get(status, status)}: {total}")

    linhas.append(f"Ocorrências abertas: {contexto['ocorrencias_abertas']}")
    linhas.append(f"Ocorrências resolvidas: {contexto['ocorrencias_resolvidas']}")

    if contexto["diagnosticos_por_acao"]:
        linhas.append("Diagnósticos concluídos, pela recomendação dada ao aluno:")
        for acao, total in contexto["diagnosticos_por_acao"].items():
            linhas.append(f"  - {ROTULO_ACAO.get(acao, acao)}: {total}")

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
            reasoning_effort="low",
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
