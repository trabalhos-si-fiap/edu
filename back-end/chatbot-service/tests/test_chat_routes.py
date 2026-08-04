"""Contrato e segurança de `/chat/ask` e `/chat/explain-question`.

Cobre: 401 vs 403 (contrato do gateway/refresh do Flutter), que AMBAS as
rotas exigem sessão (nenhuma delas é o caso "quem ainda não tem token" de
/auth/login — todo chamador deste produto já está logado, e /chat/ask
aciona uma chamada paga por request, então anônimo seria um vetor de
dreno de custo), a autenticação encadeada com o Learning Service (o
motivo de `raw_token` existir), que o token do aluno nunca aparece no
corpo da resposta, que os paths antigos em português sumiram, que o
input tem limite de tamanho, e que uma falha do provedor de LLM (Groq)
nunca vaza como 500 cru.
"""

from types import SimpleNamespace

from edu_common.security import create_access_token, create_refresh_token

from app.config import settings
from app.rag import RagIndisponivelError
from app.services.diagnostico_client import DiagnosticoContextoError

ALUNO_ID = "00000000-0000-0000-0000-000000000001"


def student_headers() -> dict[str, str]:
    token = create_access_token(ALUNO_ID, "student", settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def contexto_questao_fake(questao_id: int = 5, acertou: bool = False) -> dict:
    """Formato real de `QuestaoContextoOut`
    (back-end/learning-service/app/schemas/diagnostico.py) — usado nos
    testes que deixam `explicar_questao` (real) rodar contra o Groq
    stubado (ver `no_real_groq_calls` em conftest.py), então precisa ter
    todas as chaves que `_montar_prompt_usuario` acessa.
    """
    return {
        "questao_id": questao_id,
        "enunciado": "Qual organela realiza a fotossíntese?",
        "alternativas": {"A": "Cloroplasto", "B": "Mitocôndria"},
        "gabarito": "A",
        "alternativa_escolhida": "B",
        "acertou": acertou,
        "subtema_nome": "Citologia",
        "tema_nome": "Biologia Celular",
    }


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_explain_question_requires_authentication(client):
    response = await client.post("/chat/explain-question", json={"questao_id": 5})
    assert response.status_code == 403


async def test_explain_question_rejects_invalid_token(client):
    response = await client.post(
        "/chat/explain-question",
        json={"questao_id": 5},
        headers={"Authorization": "Bearer lixo"},
    )
    assert response.status_code == 401


async def test_explain_question_rejects_a_refresh_token(client):
    token = create_refresh_token(ALUNO_ID, "student", settings.jwt_secret)
    response = await client.post(
        "/chat/explain-question",
        json={"questao_id": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


async def test_explain_question_forwards_the_students_token_to_learning(client, monkeypatch):
    """`/chat/explain-question` precisa repassar o MESMO token do aluno na
    chamada ao Learning Service — é o Learning Service quem só libera o
    gabarito se ESTE aluno já respondeu ESTA questão (ver
    app/services/diagnostico_client.py). Sem isso, trocar o token
    encadeado por uma credencial de serviço deixaria qualquer aluno ler o
    gabarito de qualquer questão.

    O alvo do monkeypatch é `app.main.buscar_contexto_questao` — onde
    `app/main.py` importou o nome (`from app.services.diagnostico_client
    import buscar_contexto_questao`) — não
    `app.services.diagnostico_client.buscar_contexto_questao` (onde a
    função é DEFINIDA). `from x import y` copia a referência para o
    namespace de quem importa; remendar a origem depois não afeta essa
    cópia. Ver a mesma pegadinha documentada para `publish_event` na
    Recipe C do plano de migração.
    """
    captured = {}

    async def fake_get_context(questao_id: int, raw_token: str) -> dict:
        captured["questao_id"] = questao_id
        captured["token"] = raw_token
        return contexto_questao_fake(questao_id)

    monkeypatch.setattr("app.main.buscar_contexto_questao", fake_get_context, raising=True)

    headers = student_headers()
    sent_token = headers["Authorization"].removeprefix("Bearer ")

    response = await client.post("/chat/explain-question", json={"questao_id": 5}, headers=headers)

    assert response.status_code == 200
    assert captured["questao_id"] == 5
    assert captured["token"], "o token do aluno não foi repassado ao learning-service"
    assert captured["token"] == sent_token


async def test_explain_question_response_never_leaks_the_raw_token(client, monkeypatch):
    """`ExplicacaoOut` só declara `questao_id`/`acertou`/`explicacao` — mas
    isso é garantido pelo schema, não por acidente. Trava explícita para
    que ninguém troque `response_model=ExplicacaoOut` por um dict solto
    (ex.: `return {**contexto, **user}`) sem que um teste acuse.
    """

    async def fake_get_context(questao_id: int, raw_token: str) -> dict:
        return contexto_questao_fake(questao_id)

    monkeypatch.setattr("app.main.buscar_contexto_questao", fake_get_context, raising=True)

    headers = student_headers()
    sent_token = headers["Authorization"].removeprefix("Bearer ")

    response = await client.post("/chat/explain-question", json={"questao_id": 5}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"questao_id", "acertou", "explicacao"}
    assert sent_token not in response.text


async def test_explain_question_propagates_the_upstream_denial(client, monkeypatch):
    """Se o Learning Service recusar (aluno não respondeu essa questão
    ainda), o Chatbot Service precisa devolver o MESMO 403 ao cliente, não
    engolir num 502/500 genérico nem, pior, num 200 vazio."""

    async def fake_get_context(questao_id: int, raw_token: str) -> dict:
        raise DiagnosticoContextoError(
            "Você ainda não respondeu essa questão em nenhum diagnóstico", status_code=403
        )

    monkeypatch.setattr("app.main.buscar_contexto_questao", fake_get_context, raising=True)

    response = await client.post(
        "/chat/explain-question", json={"questao_id": 5}, headers=student_headers()
    )
    assert response.status_code == 403


async def test_explain_question_returns_a_clean_503_when_the_llm_fails(client, monkeypatch):
    """Falha do Groq ao gerar a explicação (rede, rate limit, etc.) precisa
    virar um 503 controlado — nunca um 500 cru com o traceback do SDK."""

    async def fake_get_context(questao_id: int, raw_token: str) -> dict:
        return contexto_questao_fake(questao_id)

    async def fake_explicar_falha(contexto: dict) -> str:
        raise RuntimeError("Groq indisponível (simulado no teste)")

    monkeypatch.setattr("app.main.buscar_contexto_questao", fake_get_context, raising=True)
    monkeypatch.setattr("app.main.explicar_questao", fake_explicar_falha, raising=True)

    response = await client.post(
        "/chat/explain-question", json={"questao_id": 5}, headers=student_headers()
    )
    assert response.status_code == 503
    assert "Groq indisponível" not in response.text


async def test_old_explain_question_portuguese_path_is_gone(client):
    response = await client.post(
        "/chat/explicar-questao", json={"questao_id": 5}, headers=student_headers()
    )
    assert response.status_code == 404


async def test_old_ask_portuguese_path_is_gone(client):
    response = await client.post("/chat/mensagem", json={"pergunta": "oi"})
    assert response.status_code == 404


async def test_ask_requires_authentication(client):
    """`/chat/ask` aciona uma chamada paga ao provedor de LLM por request —
    diferente de /auth/login (que precisa ficar aberto porque autentica
    quem ainda não tem sessão) ou /health, todo chamador deste produto já
    está logado, então deixar esta rota anônima seria um vetor de dreno de
    custo aberto pra internet inteira, sem ganho nenhum (nenhum caller
    legítimo se beneficia de não estar autenticado aqui)."""
    response = await client.post("/chat/ask", json={"pergunta": "Qual o prazo de entrega?"})
    assert response.status_code == 403


async def test_ask_returns_a_response_when_authenticated(client):
    response = await client.post(
        "/chat/ask", json={"pergunta": "Qual o prazo de entrega?"}, headers=student_headers()
    )
    assert response.status_code == 200
    assert response.json()["resposta"]


async def test_ask_rejects_an_oversized_pergunta(client):
    response = await client.post(
        "/chat/ask", json={"pergunta": "x" * 1001}, headers=student_headers()
    )
    assert response.status_code == 422


async def test_ask_rejects_an_empty_pergunta(client):
    response = await client.post("/chat/ask", json={"pergunta": ""}, headers=student_headers())
    assert response.status_code == 422


async def test_ask_returns_a_clean_503_when_the_embeddings_index_is_unavailable(
    client, monkeypatch
):
    """Distinto da falha de LLM abaixo: aqui é o índice FAISS/encoder que
    não pôde ser carregado (`RagIndisponivelError`, ver app/rag.py) — o
    caminho tratado pelo primeiro `except` de `chat_ask`, não pelo
    genérico. Precisa continuar sendo um 503 limpo."""

    async def fake_responder_indisponivel(pergunta: str) -> str:
        raise RagIndisponivelError("índice indisponível (simulado no teste)")

    monkeypatch.setattr("app.main.responder", fake_responder_indisponivel, raising=True)

    response = await client.post(
        "/chat/ask", json={"pergunta": "Qual o prazo de entrega?"}, headers=student_headers()
    )
    assert response.status_code == 503


async def test_ask_returns_a_clean_503_when_the_llm_provider_fails(client, monkeypatch):
    """GROQ_API_KEY ausente/inválida (ou qualquer outra falha do provedor)
    precisa falhar de forma limpa na CHAMADA, não no import do serviço, e
    nunca como um 500 cru vazando detalhes do SDK/provedor ao cliente."""

    async def _broken_create(**kwargs):
        raise RuntimeError("Incorrect API key provided (simulado no teste)")

    class _BrokenGroq:
        def __init__(self, *args, **kwargs) -> None:
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_broken_create))

    monkeypatch.setattr("app.rag.AsyncGroq", _BrokenGroq, raising=True)

    response = await client.post(
        "/chat/ask", json={"pergunta": "Qual o prazo de entrega?"}, headers=student_headers()
    )
    assert response.status_code == 503
    assert "Incorrect API key" not in response.text
    assert "RuntimeError" not in response.text
