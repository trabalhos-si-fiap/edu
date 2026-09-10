from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObjetivoIn(BaseModel):
    """Entrada do onboarding: o que o aluno quer e para quando.

    A data no passado é recusada AQUI, no schema, não na tela: a tela é uma
    das duas portas (a outra é o PUT do perfil) e uma regra que vive no
    cliente é uma regra que o segundo cliente não tem.
    """

    titulo: str = Field(min_length=1, max_length=120)
    data_alvo: date

    @field_validator("titulo")
    @classmethod
    def _titulo_nao_pode_ser_so_espaco(cls, valor: str) -> str:
        limpo = valor.strip()
        if not limpo:
            raise ValueError("O objetivo não pode ficar em branco")
        return limpo

    @field_validator("data_alvo")
    @classmethod
    def _data_nao_pode_estar_no_passado(cls, valor: date) -> date:
        if valor < date.today():
            raise ValueError("A data-alvo não pode estar no passado")
        return valor


class ObjetivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    titulo: str
    data_alvo: date
    criado_em: datetime
    atualizado_em: datetime


class ObjetivoSalvoOut(BaseModel):
    """Resposta de POST e PUT: o objetivo e o que a geração do percurso fez.

    `etapas_geradas` e `prazo_apertado` viajam junto porque a tela mostra
    "seu percurso tem N etapas" logo depois de salvar — sem isso ela faria
    uma segunda chamada só para contar.
    """

    objetivo: ObjetivoOut
    etapas_geradas: int
    prazo_apertado: bool
