"""Seed de parceiro. Idempotente em DUAS passadas, como o seed de produto.

Este seed também repara o catálogo existente: os seis produtos de
`SEED_PRODUCTS` (`app/seeds/products.py`) nunca tiveram linha de estoque —
medido, `grep -n "Estoque" app/seeds/products.py` não devolvia nada antes
desta task. Sem fornecedor, eles não aparecem sob parceiro nenhum e o pedido
que os contém sai sem origem. Aqui eles passam a pertencer ao fornecedor
"Edu", com origem Aclimação/SP.
"""

import uuid

import pytest
from edu_common.security import create_access_token
from sqlalchemy import func, select

from app.config import settings
from app.models.pedido import Order
from app.models.produto import Estoque, Fornecedor, Product
from app.seeds.parceiros import (
    FORNECEDOR_EDU,
    FORNECEDOR_LEROY,
    SEED_PRODUTOS_LEROY,
    seed_parceiros,
)
from app.seeds.products import SEED_PRODUCTS, seed_products
from app.services.substituicao_ia import sugerir_substitutos

_ALUNO = "00000000-0000-0000-0000-0000000000dd"
_ADMIN = "00000000-0000-0000-0000-0000000000a9"


def _headers_admin() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(_ADMIN, 'admin', settings.jwt_secret)}"}


def _headers_aluno() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(_ALUNO, 'student', settings.jwt_secret)}"
    }


async def test_the_seed_creates_both_suppliers_with_their_origins(db_session):
    await seed_parceiros(db_session)

    fornecedores = {
        f.nome: f for f in (await db_session.execute(select(Fornecedor))).scalars().all()
    }
    assert set(fornecedores) == {FORNECEDOR_EDU["nome"], FORNECEDOR_LEROY["nome"]}
    assert fornecedores["Edu"].origem_rotulo == "Aclimação, SP"
    assert fornecedores["Leroy Merlin"].origem_rotulo == "Cajamar, SP"
    assert fornecedores["Leroy Merlin"].origem_lat is not None
    assert fornecedores["Leroy Merlin"].origem_lng is not None
    assert fornecedores["Leroy Merlin"].ativo is True


async def test_the_seed_is_idempotent_over_two_full_passes(db_session):
    primeira = await seed_parceiros(db_session)
    segunda = await seed_parceiros(db_session)

    assert primeira["parceiros"] == 2
    assert segunda == {"parceiros": 0, "produtos": 0, "estoques": 0}

    total_fornecedores = (
        await db_session.execute(select(func.count()).select_from(Fornecedor))
    ).scalar_one()
    assert total_fornecedores == 2


async def test_the_leroy_catalog_lands_with_stock_under_leroy(db_session):
    await seed_parceiros(db_session)

    leroy = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Leroy Merlin"))
    ).scalar_one()
    linhas = (
        (await db_session.execute(select(Estoque).where(Estoque.fornecedor_id == leroy.id)))
        .scalars()
        .all()
    )

    assert len(linhas) >= 4
    assert all(linha.quantidade > 0 for linha in linhas)
    assert all(linha.estoque_minimo >= 0 for linha in linhas)


async def test_every_seeded_leroy_product_has_a_unique_sku(db_session):
    await seed_parceiros(db_session)
    leroy = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Leroy Merlin"))
    ).scalar_one()
    produtos = (
        (
            await db_session.execute(
                select(Product)
                .join(Estoque, Estoque.produto_id == Product.id)
                .where(Estoque.fornecedor_id == leroy.id)
            )
        )
        .scalars()
        .all()
    )
    skus = [p.sku for p in produtos]
    assert all(skus)
    assert len(set(skus)) == len(skus)


def test_every_leroy_product_has_its_own_photo():
    fotos = [dados["photo_id"] for dados in SEED_PRODUTOS_LEROY]
    assert len(set(fotos)) == len(fotos)


# ── Uma segunda mesa, para a substituição ter o que sugerir ────────────────
#
# O roteiro de demonstração faz o separador reportar a mesa de 120 cm em
# falta. `sugerir_substitutos` só sugere produto ATIVO com estoque — sem outra
# mesa no catálogo, o aluno recebia uma cadeira ou nada.


