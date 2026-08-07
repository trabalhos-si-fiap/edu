"""Porte de `legacy/tests/seeds/test_products_seed.py`.

Duas adaptações, ambas medidas:

1. `app.modules.products.models` virou `app.models.produto` (Product) e
   `app.models.review` (Review) — layout deste serviço.
2. `test_solid_png_is_a_valid_image` do legacy chamava
   `app.core.media.validate_image_bytes`, que NÃO existe neste serviço
   (`grep -rn "validate_image_bytes" back-end --include="*.py"` só devolve
   linhas em `legacy/`). A validação foi reescrita com a stdlib: assinatura,
   CRC de cada chunk, IHDR e IDAT descomprimido. Prova mais, não menos.
"""

import struct
import zlib

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.produto import Product
from app.models.review import Review
from app.seeds.products import SEED_PRODUCTS, seed_products

# Valores DIGITADOS À MÃO a partir do legacy, não lidos de `SEED_PRODUCTS` — é
# o que dá a este teste independência do que ele trava. Lidos com:
#
#     grep -n '"name":\|"type":\|"subtype":\|"price":' \
#         back-end/legacy/app/seeds/products.py
#
# Os outros testes deste arquivo aferem contra `len(SEED_PRODUCTS)` e
# `SEED_PRODUCTS[0]["name"]`, isto é, contra a própria constante que deveriam
# proteger: medido pelo review, trocar um preço ou APAGAR um produto inteiro
# deixava a suíte com 176 verdes. Este é o único teste do arquivo que pega
# essas duas mutações.
_CATALOGO_LEGACY = (
    ("Guia de Redação Nota 1000", "apostila", "Apostila Digital", "49.90"),
    ("Mastering Data Synthesis", "curso", "Premium Course", "189.90"),
    ("Diagnostic AI Toolkit", "digital", "Digital Tool", "45.00"),
    ("Simulado ENEM Completo", "apostila", "Apostila", "29.90"),
    ("Mapa Mental de Biologia", "digital", "Material Digital", "19.90"),
    ("Curso de Matemática Essencial", "curso", "Curso", "149.90"),
)


def test_catalog_matches_the_legacy_contract() -> None:
    esperado = {nome: campos for nome, *campos in map(list, _CATALOGO_LEGACY)}
    atual = {d["name"]: [d["type"], d["subtype"], d["price"]] for d in SEED_PRODUCTS}

    # Esta asserção vem ANTES da contagem de propósito: com ela depois, apagar
    # um produto falhava só com `assert 5 == 6`, sem dizer QUAL sumiu — medido
    # na rodada de correção 1.
    assert sorted(atual) == sorted(esperado), (
        f"o catálogo mudou — sumiram: {sorted(set(esperado) - set(atual))}; "
        f"entraram: {sorted(set(atual) - set(esperado))}"
    )
    assert len(SEED_PRODUCTS) == 6
    for nome, campos in esperado.items():
        assert atual[nome] == campos, f"{nome}: (type, subtype, price) saiu do contrato"

    # A ORDEM também é contrato: o índice da lista vira a chave
    # `products/seed-{i}.jpg`, então reordenar troca a foto de cada produto sem
    # mudar nenhum valor.
    assert [d["name"] for d in SEED_PRODUCTS] == [t[0] for t in _CATALOGO_LEGACY]


def test_every_seed_product_has_a_unique_unsplash_photo_url() -> None:
    from app.seeds.products import SEED_PRODUCTS

    urls = [data["photo_url"] for data in SEED_PRODUCTS]
    for url in urls:
        assert url.startswith("https://images.unsplash.com/")
        assert "fm=jpg" in url
        assert "fit=crop" in url
    assert len(set(urls)) == len(urls)  # one distinct photo per product


class TestProductsSeed:
    async def test_inserts_full_catalog(self, db_session: AsyncSession) -> None:
        inserted = await seed_products(db_session)
        assert inserted == len(SEED_PRODUCTS)

        total = (await db_session.execute(select(func.count()).select_from(Product))).scalar_one()
        assert total == len(SEED_PRODUCTS)

    async def test_seeds_sample_reviews_and_headline_aggregates(
        self, db_session: AsyncSession
    ) -> None:
        await seed_products(db_session)

        product = (
            await db_session.execute(
                select(Product).where(Product.name == "Guia de Redação Nota 1000")
            )
        ).scalar_one()
        assert product.rating_count == 128
        assert float(product.rating_avg) == 4.5

        review_count = (
            await db_session.execute(
                select(func.count()).select_from(Review).where(Review.product_id == product.id)
            )
        ).scalar_one()
        assert review_count == 2

    async def test_is_idempotent(self, db_session: AsyncSession) -> None:
        first = await seed_products(db_session)
        second = await seed_products(db_session)
        assert first == len(SEED_PRODUCTS)
        assert second == 0

        total = (await db_session.execute(select(func.count()).select_from(Product))).scalar_one()
        assert total == len(SEED_PRODUCTS)


