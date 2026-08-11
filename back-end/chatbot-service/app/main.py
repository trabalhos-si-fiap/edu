from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from loguru import logger

from app.dependencies import get_current_user
from app.rag import RagIndisponivelError, inicializar_index, responder
from app.routers import suporte
from app.schemas import ExplicacaoOut, ExplicarQuestaoIn, MensagemIn, MensagemOut
from app.services.diagnostico_client import DiagnosticoContextoError, buscar_contexto_questao
from app.services.explicacao_questao import explicar_questao


@asynccontextmanager
async def lifespan(app: FastAPI):
    # inicializar_index() nunca propaga exceção (ver rag.py) — se o
    # modelo de embeddings não puder ser carregado, o serviço sobe do
    # mesmo jeito, só com /chat/ask temporariamente indisponível (ver
    # tratamento de RagIndisponivelError abaixo). /chat/explain-question
    # não depende deste índice e continua funcionando normalmente.
    inicializar_index()
    yield


app = FastAPI(title="Chatbot Service", lifespan=lifespan)
app.include_router(suporte.router)


@app.post("/chat/ask", response_model=MensagemOut)
async def chat_ask(
    payload: MensagemIn,
    _user: dict = Depends(get_current_user),
) -> MensagemOut:
    """Assistente genérico (RAG estático) — dúvidas de suporte (frete,
    troca, etc.), sem contexto pessoal do aluno. Autenticado: cada chamada
    aciona uma consulta paga ao provedor de LLM (Groq), então um endpoint
    anônimo seria um vetor de dreno de custo aberto pra internet inteira —
    todo chamador deste produto já está logado, então não há necessidade
    de deixar isso público (diferente de /auth/login, que precisa ficar
    aberto porque autentica quem ainda não tem sessão). `_user` não é
    usado além da checagem de auth: esta rota não consulta nem revela
    nenhum dado pessoal do aluno."""
    try:
        resposta = await responder(payload.pergunta)
    except RagIndisponivelError:
        raise HTTPException(
            status_code=503,
            detail="Assistente temporariamente indisponível. Tente novamente em instantes.",
        ) from None
    except Exception as exc:
        # Cobre qualquer falha do provedor de LLM (Groq): API key ausente
        # ou inválida, timeout, rate limit, erro de rede. Nunca deixa a
        # exceção crua (que pode citar detalhes internos do provedor)
        # vazar pro corpo da resposta como um 500 — sempre um 503 limpo.
        # Só a CLASSE do erro vai pro log, nunca a mensagem crua (poderia
        # ecoar cabeçalhos/payload da chamada ao provedor).
        logger.warning(f"Falha ao consultar o provedor de LLM em /chat/ask: {type(exc).__name__}")
        raise HTTPException(
            status_code=503,
            detail="Assistente temporariamente indisponível. Tente novamente em instantes.",
        ) from exc
    return MensagemOut(resposta=resposta)


@app.post("/chat/explain-question", response_model=ExplicacaoOut)
async def chat_explain_question(
    payload: ExplicarQuestaoIn,
    user: dict = Depends(get_current_user),
) -> ExplicacaoOut:
    """
    Explica por que o aluno errou (ou acertou) uma questão específica —
    conecta o Chatbot Service ao contexto real do diagnóstico, buscando
    enunciado/gabarito/resposta do aluno no Learning Service antes de
    perguntar ao LLM. Requer autenticação: só explica questões que o
    próprio aluno logado já respondeu (validado no Learning Service, que
    recebe o MESMO token do aluno — autenticação encadeada, ver
    app/dependencies.py e app/services/diagnostico_client.py).
    """
    try:
        contexto = await buscar_contexto_questao(payload.questao_id, user["raw_token"])
    except DiagnosticoContextoError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        explicacao = await explicar_questao(contexto)
    except Exception as exc:
        logger.warning(
            f"Falha ao gerar explicação via LLM em /chat/explain-question: {type(exc).__name__}"
        )
        raise HTTPException(
            status_code=503,
            detail="Não foi possível gerar a explicação no momento. Tente novamente em instantes.",
        ) from exc

    return ExplicacaoOut(
        questao_id=contexto["questao_id"],
        acertou=contexto["acertou"],
        explicacao=explicacao,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
