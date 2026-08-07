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
"""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
