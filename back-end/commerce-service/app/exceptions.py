class ProductNotFoundError(Exception):
    """Produto inexistente. O router a traduz em 404 "Product not found".

    Nome com sufixo `Error` (não `ProductNotFound`, como o rascunho do brief
    tinha) para seguir a convenção já usada na frota (`RagIndisponivelError`,
    `DiagnosticoContextoError`) — `ruff` regra N818 barra exceção sem sufixo
    `Error`, confirmado com `uv run ruff check .`.
    """
