"""Testes de rota para `/diagnostic`, `/recommendations`, `/reviews`.

Estes quatro testes vêm do brief da task 9 sem alteração — os endpoints já
exigiam autenticação antes desta task (só o path mudou de português para
inglês), então "sem header -> 403" continua batendo direto, sem nenhum
outro parâmetro inválido competindo pela resposta.

Os dois testes adicionais no final cobrem o segundo achado do review da
task anterior que estava no escopo desta task: `GET
/recommendations/related/{id}` não tinha nenhum controle de acesso.
"""


async def test_answer_requires_authentication(client):
    response = await client.post("/diagnostic/answer", json={"tema_id": 1, "respostas": []})
    assert response.status_code == 403


async def test_question_context_requires_authentication(client):
    assert (await client.get("/diagnostic/questions/1/context")).status_code == 403


async def test_recommendations_require_authentication(client):
    assert (await client.get("/recommendations?tema_id=1")).status_code == 403


async def test_reviews_today_requires_authentication(client):
    assert (await client.get("/reviews/today")).status_code == 403


async def test_related_subtopics_require_authentication(client):
    assert (await client.get("/recommendations/related/1")).status_code == 403


async def test_recommendation_response_never_leaks_the_internal_ai_description(
    client, auth_headers
):
    """`get_recomendacao` costumava devolver o objeto `Subtema` do SQLAlchemy
    cru (achado do review da task anterior) — o que vazava
    `descricao_ia` (texto interno só para o classificador de IA, nunca
    exibido ao aluno) na resposta JSON. Sem nenhum progresso/subtema
    cadastrado para este tema, o endpoint responde 200 com corpo `null`
    (nenhum próximo subtema) em vez de 404 — comportamento preexistente
    de `proximo_subtema`, preservado aqui.
    """
    response = await client.get("/recommendations?tema_id=999999", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() is None
