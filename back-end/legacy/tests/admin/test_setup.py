from starlette.applications import Starlette

from app.admin.setup import setup_admin
from app.admin.views import ALL_VIEWS


def test_setup_registers_all_views():
    app = Starlette()
    admin = setup_admin(app)
    registered = {type(view).model for view in admin.views}
    expected = {v.model for v in ALL_VIEWS}
    assert registered == expected
    assert len(admin.views) == len(ALL_VIEWS)


async def test_admin_redirects_to_login_when_unauthenticated(client):
    response = await client.get("/admin/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/admin/login" in response.headers["location"]
