"""Contas fixas para conduzir a apresentação.

A demonstração é conduzida por UMA pessoa alternando entre os quatro perfis,
então as quatro contas precisam existir com senha conhecida e papéis
corretos.

Não há caminho de rota para o primeiro admin: `/auth/register` sempre cria
`role="student"` e `/auth/register-staff` exige um admin já autenticado. Este
seed dirige a aplicação por `httpx.AsyncClient` sobre `ASGITransport` — mesmo
caminho de código das rotas, sem rede — e rompe o ciclo do ovo e da galinha
exatamente uma vez, de forma visível: `admin@demo.edu` é a ÚNICA conta criada
por INSERT direto (ver comentário no bootstrap, abaixo). As outras três
nascem pelas rotas de verdade:

- `aluno@demo.edu`      -> `POST /auth/register`
- `separador@demo.edu`  -> `POST /auth/register-staff` (com o token do admin)
- `entregador@demo.edu` -> `POST /auth/register-staff` (com o token do admin)

Passar pelas rotas reais publica os mesmos eventos que um cadastro de verdade
publicaria (`student.created`, `staff.created`) — sem isso, learning-service e
analytics-service nunca saberiam que o aluno de demonstração existe, e as
telas de tracker/analytics que consultam esses dados ficariam vazias na
apresentação.

O seed também REANUNCIA (`staff.created`) as contas staff que encontra já
criadas — ver `_reanunciar_staff_existente`. Ele continua idempotente no que
cria (segunda passada devolve 0), mas o registro de staff do
`notification-service` é alimentado só por evento, e num ambiente onde as
contas já existiam o evento nunca voltaria a sair.

A senha NUNCA vem do código: `main()` a lê de `DEMO_ACCOUNTS_PASSWORD` e
recusa rodar sem ela.
"""

import asyncio
import os

from edu_common.security import MAX_PASSWORD_BYTES, hash_password
from httpx import ASGITransport, AsyncClient
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.events.publisher import close_publisher, init_publisher, publish_event
from app.main import app
from app.models.user import User

DEMO_ACCOUNTS: tuple[dict[str, str], ...] = (
    {"email": "admin@demo.edu", "nome": "Admin Demo", "role": "admin"},
    {
        "email": "aluno@demo.edu",
        "nome": "Aluno Demo",
        "role": "student",
        # Campos extras exigidos por `RegisterIn` — não usados pelas outras
        # três contas, que não passam por essa rota.
        "phone": "11999990000",
        "birth_date": "15/01/2005",
        "education_level": "3º ano",
    },
    {"email": "separador@demo.edu", "nome": "Separador Demo", "role": "separador"},
    {"email": "entregador@demo.edu", "nome": "Entregador Demo", "role": "entregador"},
)

# Mesmo alfabeto de `RegisterIn.senha_forte` (app/schemas/auth.py) — checar
# aqui, antes de bater na rota, dá ao operador do seed uma mensagem que nomeia
# o requisito em vez de um 422 do FastAPI.
_SENHA_CARACTERES_ESPECIAIS = '!@#$%^&*(),.?":{}|<>'


def _validar_senha(senha: str) -> None:
    if not senha:
        raise ValueError(
            "DEMO_ACCOUNTS_PASSWORD não definida — o seed de demonstração não "
            "tem senha padrão de propósito"
        )
    if len(senha) < 8 or not any(c in _SENHA_CARACTERES_ESPECIAIS for c in senha):
        raise ValueError(
            "DEMO_ACCOUNTS_PASSWORD deve ter ao menos 8 caracteres e ao menos "
            f"um caractere especial ({_SENHA_CARACTERES_ESPECIAIS}) — mesma "
            "regra de RegisterIn.senha_forte, porque a conta aluno@demo.edu "
            "passa por /auth/register"
        )
    if len(senha.encode("utf-8")) > MAX_PASSWORD_BYTES:
        # Terceiro checque de `RegisterIn.senha_forte` (via
        # `_validar_bytes_senha`, app/schemas/auth.py): o teto real é de
        # BYTES, não caracteres, porque é o que `bcrypt`/`hash_password`
        # aplicam. Sem isso aqui, uma senha grande passa pelos dois guards
        # acima e só estoura dentro do bootstrap do admin, com um
        # `ValueError` que não menciona `DEMO_ACCOUNTS_PASSWORD`.
        raise ValueError(
            f"DEMO_ACCOUNTS_PASSWORD não pode passar de {MAX_PASSWORD_BYTES} "
            "bytes — mesmo limite de bcrypt que RegisterIn.senha_forte aplica"
        )


