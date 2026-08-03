import re
from typing import ClassVar

import wtforms
from sqladmin import ModelView

from app.modules.addresses.models import Address
from app.modules.auth.models import User
from app.modules.auth.security import hash_password
from app.modules.cart.models import Cart, CartItem
from app.modules.notifications.models import DeviceToken, Notification
from app.modules.orders.models import Order, OrderItem
from app.modules.payment_methods.models import PaymentMethod
from app.modules.products.models import Product, Review
from app.modules.support.models import SupportMessage

# Mirrors the registration password policy in app/modules/auth/schemas.py
# (min 8 chars + at least one special character). Kept in sync by hand — the
# admin form must not be a weaker door into the same auth_users table.
_MIN_PASSWORD_LEN = 8
_PASSWORD_SPECIAL_RE = re.compile(r'[!@#$%^&*(),.?":{}|<>]')


class UserAdmin(ModelView, model=User):
    name = "Usuário"
    name_plural = "Usuários"
    icon = "fa-solid fa-user"
    column_list: ClassVar[list[str]] = [
        "id",
        "name",
        "email",
        "phone",
        "education_level",
        "is_active",
        "is_verified",
        "is_admin",
        "created_at",
    ]
    column_searchable_list: ClassVar[list[str]] = ["name", "email"]
    column_sortable_list: ClassVar[list[str]] = ["name", "email", "created_at"]
    # password_hash NUNCA é renderizado (lista nem detalhe) nem editável.
    column_details_exclude_list: ClassVar[list[str]] = ["password_hash"]
    form_excluded_columns: ClassVar[list[str]] = ["password_hash", "created_at", "updated_at"]

    async def scaffold_form(self, rules=None):
        form_class = await super().scaffold_form(rules)
        # Virtual fields: the real password_hash is never in the form. On edit,
        # leaving both blank keeps the current password.
        form_class.password = wtforms.PasswordField(
            "Senha (em branco mantém a atual na edição)"
        )
        form_class.password_confirm = wtforms.PasswordField("Confirmar senha")
        return form_class

    async def on_model_change(self, data, model, is_created, request) -> None:
        password = (data.pop("password", "") or "").strip()
        confirm = (data.pop("password_confirm", "") or "").strip()

        if not password and not confirm:
            if is_created:
                raise ValueError("Senha é obrigatória ao criar um usuário.")
            return  # edit with blank password: keep the current hash

        if password != confirm:
            raise ValueError("As senhas não conferem.")
        if len(password) < _MIN_PASSWORD_LEN:
            raise ValueError(
                f"A senha deve ter ao menos {_MIN_PASSWORD_LEN} caracteres."
            )
        if not _PASSWORD_SPECIAL_RE.search(password):
            raise ValueError("A senha deve conter ao menos um caractere especial.")

        data["password_hash"] = hash_password(password)


class AddressAdmin(ModelView, model=Address):
    name = "Endereço"
    name_plural = "Endereços"
    column_list: ClassVar[list[str]] = [
        "id",
        "user_id",
        "label",
        "city",
        "state",
        "zip_code",
        "is_favorite",
    ]
    column_searchable_list: ClassVar[list[str]] = ["city", "zip_code"]
    column_sortable_list: ClassVar[list[str]] = ["city", "state", "created_at"]


class ProductAdmin(ModelView, model=Product):
    name = "Produto"
    name_plural = "Produtos"
    column_list: ClassVar[list[str]] = [
        "id",
        "name",
        "type",
        "subtype",
        "price",
        "rating_avg",
        "rating_count",
        "created_at",
    ]
    column_searchable_list: ClassVar[list[str]] = ["name", "type"]
    column_sortable_list: ClassVar[list[str]] = ["name", "price", "rating_avg", "created_at"]


class ReviewAdmin(ModelView, model=Review):
    name = "Avaliação"
    name_plural = "Avaliações"
    column_list: ClassVar[list[str]] = ["id", "product_id", "author", "rating", "created_at"]
    column_searchable_list: ClassVar[list[str]] = ["author"]
    column_sortable_list: ClassVar[list[str]] = ["rating", "created_at"]


