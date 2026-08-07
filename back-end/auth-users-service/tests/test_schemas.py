"""Unit tests puros de schema (sem DB/HTTP) para os dois campos de senha que
`test_auth.py` não exercita via rota: `RegisterStaffIn.senha` (rota exige JWT
de admin) e `PasswordResetConfirmIn.new_password` (rota exige um código de
reset válido já persistido). Fecham o Important 3 para os três schemas
citados pelo review, sem montar a suíte de caracterização completa."""

import pytest
from pydantic import ValidationError

from app.schemas.address import AddressIn, AddressPatch
from app.schemas.auth import PasswordResetConfirmIn, RegisterIn, RegisterStaffIn
from app.schemas.user import UserUpdateIn
from tests.helpers import senha_curta_em_caracteres_mas_grande_em_bytes


def test_register_staff_in_rejects_password_over_byte_limit():
    with pytest.raises(ValidationError):
        RegisterStaffIn(
            nome="Admin Dois",
            email="admin2@example.com",
            senha=senha_curta_em_caracteres_mas_grande_em_bytes(),
            role="admin",
        )


def test_password_reset_confirm_in_rejects_password_over_byte_limit():
    with pytest.raises(ValidationError):
        PasswordResetConfirmIn(
            email="ana.souza@example.com",
            code="123456",
            new_password=senha_curta_em_caracteres_mas_grande_em_bytes(),
        )


# ── Regra 4 do CLAUDE.md: limite no model E no schema. Os models já
# declaravam String(...); os schemas não declaravam nada, então um `name` de
# 10 MB atravessava o Pydantic e só morria no INSERT — 500 não autenticado.
#
# Cada literal abaixo é o tamanho da coluna + 1, escrito à mão (constraint 12:
# o teste não importa a constante da implementação). Medidos em
# app/models/user.py e app/models/address.py.


def _register_payload(**overrides):
    base = {
        "name": "Ana",
        "email": "ana@example.com",
        "phone": "11999999999",
        "birth_date": "15/01/2000",
        "education_level": "3º ano",
        "password": "senha!forte1",
    }
    return {**base, **overrides}


def test_register_name_is_bounded():
    with pytest.raises(ValidationError):
        RegisterIn(**_register_payload(name="A" * 151))


def test_register_phone_is_bounded():
    with pytest.raises(ValidationError):
        RegisterIn(**_register_payload(phone="9" * 21))


def test_register_staff_fields_are_bounded():
    base = {
        "nome": "Bruno",
        "email": "bruno@example.com",
        "senha": "senha!forte1",
        "role": "separador",
    }
    with pytest.raises(ValidationError):
        RegisterStaffIn(**{**base, "nome": "B" * 151})
    with pytest.raises(ValidationError):
        RegisterStaffIn(**{**base, "telefone": "9" * 21})
    with pytest.raises(ValidationError):
        RegisterStaffIn(**{**base, "documento": "1" * 21})


def test_password_reset_code_is_bounded():
    """O código tem 6 dígitos; sem teto ele chega inteiro ao `verify_password`."""
    with pytest.raises(ValidationError):
        PasswordResetConfirmIn(email="ana@example.com", code="0" * 100, new_password="senha!forte1")


def test_user_update_fields_are_bounded():
    with pytest.raises(ValidationError):
        UserUpdateIn(nome="A" * 151)
    with pytest.raises(ValidationError):
        UserUpdateIn(telefone="9" * 21)


def _address_payload(**overrides):
    base = {
        "zip_code": "01310100",
        "street": "Av. Paulista",
        "number": "1000",
        "neighborhood": "Bela Vista",
        "city": "São Paulo",
        "state": "SP",
    }
    return {**base, **overrides}


def test_address_fields_are_bounded():
    with pytest.raises(ValidationError):
        AddressIn(**_address_payload(label="L" * 61))
    with pytest.raises(ValidationError):
        AddressIn(**_address_payload(zip_code="0" * 10))
    with pytest.raises(ValidationError):
        AddressIn(**_address_payload(street="R" * 161))
    with pytest.raises(ValidationError):
        AddressIn(**_address_payload(number="1" * 21))
    with pytest.raises(ValidationError):
        AddressIn(**_address_payload(complement="C" * 121))
    with pytest.raises(ValidationError):
        AddressIn(**_address_payload(neighborhood="B" * 121))
    with pytest.raises(ValidationError):
        AddressIn(**_address_payload(city="C" * 121))


def test_address_patch_fields_are_bounded():
    """O PATCH escreve nas MESMAS colunas — sem teto aqui o limite do AddressIn
    seria contornável pela rota de atualização parcial."""
    with pytest.raises(ValidationError):
        AddressPatch(label="L" * 61)
    with pytest.raises(ValidationError):
        AddressPatch(zip_code="0" * 10)
    with pytest.raises(ValidationError):
        AddressPatch(street="R" * 161)
    with pytest.raises(ValidationError):
        AddressPatch(number="1" * 21)
    with pytest.raises(ValidationError):
        AddressPatch(complement="C" * 121)
    with pytest.raises(ValidationError):
        AddressPatch(neighborhood="B" * 121)
    with pytest.raises(ValidationError):
        AddressPatch(city="C" * 121)
