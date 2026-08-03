"""
Explicação de uma questão específica via LLM (Groq), usando o contexto
real buscado no Learning Service (enunciado, alternativas, gabarito, e a
alternativa que o próprio aluno escolheu) — diferente do RAG genérico em
`rag.py`, que usa uma base de conhecimento estática para perguntas gerais
de suporte (frete, troca, etc.).

IMPORTANTE — trade-off consciente, diferente de `tutor_llm.py` no
Learning Service: aqui o LLM PRECISA explicar o conceito de Biologia por
trás da resposta certa, o que usa o conhecimento próprio do modelo, não
só dados estruturados fornecidos. Existe risco real de alucinação
factual sobre o conteúdo — diferente da mensagem do tutor (que só
reescreve números já calculados, sem explicar conceitos). Mitigamos
restringindo o prompt a citar a alternativa correta literalmente e
pedindo concisão, mas isso não elimina o risco por completo. Documentado
aqui de propósito, não escondido — para questões de alto risco (ex:
provas valendo nota), recomenda-se revisão humana do conteúdo gerado.
"""

from groq import AsyncGroq

from app.config import settings

_client: AsyncGroq | None = None

MODELO = "llama-3.1-8b-instant"

PROMPT_SISTEMA = (
    "Você é um tutor de Biologia brasileiro, paciente e didático. Você "
    "recebe uma questão de múltipla escolha, a alternativa correta e a "
    "alternativa que o aluno escolheu, e explica em 3 a 5 frases por que "
    "a alternativa correta está certa e, se o aluno errou, por que a "
    "escolha dele não está correta.\n\n"
    "REGRAS:\n"
    "1. Cite a alternativa correta pelo texto dela, não só pela letra.\n"
    "2. Se o aluno acertou, parabenize brevemente e reforce o conceito.\n"
    "3. Seja didático mas conciso — o aluno já viu a questão, não repita "
    "o enunciado inteiro.\n"
    "4. Responda em português do Brasil, sem markdown, sem saudação "
    "genérica de abertura."
)


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key, timeout=10.0)
    return _client


def _montar_prompt_usuario(contexto: dict) -> str:
    alternativas_texto = "\n".join(
        f"{letra}) {texto}" for letra, texto in contexto["alternativas"].items()
    )
    return (
        f"Questão (assunto: {contexto['subtema_nome']}):\n"
        f"{contexto['enunciado']}\n\n"
        f"Alternativas:\n{alternativas_texto}\n\n"
        f"Alternativa correta: {contexto['gabarito']}\n"
        f"Alternativa escolhida pelo aluno: {contexto['alternativa_escolhida']}\n"
        f"O aluno {'acertou' if contexto['acertou'] else 'errou'}."
    )


async def explicar_questao(contexto: dict) -> str:
    """
    Gera a explicação via LLM. Diferente de
    `tutor_llm.gerar_mensagem_tutor` no Learning Service, NÃO há fallback
    de template local aqui — explicar o "porquê" de um conceito de
    Biologia exige o LLM; um template genérico não teria conteúdo
    pedagógico de verdade para oferecer. Se o Groq falhar, a exceção
    propaga para o endpoint decidir como informar o aluno (ver main.py).
    """
    client = _get_client()
    resposta = await client.chat.completions.create(
        model=MODELO,
        messages=[
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": _montar_prompt_usuario(contexto)},
        ],
        temperature=0.4,
        max_tokens=280,
    )
    texto = resposta.choices[0].message.content
    if not texto:
        raise RuntimeError("O modelo não retornou conteúdo")
    return texto.strip()
