"""Dependências de auth do serviço — construídas a partir de edu-common."""

from edu_common.deps import build_auth_deps

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
get_current_student_id = _auth.get_current_user_id
