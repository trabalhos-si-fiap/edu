from enum import StrEnum


class StatusPedido(StrEnum):
    """Estados INTERNOS do pedido — o vocabulário da operação de staff.

    São nove. O contrato público expõe seis (ver `StatusContrato` abaixo):
    a operação distingue "aguardando separação" de "em separação" de
    "separado", e o aluno não precisa dessa granularidade.
    """

    CRIADO = "CRIADO"
    CONFIRMADO = "CONFIRMADO"
    AGUARDANDO_SEPARACAO = "AGUARDANDO_SEPARACAO"
    EM_SEPARACAO = "EM_SEPARACAO"
    SEPARADO = "SEPARADO"
    AGUARDANDO_COLETA = "AGUARDANDO_COLETA"
    EM_TRANSITO = "EM_TRANSITO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class StatusContrato(StrEnum):
    """Estados PÚBLICOS — o que `GET /orders` devolve e o Flutter lê.

    São exatamente os cinco do legacy mais `cancelled`. O sexto existe
    porque o enum do Flutter tem `default: return OrderSummaryStatus.pending`:
    sem um valor próprio, um pedido cancelado apareceria como "Pendente", no
    passo 0 do stepper, para sempre. E `CANCELADO` é alcançável por decisão
    do próprio aluno (resolução `cancelar_pedido` de uma ocorrência).
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEPARATING = "separating"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# Progressão VISÍVEL, na ordem. `CANCELLED` fica de fora de propósito: ele não
# é um passo da timeline, é a saída do fluxo. Um `.index(CANCELLED)` no
# construtor do rastreio estouraria `ValueError` — ver rastreio_builder.py.
FLUXO_CONTRATO: tuple[StatusContrato, ...] = (
    StatusContrato.PENDING,
    StatusContrato.CONFIRMED,
    StatusContrato.SEPARATING,
    StatusContrato.OUT_FOR_DELIVERY,
    StatusContrato.DELIVERED,
)

# Transições válidas: de onde -> pra onde.
#
# CONFIRMADO entra entre CRIADO e AGUARDANDO_SEPARACAO: o pagamento passa a
# ser um estado observável, não um pulo. `confirmar_pagamento` (admin.py)
# encadeia as duas transições, porque não há simulador na fase 2 e parar em
# CONFIRMADO deixaria a fila de separação sempre vazia.
#
# CANCELADO é alcançável de vários estágios porque ocorrências (falta de
# estoque, atraso de entrega) podem levar o aluno a cancelar o pedido em
# quase qualquer ponto do fluxo, exceto após a entrega já confirmada.
TRANSICOES_VALIDAS: dict[StatusPedido, list[StatusPedido]] = {
    StatusPedido.CRIADO: [StatusPedido.CONFIRMADO, StatusPedido.CANCELADO],
    StatusPedido.CONFIRMADO: [StatusPedido.AGUARDANDO_SEPARACAO, StatusPedido.CANCELADO],
    StatusPedido.AGUARDANDO_SEPARACAO: [StatusPedido.EM_SEPARACAO, StatusPedido.CANCELADO],
    StatusPedido.EM_SEPARACAO: [StatusPedido.SEPARADO, StatusPedido.CANCELADO],
    StatusPedido.SEPARADO: [StatusPedido.AGUARDANDO_COLETA, StatusPedido.CANCELADO],
    StatusPedido.AGUARDANDO_COLETA: [StatusPedido.EM_TRANSITO, StatusPedido.CANCELADO],
    StatusPedido.EM_TRANSITO: [StatusPedido.ENTREGUE, StatusPedido.CANCELADO],
    StatusPedido.ENTREGUE: [],
    StatusPedido.CANCELADO: [],
}

# Nove internos -> seis do contrato. Exaustivo por construção: o teste
# `test_the_mapping_covers_every_internal_state` percorre `StatusPedido`
# inteiro, então um estado novo sem entrada aqui quebra a suíte em vez de
# virar "pending" por acidente — que faria a tela mostrar um pedido ativo.
STATUS_CONTRATO: dict[StatusPedido, StatusContrato] = {
    StatusPedido.CRIADO: StatusContrato.PENDING,
    StatusPedido.CONFIRMADO: StatusContrato.CONFIRMED,
    StatusPedido.AGUARDANDO_SEPARACAO: StatusContrato.SEPARATING,
    StatusPedido.EM_SEPARACAO: StatusContrato.SEPARATING,
    StatusPedido.SEPARADO: StatusContrato.SEPARATING,
    StatusPedido.AGUARDANDO_COLETA: StatusContrato.OUT_FOR_DELIVERY,
    StatusPedido.EM_TRANSITO: StatusContrato.OUT_FOR_DELIVERY,
    StatusPedido.ENTREGUE: StatusContrato.DELIVERED,
    StatusPedido.CANCELADO: StatusContrato.CANCELLED,
}


def validar_transicao(status_atual: str, novo_status: str) -> bool:
    try:
        atual = StatusPedido(status_atual)
        novo = StatusPedido(novo_status)
    except ValueError:
        return False
    return novo in TRANSICOES_VALIDAS.get(atual, [])


def status_do_contrato(status_interno: str) -> StatusContrato:
    """Traduz o estado interno no valor que o app lê.

    Levanta `KeyError` para um estado desconhecido, de propósito: cair num
    default silencioso ("pending") faria um pedido em estado novo aparecer
    como ativo na tela do aluno, indefinidamente.
    """
    return STATUS_CONTRATO[StatusPedido(status_interno)]
