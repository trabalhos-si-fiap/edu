from pydantic import BaseModel, ConfigDict


class MateriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class TemaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    materia_id: int
    nome: str
    ordem: int


class SubtemaOut(BaseModel):
    """
    Campos públicos de um subtema. `descricao_ia` é intencionalmente omitido:
    é texto interno usado só como sinal semântico para o classificador de IA
    (ver `models/subtema.py`), nunca deve ser exibido ao aluno.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    tema_id: int
    nome: str
    ordem: int
    videoaula_base_url: str | None = None
    videoaula_revisao_url: str | None = None
