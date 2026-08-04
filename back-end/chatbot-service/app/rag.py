"""
RAG simples: indexa uma base de conhecimento estática (FAQ + resumos de
subtemas + política de troca/entrega) em FAISS, e usa a Groq API como LLM
para responder com base no contexto recuperado.

Esse é o esqueleto funcional pro MVP — a base de conhecimento em
BASE_CONHECIMENTO abaixo deve ser expandida pelo time com o conteúdo real
(FAQ de suporte, resumos por subtema, políticas do marketplace).
"""

import faiss
from groq import AsyncGroq
from loguru import logger
from sentence_transformers import SentenceTransformer

from app.config import settings

_modelo_embeddings: SentenceTransformer | None = None
_index: faiss.Index | None = None
_documentos: list[str] = []
_indisponivel = False  # True se a última tentativa de carregar o modelo falhou

# Base de conhecimento inicial — expandir com conteúdo real do time.
BASE_CONHECIMENTO = [
    "O prazo médio de entrega dos materiais didáticos é de 5 a 7 dias úteis.",
    "Trocas de material com defeito podem ser solicitadas em até 7 dias após o recebimento.",
    "O diagnóstico adaptativo usa questões do ENEM para identificar lacunas de aprendizado.",
    "A revisão espaçada é agendada automaticamente com base no desempenho do aluno.",
    "O aluno pode acompanhar o status do pedido na tela de rastreio do marketplace.",
]


class RagIndisponivelError(Exception):
    """O índice/modelo de embeddings não pôde ser carregado (sem internet
    na primeira execução, huggingface.co indisponível, etc.)."""


def _get_modelo_embeddings() -> SentenceTransformer:
    global _modelo_embeddings
    if _modelo_embeddings is None:
        _modelo_embeddings = SentenceTransformer("all-MiniLM-L6-v2")
    return _modelo_embeddings


def inicializar_index() -> None:
    """
    Constrói o índice FAISS a partir da base de conhecimento em memória.

    IMPORTANTE (achado testando de verdade, não uma precaução teórica):
    esta função é chamada no `lifespan` da aplicação — se ela levantar uma
    exceção sem tratamento ali, o Uvicorn/Granian recusa subir o processo
    INTEIRO, derrubando não só o assistente genérico (`/chat/ask`) mas
    também `/chat/explain-question`, que nem depende deste índice. Por isso
    essa função nunca propaga exceção: registra a falha em `_indisponivel`
    (e no log, para diagnóstico) e deixa quem chama (`buscar_contexto`)
    decidir o que fazer.
    """
    global _index, _documentos, _indisponivel
    try:
        modelo = _get_modelo_embeddings()
        _documentos = BASE_CONHECIMENTO
        embeddings = modelo.encode(_documentos, convert_to_numpy=True)

        dimensao = embeddings.shape[1]
        _index = faiss.IndexFlatL2(dimensao)
        _index.add(embeddings)
        _indisponivel = False
    except Exception as exc:
        # Nunca logar `exc` bruto sem checar: aqui é seguro (falha de
        # carregamento de modelo/índice, sem dado sensível envolvido), mas
        # o padrão do serviço é logar só a classe do erro nos pontos que
        # tocam segredo (ver app/main.py).
        logger.warning(f"Falha ao inicializar o índice FAISS: {type(exc).__name__}")
        _indisponivel = True


def buscar_contexto(pergunta: str, top_k: int = 3) -> list[str]:
    if _index is None:
        inicializar_index()

    if _indisponivel or _index is None:
        raise RagIndisponivelError(
            "Índice de conhecimento indisponível no momento (falha ao "
            "carregar o modelo de embeddings)."
        )

    modelo = _get_modelo_embeddings()
    embedding_pergunta = modelo.encode([pergunta], convert_to_numpy=True)
    _, indices = _index.search(embedding_pergunta, top_k)

    return [_documentos[i] for i in indices[0] if i < len(_documentos)]


async def responder(pergunta: str) -> str:
    contexto = buscar_contexto(pergunta)  # propaga RagIndisponivelError, tratado no endpoint
    contexto_texto = "\n".join(f"- {c}" for c in contexto)

    prompt_sistema = (
        "Você é o assistente virtual do Edu, uma plataforma educacional "
        "brasileira. Responda de forma clara e objetiva, usando apenas o "
        "contexto fornecido. Se não souber a resposta, diga que vai "
        "encaminhar para o suporte humano."
    )

    # Falha do provedor (GROQ_API_KEY ausente/inválida, timeout, rate
    # limit) propaga daqui pra cima sem tratamento — app.main.chat_ask
    # é quem converte qualquer exceção num 503 limpo, nunca um 500 cru.
    client = AsyncGroq(api_key=settings.groq_api_key, timeout=10.0)
    completion = await client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": prompt_sistema},
            {
                "role": "user",
                "content": f"Contexto:\n{contexto_texto}\n\nPergunta: {pergunta}",
            },
        ],
        temperature=0.3,
    )

    return completion.choices[0].message.content
