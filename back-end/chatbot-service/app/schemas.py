from pydantic import BaseModel, Field


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
