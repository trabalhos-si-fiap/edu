from pydantic import BaseModel, Field


class MensagemIn(BaseModel):
    # `/chat/ask` é público (sem autenticação) — um limite de tamanho aqui
    # não é só higiene de input, é a única barreira contra abuso (cada
    # pergunta gera uma chamada real ao encoder + à API paga da Groq).
    pergunta: str = Field(..., min_length=1, max_length=1000)


class MensagemOut(BaseModel):
    resposta: str


class ExplicarQuestaoIn(BaseModel):
    questao_id: int


class ExplicacaoOut(BaseModel):
    questao_id: int
    acertou: bool
    explicacao: str
