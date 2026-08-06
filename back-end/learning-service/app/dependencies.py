"""Dependências de auth do serviço — construídas a partir de edu-common.

Os aliases em português preservam os nomes que os routers já usam.
"""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
# Nome igual ao do `edu-common`: este serviço reexportava a dependência de
# id como `get_current_student_id`, um nome próprio que só este router
# usava — ler outro serviço da frota exigia lembrar qual apelido ele tinha
# escolhido para a mesma função.
get_current_user_id = _auth.get_current_user_id
requer_papel = _auth.require_role