async def seed_demo_accounts(client: AsyncClient, session: AsyncSession, senha: str) -> int:
    """Cria as contas de demonstração que ainda não existem.

    Devolve quantas criou. Idempotente: uma segunda passada devolve 0. A
    checagem de quem já existe é feita uma vez, no início — as rotas de
    cadastro respondem 409 para e-mail duplicado, mas depender disso para a
    idempotência confundiria "já existe" com "erro inesperado".
    """
    _validar_senha(senha)

    emails = [conta["email"] for conta in DEMO_ACCOUNTS]
    existentes = set(
        (await session.execute(select(User.email).where(User.email.in_(emails)))).scalars().all()
    )
    # Cópia congelada ANTES de qualquer criação: `existentes` é mutado abaixo
    # à medida que as contas nascem, e o reanúncio do fim precisa saber quem
    # já estava aqui quando o seed começou.
    ja_existiam = set(existentes)

    criadas = 0

    admin = next(conta for conta in DEMO_ACCOUNTS if conta["role"] == "admin")
    if admin["email"] not in existentes:
        # BOOTSTRAP — a única exceção a "sempre pela rota". `/auth/register`
        # sempre cria role="student" e `/auth/register-staff` exige um admin
        # já autenticado: não existe rota que crie o primeiro admin. Este
        # INSERT direto rompe o ciclo do ovo e da galinha uma vez, de forma
        # visível (ver docs/back-end/demo-accounts.md).
        admin_user = User(
            nome=admin["nome"],
            email=admin["email"],
            senha_hash=hash_password(senha),
            role="admin",
        )
        session.add(admin_user)
        await session.commit()
        existentes.add(admin["email"])
        criadas += 1
        logger.info("conta de demonstração criada (bootstrap direto): {} (admin)", admin["email"])

        # As outras três contas nascem por rota e publicam `student.created` /
        # `staff.created` por conta própria. O admin é INSERT direto (é o que
        # rompe o ciclo do ovo e da galinha), então o evento sai daqui — sem
        # ele, o registro de staff do notification-service (spec C) nunca
        # conhece o admin, e toda transição que avisa admin fica sem
        # destinatário.
        await publish_event(
            "staff.created",
            {"user_id": str(admin_user.id), "nome": admin_user.nome, "role": admin_user.role},
        )

    aluno = next(conta for conta in DEMO_ACCOUNTS if conta["role"] == "student")
    if aluno["email"] not in existentes:
        resposta = await client.post(
            "/auth/register",
            json={
                "name": aluno["nome"],
                "email": aluno["email"],
                "phone": aluno["phone"],
                "birth_date": aluno["birth_date"],
                "education_level": aluno["education_level"],
                "password": senha,
            },
        )
        if resposta.status_code != 201:
            raise RuntimeError(
                f"POST /auth/register falhou ao criar {aluno['email']}: "
                f"status={resposta.status_code}"
            )
        existentes.add(aluno["email"])
        criadas += 1
        logger.info("conta de demonstração criada (rota /auth/register): {}", aluno["email"])

    staff_faltando = [
        conta
        for conta in DEMO_ACCOUNTS
        if conta["role"] in ("separador", "entregador") and conta["email"] not in existentes
    ]
    if staff_faltando:
        login = await client.post("/auth/login", json={"email": admin["email"], "password": senha})
        if login.status_code != 200:
            raise RuntimeError(
                f"POST /auth/login falhou para o admin de demonstração: status={login.status_code}"
            )
        token = login.json()["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for conta in staff_faltando:
            resposta = await client.post(
                "/auth/register-staff",
                json={
                    "nome": conta["nome"],
                    "email": conta["email"],
                    "senha": senha,
                    "role": conta["role"],
                },
                headers=headers,
            )
            if resposta.status_code != 201:
                raise RuntimeError(
                    f"POST /auth/register-staff falhou ao criar {conta['email']}: "
                    f"status={resposta.status_code}"
                )
            criadas += 1
            logger.info(
                "conta de demonstração criada (rota /auth/register-staff): {} ({})",
                conta["email"],
                conta["role"],
            )

    await _reanunciar_staff_existente(session, ja_existiam)

    return criadas


async def _reanunciar_staff_existente(session: AsyncSession, ja_existiam: set[str]) -> None:
    """Publica `staff.created` para as contas staff que o seed ENCONTROU já
    criadas.

    Sem isto o registro de staff do `notification-service` (spec C) só se
    enchia numa instalação virgem: o evento saía apenas do ramo "a conta não
    existe ainda", e o seed é idempotente — em qualquer ambiente onde as
    contas de demonstração já existem (toda stack já rodada, e a fila
    `notification.staff_created` pode muito bem ter nascido depois delas), a
    tabela `staff` ficava vazia e TODO push de staff sumia em silêncio.

    Reanunciar é seguro e repetível: o consumidor insere com
    `INSERT ... ON CONFLICT DO NOTHING` sobre a PK `user_id`
    (`notification-service/app/events/consumer.py::handle_staff_created`), o
    mesmo motivo pelo qual a reentrega do próprio RabbitMQ não duplica linha.
    Não mexe no valor de retorno do seed: ele conta contas CRIADAS, e aqui
    nada é criado.
    """
    emails_staff = [
        conta["email"]
        for conta in DEMO_ACCOUNTS
        if conta["role"] != "student" and conta["email"] in ja_existiam
    ]
    if not emails_staff:
        return

    usuarios = (
        (await session.execute(select(User).where(User.email.in_(emails_staff)))).scalars().all()
    )
    for usuario in usuarios:
        # Mesmo payload que `/auth/register-staff` publica (app/routers/auth.py)
        # — o consumidor lê as três chaves e não sabe (nem precisa saber) se o
        # evento veio de um cadastro novo ou deste reanúncio.
        await publish_event(
            "staff.created",
            {"user_id": str(usuario.id), "nome": usuario.nome, "role": usuario.role},
        )
        logger.info(
            "conta de demonstração já existente reanunciada: {} ({})",
            usuario.email,
            usuario.role,
        )


async def main() -> None:
    senha = os.environ.get("DEMO_ACCOUNTS_PASSWORD", "")
    _validar_senha(senha)  # falha cedo, antes de abrir conexão com o broker

    await init_publisher()
    try:
        transport = ASGITransport(app=app)
        async with (
            AsyncClient(transport=transport, base_url="http://demo-seed") as client,
            async_session() as session,
        ):
            criadas = await seed_demo_accounts(client, session, senha)
    finally:
        await close_publisher()

    logger.info("seed de demonstração: {} conta(s) criada(s)", criadas)


if __name__ == "__main__":
    asyncio.run(main())
