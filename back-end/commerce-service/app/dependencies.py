"""Dependências de auth do serviço — construídas a partir de edu-common."""

from dataclasses import dataclass

from edu_common.deps import build_auth_deps
from fastapi import Depends, HTTPException

from app.config import settings

_auth = build_auth_deps(settings.jwt_secret, settings.jwt_algorithm)

get_current_user = _auth.get_current_user
# Nome igual ao do `edu-common`: este serviço reexportava a dependência de
# id como `get_current_student_id`, um apelido próprio deste serviço — os
# routers que a chamavam tinham que lembrar qual nome cada serviço da
# frota tinha escolhido para a mesma função.
get_current_user_id = _auth.get_current_user_id
requer_papel = _auth.require_role

PAPEL_CARREGAMENTO = "carregamento"


@dataclass(frozen=True)
class AtorEntrega:
    """Quem está operando uma rota de `/delivery`.

    Dois atores, um contrato. `requer_papel` do `edu-common` não serve aqui:
    ele responde "este token tem um destes papéis?", e a pergunta desta spec é
    "este token pode mexer NESTE pedido?" — que para o token de lote depende
    do `carregamento_id` do pedido, não do papel.
    """

    tipo: str
    id: str
    carregamento_id: int | None

    def autoriza(self, pedido) -> bool:
        if self.tipo == PAPEL_CARREGAMENTO:
            return pedido.carregamento_id == self.carregamento_id
        # Usuário: mantém a regra que já existia — claim-on-first-action na
        # coleta, posse obrigatória na entrega (ver os docstrings das rotas).
        return pedido.deliverer_id is None or str(pedido.deliverer_id) == self.id


async def ator_entrega(user: dict = Depends(get_current_user)) -> AtorEntrega:
    papel = user.get("role")
    if papel == PAPEL_CARREGAMENTO:
        try:
            carregamento_id = int(user["sub"])
        except (TypeError, ValueError) as exc:
            # Token com role de lote e `sub` que não é id de lote: recusa como
            # credencial inválida, não como 500.
            raise HTTPException(401, "Token inválido ou expirado") from exc
        return AtorEntrega(tipo=PAPEL_CARREGAMENTO, id=user["sub"], carregamento_id=carregamento_id)
    if papel in ("entregador", "admin"):
        return AtorEntrega(tipo="usuario", id=user["sub"], carregamento_id=None)
    raise HTTPException(403, "Sem permissão para esta ação")
