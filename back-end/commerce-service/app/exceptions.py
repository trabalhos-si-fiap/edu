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


class ParceiroNotFoundError(Exception):
    """Nenhum parceiro (`Fornecedor`) com o id dado. O router traduz em 404
    "Parceiro não encontrado".

    Sufixo `Error` por N818, como todas as outras deste módulo.
    """


class EstoqueNotFoundError(Exception):
    """Não há linha de estoque para o produto (ou id de estoque) pedido. O
    router traduz em 404 "Registro de estoque não encontrado".

    Sufixo `Error` por N818.
    """


class EstoqueNegativoError(Exception):
    """O ajuste levaria a quantidade abaixo de zero. O router traduz em 422.

    Levantada DENTRO da transação, antes de qualquer escrita — nem o estoque
    nem a linha de auditoria são gravados. Auditar um ajuste recusado faria a
    trilha mentir. Mesma regra do Java (`Inventory.adjustTo` levanta
    `BusinessException` antes de construir o `InventoryAdjustment`).

    Sufixo `Error` por N818.
    """


class TransportadoraNotFoundError(Exception):
    """Nenhuma transportadora com o id dado. O router traduz em 404
    "Transportadora não encontrada".

    Sufixo `Error` por N818.
    """


class CarrinhoOrigemMistaError(Exception):
    """Tentativa de pôr no carrinho um item de outro parceiro. O router
    traduz em 409 com `MENSAGEM` como `detail`.

    Pedido misto é PROIBIDO por decisão da spec B, não adiado: um pedido sai
    de UMA origem, e a spec C simula a rota a partir dela. Um carrinho misto
    produziria um pedido sem origem definida.

    A mensagem mora aqui, não no router, porque ela é contrato de UI: o app
    a exibe verbatim, sem reescrever (`cart_service.dart`, task 12).

    Sufixo `Error` por N818.
    """

    MENSAGEM = (
        "Seu carrinho já tem itens de outro parceiro. "
        "Finalize ou esvazie o carrinho antes de misturar."
    )


class SkuDuplicadoError(Exception):
    """Já existe produto com este `sku`. O router traduz em 409.

    A unicidade é do BANCO (índice parcial `uq_products_sku`), e o serviço a
    detecta pelo `IntegrityError` em vez de por um SELECT prévio: um SELECT
    seguido de INSERT é uma corrida, e o índice é a única coisa que resolve
    duas criações simultâneas do mesmo sku. Mesmo idioma de
    `get_or_create_cart` (`app/services/carrinho.py`) e de `criar_metodo`
    (`app/services/pagamento.py`).

    Sufixo `Error` por N818.
    """


class CarregamentoNotFoundError(Exception):
    """Nenhum carregamento com o id dado. O router traduz em 404
    "Carregamento não encontrado".

    Sufixo `Error` por N818.
    """


class CarregamentoOrigemDivergenteError(Exception):
    """Tentativa de pôr num carregamento um pedido que sai de outra origem.
    O router traduz em 409 com `MENSAGEM` como `detail`.

    Um carregamento é o lote que sai de UMA origem (spec C, "Carregamento e
    credencial do entregador"). A interpolação de posição (task 6) parte da
    origem do lote; um lote de duas origens não tem ponto de partida. Mesmo
    espírito de `CarrinhoOrigemMistaError`, um nível acima.

    Sufixo `Error` por N818.
    """

    MENSAGEM = (
        "Este carregamento sai de outra origem. "
        "Crie um carregamento separado para os pedidos desta origem."
    )


class PedidoJaCarregadoError(Exception):
    """O pedido já está em OUTRO carregamento. O router traduz em 409.

    Reatribuir ao MESMO carregamento não cai aqui — é idempotente, e o admin
    que clica duas vezes não pode receber erro.

    Sufixo `Error` por N818.
    """
