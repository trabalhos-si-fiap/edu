"""Configuração do Chatbot Service, carregada de variáveis de ambiente.

Nota sobre settings removidas do zip original (herdadas por copy-paste dos
outros serviços, mas mortas neste): `rabbitmq_url`/`exchange_name` — nada
em `app/` publica ou consome eventos (sem dependência de `aio-pika`, e o
Chatbot Service não está na lista de serviços que publicam eventos do
plano de migração); e `faiss_index_path` — o índice FAISS é construído
100% em memória a partir de `BASE_CONHECIMENTO` (ver `app/rag.py`), nenhum
código lê ou escreve nesse path. Manter qualquer uma delas exigiria que
toda config local/CI declarasse uma variável morta, e sugeriria
persistência que não existe — o oposto de YAGNI/KISS.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Necessário para as duas rotas de chat: `/chat/ask` e
    # `/chat/explain-question` exigem autenticação via `get_current_student`.
    # Em `/chat/explain-question` o mesmo token ainda é repassado ao Learning
    # Service (autenticação encadeada) — ver app/dependencies.py.
    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # Vazio por padrão de propósito: uma GROQ_API_KEY ausente NUNCA pode
    # quebrar o import/startup do serviço (health check continua de pé). A
    # falta da chave só se manifesta na chamada real ao Groq, tratada como
    # falha limpa (503) em app/main.py — nunca uma exceção crua.
    groq_api_key: str = ""

    # Chamada serviço-a-serviço direta, dentro da rede Docker — NÃO passa
    # pelo API Gateway (que é só para tráfego externo do app Flutter). Ver
    # app/services/diagnostico_client.py.
    learning_service_url: str = "http://learning-service:8000"


settings = Settings()
