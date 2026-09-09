"""Emissão dos códigos copia-e-cola de PIX e boleto.

NÃO É INTEGRAÇÃO COM PROVEDOR DE PAGAMENTO. Nenhum banco, nenhuma API, nenhum
dinheiro. É exatamente o mesmo algoritmo que rodava dentro do app Flutter
(`checkout_screen.dart::_generatePixCode` e `::_generateBoletoCode`), movido
para onde o dado nasce. O payload tem a FORMA de um EMV de PIX e a linha tem
a FORMA de uma linha digitável, e nenhum dos dois é pagável em lugar nenhum.
Isto está dito aqui, e no relatório final da entrega, de propósito.

O que MUDA em relação ao mock do cliente: o identificador é DERIVADO do
`order_id` em vez de sorteado. O cliente usava `Random()`, então o mesmo
pedido produzia um código diferente a cada vez — o aluno que fechasse a
caixa de diálogo e a reabrisse recebia outro código do que já tinha copiado.
Derivar do pedido conserta isso e torna o teste de paridade possível.

A derivação é `sha256` do id do pedido. Não é segredo, não é assinatura, não
protege nada — é só uma função determinística e bem distribuída de UUID para
alfabeto. Por isso NÃO usa `hmac` nem chave: não há nada a autenticar aqui, e
fingir que há seria pior que não ter. `usedforsecurity=False` documenta essa
intenção para quem lê o código (e também satisfaz a regra `S324` do ruff, que
sinaliza hash fraco quando pensa que o uso É de segurança).
"""

import hashlib
import uuid

# Template EMV do mock do cliente, byte a byte. O `6304ABCD` do fim é um CRC
# fixo e FALSO — no EMV real ele é calculado sobre o payload. Preservado como
# estava: mudá-lo não tornaria o código pagável, só esconderia que é mock.
PIX_PREFIXO = (
    "00020126360014BR.GOV.BCB.PIX0114+5511999999999"
    "5204000053039865802BR5909EDU STORE6009SAO PAULO62290525"
)
PIX_SUFIXO = "6304ABCD"
TXID_ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
TXID_TAMANHO = 25
LINHA_DIGITOS = 47


def _bytes_do_pedido(order_id: uuid.UUID, dominio: str) -> bytes:
    """`dominio` separa os dois códigos: sem ele, PIX e boleto do mesmo
    pedido derivariam da mesma sequência de bytes."""
    return hashlib.sha256(f"{dominio}:{order_id}".encode(), usedforsecurity=False).digest()


def gerar_codigo_pix(order_id: uuid.UUID) -> str:
    fonte = _bytes_do_pedido(order_id, "pix")
    txid = "".join(
        TXID_ALFABETO[fonte[i % len(fonte)] % len(TXID_ALFABETO)] for i in range(TXID_TAMANHO)
    )
    return f"{PIX_PREFIXO}{txid}{PIX_SUFIXO}"


def gerar_linha_digitavel(order_id: uuid.UUID) -> str:
    fonte = _bytes_do_pedido(order_id, "boleto")
    d = "".join(str(fonte[i % len(fonte)] % 10) for i in range(LINHA_DIGITOS))
    # Agrupamento idêntico ao do cliente: 5.5 5.6 5.6 1 14.
    return f"{d[0:5]}.{d[5:10]} {d[10:15]}.{d[15:21]} {d[21:26]}.{d[26:32]} {d[32:33]} {d[33:47]}"


def gerar_codigo_pagamento(order_id: uuid.UUID, payment_method: str) -> str | None:
    """Despacha pelo RÓTULO que o app escolheu e que `orders.payment_method`
    guarda ("PIX", "Boleto", "Visa ••••1234").

    Cartão devolve `None`: não há nada para copiar, e o app já mostra
    "Pedido finalizado com sucesso!" nesse caminho. Devolver string vazia em
    vez de `None` faria a tela abrir uma caixa de diálogo vazia.
    """
    rotulo = (payment_method or "").strip().lower()
    if rotulo == "pix":
        return gerar_codigo_pix(order_id)
    if rotulo == "boleto":
        return gerar_linha_digitavel(order_id)
    return None