async def _produto_por_sku(db_session, sku: str) -> Product:
    return (await db_session.execute(select(Product).where(Product.sku == sku))).scalar_one()


async def test_the_leroy_catalog_has_a_second_desk_with_stock(db_session):
    await seed_parceiros(db_session)

    mesa_grande = await _produto_por_sku(db_session, "LM-MESA-120")
    mesa_compacta = await _produto_por_sku(db_session, "LM-MESA-90")

    assert mesa_compacta.name == "Mesa de estudo compacta 90 cm"
    assert mesa_compacta.active is True
    # Mesmo `type` e `subtype`: é o que o fallback por categoria de
    # `sugerir_substitutos` compara quando os embeddings não respondem.
    assert (mesa_compacta.type, mesa_compacta.subtype) == (mesa_grande.type, mesa_grande.subtype)
    assert mesa_compacta.price < mesa_grande.price

    leroy = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Leroy Merlin"))
    ).scalar_one()
    estoque = (
        await db_session.execute(
            select(Estoque).where(
                Estoque.produto_id == mesa_compacta.id, Estoque.fornecedor_id == leroy.id
            )
        )
    ).scalar_one()
    assert estoque.quantidade > 0


async def test_a_desk_out_of_stock_gets_the_other_desk_suggested_without_embeddings(
    db_session, monkeypatch: pytest.MonkeyPatch
):
    """O caminho degradado, que é o determinístico: com o modelo de
    embeddings fora do ar, a sugestão cai para "mesmo `type` com estoque" — e
    a mesa compacta tem que estar nela."""
    await seed_parceiros(db_session)
    mesa_grande = await _produto_por_sku(db_session, "LM-MESA-120")
    mesa_compacta = await _produto_por_sku(db_session, "LM-MESA-90")

    def _modelo_fora_do_ar(*args, **kwargs):
        raise RuntimeError("sem internet")

    monkeypatch.setattr("app.services.substituicao_ia.gerar_embedding", _modelo_fora_do_ar)

    sugeridos = await sugerir_substitutos(db_session, mesa_grande.id)

    assert str(mesa_compacta.id) in sugeridos


async def test_the_seed_adopts_the_pre_existing_edu_catalog(db_session):
    """Rodar o seed de produto ANTES: os seis produtos próprios existem sem
    estoque. `seed_parceiros` tem que adotá-los sob "Edu", senão eles somem
    de toda seção de parceiro e todo pedido que os contém sai sem origem."""
    await seed_products(db_session)
    await seed_parceiros(db_session)

    edu = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Edu"))
    ).scalar_one()
    adotados = (
        await db_session.execute(
            select(func.count()).select_from(Estoque).where(Estoque.fornecedor_id == edu.id)
        )
    ).scalar_one()
    assert adotados == len(SEED_PRODUCTS)


async def test_running_in_the_other_order_gives_the_same_result(db_session):
    """`seed_parceiros` antes de `seed_products` também tem que fechar. O
    Makefile roda os dois, e a ordem entre eles não pode ser um detalhe que
    só quem escreveu conhece.

    A terceira chamada, no fim, prova que a ADOÇÃO em si é idempotente: as
    duas primeiras chamadas já cobrem "duas passadas completas" no sentido
    do seed como um todo, mas nenhuma delas roda a adoção duas vezes — a
    primeira não tem produto para adotar (ainda não existem), a segunda
    adota os seis pela primeira e única vez. Sem uma terceira chamada depois
    da adoção já ter acontecido, um bug que duplicasse a linha de estoque
    adotada a cada repetição passaria os outros testes deste arquivo em
    silêncio."""
    await seed_parceiros(db_session)
    await seed_products(db_session)
    await seed_parceiros(db_session)

    edu = (
        await db_session.execute(select(Fornecedor).where(Fornecedor.nome == "Edu"))
    ).scalar_one()
    adotados = (
        await db_session.execute(
            select(func.count()).select_from(Estoque).where(Estoque.fornecedor_id == edu.id)
        )
    ).scalar_one()
    assert adotados == len(SEED_PRODUCTS)

    terceira = await seed_parceiros(db_session)
    assert terceira == {"parceiros": 0, "produtos": 0, "estoques": 0}

    adotados_apos_repeticao = (
        await db_session.execute(
            select(func.count()).select_from(Estoque).where(Estoque.fornecedor_id == edu.id)
        )
    ).scalar_one()
    assert adotados_apos_repeticao == len(SEED_PRODUCTS)


