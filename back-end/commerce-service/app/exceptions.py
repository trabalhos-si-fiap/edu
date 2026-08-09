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


class EmptyCartError(Exception):
    """Checkout tentado com carrinho vazio (nunca existiu ou já foi
    esvaziado por um checkout concorrente que ganhou a corrida pelo lock de
    linha do carrinho — ver `services.pedidos.criar_pedido_do_carrinho`). O
    router traduz em 400 "Cart is empty" (task C6).

    Nome com sufixo `Error`, mesma razão de `ProductNotFoundError` acima
    (`ruff` N818) — o rascunho do brief da task C6 chamava `EmptyCart`.
    """


class OrderNotFoundError(Exception):
    """Pedido inexistente OU que não pertence ao usuário autenticado — o
    filtro por `user_id` em `_buscar_com_itens` (regra 2 do CLAUDE.md) é o
    que torna esta exceção também o veículo de ownership, mesma classe de
    `PaymentMethodNotFoundError` acima. O router traduz em 404 "Pedido não
    encontrado" (task C6).

    Nome com sufixo `Error`, mesma razão de `ProductNotFoundError` acima
    (`ruff` N818) — o rascunho do brief da task C6 chamava `OrderNotFound`.
    """


class RouteUnavailableError(Exception):
    """O provedor de rotas (Google Directions) não devolveu uma rota
    utilizável — chave não configurada, pedido sem snapshot de endereço,
    erro de transporte, status não-OK ou resposta sem `end_location`. O
    router traduz em 503 "Rota indisponível no momento", **nunca**
    ecoando `str(exc)`: o detalhe interno pode carregar a chave da API ou
    o endereço completo do pedido (task C9, constraint de segurança #5).

    Nome com sufixo `Error`, mesma razão de `ProductNotFoundError` acima
    (`ruff` N818) — o legacy (`app/modules/tracking/exceptions.py`) chama
    `RouteUnavailable`.
    """
