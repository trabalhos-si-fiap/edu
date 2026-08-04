"""
Geração da mensagem personalizada do tutor via LLM (Groq).

IMPORTANTE — separação de responsabilidades: o LLM NUNCA decide nota,
domínio ou ação (estudar/avançar/retroceder). Isso continua 100%
determinístico, calculado em `services/decisao.py` e `services/dominio.py`
ANTES de chegar aqui. O papel do LLM é só reescrever esse resultado já
pronto numa mensagem em tom de tutor — não gerar fatos novos sobre o
conteúdo (evita risco de alucinação sobre Biologia/ENEM).

Se a chamada ao Groq falhar por qualquer motivo (sem API key configurada,
timeout, rate limit, erro do provedor), `gerar_mensagem_tutor` retorna
None e o chamador usa `gerar_mensagem_fallback` — o diagnóstico nunca
quebra nem fica sem mensagem só porque o LLM está indisponível.
"""

from groq import AsyncGroq

from app.config import settings

_client: AsyncGroq | None = None

MODELO = "llama-3.1-8b-instant"

PROMPT_SISTEMA = (
    "Você é um tutor educacional brasileiro, gentil, direto e específico. "
    "Você recebe o resultado JÁ CALCULADO do diagnóstico de um aluno "
    "(domínio por assunto, o que ele deve fazer a seguir) e escreve uma "
    "mensagem curta (3 a 5 frases) em tom de tutor, encorajador mas "
    "honesto sobre os pontos fracos.\n\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Use APENAS os dados fornecidos no contexto — nunca invente fatos "
    "novos sobre Biologia ou qualquer outro conteúdo, nem explique "
    "conceitos que não estejam no contexto.\n"
    "2. Não repita números brutos (ex: '0.45') — traduza em linguagem "
    "natural (ex: 'ainda precisa de reforço nesse assunto').\n"
    "3. Cite pelo menos um ponto forte e um ponto a melhorar pelo nome, "
    "se existirem nos dados.\n"
    "4. Termine com uma orientação clara e acionável do próximo passo.\n"
    "5. Responda em português do Brasil, sem markdown, sem saudação "
    "genérica de abertura (vá direto ao ponto)."
)


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key, timeout=8.0)
    return _client


def _montar_prompt_usuario(contexto: dict) -> str:
    linhas = [
        f"Tema avaliado: {contexto['tema_nome']}",
        f"Ação decidida pelo sistema: {contexto['acao']}",
    ]

    if contexto.get("tema_recomendado"):
        linhas.append(f"Tema sugerido em seguida: {contexto['tema_recomendado']}")

    linhas.append("Desempenho por assunto dentro do tema:")
    for s in contexto["subtemas"]:
        rotulo = {
            "dominado": "bom domínio",
            "revisar": "domínio parcial, precisa de revisão",
            "estudar_do_zero": "lacuna importante, precisa estudar do zero",
        }.get(s["classificacao"], s["classificacao"])
        linhas.append(f"- {s['nome']}: {rotulo}")

    return "\n".join(linhas)


async def gerar_mensagem_tutor(contexto: dict) -> str | None:
    """
    Retorna uma mensagem em tom de tutor gerada pelo LLM a partir do
    `contexto` (ver `_montar_prompt_usuario` para o formato esperado), ou
    None se a chamada falhar — o chamador DEVE tratar None com
    `gerar_mensagem_fallback`.
    """
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
            temperature=0.6,
            max_tokens=220,
        )
        texto = resposta.choices[0].message.content
        return texto.strip() if texto else None
    except Exception:
        # Cobre timeout, rate limit, erro de rede, resposta malformada etc.
        # — qualquer falha aqui degrada para o fallback local, nunca
        # propaga um 500 para o aluno só porque o provedor de LLM falhou.
        return None


def gerar_mensagem_fallback(contexto: dict) -> str:
    """
    Mensagem determinística (sem LLM), usada quando o Groq não está
    configurado ou a chamada falha. Não é tão natural quanto a versão
    gerada, mas garante que o campo `mensagem_tutor` nunca fica vazio.
    """
    acao = contexto["acao"]
    subtemas = contexto["subtemas"]

    fracos = [s["nome"] for s in subtemas if s["classificacao"] == "estudar_do_zero"]
    parciais = [s["nome"] for s in subtemas if s["classificacao"] == "revisar"]
    fortes = [s["nome"] for s in subtemas if s["classificacao"] == "dominado"]

    partes = []
    if fortes:
        partes.append(f"Você mostrou bom domínio em {', '.join(fortes)}.")
    if parciais:
        partes.append(f"Vale revisar {', '.join(parciais)}.")
    if fracos:
        partes.append(f"Recomendamos estudar do zero: {', '.join(fracos)}.")

    if acao == "avancar":
        destino = contexto.get("tema_recomendado")
        partes.append(
            f"Você já pode avançar para o próximo tema{f': {destino}' if destino else ''}."
        )
    elif acao == "retroceder":
        destino = contexto.get("tema_recomendado")
        partes.append(
            f"Recomendamos revisar antes o tema pré-requisito{f': {destino}' if destino else ''}."
        )
    else:
        partes.append("Continue estudando os pontos indicados antes de avançar.")

    return " ".join(partes)
