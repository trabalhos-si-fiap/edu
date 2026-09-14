"""Dados do roteiro que não dependem do aparelho: datas, e-mail, senha e a
escolha de resposta no questionário."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from datetime import date, datetime

# A mesma regra de `RegisterIn.senha_forte` e do seed de contas de demo.
CARACTERES_ESPECIAIS = '!@#$%^&*(),.?":{}|<>'


@dataclass(frozen=True)
class Questao:
    subtema_id: int
    gabarito: str
    enunciado: str


def proximo_8_de_novembro(hoje: date) -> date:
    """A prova da narração ("ENEM em novembro"), sempre no futuro."""
    deste_ano = date(hoje.year, 11, 8)
    return deste_ano if hoje < deste_ano else date(hoje.year + 1, 11, 8)


def email_da_ana(agora: datetime) -> str:
    """E-mail novo a cada execução: o cadastro aparece de verdade no vídeo."""
    return f"ana.{agora:%Y%m%d%H%M%S}@example.com"


def validar_senha(senha: str) -> None:
    if not senha.isascii():
        raise ValueError("a senha precisa ser ASCII para ser digitada pelo adb")
    if len(senha) < 8 or not any(c in CARACTERES_ESPECIAIS for c in senha):
        raise ValueError("a senha precisa de 8 caracteres e um caractere especial")


def escolher_alternativa(enunciado_na_tela: str, gabarito: list[Questao], acertar: set[int]) -> str:
    """Letra a tocar: a certa nos subtemas de `acertar`, uma errada nos demais.

    O enunciado na tela é casado com o do banco por semelhança do texto
    inteiro — duas questões de Mendel começam com a mesma frase, então casar
    pelo começo erraria a questão.
    """

    def semelhanca(questao: Questao) -> float:
        return difflib.SequenceMatcher(None, questao.enunciado, enunciado_na_tela).ratio()

    questao = max(gabarito, key=semelhanca)
    if questao.subtema_id in acertar:
        return questao.gabarito
    return next(letra for letra in "ABCD" if letra != questao.gabarito)
