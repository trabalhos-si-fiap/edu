class ProductNotFoundError(Exception):
    """Produto inexistente. O router a traduz em 404 "Product not found".

    Nome com sufixo `Error` (não `ProductNotFound`, como o rascunho do brief
    tinha) para seguir a convenção já usada na frota (`RagIndisponivelError`,
    `DiagnosticoContextoError`) — `ruff` regra N818 barra exceção sem sufixo
    `Error`, confirmado com `uv run ruff check .`.
    """


class CartProductNotFoundError(Exception):
    """Tentativa de adicionar ao carrinho um produto que não existe no
    catálogo. O router traduz em 404 "Product not found" (task B8).

    Nome com sufixo `Error`, mesma razão de `ProductNotFoundError` acima
    (`ruff` N818) — o brief original chamava `CartProductNotFound`.
    """


class CartItemNotFoundError(Exception):
    """Tentativa de remover um item que não está no carrinho. O router
    traduz em 404 "Item not in cart" (task B8).

    Nome com sufixo `Error`, mesma razão acima — o brief original chamava
    `CartItemNotFound`.
    """


class PaymentMethodNotFoundError(Exception):
    """Nenhuma forma de pagamento com o id dado pertence a este usuário — o
    filtro por `user_id` é o que torna esta exceção também o veículo de
    ownership (regra 2 do CLAUDE.md): tentar mexer no método de outro
    usuário cai aqui, igual a tentar mexer num id inexistente. O router
    traduz em 404 "Payment method not found" (task B9).

    Nome com sufixo `Error`, mesma razão de `CartProductNotFoundError` acima
    (`ruff` N818) — o legacy chama `PaymentMethodNotFound`.
    """
