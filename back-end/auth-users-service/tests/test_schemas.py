"""Unit tests puros de schema (sem DB/HTTP) para os dois campos de senha que
`test_auth.py` não exercita via rota: `RegisterStaffIn.senha` (rota exige JWT
de admin) e `PasswordResetConfirmIn.new_password` (rota exige um código de
reset válido já persistido). Fecham o Important 3 para os três schemas
citados pelo review, sem montar a suíte de caracterização completa."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import PasswordResetConfirmIn, RegisterStaffIn
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
