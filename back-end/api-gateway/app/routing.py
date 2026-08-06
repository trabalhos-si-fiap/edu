from app.config import settings

# Primeiro segmento do path (depois de /api/) -> qual serviço atende.
# Mantém o Gateway "burro" de propósito: ele só decide PARA ONDE mandar,
# nunca decide autenticação/autorização — isso continua 100% no serviço
# de destino (cada um valida o JWT com o mesmo JWT_SECRET compartilhado).
SERVICE_MAP: dict[str, str] = {
    "auth": "auth",
    "users": "auth",
    "subjects": "learning",
    "topics": "learning",
    "subtopics": "learning",
    "diagnostic": "learning",
    "recommendations": "learning",
    "reviews": "learning",
    "products": "commerce",
    "orders": "commerce",
    "cart": "commerce",
    "payment-methods": "commerce",
    "picking": "commerce",
    "delivery": "commerce",
    "occurrences": "commerce",
    "admin": "commerce",
    "notifications": "notification",
    "analytics": "analytics",
    "chat": "chatbot",
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


def resolve_destination(path: str) -> tuple[str, str] | None:
    """Recebe o path já sem o prefixo `/api` (ex: "auth/login") e devolve
    (base_url_do_servico, path_final_com_barra_inicial), ou None se não
    houver serviço mapeado."""
    first_segment = path.split("/", 1)[0] if path else ""
    service = SERVICE_MAP.get(first_segment)
    if service is None:
        return None
    return SERVICE_BASE_URLS[service], f"/{path}"