def test_no_partner_name_appears_in_a_decision_path():
    """A regra da spec: "Filtro de parceiro ativo é regra de verdade, sem
    `if parceiro == "leroy"` em lugar nenhum". A string só pode existir em
    DADO de seed.

    Este é um teste de costura — nenhuma task individual o possuiria, e é
    exatamente a classe de achado que a revisão por task não vê (lição 3 do
    registro da spec A).
    """
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[1] / "app"
    permitidos = {raiz / "seeds" / "parceiros.py"}
    ofensores = []
    for arquivo in sorted(raiz.rglob("*.py")):
        if arquivo in permitidos:
            continue
        texto = arquivo.read_text(encoding="utf-8").lower()
        if "leroy" in texto:
            ofensores.append(str(arquivo.relative_to(raiz.parent)))
    assert ofensores == []


# ── Revisão final de branch, finding 5 ─────────────────────────────────────
#
# `Edu` semeado como parceiro ATIVO fazia o app mostrar todo produto duas
# vezes: a seção de parceiros renderizava um bloco `Edu` repetindo os seis
# produtos que a grade principal já mostra, mais um bloco `Leroy` repetindo os
# outros quatro. A spec previa "uma lista de UM elemento, a Leroy Merlin".
#
# `Edu` é o fornecedor da própria loja, não uma vitrine de parceiro. Semeá-lo
# INATIVO é a descrição honesta disso — e não afrouxa nada: a origem do pedido
# resolve por `Estoque -> Fornecedor` sem olhar `ativo`.


async def test_the_stores_own_supplier_is_seeded_inactive(db_session):
    await seed_parceiros(db_session)

    fornecedores = {
        f.nome: f for f in (await db_session.execute(select(Fornecedor))).scalars().all()
    }
    assert fornecedores[FORNECEDOR_EDU["nome"]].ativo is False
    assert fornecedores[FORNECEDOR_LEROY["nome"]].ativo is True


async def test_the_partners_section_lists_exactly_one_storefront(client, db_session):
    """O que o app pede: `GET /partners?active=true`."""
    await seed_parceiros(db_session)

    response = await client.get("/partners?active=true", headers=_headers_admin())

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["total"] == 1
    assert [p["nome"] for p in corpo["items"]] == [FORNECEDOR_LEROY["nome"]]


async def test_an_inactive_edu_still_anchors_the_shipping_origin(client, db_session):
    """A metade que não pode quebrar: `Edu` inativo continua sendo a origem
    de expedição dos produtos próprios. `criar_pedido_do_carrinho` resolve por
    `Estoque -> Fornecedor`, sem filtro de `ativo`."""
    await seed_products(db_session)
    await seed_parceiros(db_session)

    edu = (
        await db_session.execute(
            select(Fornecedor).where(Fornecedor.nome == FORNECEDOR_EDU["nome"])
        )
    ).scalar_one()
    produto_id = (
        (
            await db_session.execute(
                select(Estoque.produto_id).where(Estoque.fornecedor_id == edu.id)
            )
        )
        .scalars()
        .first()
    )

    await client.post(
        "/cart/items", json={"product_id": str(produto_id), "quantity": 1}, headers=_headers_aluno()
    )
    response = await client.post(
        "/orders", json={"payment_method": "PIX"}, headers=_headers_aluno()
    )

    assert response.status_code == 201
    pedido = (
        await db_session.execute(select(Order).where(Order.id == uuid.UUID(response.json()["id"])))
    ).scalar_one()
    assert pedido.origem_rotulo == FORNECEDOR_EDU["origem_rotulo"]
