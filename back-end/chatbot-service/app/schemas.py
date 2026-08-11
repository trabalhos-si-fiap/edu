import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MensagemIn(BaseModel):
    # `/chat/ask` exige autenticação (`get_current_user` em app/main.py),
    # mas o limite de tamanho aqui continua sendo defesa de custo e não só
    # higiene de input: cada pergunta gera uma chamada real ao encoder + à
    # API paga da Groq, e o aluno autenticado ainda pode abusar do volume.
    pergunta: str = Field(..., min_length=1, max_length=1000)


class MensagemOut(BaseModel):
    resposta: str


class ExplicarQuestaoIn(BaseModel):
    questao_id: int


class ExplicacaoOut(BaseModel):
    questao_id: int
    acertou: bool
    explicacao: str


class SupportMessageIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # `min_length=1` DEPOIS do strip: uma mensagem só de espaços vira "" e é
    # rejeitada com 422, em vez de virar um balão vazio na conversa.
    # `max_length` bate com a coluna (regra 4 do CLAUDE.md) — ver
    # app/models/suporte.py:38.
    body: str = Field(min_length=1, max_length=2000)


class SupportMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender: str
    body: str
    created_at: datetime
