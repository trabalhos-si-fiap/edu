"""Produto inativo não entra em carrinho novo, e a recompra o pula.

A outra metade da correção do finding 6 da revisão final de branch. O filtro
de LISTAGEM (`GET /products`, com e sem `partner_id`) está em
`tests/test_products_partner_filter.py`; aqui está a metade que o switch do
painel também promete: um produto tirado da prateleira não pode ser comprado
por quem tem o id dele.

Sem isto, o switch fecha só metade do caminho — o admin desativa o produto,
ele some da vitrine, e o aluno com a tela velha aberta ainda fecha o pedido.

**Carrinho e pedido JÁ EXISTENTES não são tocados.** Nada de varredura, nada
de remoção retroativa: um carrinho montado antes da desativação mantém o item
e fecha normalmente. Decidir o contrário seria regra de negócio sobre estorno
e estoque que ninguém pediu.
"""

import uuid
from decimal import Decimal

from edu_common.security import create_access_token
from sqlalchemy import select

from app.config import settings
from app.models.carrinho import Cart, CartItem
from app.models.ocorrencia import Ocorrencia
from app.models.pedido import Order, OrderItem
from app.models.produto import Estoque, Fornecedor, Product

_ALUNO = "00000000-0000-0000-0000-0000000000ee"


def headers_for(sub: str = _ALUNO) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, 'student', settings.jwt_secret)}"}


async def _parceiro(db_session) -> Fornecedor:
    fornecedor = Fornecedor(nome="Leroy Merlin", origem_rotulo="Cajamar, SP")
    db_session.add(fornecedor)
    await db_session.commit()
    await db_session.refresh(fornecedor)
    return fornecedor


async def _produto(db_session, fornecedor, *, nome: str, active: bool = True) -> Product:
    produto = Product(
        name=nome,
        type="mobiliario",
        price=Decimal("10.00"),
        sku=nome[:60],
        active=active,
    )
    db_session.add(produto)
    await db_session.commit()
    await db_session.refresh(produto)
    db_session.add(Estoque(produto_id=produto.id, fornecedor_id=fornecedor.id, quantidade=50))
    await db_session.commit()
    return produto


# ── POST /cart/items ───────────────────────────────────────────────────────


async def test_an_inactive_product_cannot_be_added_to_the_cart(client, db_session):
    fornecedor = await _parceiro(db_session)
    inativo = await _produto(db_session, fornecedor, nome="Cadeira aposentada", active=False)

    response = await client.post(
        "/cart/items", json={"product_id": str(inativo.id), "quantity": 1}, headers=headers_for()
    )

    assert response.status_code == 404


async def test_the_refused_item_never_lands_in_the_cart(client, db_session):
    fornecedor = await _parceiro(db_session)
    inativo = await _produto(db_session, fornecedor, nome="Cadeira aposentada", active=False)

    await client.post(
        "/cart/items", json={"product_id": str(inativo.id), "quantity": 1}, headers=headers_for()
    )

    itens = (await client.get("/cart", headers=headers_for())).json()["items"]
    assert itens == []


async def test_an_active_product_is_still_added(client, db_session):
    """O controle positivo: a recusa não pode alcançar o caminho normal."""
    fornecedor = await _parceiro(db_session)
    ativo = await _produto(db_session, fornecedor, nome="Luminária")

    response = await client.post(
        "/cart/items", json={"product_id": str(ativo.id), "quantity": 1}, headers=headers_for()
    )

    assert response.status_code == 201
    assert [i["name"] for i in response.json()["items"]] == ["Luminária"]


# ── POST /orders/{id}/rebuy ────────────────────────────────────────────────


