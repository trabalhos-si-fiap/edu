"""Helpers compartilhados entre módulos de teste (não é um arquivo de
fixtures — por isso fica separado de conftest.py)."""


def senha_curta_em_caracteres_mas_grande_em_bytes() -> str:
    """40 caracteres, 74 bytes em UTF-8. "é" ocupa 2 bytes — repeti-lo
    multiplica bytes sem multiplicar caracteres na mesma proporção: o
    cenário exato que `Field(max_length=...)` (que conta caracteres, não
    bytes) deixaria passar e que estouraria o limite de 72 bytes do bcrypt.
    """
    senha = "Sénha!1" + "é" * 33
    assert len(senha) < 72
    assert len(senha.encode("utf-8")) > 72
    return senha
