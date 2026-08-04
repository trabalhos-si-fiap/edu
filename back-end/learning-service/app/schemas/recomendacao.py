from pydantic import BaseModel


class SubtemaRecomendadoOut(BaseModel):
    """
    Próximo subtema não dominado dentro do tema (ver
    `services/recomendacao.py::proximo_subtema`). `descricao_ia` é
    intencionalmente omitido — é texto interno usado só como sinal
    semântico para o classificador de IA, nunca deve ser exibido ao aluno.
    """

    id: int
    tema_id: int
    nome: str
    ordem: int
    videoaula_base_url: str | None = None
    videoaula_revisao_url: str | None = None
