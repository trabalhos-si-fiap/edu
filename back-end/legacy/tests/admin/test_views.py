from unittest.mock import AsyncMock, patch

import pytest
import wtforms
from sqladmin.widgets import BooleanInputWidget

from app.admin import views
from app.modules.auth.models import User
from app.modules.auth.security import verify_password


def test_boolean_field_renders_with_sqladmin_widget():
    # Regression: sqladmin 0.27.2's BooleanInputWidget subclasses the *base*
    # wtforms Input, whose __call__ reads self.validation_attrs. That attribute
    # only exists on the base class in wtforms < 3.2; with wtforms 3.2 the User
    # edit/create form (is_active/is_verified/is_admin checkboxes) raises
    # AttributeError and the page 500s. This guards the pinned combination.
    class _F(wtforms.Form):
        flag = wtforms.BooleanField(widget=BooleanInputWidget())

    html = str(_F().flag())
    assert 'type="checkbox"' in html


def test_user_admin_hides_password_hash():
    # Hidden in the list, the detail page, AND the form — a leak on any of the
    # three would expose the bcrypt hash to anyone with a session.
    assert "password_hash" not in views.UserAdmin.column_list
    assert "password_hash" not in views.UserAdmin().get_details_columns()
    assert "password_hash" in views.UserAdmin.form_excluded_columns


def test_device_token_admin_hides_token_value():
    assert "token" not in views.DeviceTokenAdmin.column_list
    assert "token" not in views.DeviceTokenAdmin().get_details_columns()
    assert "token" in views.DeviceTokenAdmin.form_excluded_columns


def test_payment_method_admin_hides_pii():
    # pix_key / cardholder_name / card_expiry are PII — never in detail or form.
    details = views.PaymentMethodAdmin().get_details_columns()
    for field in ("pix_key", "cardholder_name", "card_expiry"):
        assert field not in views.PaymentMethodAdmin.column_list
        assert field not in details
        assert field in views.PaymentMethodAdmin.form_excluded_columns


async def test_user_form_has_password_and_confirm_fields():
    # scaffold_form calls super() which needs a live session_maker; patch it to
    # return a bare Form class so we can verify our PasswordField injection.
    class _BaseForm(wtforms.Form):
        pass

    with patch(
        "sqladmin.ModelView.scaffold_form",
        new=AsyncMock(return_value=_BaseForm),
    ):
        form_type = await views.UserAdmin().scaffold_form()

    fields = form_type()._fields
    assert "password" in fields
    assert "password_confirm" in fields


async def test_on_model_change_hashes_password_on_create():
    data = {
        "email": "new@example.com",
        "password": "PlainPass!1",
        "password_confirm": "PlainPass!1",
    }
    await views.UserAdmin().on_model_change(data, User(), is_created=True, request=None)
    assert "password" not in data
    assert "password_confirm" not in data
    assert data["password_hash"] != "PlainPass!1"
    # The stored hash is a real bcrypt hash that verifies the plaintext.
    assert verify_password("PlainPass!1", data["password_hash"])


async def test_on_model_change_blank_password_on_edit_keeps_hash():
    data = {"email": "x@example.com", "password": "", "password_confirm": ""}
    await views.UserAdmin().on_model_change(data, User(), is_created=False, request=None)
    assert "password" not in data
    assert "password_confirm" not in data
    assert "password_hash" not in data


async def test_on_model_change_blank_password_on_create_raises():
    data = {"email": "x@example.com", "password": "", "password_confirm": ""}
    with pytest.raises(ValueError, match="obrigatória"):
        await views.UserAdmin().on_model_change(data, User(), is_created=True, request=None)


async def test_on_model_change_mismatched_passwords_raise():
    data = {"email": "x@example.com", "password": "GoodPass!1", "password_confirm": "Other!1"}
    with pytest.raises(ValueError, match="não conferem"):
        await views.UserAdmin().on_model_change(data, User(), is_created=True, request=None)


async def test_on_model_change_short_password_raises():
    data = {"email": "x@example.com", "password": "Ab!1", "password_confirm": "Ab!1"}
    with pytest.raises(ValueError, match="8 caracteres"):
        await views.UserAdmin().on_model_change(data, User(), is_created=True, request=None)


async def test_on_model_change_password_without_special_char_raises():
    data = {"email": "x@example.com", "password": "NoSpecial1", "password_confirm": "NoSpecial1"}
    with pytest.raises(ValueError, match="caractere especial"):
        await views.UserAdmin().on_model_change(data, User(), is_created=True, request=None)
