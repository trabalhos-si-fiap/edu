import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.addresses import services
from app.modules.addresses.exceptions import AddressNotFound
from app.modules.addresses.schemas import AddressIn
from app.modules.auth.models import User
from tests.modules.addresses.conftest import make_address


def _address_in(**overrides: object) -> AddressIn:
    return AddressIn(**make_address(**overrides))


class TestOwnership:
    async def test_user_cannot_read_anothers_address(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        address = await services.create_address(db_session, created_user.id, _address_in())
        with pytest.raises(AddressNotFound):
            await services.get_address(db_session, uuid.uuid4(), address.id)


class TestSingleFavoriteInvariant:
    async def test_only_one_favorite_after_multiple_sets(
        self, db_session: AsyncSession, created_user: User
    ) -> None:
        await services.create_address(db_session, created_user.id, _address_in(is_favorite=True))
        await services.create_address(
            db_session, created_user.id, _address_in(label="B", is_favorite=True)
        )
        await services.create_address(
            db_session, created_user.id, _address_in(label="C", is_favorite=True)
        )

        addresses = await services.list_addresses(db_session, created_user.id)
        favorites = [a for a in addresses if a.is_favorite]
        assert len(favorites) == 1
        assert favorites[0].label == "C"
