from app.models.pedido import Order


def endereco_formatado(order: Order) -> str:
    """Monta a string que `endereco_entrega` guardava, a partir de sete dos
    oito campos `ship_*` do snapshot (ver app/models/pedido.py::Order).
    `ship_label` fica de fora de propósito: é um apelido escolhido pelo
    aluno ("Casa", "Trabalho"), não parte do endereço postal — não faz
    sentido dentro de uma string para geocodificar nem para a operação ler
    como endereço. Correção de fix round 2 (code review): a versão
    anterior deste docstring dizia "oito campos", contado errado — o corpo
    da função só lê `ship_street`, `ship_number`, `ship_complement`,
    `ship_neighborhood`, `ship_city`, `ship_state` e `ship_zip_code`.

    A coluna morreu porque um endereço em texto livre não dá para
    geocodificar (`GET /orders/{id}/route` precisa dos campos separados) nem
    para renderizar por parte. Mas a operação de staff lia essa string —
    então ela continua existindo, agora derivada (`PedidoStaffOut.de_order`).

    O FORMATO abaixo é invenção desta task, não algo herdado do legacy:
    `grep -rn "endereco_formatado" back-end/legacy/` não devolve nada (medido
    em 2026-08-09). O legacy tem `_destination_query`
    (`back-end/legacy/app/modules/tracking/services.py:117-127`), mas é uma
    string para GEOCODIFICAR (termina em `", Brazil"`, junta tudo com `", "`
    sem compor rua+número+complemento numa mesma parte), não uma string para
    a operação LER — formatos diferentes, propósitos diferentes.

    Pedido sem snapshot nenhum (criação com corpo vazio, ver
    `PedidoCreateIn`) devolve string vazia, não "None, None - None": cada
    parte só entra na composição se o campo correspondente não for None.
    """
    linha = ", ".join(p for p in (order.ship_street, order.ship_number, order.ship_complement) if p)
    if order.ship_neighborhood:
        linha = f"{linha} - {order.ship_neighborhood}" if linha else order.ship_neighborhood

    cidade_estado = " - ".join(p for p in (order.ship_city, order.ship_state) if p)

    partes = [linha, cidade_estado, order.ship_zip_code]
    return ", ".join(p for p in partes if p)
