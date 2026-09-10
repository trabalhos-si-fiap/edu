"""Dependências de auth do serviço — construídas a partir de edu-common."""

import uuid

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


async def get_current_user_uuid(sub: str = Depends(get_current_user_id)) -> uuid.UUID:
    """O `sub` autenticado como `uuid.UUID`, ou 403 quando ele não é um.

    Nem todo token desta frota tem um usuário por trás. O de carregamento
    (`POST /shipments/login` no commerce-service, decisão D8 do plano) carrega
    no `sub` o id do LOTE — um inteiro —, porque
    `edu_common.security.create_access_token` não aceita claim extra.

    Toda coluna de destinatário deste serviço (`Notificacao.aluno_id`,
    `DeviceToken.aluno_id`) é `UUID(as_uuid=True)`: comparar um `sub` inteiro
    contra ela estoura dentro do driver e vira 500. E a rota é alcançável
    hoje — a fila do entregador tem sino de notificações, e o entregador
    entra por código de carregamento.

    403 é a resposta honesta: não houve falha de servidor, o token
    simplesmente não é de um usuário destas rotas. A guarda fica aqui, uma
    vez, em vez de repetida em cada rota — a pergunta é sempre a mesma.
    """
    try:
        return uuid.UUID(str(sub))
    except (TypeError, ValueError) as exc:
        raise HTTPException(403, "Este token não pertence a um usuário destas rotas") from exc