class OrderAdmin(ModelView, model=Order):
    name = "Pedido"
    name_plural = "Pedidos"
    column_list: ClassVar[list[str]] = [
        "id",
        "user_id",
        "total",
        "status",
        "payment_method",
        "created_at",
    ]
    column_searchable_list: ClassVar[list[str]] = ["status"]
    column_sortable_list: ClassVar[list[str]] = ["total", "status", "created_at"]


class OrderItemAdmin(ModelView, model=OrderItem):
    name = "Item de pedido"
    name_plural = "Itens de pedido"
    column_list: ClassVar[list[str]] = ["id", "order_id", "product_name", "unit_price", "quantity"]
    column_sortable_list: ClassVar[list[str]] = ["unit_price", "quantity"]


class CartAdmin(ModelView, model=Cart):
    name = "Carrinho"
    name_plural = "Carrinhos"
    column_list: ClassVar[list[str]] = ["id", "user_id", "created_at", "updated_at"]
    column_sortable_list: ClassVar[list[str]] = ["created_at", "updated_at"]


class CartItemAdmin(ModelView, model=CartItem):
    name = "Item de carrinho"
    name_plural = "Itens de carrinho"
    column_list: ClassVar[list[str]] = ["id", "cart_id", "product_id", "quantity", "created_at"]
    column_sortable_list: ClassVar[list[str]] = ["quantity", "created_at"]


class PaymentMethodAdmin(ModelView, model=PaymentMethod):
    name = "Forma de pagamento"
    name_plural = "Formas de pagamento"
    # Só dados mascarados de cartão. pix_key (PII), cardholder_name e card_expiry
    # ficam fora da lista, do detalhe E do form — não reexpor sem justificativa.
    column_list: ClassVar[list[str]] = [
        "id",
        "user_id",
        "type",
        "is_default",
        "card_brand",
        "card_last4",
        "created_at",
    ]
    column_sortable_list: ClassVar[list[str]] = ["type", "created_at"]
    _sensitive: ClassVar[list[str]] = ["pix_key", "cardholder_name", "card_expiry"]
    column_details_exclude_list: ClassVar[list[str]] = _sensitive
    form_excluded_columns: ClassVar[list[str]] = _sensitive


class DeviceTokenAdmin(ModelView, model=DeviceToken):
    name = "Token de dispositivo"
    name_plural = "Tokens de dispositivo"
    # O valor do token é sensível — só metadados, nunca o token (lista, detalhe ou form).
    column_list: ClassVar[list[str]] = ["id", "user_id", "platform", "created_at", "updated_at"]
    column_sortable_list: ClassVar[list[str]] = ["platform", "created_at"]
    column_details_exclude_list: ClassVar[list[str]] = ["token"]
    form_excluded_columns: ClassVar[list[str]] = ["token"]


class NotificationAdmin(ModelView, model=Notification):
    name = "Notificação"
    name_plural = "Notificações"
    column_list: ClassVar[list[str]] = ["id", "user_id", "title", "read_at", "created_at"]
    column_searchable_list: ClassVar[list[str]] = ["title"]
    column_sortable_list: ClassVar[list[str]] = ["created_at", "read_at"]


class SupportMessageAdmin(ModelView, model=SupportMessage):
    name = "Mensagem de suporte"
    name_plural = "Mensagens de suporte"
    column_list: ClassVar[list[str]] = ["id", "user_id", "sender", "body", "created_at"]
    column_searchable_list: ClassVar[list[str]] = ["body"]
    column_sortable_list: ClassVar[list[str]] = ["created_at"]


ALL_VIEWS: list[type[ModelView]] = [
    UserAdmin,
    AddressAdmin,
    ProductAdmin,
    ReviewAdmin,
    OrderAdmin,
    OrderItemAdmin,
    CartAdmin,
    CartItemAdmin,
    PaymentMethodAdmin,
    DeviceTokenAdmin,
    NotificationAdmin,
    SupportMessageAdmin,
]
