import pytest

from app.services.status_pedido import (
    FLUXO_CONTRATO,
    TRANSICOES_VALIDAS,
    StatusContrato,
    StatusPedido,
    status_do_contrato,
    validar_transicao,
)


def test_confirmado_sits_between_criado_and_aguardando_separacao():
    assert validar_transicao(StatusPedido.CRIADO, StatusPedido.CONFIRMADO)
    assert validar_transicao(StatusPedido.CONFIRMADO, StatusPedido.AGUARDANDO_SEPARACAO)
    # O atalho antigo some: o pagamento passa a ser um estado, não um pulo.
    assert not validar_transicao(StatusPedido.CRIADO, StatusPedido.AGUARDANDO_SEPARACAO)


def test_cancelado_is_reachable_from_confirmado():
    assert validar_transicao(StatusPedido.CONFIRMADO, StatusPedido.CANCELADO)


@pytest.mark.parametrize(
    ("interno", "contrato"),
    [
        ("CRIADO", "pending"),
        ("CONFIRMADO", "confirmed"),
        ("AGUARDANDO_SEPARACAO", "separating"),
        ("EM_SEPARACAO", "separating"),
        ("SEPARADO", "separating"),
        ("AGUARDANDO_COLETA", "out_for_delivery"),
        ("EM_TRANSITO", "out_for_delivery"),
        ("ENTREGUE", "delivered"),
        ("CANCELADO", "cancelled"),
    ],
)
def test_every_internal_state_maps_to_a_contract_value(interno, contrato):
    assert status_do_contrato(interno) == contrato


def test_the_mapping_covers_every_internal_state():
    """Um estado interno novo sem entrada no mapa não pode passar em silêncio:
    ele viraria `pending` por acidente e a tela mostraria um pedido ativo."""
    for estado in StatusPedido:
        assert status_do_contrato(estado.value) is not None


def test_the_contract_has_exactly_six_values():
    assert len(StatusContrato) == 6


def test_the_visible_flow_excludes_cancelled():
    """A timeline tem quatro passos visíveis. `cancelled` não é um passo — é a
    saída do fluxo, e um `FLUXO_CONTRATO.index(cancelled)` estouraria."""
    assert StatusContrato.CANCELLED not in FLUXO_CONTRATO
    assert FLUXO_CONTRATO == (
        StatusContrato.PENDING,
        StatusContrato.CONFIRMED,
        StatusContrato.SEPARATING,
        StatusContrato.OUT_FOR_DELIVERY,
        StatusContrato.DELIVERED,
    )


def test_the_substitution_wait_is_reachable_only_from_picking():
    """Só quem está separando descobre que faltou item. Entrar em
    AGUARDANDO_SUBSTITUICAO de qualquer outro estado seria uma ocorrência
    aberta sobre um pedido que ninguém está separando."""
    origens = [
        s for s in StatusPedido if StatusPedido.AGUARDANDO_SUBSTITUICAO in TRANSICOES_VALIDAS[s]
    ]
    assert origens == [StatusPedido.EM_SEPARACAO]


def test_the_substitution_wait_returns_to_picking_or_cancels():
    """Os dois desfechos da spec: o aluno decidiu (volta ao separador, que
    ainda precisa pegar o substituto da prateleira) ou cancelou o pedido."""
    assert TRANSICOES_VALIDAS[StatusPedido.AGUARDANDO_SUBSTITUICAO] == [
        StatusPedido.EM_SEPARACAO,
        StatusPedido.CANCELADO,
    ]


def test_the_substitution_wait_never_jumps_the_picker():
    """Ir direto a SEPARADO tornaria `/picking/{id}/finish` inalcançável:
    ela exige EM_SEPARACAO e encadeia SEPARADO -> AGUARDANDO_COLETA. Ver D7."""
    assert not validar_transicao(
        StatusPedido.AGUARDANDO_SUBSTITUICAO.value, StatusPedido.SEPARADO.value
    )
    assert not validar_transicao(
        StatusPedido.AGUARDANDO_SUBSTITUICAO.value, StatusPedido.AGUARDANDO_COLETA.value
    )


def test_the_substitution_wait_reads_as_separating_to_the_student():
    """No contrato público o aluno continua vendo "em separação"; a decisão
    pendente aparece como AÇÃO na tela, não como um sexto passo na timeline."""
    assert (
        status_do_contrato(StatusPedido.AGUARDANDO_SUBSTITUICAO.value) == StatusContrato.SEPARATING
    )
