"""Dependências de auth do serviço — construídas a partir de edu-common."""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
# Nome igual ao do `edu-common`: este serviço reexportava a dependência de
# id como `get_current_student_id`, um apelido próprio deste serviço — os
# routers que a chamavam tinham que lembrar qual nome cada serviço da
# frota tinha escolhido para a mesma função.
get_current_user_id = _auth.get_current_user_id
