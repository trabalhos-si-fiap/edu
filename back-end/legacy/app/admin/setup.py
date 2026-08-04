from sqladmin import Admin
from starlette.applications import Starlette

from app.admin.auth import AdminAuth
from app.admin.views import ALL_VIEWS
from app.core.config import settings
from app.core.database import engine


def setup_admin(app: Starlette) -> Admin:
    """Monta o painel SQLAdmin em /admin e registra todas as ModelViews."""
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    admin = Admin(
        app,
        engine,
        title=f"{settings.APP_NAME} Admin",
        authentication_backend=authentication_backend,
    )
    for view in ALL_VIEWS:
        admin.add_view(view)
    return admin