def _png_chunks(data: bytes):
    """Itera os chunks de um PNG conferindo o CRC de cada um."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        typ = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        assert crc == zlib.crc32(typ + payload) & 0xFFFFFFFF, f"CRC inválido no chunk {typ!r}"
        yield typ, payload
        pos += 12 + length


def test_solid_png_is_a_valid_image() -> None:
    from app.seeds.products import _solid_png

    png = _solid_png(8, 8, (10, 20, 30))
    chunks = dict(_png_chunks(png))
    assert set(chunks) == {b"IHDR", b"IDAT", b"IEND"}

    width, height, bit_depth, color_type = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert (width, height, bit_depth, color_type) == (8, 8, 8, 2)  # 8-bit RGB

    # Cada linha é "byte de filtro 0" + 8 pixels RGB da cor pedida.
    raw = zlib.decompress(chunks[b"IDAT"])
    assert raw == (b"\x00" + bytes((10, 20, 30)) * 8) * 8


class _RecordingStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str]] = []
        self.deletes: list[str] = []

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        self.puts.append((key, content_type))

    async def delete_object(self, key: str) -> None:
        self.deletes.append(key)


# Minimal valid-looking JPEG payload for the fake downloader.
_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 64 + b"\xff\xd9"


async def _fake_fetch(url: str) -> bytes:
    return _JPEG_BYTES


async def test_seed_uses_the_injected_fetch_image_and_opens_no_client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova que o parâmetro `fetch_image` sobreviveu ao porte.

    Sabotar `httpx.AsyncClient` é o que fecha a prova: `_fetch_image` (o default)
    o instancia, então se o seed caísse no downloader real esta chamada
    estouraria `AssertionError` em vez de passar. Remendar
    `app.seeds.products._fetch_image` NÃO serviria — o default do parâmetro é
    resolvido no `def`, e ficaria apontando para a função original.

    O fetch injetado também confere a URL recebida: tem que ser exatamente a
    `photo_url` de cada entrada de `SEED_PRODUCTS`, na ordem.
    """

    class _NoNetwork:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("o seed abriu um httpx.AsyncClient — injeção perdida")

    monkeypatch.setattr(httpx, "AsyncClient", _NoNetwork)

    esperadas = [data["photo_url"] for data in SEED_PRODUCTS]
    vistas: list[str] = []

    async def _recording_fetch(url: str) -> bytes:
        assert url in esperadas, f"URL inesperada: {url}"
        vistas.append(url)
        return _JPEG_BYTES

    storage = _RecordingStorage()
    inserted = await seed_products(db_session, storage=storage, fetch_image=_recording_fetch)

    assert inserted == len(SEED_PRODUCTS)
    assert vistas == esperadas
    assert [k for k, _ in storage.puts] == [f"products/seed-{i}.jpg" for i in range(len(esperadas))]


async def test_seed_uploads_image_and_sets_key_when_storage_given(
    db_session: AsyncSession,
) -> None:
    storage = _RecordingStorage()
    inserted = await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)
    assert inserted == len(SEED_PRODUCTS)
    assert len(storage.puts) == len(SEED_PRODUCTS)
    assert all(
        k.startswith("products/seed-") and k.endswith(".jpg") and ct == "image/jpeg"
        for k, ct in storage.puts
    )

    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    assert product.image_url.startswith("products/seed-")
    assert product.image_url.endswith(".jpg")


async def test_seed_backfills_images_for_existing_products_without_one(
    db_session: AsyncSession,
) -> None:
    # Products inserted before the storage wiring have an empty image_url.
    # Re-running with storage must backfill them (download + upload).
    await seed_products(db_session)
    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    assert product.image_url == ""

    storage = _RecordingStorage()
    inserted = await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)
    assert inserted == 0  # nothing new inserted
    assert len(storage.puts) == len(SEED_PRODUCTS)  # but every product got an image

    await db_session.refresh(product)
    assert product.image_url.startswith("products/seed-")
    assert product.image_url.endswith(".jpg")


async def test_seed_always_overwrites_images(db_session: AsyncSession) -> None:
    storage = _RecordingStorage()
    await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)

    # A second run re-uploads every product's image (always overwrite). Keys are
    # already .jpg, so there is no superseded object to delete.
    storage2 = _RecordingStorage()
    await seed_products(db_session, storage=storage2, fetch_image=_fake_fetch)
    assert len(storage2.puts) == len(SEED_PRODUCTS)
    assert storage2.deletes == []


async def test_seed_replaces_legacy_png_and_deletes_old_object(
    db_session: AsyncSession,
) -> None:
    # Simulate a product that still carries a legacy solid-color .png key.
    await seed_products(db_session)
    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    product.image_url = "products/seed-0.png"
    await db_session.commit()

    storage = _RecordingStorage()
    await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)

    await db_session.refresh(product)
    assert product.image_url == "products/seed-0.jpg"
    assert "products/seed-0.png" in storage.deletes


async def test_seed_download_failure_keeps_existing_image(
    db_session: AsyncSession,
) -> None:
    storage = _RecordingStorage()
    await seed_products(db_session, storage=storage, fetch_image=_fake_fetch)
    product = (
        await db_session.execute(select(Product).where(Product.name == SEED_PRODUCTS[0]["name"]))
    ).scalar_one()
    before = product.image_url
    assert before.endswith(".jpg")

    async def _boom(url: str) -> bytes:
        raise RuntimeError("network down")

    storage2 = _RecordingStorage()
    await seed_products(db_session, storage=storage2, fetch_image=_boom)
    assert storage2.puts == []

    await db_session.refresh(product)
    assert product.image_url == before