async def test_rebuy_skips_a_product_that_was_deactivated(client, db_session):
    """Mesmo tratamento que o produto que saiu do catálogo: o aluno recebe o
    RESTO do pedido, não um erro. Um pedido de meses atrás quase sempre tem
    pelo menos um item fora de linha, e falhar por causa dele tornaria o botão
    inútil — a razão pela qual o `continue` já existia."""
    fornecedor = await _parceiro(db_session)
    ativo = await _produto(db_session, fornecedor, nome="Luminária")
    inativo = await _produto(db_session, fornecedor, nome="Cadeira aposentada", active=False)

    pedido = Order(user_id=uuid.UUID(_ALUNO), status="CRIADO", total=Decimal("20.00"))
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    for produto in (ativo, inativo):
        db_session.add(
            OrderItem(
                order_id=pedido.id,
                product_id=produto.id,
                product_name=produto.name,
                unit_price=Decimal("10.00"),
                quantity=1,
            )
        )
    await db_session.commit()

    response = await client.post(f"/orders/{pedido.id}/rebuy", headers=headers_for())

    assert response.status_code == 200
    assert [i["name"] for i in response.json()["items"]] == ["Luminária"]


# ── O que NÃO muda ─────────────────────────────────────────────────────────


async def test_an_item_already_in_the_cart_survives_deactivation_and_checks_out(client, db_session):
    """Sem varredura e sem remoção retroativa. O carrinho montado antes da
    desativação continua fechando o pedido."""
    fornecedor = await _parceiro(db_session)
    produto = await _produto(db_session, fornecedor, nome="Luminária")

    adicionado = await client.post(
        "/cart/items", json={"product_id": str(produto.id), "quantity": 1}, headers=headers_for()
    )
    assert adicionado.status_code == 201

    produto.active = False
    await db_session.commit()

    ainda_la = (await client.get("/cart", headers=headers_for())).json()["items"]
    assert [i["name"] for i in ainda_la] == ["Luminária"]

    pedido = await client.post("/orders", json={"payment_method": "PIX"}, headers=headers_for())
    assert pedido.status_code == 201
    assert [i["product_name"] for i in pedido.json()["items"]] == ["Luminária"]


async def test_a_past_order_still_lists_its_deactivated_item(client, db_session):
    """Pedido é registro histórico. Desativar o produto não pode reescrevê-lo."""
    fornecedor = await _parceiro(db_session)
    inativo = await _produto(db_session, fornecedor, nome="Cadeira aposentada", active=False)

    pedido = Order(user_id=uuid.UUID(_ALUNO), status="CRIADO", total=Decimal("10.00"))
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    db_session.add(
        OrderItem(
            order_id=pedido.id,
            product_id=inativo.id,
            product_name=inativo.name,
            unit_price=Decimal("10.00"),
            quantity=1,
        )
    )
    await db_session.commit()

    detalhe = await client.get(f"/orders/{pedido.id}", headers=headers_for())

    assert detalhe.status_code == 200
    assert [i["product_name"] for i in detalhe.json()["items"]] == ["Cadeira aposentada"]


async def test_the_service_refuses_before_creating_a_cart_row(client, db_session):
    """A recusa acontece ANTES de qualquer escrita — é essa propriedade que o
    `continue` de `recomprar` depende para não deixar a sessão suja, e a mesma
    que o docstring de `POST /orders/{id}/rebuy` declara."""
    fornecedor = await _parceiro(db_session)
    inativo = await _produto(db_session, fornecedor, nome="Cadeira aposentada", active=False)

    await client.post(
        "/cart/items", json={"product_id": str(inativo.id), "quantity": 1}, headers=headers_for()
    )

    assert (await db_session.execute(select(CartItem))).scalars().all() == []
    assert (await db_session.execute(select(Cart))).scalars().first() is None


# ── A terceira porta: a substituição de ocorrência de falta de estoque ─────
#
# `sugerir_substitutos` filtrava candidatos por `Estoque.quantidade > 0` e não
# por `Product.active`, e o ramo `substituir` de `POST /occurrences/{id}/resolve`
# escreve o produto escolhido DIRETO no `order_items` — sem passar por
# `adicionar_item`. Era a única porta que contornava a regra inteira, e ela
# escreve num PEDIDO, não num carrinho.
#
# Duas consultas de candidato, não uma: a semântica e o fallback
# `_buscar_por_categoria`, que dispara sempre que a similaridade fica abaixo
# do limiar ou o modelo de embeddings falha. Filtrar só a primeira deixaria a
# porta aberta pelo caminho degradado, que é justamente o que roda quando algo
# dá errado.

_SEPARADOR = "00000000-0000-0000-0000-0000000000e1"


