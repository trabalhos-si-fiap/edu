"""Seed idempotente de parceiro, do catálogo da Leroy Merlin, e de estoque.

TRÊS coisas num arquivo só porque as três são a MESMA invariante da spec:
todo produto tem estoque, todo estoque tem fornecedor, todo fornecedor tem
origem. Separá-las produziria três seeds cuja ordem de execução importa e
não está escrita em lugar nenhum.

O catálogo da Leroy é SEED, não integração: não existe API pública da Leroy
Merlin, e o ponto da entrega é o app abrir uma seção de parceiro, não puxar
preço de terceiro.

O nome "Leroy Merlin" aparece aqui e SÓ aqui. Quem decide se a seção do app
aparece é `fornecedores.ativo` (ver `app/services/parceiros.py`); desativar
no painel esvazia a seção sem tocar em código. O teste
`test_no_partner_name_appears_in_a_decision_path` trava isso varrendo `app/`.

Rodar dentro do container do commerce-service (`make services-seed`):

    uv run python -m app.seeds.parceiros
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.produto import Estoque, Fornecedor, Product
from app.seeds.products import _fetch_image  # mesmo downloader do seed de produto

if TYPE_CHECKING:
    from app.storage import ObjectStorage

# Lock consultivo de transação, no mesmo espírito do `_SEED_LOCK_ID` de
# `app/seeds/products.py` (task 1 da spec A): duas execuções simultâneas do
# seed liam "não existe" ao mesmo tempo e inseriam as duas.
_SEED_LOCK_ID = 0x5EED_B_0001

FORNECEDOR_EDU = {
    "nome": "Edu",
    "contato": "logistica@edu.example.com",
    "origem_rotulo": "Aclimação, SP",
    "origem_lat": Decimal("-23.573000"),
    "origem_lng": Decimal("-46.630000"),
}

FORNECEDOR_LEROY = {
    "nome": "Leroy Merlin",
    "contato": "parceria@leroymerlin.com.br",
    "origem_rotulo": "Cajamar, SP",
    "origem_lat": Decimal("-23.355800"),
    "origem_lng": Decimal("-46.876400"),
}

SEED_PARCEIROS: list[dict] = [FORNECEDOR_EDU, FORNECEDOR_LEROY]

# Produtos de ambiente de estudo, como a spec pede: mesa, luminária, cadeira,
# organizadores. Preço e estoque plausíveis; a foto usa o mesmo caminho
# Unsplash do seed de produto.
SEED_PRODUTOS_LEROY: list[dict] = [
    {
        "sku": "LM-MESA-120",
        "name": "Mesa de estudo 120 cm",
        "type": "mobiliario",
        "subtype": "Mesa",
        "description": "Tampo de 120 x 60 cm em MDF, com passa-cabos e pés de aço.",
        "price": "399.90",
        "photo_id": "photo-1518455027359-f3f8164ba6bd",
        "quantidade": 24,
        "estoque_minimo": 4,
    },
    {
        "sku": "LM-LUMI-LED",
        "name": "Luminária de mesa LED",
        "type": "iluminacao",
        "subtype": "Luminária",
        "description": "Três temperaturas de cor e braço articulado, com porta USB.",
        "price": "129.90",
        "photo_id": "photo-1507473885765-e6ed057f782c",
        "quantidade": 40,
        "estoque_minimo": 8,
    },
    {
        "sku": "LM-CADEIRA-ERG",
        "name": "Cadeira ergonômica",
        "type": "mobiliario",
        "subtype": "Cadeira",
        "description": "Encosto em tela, apoio lombar ajustável e braços reguláveis.",
        "price": "749.00",
        "photo_id": "photo-1580480055273-228ff5388ef8",
        "quantidade": 12,
        "estoque_minimo": 3,
    },
    {
        "sku": "LM-ORG-GAV",
        "name": "Organizador de gavetas",
        "type": "organizacao",
        "subtype": "Organizador",
        "description": "Conjunto de quatro divisórias empilháveis para material de estudo.",
        "price": "89.90",
        "photo_id": "photo-1544816155-12df9643f363",
        "quantidade": 60,
        "estoque_minimo": 10,
    },
]


def _unsplash(photo_id: str) -> str:
    return f"https://images.unsplash.com/{photo_id}?w=800&h=800&fit=crop&q=80&fm=jpg"


async def seed_parceiros(
    session: AsyncSession,
    *,
    storage: "ObjectStorage | None" = None,
    fetch_image=_fetch_image,
) -> dict[str, int]:
    """Cria os dois fornecedores, o catálogo da Leroy e as linhas de estoque.

    Também ADOTA o catálogo próprio: todo produto sem linha de estoque passa
    a pertencer ao fornecedor "Edu". Sem isso os seis produtos de
    `SEED_PRODUCTS` continuariam invisíveis para toda seção de parceiro e
    todo pedido que os contivesse sairia sem origem.

    Idempotente: fornecedor casado por `nome`, produto por `sku`, estoque
    pelo par (produto, fornecedor) — a unicidade que a tabela já declara.
    Devolve quantos de cada foram INSERIDOS.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": _SEED_LOCK_ID}
    )

    inseridos = {"parceiros": 0, "produtos": 0, "estoques": 0}

    existentes = {f.nome: f for f in (await session.execute(select(Fornecedor))).scalars().all()}
    for dados in SEED_PARCEIROS:
        if dados["nome"] in existentes:
            continue
        fornecedor = Fornecedor(**dados, ativo=True)
        session.add(fornecedor)
        existentes[dados["nome"]] = fornecedor
        inseridos["parceiros"] += 1
    await session.flush()

    edu = existentes[FORNECEDOR_EDU["nome"]]
    leroy = existentes[FORNECEDOR_LEROY["nome"]]

    produtos_por_sku = {
        p.sku: p for p in (await session.execute(select(Product))).scalars().all() if p.sku
    }
    for dados in SEED_PRODUTOS_LEROY:
        produto = produtos_por_sku.get(dados["sku"])
        if produto is None:
            produto = Product(
                name=dados["name"],
                type=dados["type"],
                subtype=dados["subtype"],
                description=dados["description"],
                price=Decimal(dados["price"]),
                sku=dados["sku"],
                active=True,
            )
            session.add(produto)
            produtos_por_sku[dados["sku"]] = produto
            inseridos["produtos"] += 1
        await _aplicar_imagem(produto, dados, storage=storage, fetch_image=fetch_image)
    await session.flush()

    # Estoque: casado pelo par (produto, fornecedor) — a mesma unicidade que
    # `uq_produto_fornecedor` declara na tabela.
    pares = {
        (e.produto_id, e.fornecedor_id)
        for e in (await session.execute(select(Estoque))).scalars().all()
    }
    for dados in SEED_PRODUTOS_LEROY:
        produto = produtos_por_sku[dados["sku"]]
        if (produto.id, leroy.id) in pares:
            continue
        session.add(
            Estoque(
                produto_id=produto.id,
                fornecedor_id=leroy.id,
                quantidade=dados["quantidade"],
                estoque_minimo=dados["estoque_minimo"],
            )
        )
        pares.add((produto.id, leroy.id))
        inseridos["estoques"] += 1

    # Adoção do catálogo próprio.
    com_estoque = {produto_id for produto_id, _ in pares}
    orfaos = [
        p
        for p in (await session.execute(select(Product))).scalars().all()
        if p.id not in com_estoque
    ]
    for produto in orfaos:
        session.add(
            Estoque(produto_id=produto.id, fornecedor_id=edu.id, quantidade=25, estoque_minimo=5)
        )
        inseridos["estoques"] += 1

    await session.commit()
    logger.info("seed de parceiros: {}", inseridos)
    return inseridos


async def _aplicar_imagem(produto, dados, *, storage, fetch_image) -> None:
    """Mesmo contrato do `_apply_image` do seed de produto: falha de download
    é logada e deixa a imagem atual intacta, nunca apaga uma foto boa."""
    if storage is None:
        return
    chave = f"products/partner-{dados['sku'].lower()}.jpg"
    try:
        corpo = await fetch_image(_unsplash(dados["photo_id"]))
    except Exception as exc:  # rede/HTTP/timeout/tamanho
        logger.warning("seed: falha ao baixar foto de {!r}: {}", dados["sku"], exc)
        return
    await storage.put_object(chave, corpo, "image/jpeg")
    produto.image_url = chave


async def main() -> None:
    from app.storage import ObjectStorage

    async with async_session() as session:
        inseridos = await seed_parceiros(session, storage=ObjectStorage())
        logger.info("inseridos: {}", inseridos)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
