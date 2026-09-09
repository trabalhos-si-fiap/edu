import pytest
from sqlalchemy import select

from app.models.user import User
from app.seeds.demo_accounts import DEMO_ACCOUNTS, seed_demo_accounts

# Precisa satisfazer `RegisterIn.senha_forte` (8+ caracteres, 1 caractere
# especial) — as três contas não-admin nascem por `/auth/register` ou
# `/auth/register-staff`, que validam a senha como qualquer cadastro real.
SENHA = "senha-de-demonstracao-nao-usada-em-producao!1"


async def test_seed_creates_one_account_per_role(client, db_session, _stub_publish_event):
    criadas = await seed_demo_accounts(client, db_session, SENHA)

    assert criadas == len(DEMO_ACCOUNTS) == 4

    papeis = (await db_session.execute(select(User.role))).scalars().all()
    assert sorted(papeis) == ["admin", "entregador", "separador", "student"]

    # As quatro contas publicam evento, agora — inclusive o admin, criado por
    # INSERT direto no bootstrap (task 8 da spec C): sem isso, o registro de
    # staff do notification-service nasceria sem o admin, e toda transição
    # que avisa admin ficaria sem destinatário. Amendment declarado: esta
    # asserção antes tinha só dois "staff.created" (separador, entregador) —
    # ver relato da task 8.
    routing_keys = sorted(routing_key for routing_key, _ in _stub_publish_event)
    assert routing_keys == [
        "staff.created",
        "staff.created",
        "staff.created",
        "student.created",
    ]


async def test_the_bootstrap_admin_announces_itself_like_the_others(
    client, db_session, _stub_publish_event
):
    """`admin@demo.edu` é a única conta criada por INSERT direto, então ela
    nunca publicou `staff.created` — e o registro de staff do
    notification-service (spec C, task 8) nasceria sem o admin, deixando as
    transições que avisam admin sem destinatário nenhum."""
    await seed_demo_accounts(client, db_session, SENHA)

    usuarios = (await db_session.execute(select(User))).scalars().all()
    admin = next(u for u in usuarios if u.role == "admin")
    evento_esperado = (
        "staff.created",
        {"user_id": str(admin.id), "nome": "Admin Demo", "role": "admin"},
    )
    assert evento_esperado in _stub_publish_event


async def test_seed_is_idempotent(client, db_session):
    await seed_demo_accounts(client, db_session, SENHA)
    criadas = await seed_demo_accounts(client, db_session, SENHA)

    assert criadas == 0, "a segunda passada criou contas de novo"

    emails = (await db_session.execute(select(User.email))).scalars().all()
    assert len(emails) == len(set(emails)) == 4


async def test_seed_never_stores_the_password_in_clear(client, db_session):
    await seed_demo_accounts(client, db_session, SENHA)

    hashes = (await db_session.execute(select(User.senha_hash))).scalars().all()
    assert all(SENHA not in h for h in hashes)


async def test_seed_refuses_an_empty_password(client, db_session):
    with pytest.raises(ValueError, match="DEMO_ACCOUNTS_PASSWORD"):
        await seed_demo_accounts(client, db_session, "")


async def test_seed_refuses_a_password_under_eight_characters(client, db_session):
    with pytest.raises(ValueError, match="8 caracteres"):
        await seed_demo_accounts(client, db_session, "curta!1")


async def test_seed_refuses_a_password_without_a_special_character(client, db_session):
    with pytest.raises(ValueError, match="caractere especial"):
        await seed_demo_accounts(client, db_session, "senhalonguesemespecial")


async def test_seed_refuses_a_password_over_the_bcrypt_byte_limit(client, db_session):
    # 8+ caracteres e 1 especial (passa pelos dois primeiros guards) mas
    # acima de MAX_PASSWORD_BYTES (72) — o mesmo teto que
    # RegisterIn.senha_forte aplica via _validar_bytes_senha.
    senha_longa_demais = ("a" * 73) + "!"
    with pytest.raises(ValueError, match="DEMO_ACCOUNTS_PASSWORD"):
        await seed_demo_accounts(client, db_session, senha_longa_demais)