def _staff_headers(role: str, sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _pedido_em_separacao(db_session, produto: Product) -> Order:
    pedido = Order(
        user_id=uuid.UUID(_ALUNO),
        status="em_separacao",
        total=Decimal("10.00"),
        picker_id=uuid.UUID(_SEPARADOR),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    db_session.add(
        OrderItem(
            order_id=pedido.id,
            product_id=produto.id,
            product_name=produto.name,
            unit_price=Decimal("10.00"),
            quantity=1,
        )
    )
    await db_session.commit()
    return pedido


async def test_an_inactive_product_is_never_suggested_as_a_substitute(client, db_session):
    fornecedor = await _parceiro(db_session)
    faltante = await _produto(db_session, fornecedor, nome="Caderno universitário")
    # MESMO `type` do faltante, para que as DUAS consultas de candidato — a
    # semântica e o fallback por categoria — o encontrassem antes do fix.
    await _produto(db_session, fornecedor, nome="Caderno colegial", active=False)
    pedido = await _pedido_em_separacao(db_session, faltante)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={
            "pedido_id": str(pedido.id),
            "produto_id": str(faltante.id),
            "motivo": "sem estoque na prateleira",
        },
        headers=_staff_headers("separador", _SEPARADOR),
    )

    assert response.status_code == 201
    assert response.json()["produtos_sugeridos"] == []


async def test_an_active_product_is_still_suggested(client, db_session):
    """Controle positivo: o filtro não pode zerar a sugestão de todo mundo."""
    fornecedor = await _parceiro(db_session)
    faltante = await _produto(db_session, fornecedor, nome="Caderno universitário")
    substituto = await _produto(db_session, fornecedor, nome="Caderno colegial")
    pedido = await _pedido_em_separacao(db_session, faltante)

    response = await client.post(
        "/occurrences/stock-shortage",
        json={
            "pedido_id": str(pedido.id),
            "produto_id": str(faltante.id),
            "motivo": "sem estoque na prateleira",
        },
        headers=_staff_headers("separador", _SEPARADOR),
    )

    assert response.status_code == 201
    assert [p["id"] for p in response.json()["produtos_sugeridos"]] == [str(substituto.id)]


async def test_resolving_with_an_inactive_substitute_is_refused(client, db_session):
    """A porta de ESCRITA, e ela não depende da lista de sugestões: o
    `produto_escolhido_id` vem do corpo da requisição. Fechar só a sugestão
    seria meia resposta de novo."""
    fornecedor = await _parceiro(db_session)
    faltante = await _produto(db_session, fornecedor, nome="Caderno universitário")
    inativo = await _produto(db_session, fornecedor, nome="Caderno aposentado", active=False)
    pedido = await _pedido_em_separacao(db_session, faltante)

    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="FALTA_ESTOQUE",
        status="ABERTA",
        motivo="sem estoque",
        produto_id=faltante.id,
        criado_por=uuid.UUID(_SEPARADOR),
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        json={"resolucao": "substituir", "produto_escolhido_id": str(inativo.id)},
        headers=headers_for(),
    )

    assert response.status_code == 404

    item = (
        await db_session.execute(select(OrderItem).where(OrderItem.order_id == pedido.id))
    ).scalar_one()
    await db_session.refresh(item)
    assert item.product_id == faltante.id
    assert item.product_name == "Caderno universitário"


async def test_resolving_with_an_active_substitute_still_works(client, db_session):
    fornecedor = await _parceiro(db_session)
    faltante = await _produto(db_session, fornecedor, nome="Caderno universitário")
    substituto = await _produto(db_session, fornecedor, nome="Caderno colegial")
    pedido = await _pedido_em_separacao(db_session, faltante)

    ocorrencia = Ocorrencia(
        pedido_id=pedido.id,
        tipo="FALTA_ESTOQUE",
        status="ABERTA",
        motivo="sem estoque",
        produto_id=faltante.id,
        criado_por=uuid.UUID(_SEPARADOR),
    )
    db_session.add(ocorrencia)
    await db_session.commit()
    await db_session.refresh(ocorrencia)

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        json={"resolucao": "substituir", "produto_escolhido_id": str(substituto.id)},
        headers=headers_for(),
    )

    assert response.status_code == 200

    item = (
        await db_session.execute(select(OrderItem).where(OrderItem.order_id == pedido.id))
    ).scalar_one()
    await db_session.refresh(item)
    assert item.product_id == substituto.id


