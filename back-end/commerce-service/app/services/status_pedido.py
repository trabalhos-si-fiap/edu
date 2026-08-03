from enum import StrEnum


class StatusPedido(StrEnum):
    CRIADO = "CRIADO"
    AGUARDANDO_SEPARACAO = "AGUARDANDO_SEPARACAO"
    EM_SEPARACAO = "EM_SEPARACAO"
    SEPARADO = "SEPARADO"
    AGUARDANDO_COLETA = "AGUARDANDO_COLETA"
    EM_TRANSITO = "EM_TRANSITO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


# Transições válidas: de onde -> pra onde
# CANCELADO é alcançável de vários estágios porque ocorrências (falta de
# estoque, atraso de entrega) podem levar o aluno a cancelar o pedido em
# quase qualquer ponto do fluxo, exceto após a entrega já confirmada.
TRANSICOES_VALIDAS: dict[StatusPedido, list[StatusPedido]] = {
    StatusPedido.CRIADO: [StatusPedido.AGUARDANDO_SEPARACAO, StatusPedido.CANCELADO],
    StatusPedido.AGUARDANDO_SEPARACAO: [StatusPedido.EM_SEPARACAO, StatusPedido.CANCELADO],
    StatusPedido.EM_SEPARACAO: [StatusPedido.SEPARADO, StatusPedido.CANCELADO],
    StatusPedido.SEPARADO: [StatusPedido.AGUARDANDO_COLETA, StatusPedido.CANCELADO],
    StatusPedido.AGUARDANDO_COLETA: [StatusPedido.EM_TRANSITO, StatusPedido.CANCELADO],
    StatusPedido.EM_TRANSITO: [StatusPedido.ENTREGUE, StatusPedido.CANCELADO],
    StatusPedido.ENTREGUE: [],
    StatusPedido.CANCELADO: [],
}


def validar_transicao(status_atual: str, novo_status: str) -> bool:
    try:
        atual = StatusPedido(status_atual)
        novo = StatusPedido(novo_status)
    except ValueError:
        return False
    return novo in TRANSICOES_VALIDAS.get(atual, [])
