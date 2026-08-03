from app.config import settings

# Primeiro segmento do path (depois de /api/) -> qual serviço atende.
# Mantém o Gateway "burro" de propósito: ele só decide PARA ONDE mandar,
# nunca decide autenticação/autorização — isso continua 100% no serviço
# de destino (cada um valida o JWT com o mesmo JWT_SECRET compartilhado).
SERVICE_MAP: dict[str, str] = {
    "auth": "auth",
    "users": "auth",
    "materias": "learning",
    "temas": "learning",
    "subtemas": "learning",
    "diagnostico": "learning",
    "recomendacoes": "learning",
    "revisoes": "learning",
    "produtos": "commerce",
    "pedidos": "commerce",
    "separacao": "commerce",
    "entrega": "commerce",
    "admin": "commerce",
    "ocorrencias": "commerce",
    "notifications": "notification",
    "analytics": "analytics",
    "chat": "chatbot",
    # ATENÇÃO — mapeados para o Commerce Service, mas os endpoints reais
    # ainda não existem lá com esse contrato (ver STATUS.md, seção
    # Marketplace/Checkout). Requests para estes paths hoje respondem 404
    # vindo do próprio Commerce Service, não do Gateway.
    "products": "commerce",
    "orders": "commerce",
    "cart": "commerce",
    "payment-methods": "commerce",
    "support": "chatbot",
}

SERVICE_BASE_URLS: dict[str, str] = {
    "auth": settings.auth_service_url,
    "learning": settings.learning_service_url,
    "commerce": settings.commerce_service_url,
    "notification": settings.notification_service_url,
    "analytics": settings.analytics_service_url,
    "chatbot": settings.chatbot_service_url,
}


def resolver_destino(path: str) -> tuple[str, str] | None:
    """
    Recebe o path já sem o prefixo `/api` (ex: "auth/login") e devolve
    (base_url_do_servico, path_final_com_barra_inicial), ou None se não
    houver nenhum serviço mapeado para esse path.
    """
    primeiro_segmento = path.split("/", 1)[0] if path else ""
    servico = SERVICE_MAP.get(primeiro_segmento)
    if servico is None:
        return None

    return SERVICE_BASE_URLS[servico], f"/{path}"
