from datetime import datetime

from pydantic import BaseModel


class RespostaItem(BaseModel):
    questao_id: int
    alternativa_escolhida: str


class RespostaDiagnosticoIn(BaseModel):
    """
    O diagnóstico agora é por TEMA (ex: Citologia), não mais por subtema
    isolado — o questionário de 15 perguntas cobre vários subtemas do tema,
    e cada um é avaliado individualmente dentro do resultado agregado.
    """

    tema_id: int
    respostas: list[RespostaItem]


class SubtemaAvaliadoOut(BaseModel):
    """Resultado individual de cada subtema coberto pelo questionário."""

    subtema_id: int
    nome: str
    dominio: float
    classificacao: str  # estudar_do_zero | revisar | dominado
    proxima_revisao: datetime


class SubtemaRelacionadoOut(BaseModel):
    """Sugestão de reforço cruzado via IA (embeddings), ver services/recomendacao_semantica.py."""

    subtema_id: int
    nome: str
    similaridade: float


class RecomendacaoConteudoOut(BaseModel):
    """
    Vídeo gratuito sugerido para um subtema ainda não dominado — devolvido
    para QUALQUER subtema abaixo do limiar de domínio, independente da
    ação geral do tema (estudar/avançar/retroceder).
    """

    subtema_id: int
    nome: str
    motivo: str  # estudar_do_zero | revisar
    video_url: str | None = None
    # Preenchido por IA (embeddings + NearestNeighbors) só quando motivo ==
    # estudar_do_zero — reforço cruzado com subtemas conceitualmente
    # relacionados, mesmo que estejam em outro tema/matéria.
    subtemas_relacionados: list[SubtemaRelacionadoOut] = []


class TemaResumoOut(BaseModel):
    id: int
    nome: str


class QuestaoContextoOut(BaseModel):
    """
    Contexto completo de uma questão já respondida pelo aluno — usado
    pelo Chatbot Service para explicar por que ele errou (ou acertou).
    Só é exposto para questões que o aluno JÁ respondeu (ver validação em
    GET /diagnostic/questions/{id}/context); nunca revela o gabarito de
    uma questão ainda não respondida.
    """

    questao_id: int
    enunciado: str
    alternativas: dict
    gabarito: str
    alternativa_escolhida: str
    acertou: bool
    subtema_nome: str
    tema_nome: str


class DiagnosticoResultado(BaseModel):
    tema_id: int
    dominio_tema: float
    acao: str  # estudar | avancar | retroceder
    subtemas_avaliados: list[SubtemaAvaliadoOut]
    recomendacoes_conteudo: list[RecomendacaoConteudoOut]
    # Tema pré-requisito (se acao == retroceder) ou próximo tema da trilha
    # (se acao == avancar). None quando acao == estudar, ou quando não há
    # tema anterior/próximo cadastrado (ex: já é o primeiro ou o último).
    tema_recomendado: TemaResumoOut | None = None
    # Mensagem em tom de tutor, gerada por LLM (Groq) a partir do
    # resultado já calculado acima — ver services/tutor_llm.py. Nunca é
    # None: se o LLM falhar/não estiver configurado, cai num fallback
    # local determinístico.
    mensagem_tutor: str
