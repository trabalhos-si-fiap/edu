from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Staff(Base):
    """Quem é staff, na visão deste serviço.

    Réplica local mantida por EVENTO (`staff.created`), não por consulta ao
    auth-users. O serviço precisa saber "quem são os separadores" para
    endereçar um push, e as alternativas eram piores: chamar
    `GET /users?role=` exigiria um token de admin fabricado aqui — um serviço
    que não é dono de identidade emitindo credencial de admin —, e pôr os ids
    no payload do commerce não resolveria `order.created`, que precisa avisar
    gente que ainda não tocou no pedido. Ver D6 do plano da spec C.

    `user_id` é a PK: o id vem do auth-users e é único lá.
    """

    __tablename__ = "staff"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    papel = Column(String(20), nullable=False, index=True)
    nome = Column(String(150), nullable=False, default="", server_default="")
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
