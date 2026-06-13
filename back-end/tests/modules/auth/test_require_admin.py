import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User


async def test_require_admin_allows_admin() -> None:
    user = User(name="Root", is_admin=True)
    assert await require_admin(user) is user


async def test_require_admin_rejects_non_admin() -> None:
    user = User(name="Student", is_admin=False)
    with pytest.raises(HTTPException) as exc:
        await require_admin(user)
    assert exc.value.status_code == 403
