"""Seed de parceiro. Idempotente em DUAS passadas, como o seed de produto.

Este seed também repara o catálogo existente: os seis produtos de
`SEED_PRODUCTS` (`app/seeds/products.py`) nunca tiveram linha de estoque —
medido, `grep -n "Estoque" app/seeds/products.py` não devolvia nada antes
desta task. Sem fornecedor, eles não aparecem sob parceiro nenhum e o pedido
que os contém sai sem origem. Aqui eles passam a pertencer ao fornecedor
"Edu", com origem Aclimação/SP.
"""

from sqlalchemy import func, select

from app.models.produto import Estoque, Fornecedor, Product
from app.seeds.parceiros import FORNECEDOR_EDU, FORNECEDOR_LEROY, seed_parceiros
from app.seeds.products import SEED_PRODUCTS, seed_products


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
