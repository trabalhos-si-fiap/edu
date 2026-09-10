from datetime import date

from pydantic import BaseModel


class ObjetivoResumoOut(BaseModel):
    titulo: str
    data_alvo: date
    # Dias desde a criação do objetivo e dias entre a criação e a data-alvo —
    # é o par que a tela inicial exibe como "124/200 dias". `decorridos`
    # nunca passa de `totais`: uma prova que já passou mostra o percurso
    # cheio, não um número maior que o denominador.
    dias_decorridos: int
    dias_totais: int


class RoadmapResumoOut(BaseModel):
    etapas_totais: int
    etapas_concluidas: int
    # 0.0 a 1.0 — é o valor da barra da tela inicial, que antes era 0.68 fixo.
    progresso: float


class PontosResumoOut(BaseModel):
    total: int
    nivel: int
    streak: int


class EstudoResumoOut(BaseModel):
    questoes_respondidas: int
    subtemas_iniciados: int


class ResumoOut(BaseModel):
    """Um agregador para duas telas: sem ele, abrir o app faria quatro
    chamadas em série antes de desenhar qualquer número."""

    objetivo: ObjetivoResumoOut | None
    roadmap: RoadmapResumoOut
    pontos: PontosResumoOut
    estudo: EstudoResumoOut
