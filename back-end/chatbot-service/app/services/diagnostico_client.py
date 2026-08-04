"""
Cliente HTTP interno para o Learning Service — chamada serviço-a-serviço
dentro da rede Docker (`http://learning-service:8000`), NÃO passa pelo
API Gateway (que é só para tráfego externo do app Flutter).
"""

import httpx

from app.config import settings


class DiagnosticoContextoError(Exception):
    """Erro ao buscar o contexto de uma questão no Learning Service."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


async def buscar_contexto_questao(questao_id: int, raw_token: str) -> dict:
    """
    Busca o contexto de uma questão no Learning Service, repassando o
    MESMO token JWT do aluno que chamou o Chatbot Service — é o Learning
    Service quem valida que o aluno autenticado é o mesmo que respondeu a
    questão, e só libera o gabarito nesse caso (autenticação encadeada,
    sem o Chatbot Service precisar saber nada sobre progresso do aluno).

    `raw_token` é a credencial bearer viva do aluno — nunca logar este
    valor nem incluí-lo em qualquer mensagem de erro/exceção.
    """
    # Rota renomeada pela task 9 do plano de migração: era
    # `/diagnostico/questoes/{id}/contexto`, confirmado contra o código real
    # em back-end/learning-service/app/routers/diagnostico.py:247.
    url = f"{settings.learning_service_url}/diagnostic/questions/{questao_id}/context"
    headers = {"Authorization": f"Bearer {raw_token}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise DiagnosticoContextoError(
            "Não foi possível conectar ao serviço de diagnóstico", status_code=503
        ) from exc

    if resp.status_code == 403:
        raise DiagnosticoContextoError(
            "Você ainda não respondeu essa questão em nenhum diagnóstico",
            status_code=403,
        )
    if resp.status_code == 404:
        raise DiagnosticoContextoError("Questão não encontrada", status_code=404)
    if resp.status_code != 200:
        raise DiagnosticoContextoError(
            "Falha ao buscar contexto da questão no Learning Service",
            status_code=502,
        )

    return resp.json()
