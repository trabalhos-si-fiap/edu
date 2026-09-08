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

    # Só o admin nasce por INSERT direto (bootstrap). As outras três passam
    # pelas rotas reais, que publicam evento — sem isso, learning-service e
    # analytics-service nunca saberiam que o aluno de demonstração existe.
    routing_keys = sorted(routing_key for routing_key, _ in _stub_publish_event)
    assert routing_keys == ["staff.created", "staff.created", "student.created"]


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
