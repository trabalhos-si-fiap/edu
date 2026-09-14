"""Preparo idempotente: contas de staff, checagens do backend e o app no
aparelho. Nada aqui sobe ou derruba o stack."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


class ContasFaltando(RuntimeError):
    def __init__(self, faltando: list[str]) -> None:
        super().__init__(
            "contas que continuam sem entrar depois do seed: " + ", ".join(faltando)
        )
        self.faltando = faltando


@dataclass
class ResultadoContas:
    existentes: list[str] = field(default_factory=list)
    criadas: list[str] = field(default_factory=list)


def garantir_contas(
    emails: list[str], entrar: Callable[[str], bool], semear: Callable[[], None]
) -> ResultadoContas:
    """Confere cada conta pelo login; só semeia se faltar alguma.

    O seed de contas de demo já é idempotente, mas conferir antes evita um
    `docker compose exec` a cada execução e deixa claro o que já existia.
    """
    resultado = ResultadoContas(existentes=[e for e in emails if entrar(e)])
    faltando = [e for e in emails if e not in resultado.existentes]
    if not faltando:
        return resultado

    semear()
    continuam = [e for e in faltando if not entrar(e)]
    if continuam:
        raise ContasFaltando(continuam)
    resultado.criadas = faltando
    return resultado
