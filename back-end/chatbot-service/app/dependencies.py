"""Dependências de auth do serviço — construídas a partir de edu-common.

Este serviço reexportava a dependência de payload do edu-common como
`get_current_student`, um nome próprio que nenhum outro serviço da frota
usava (analytics, learning e auth-users já chamam a mesma função de
`get_current_user`). Renomeado para o nome canônico.

`get_current_user` devolve o payload do JWT já acrescido de `raw_token`,
porque `/chat/explain-question` repassa esse MESMO token na chamada ao
Learning Service (autenticação encadeada — o aluno só vê o contexto de
questões que ele mesmo respondeu). `raw_token` é a credencial bearer viva
do aluno: nunca logar nem devolver esse dict em corpo de resposta.

`get_current_user_id` foi acrescentado na task D4 para as rotas de
`/support`: elas só precisam do `sub` do token para filtrar a conversa por
dono, não do payload inteiro. Nome igual ao do `edu-common`, mesmo padrão
de auth-users-service, commerce-service, notification-service e
learning-service.
"""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
get_current_user_id = _auth.get_current_user_id
