from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.objetivo import ObjetivoOut


class EtapaOut(BaseModel):
    """Uma etapa do percurso, com o caminho inteiro até ela.

    Os três nomes (matéria, tema, subtema) viajam juntos porque a tela
    agrupa por matéria — sem eles, o cliente faria uma chamada por etapa
    para descobrir onde ela mora.
    """

    subtema_id: int
    subtema_nome: str
    tema_id: int
    tema_nome: str
    materia_nome: str
    ordem: int
    prazo: date
    concluida: bool
    concluida_em: datetime | None
    # False quando o subtema ainda não tem questão semeada. A tela mostra a
    # etapa assim mesmo, com o botão de praticar desabilitado e o motivo —
    # esconder a matéria seria mentir sobre o tamanho do percurso.
    tem_questoes: bool


class RoadmapOut(BaseModel):
    objetivo: ObjetivoOut | None
    # Preenchido só quando `items` está vazio por falta de objetivo: é o que
    # a tela exibe convidando o aluno a fazer o onboarding.
    motivo: str | None
    prazo_apertado: bool
    items: list[EtapaOut]
    total: int
    limit: int
    offset: int