# ── O caminho DEGRADADO da substituição ────────────────────────────────────
#
# Achado da re-revisão: o `fake_encoder` do `conftest.py` sempre passa do
# `LIMIAR_SIMILARIDADE`, então a suíte inteira só exercitava a consulta
# semântica — tirar o `Product.active.is_(True)` de `_buscar_por_categoria`
# deixava tudo verde. Ou seja, a porta que abre exatamente quando o modelo de
# embeddings falha era a única sem teste atrás dela.
#
# O alvo do monkeypatch é `app.services.substituicao_ia.gerar_embedding`, o
# NOME onde o chamador importou a função — remendar
# `app.services.embeddings.gerar_embedding` não afetaria a cópia que o
# `from ... import` já colocou no namespace de `substituicao_ia`. Mesma
# armadilha que o `_stub_publish_event` do `conftest.py` documenta.
#
# **O fixture precisa de um candidato ATIVO além do inativo**, e isso não é
# detalhe: `sugerir_substitutos` faz `if not candidatos: return []` ANTES do
# `try`, usando a consulta semântica — que já é filtrada. Com só um candidato
# inativo, a função retorna cedo e `_buscar_por_categoria` nunca roda; o teste
# passaria pelo motivo errado, verde por curto-circuito. Medido: a primeira
# versão deste teste ficava verde com o filtro do fallback REMOVIDO.


def _quebrar_embeddings(monkeypatch) -> None:
    def _explode(*_args, **_kwargs):
        raise RuntimeError("modelo de embeddings indisponível")

    monkeypatch.setattr("app.services.substituicao_ia.gerar_embedding", _explode)


async def _reportar_falta(client, pedido, faltante):
    return await client.post(
        "/occurrences/stock-shortage",
        json={
            "pedido_id": str(pedido.id),
            "produto_id": str(faltante.id),
            "motivo": "sem estoque na prateleira",
        },
        headers=_staff_headers("separador", _SEPARADOR),
    )


async def test_the_degraded_path_never_suggests_an_inactive_product(
    client, db_session, monkeypatch
):
    """Sem modelo de embeddings, `sugerir_substitutos` cai em
    `_buscar_por_categoria` pelo `except Exception` — de propósito, para falha
    de IA nunca impedir o separador de reportar falta. É o caminho que roda
    quando algo já deu errado, e é o que precisa do mesmo filtro.

    A lista devolvida ser exatamente `[ativo]` prova as DUAS coisas de uma vez:
    o fallback REALMENTE rodou (senão viria vazia, com o encoder quebrado) e o
    inativo não entrou nela."""
    _quebrar_embeddings(monkeypatch)
    fornecedor = await _parceiro(db_session)
    faltante = await _produto(db_session, fornecedor, nome="Caderno universitário")
    ativo = await _produto(db_session, fornecedor, nome="Caderno colegial")
    inativo = await _produto(db_session, fornecedor, nome="Caderno aposentado", active=False)
    pedido = await _pedido_em_separacao(db_session, faltante)

    response = await _reportar_falta(client, pedido, faltante)

    assert response.status_code == 201
    sugeridos = [p["id"] for p in response.json()["produtos_sugeridos"]]
    assert sugeridos == [str(ativo.id)]
    assert str(inativo.id) not in sugeridos


async def test_a_dead_embedding_model_never_blocks_the_shortage_report(
    client, db_session, monkeypatch
):
    """A propriedade que o módulo declara no próprio docstring: falha do
    modelo degrada a qualidade da sugestão, nunca derruba o fluxo do
    separador."""
    _quebrar_embeddings(monkeypatch)
    fornecedor = await _parceiro(db_session)
    faltante = await _produto(db_session, fornecedor, nome="Caderno universitário")
    ativo = await _produto(db_session, fornecedor, nome="Caderno colegial")
    pedido = await _pedido_em_separacao(db_session, faltante)

    response = await _reportar_falta(client, pedido, faltante)

    assert response.status_code == 201
    assert [p["id"] for p in response.json()["produtos_sugeridos"]] == [str(ativo.id)]
