"""Testes de paridade de `/payment-methods` — porte de
`legacy/tests/modules/payment_methods/test_routes.py` (task B9 do bloco B).
Ver `task-B9-report.md` para a lista completa de asserções adaptadas e para
as provas de ownership e de mutação que este arquivo acrescenta (o legacy
não tem nenhuma das duas).

Divergência de contrato herdada de B0/B6/B8: header ausente devolve 403 no
commerce (`edu-common`), não 401 como no legacy — só 1 asserção deste
arquivo muda por causa disso (`TestAuthRequired.test_list_requires_auth`).
"""

import asyncio
import uuid

import pytest
from edu_common.security import create_access_token
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.pagamento as pagamento_service
from app.config import settings
from app.models.pagamento import PaymentMethod

STUDENT_A = "00000000-0000-0000-0000-0000000000a1"
STUDENT_B = "00000000-0000-0000-0000-0000000000b2"


def headers_for(role: str, sub: str = "00000000-0000-0000-0000-000000000001") -> dict[str, str]:
    token = create_access_token(sub, role, settings.jwt_secret)
    return {"Authorization": f"Bearer {token}"}


def credit_card(**overrides: object) -> dict[str, object]:
    """Porte de `legacy/tests/modules/payment_methods/conftest.py::credit_card`."""
    base: dict[str, object] = {
        "type": "credit_card",
        "card_last4": "1234",
        "card_brand": "Visa",
        "cardholder_name": "Maria Silva",
        "card_expiry": "1230",
    }
    base.update(overrides)
    return base


def pix(**overrides: object) -> dict[str, object]:
    """Porte de `legacy/tests/modules/payment_methods/conftest.py::pix`."""
    base: dict[str, object] = {"type": "pix"}
    base.update(overrides)
    return base


class TestAuthRequired:
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        r = await client.get("/payment-methods")
        # 403, não 401: divergência medida na task B0 (edu-common responde
        # 403 para header ausente, 401 para token inválido/expirado; o
        # legacy responde 401 nos dois). Esta é a 1 das N=5 asserções
        # citadas pelo CONTEXTO DO CONTROLADOR do brief.
        assert r.status_code == 403


class TestPciSafety:
    async def test_full_card_number_is_rejected(self, client: AsyncClient) -> None:
        # Um cliente nunca deve mandar o PAN completo; campo extra é proibido.
        payload = credit_card(card_number="4111111111111111")
        r = await client.post("/payment-methods", json=payload, headers=headers_for("student"))
        assert r.status_code == 422

    async def test_cvv_is_rejected(self, client: AsyncClient) -> None:
        payload = credit_card(cvv="123")
        r = await client.post("/payment-methods", json=payload, headers=headers_for("student"))
        assert r.status_code == 422

    async def test_card_last4_must_be_four_digits(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods",
            json=credit_card(card_last4="4111111111111111"),
            headers=headers_for("student"),
        )
        assert r.status_code == 422

    async def test_stored_method_never_exposes_secret_fields(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods", json=credit_card(), headers=headers_for("student")
        )
        body = r.json()
        for forbidden in ("card_number", "pan", "cvv", "cardholder_tax_id"):
            assert forbidden not in body
        assert body["card_last4"] == "1234"


class TestCreate:
    async def test_first_method_is_default(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods", json=credit_card(), headers=headers_for("student")
        )
        assert r.status_code == 201, r.text
        assert r.json()["is_default"] is True

    async def test_credit_card_missing_fields_returns_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/payment-methods",
            json={"type": "credit_card", "card_last4": "1234"},
            headers=headers_for("student"),
        )
        assert r.status_code == 422

    async def test_pix_happy_path(self, client: AsyncClient) -> None:
        # PIX não guarda dado nenhum — o código de pagamento é gerado no checkout.
        r = await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["type"] == "pix"
        assert body["pix_key"] is None

    async def test_second_default_unsets_first(self, client: AsyncClient) -> None:
        first = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()
        await client.post(
            "/payment-methods", json=pix(is_default=True), headers=headers_for("student")
        )
        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        defaults = [m for m in listing if m["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["type"] == "pix"
        first_now = next(m for m in listing if m["id"] == first["id"])
        assert first_now["is_default"] is False


class TestSetDefaultAndDelete:
    async def test_patch_sets_default(self, client: AsyncClient) -> None:
        await client.post("/payment-methods", json=credit_card(), headers=headers_for("student"))
        second = (
            await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        ).json()

        r = await client.patch(
            f"/payment-methods/{second['id']}",
            json={"is_default": True},
            headers=headers_for("student"),
        )
        assert r.status_code == 200
        assert r.json()["is_default"] is True

    async def test_delete_promotes_remaining_to_default(self, client: AsyncClient) -> None:
        first = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()  # default
        second = (
            await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        ).json()

        r = await client.delete(f"/payment-methods/{first['id']}", headers=headers_for("student"))
        assert r.status_code == 204

        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        assert len(listing) == 1
        assert listing[0]["id"] == second["id"]
        assert listing[0]["is_default"] is True

    async def test_delete_unknown_returns_404(self, client: AsyncClient) -> None:
        r = await client.delete(f"/payment-methods/{uuid.uuid4()}", headers=headers_for("student"))
        assert r.status_code == 404


class TestBareArrayContract:
    """Acréscimo da B9 — item 7 da tabela de "comportamentos preservados":
    `GET` devolve array puro, sem envelope, ao contrário de `/products`
    (`ProductList`: `items`/`total`/`limit`/`offset`) e `/cart` (`CartOut`:
    `items`/`total`). Nem o legacy nem a lista de asserções portada acima
    afirmam `isinstance(body, list)` explicitamente — só usam
    comprehensions que passariam despercebidas se a rota devolvesse um
    envelope com uma chave `items`/`data` por engano."""

    async def test_get_returns_bare_array_not_envelope(self, client: AsyncClient) -> None:
        await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        r = await client.get("/payment-methods", headers=headers_for("student"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, list)
        assert body[0]["type"] == "pix"


class TestOrdering:
    """Acréscimo da B9 — item 4: `is_default DESC, created_at ASC`. Nenhum
    teste do legacy prova a ordenação com 3+ métodos em que o default NÃO é
    o criado mais recentemente (os testes portados acima só checam
    `is_default` isolado, nunca a posição na lista)."""

    async def test_default_comes_first_even_when_not_most_recent(self, client: AsyncClient) -> None:
        # Achado da rodada de mutação (task-B9-report.md): uma primeira versão
        # deste teste criava 3 métodos e nunca trocava o default — como o
        # default É o primeiro criado, `created_at ASC` sozinho já dava a
        # ordem certa, e o teste passava mesmo com `.order_by(created_at)`
        # SEM `is_default.desc()` (mutação não pegou — passou por vácuo,
        # constraint 18). Aqui o PATCH torna `third` o default DEPOIS de ser
        # o último criado — só `is_default DESC` explica ele vir primeiro.
        first = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()  # vira default sozinho (comportamento item 5)
        second = (
            await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        ).json()
        third = (
            await client.post(
                "/payment-methods", json=pix(pix_key="chave-x"), headers=headers_for("student")
            )
        ).json()

        await client.patch(
            f"/payment-methods/{third['id']}",
            json={"is_default": True},
            headers=headers_for("student"),
        )

        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        assert [m["id"] for m in listing] == [third["id"], first["id"], second["id"]]


class TestCheckConstraintsAtDbLevel:
    """Acréscimo da B9 — item 2: os dois `CheckConstraint`. A API nunca deixa
    esses valores chegarem ao banco (o Pydantic barra antes — ver
    `TestPciSafety`/`TestCreate` acima) — para provar que o CHECK do
    Postgres também existe (defesa em profundidade, não só o schema),
    construímos o objeto ORM diretamente, contornando `PaymentMethodIn`."""

    async def test_type_check_constraint_rejects_invalid_type(
        self, db_session: AsyncSession
    ) -> None:
        db_session.add(PaymentMethod(user_id=uuid.uuid4(), type="crypto"))
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_card_last4_check_constraint_rejects_wrong_length(
        self, db_session: AsyncSession
    ) -> None:
        # "123" (3 chars) cabe na coluna `String(4)` — não dispara truncamento
        # de VARCHAR — mas viola o CHECK `char_length(card_last4) = 4`. Um
        # valor de 5 chars ("12345") dispara `StringDataRightTruncationError`
        # (erro de tamanho de coluna) ANTES de alcançar o CHECK, o que
        # provaria a coluna, não a constraint — medido: a primeira versão
        # deste teste usava "12345" e falhava com
        # `DBAPIError`/`StringDataRightTruncationError`, não `IntegrityError`.
        db_session.add(PaymentMethod(user_id=uuid.uuid4(), type="credit_card", card_last4="123"))
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestOwnership:
    """Acréscimo da B9 — regra 2 do CLAUDE.md ("nenhuma rota sem controle de
    acesso explícito... nunca consultar dados sem filtro de autorização") e
    o CONTEXTO DO CONTROLADOR do brief, que exige prova nas quatro rotas.
    `headers_for` com dois `sub` diferentes (`STUDENT_A`, `STUDENT_B`)."""

    async def test_get_only_sees_own_methods(self, client: AsyncClient) -> None:
        await client.post(
            "/payment-methods", json=pix(), headers=headers_for("student", sub=STUDENT_A)
        )
        r = await client.get("/payment-methods", headers=headers_for("student", sub=STUDENT_B))
        assert r.status_code == 200, r.text
        assert r.json() == []

    async def test_created_method_belongs_only_to_creator(self, client: AsyncClient) -> None:
        created = (
            await client.post(
                "/payment-methods", json=pix(), headers=headers_for("student", sub=STUDENT_A)
            )
        ).json()
        listing_b = (
            await client.get("/payment-methods", headers=headers_for("student", sub=STUDENT_B))
        ).json()
        assert created["id"] not in [m["id"] for m in listing_b]

    async def test_patch_on_others_method_returns_404(self, client: AsyncClient) -> None:
        method = (
            await client.post(
                "/payment-methods",
                json=credit_card(),
                headers=headers_for("student", sub=STUDENT_A),
            )
        ).json()
        r = await client.patch(
            f"/payment-methods/{method['id']}",
            json={"is_default": True},
            headers=headers_for("student", sub=STUDENT_B),
        )
        assert r.status_code == 404

    async def test_delete_on_others_method_returns_404_and_keeps_it(
        self, client: AsyncClient
    ) -> None:
        method = (
            await client.post(
                "/payment-methods",
                json=credit_card(),
                headers=headers_for("student", sub=STUDENT_A),
            )
        ).json()
        r = await client.delete(
            f"/payment-methods/{method['id']}", headers=headers_for("student", sub=STUDENT_B)
        )
        assert r.status_code == 404

        listing_a = (
            await client.get("/payment-methods", headers=headers_for("student", sub=STUDENT_A))
        ).json()
        assert len(listing_a) == 1


class TestDefaultLockConcurrency:
    """Prova o lock acrescentado a `criar_metodo`/`apagar_metodo` na rodada
    de correção 1 (task-B9-report.md, seção "Divergência do lock — read→write
    sem lock, corrigido"). Decisão do usuário de 2026-08-07: pôr o lock —
    regra 3 do CLAUDE.md é inviolável, e a fase 2b original só tinha
    REGISTRADO o achado (sem lock, replicando o legacy) até um revisor
    independente medir a corrida produzindo 2 defaults de verdade.

    Duas proteções distintas, para duas corridas distintas (ver docstring
    de `app/services/pagamento.py`):

    1. `ix_payment_methods_one_default_per_user` (índice único parcial no
       banco) + `criar_metodo` capturando `IntegrityError` e refazendo sem
       `is_default` — protege quando NÃO existe nenhuma linha ainda (o
       `with_for_update()` não tem o que travar nesse caso).
    2. `.with_for_update()` em `_listar_metodos_com_lock`, usado por
       `criar_metodo` e `apagar_metodo` — protege quando já existe pelo
       menos 1 linha (serializa a decisão de quem vira default).

    A rodada de correção 2 acrescentou o terceiro teste desta classe e
    estendeu o mesmo `_listar_metodos_com_lock` a `definir_padrao` (PATCH),
    onde o índice da proteção 1, sozinho, produzia 500 em vez de proteger.

    Limitação declarada (mesma do bloco A/B7/B8): um teste destes, num
    único processo/event loop, prova a ORDEM LÓGICA das operações e
    exercita um lock de linha real do Postgres entre duas conexões
    distintas (duas `AsyncSession`) — não prova contenção entre processos
    ou réplicas distintas do serviço.
    """

    async def test_concurrent_create_from_zero_methods_does_not_produce_two_defaults(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Corrida mais dura, medida pelo revisor: usuário SEM nenhum
        método, dois `POST` concorrentes, "leituras forçadas antes de
        qualquer commit". `with_for_update()` sozinho NÃO protege este caso
        — não há linha para travar (Postgres nunca bloqueia um INSERT novo
        por lock em linha inexistente). Quem fecha é o índice único parcial
        + `criar_metodo` capturando o `IntegrityError` do segundo commit.

        Sinal forçado no nível da FUNÇÃO (`_listar_metodos_com_lock`), não
        na forma da query via `AsyncSession.execute` — a query do lock e a
        de `listar_metodos` têm o MESMO texto SQL (só o `FOR UPDATE` muda,
        e ele precisa poder desaparecer sob mutação sem quebrar o
        detector, mesma lição da B8). Patchear a função pelo nome evita
        depender do SQL renderizado.
        """
        leituras_prontas = asyncio.Event()
        estado = {"leituras": 0, "commits": 0}

        lock_real = pagamento_service._listar_metodos_com_lock
        commit_real = AsyncSession.commit

        async def _lock_que_avisa(db: AsyncSession, user_id: uuid.UUID):
            resultado = await lock_real(db, user_id)
            estado["leituras"] += 1
            if estado["leituras"] == 2:
                leituras_prontas.set()
            return resultado

        async def _commit_que_espera(self: AsyncSession, *args: object, **kwargs: object):
            estado["commits"] += 1
            if estado["commits"] == 1:
                await asyncio.wait_for(leituras_prontas.wait(), timeout=5)
                await asyncio.sleep(0.01)
            return await commit_real(self, *args, **kwargs)

        monkeypatch.setattr(pagamento_service, "_listar_metodos_com_lock", _lock_que_avisa)
        monkeypatch.setattr(AsyncSession, "commit", _commit_que_espera)

        r1, r2 = await asyncio.gather(
            client.post("/payment-methods", json=pix(), headers=headers_for("student")),
            client.post("/payment-methods", json=pix(), headers=headers_for("student")),
        )
        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text

        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        defaults = [m for m in listing if m["is_default"]]
        assert len(defaults) == 1, (
            f"esperava exatamente 1 default, achou {len(defaults)}: {listing}"
        )

    async def test_concurrent_delete_of_default_and_create_of_new_default_does_not_duplicate(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Segunda corrida medida pelo revisor: `DELETE` do método default
        concorrente com `POST` de um método novo já pedindo
        `is_default=true`.

        MEDIÇÃO (achado desta rodada — quatro tentativas até um desenho que
        funciona nos dois sentidos; contagens 20x completas de cada uma em
        task-B9-report.md, seção "Divergência do lock"):

        1ª: `asyncio.gather` puro, só 1 método existente (o default sendo
        apagado). Contra o código sem proteção: `GREENS=20 REDS=0` — não
        reproduz, porque `_limpar_outros_padroes` (`UPDATE ... WHERE
        is_default=true`) e o `DELETE` disputam a MESMA linha (o único
        default), e o Postgres serializa isso sozinho via lock de linha
        nativo do `UPDATE`/`DELETE` concorrente — sem `with_for_update()`
        nenhum.

        2ª: sinal forçado (mesmo padrão do teste acima) + um segundo método
        (`segundo`, não-default), cuja linha é DIFERENTE da que
        `_limpar_outros_padroes` disputa. Contra o código sem proteção:
        `GREENS=0 REDS=20` — reproduz. Mas contra o código COM a proteção:
        `TimeoutError` — quando `with_for_update()` está ativo, uma das
        duas chamadas a `_listar_metodos_com_lock` fica genuinamente
        BLOQUEADA dentro do Postgres (não dentro do `asyncio.Event` do
        teste), a segunda leitura nunca completa para disparar o sinal, e o
        commit que espera o sinal trava em deadlock — mesma armadilha que a
        B8 documentou (`task-B8-report.md`, teste do item sem sinal
        forçado).

        3ª: removido o sinal, mantido `segundo`, só `asyncio.gather` puro
        (mais um tick de `asyncio.sleep(0)` entre `create_task` das duas
        chamadas). Contra o código sem proteção: `GREENS=20 REDS=0` de
        novo — sem sinal algum, as duas transações não intercalam no ponto
        exato dentro deste harness em processo único (`ASGITransport`); o
        eventloop cooperativo não gera o entrelaçamento por si só aqui.

        4ª (final): sinal forçado com TIMEOUT CURTO (0.3s) em vez de 5s, e
        o timeout é ENGOLIDO (não propagado) em vez de estourar o teste —
        se a segunda leitura não completar a tempo, é porque
        `with_for_update()` já bloqueou de verdade dentro do Postgres (a
        proteção está funcionando), e não faz sentido esperar mais: os dois
        lados prosseguem, e o próprio Postgres serializa. Contra o código
        sem proteção, as duas leituras completam bem antes de 0.3s (não há
        nada bloqueando) e o sinal dispara normalmente, reproduzindo a
        corrida como na 2ª rodada. Funciona nos dois sentidos sem deadlock.
        """
        primeiro = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()  # default
        await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        # `segundo` (não-default) é o que fica quando `primeiro` é apagado —
        # é a linha que `apagar_metodo` PROMOVE, distinta da linha que
        # `_limpar_outros_padroes` do POST concorrente disputa (`primeiro`).
        # Sem essa segunda linha, a corrida não se reproduz (ver acima).

        leituras_prontas = asyncio.Event()
        estado = {"leituras": 0, "commits": 0}

        lock_real = pagamento_service._listar_metodos_com_lock
        commit_real = AsyncSession.commit

        async def _lock_que_avisa(db: AsyncSession, user_id: uuid.UUID):
            resultado = await lock_real(db, user_id)
            estado["leituras"] += 1
            if estado["leituras"] == 2:
                leituras_prontas.set()
            return resultado

        async def _commit_que_espera_curto(self: AsyncSession, *args: object, **kwargs: object):
            estado["commits"] += 1
            if estado["commits"] == 1:
                # Timeout CURTO e ENGOLIDO — se não disparar a tempo, é
                # porque `with_for_update()` já travou de verdade dentro do
                # Postgres (a proteção funcionando), não um bug do sinal.
                # Ver docstring.
                try:
                    await asyncio.wait_for(leituras_prontas.wait(), timeout=0.3)
                    await asyncio.sleep(0.01)
                except TimeoutError:
                    pass
            return await commit_real(self, *args, **kwargs)

        monkeypatch.setattr(pagamento_service, "_listar_metodos_com_lock", _lock_que_avisa)
        monkeypatch.setattr(AsyncSession, "commit", _commit_que_espera_curto)

        r_delete, r_post = await asyncio.gather(
            client.delete(f"/payment-methods/{primeiro['id']}", headers=headers_for("student")),
            client.post(
                "/payment-methods", json=pix(is_default=True), headers=headers_for("student")
            ),
        )
        assert r_delete.status_code == 204, r_delete.text
        assert r_post.status_code == 201, r_post.text

        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        defaults = [m for m in listing if m["is_default"]]
        assert len(defaults) == 1, (
            f"esperava exatamente 1 default, achou {len(defaults)}: {listing}"
        )

    async def test_concurrent_patch_of_two_non_default_methods_keeps_200_and_one_default(
        self,
        client: AsyncClient,
    ) -> None:
        """Regressão da rodada de correção 1: o índice único parcial
        `ix_payment_methods_one_default_per_user` passou a fazer
        `definir_padrao` (PATCH) devolver **500** sob concorrência — rota que
        aquela rodada nunca tocou. Ver task-B9-report.md, "RODADA DE CORREÇÃO
        2".

        CONFIGURAÇÃO É O TESTE. Precisa de ≥3 métodos com os DOIS alvos do
        PATCH não-default. Medido, 50 rodadas cada, contra o código sem o
        lock em `definir_padrao`:

        - 3 métodos, alvos não-default: `(200, 500)` em 19/20 (`text/plain`,
          `Internal Server Error`, do `ServerErrorMiddleware`).
        - 2 métodos, um deles já o default: `(200, 200)` com 1 default em
          50/50 — ou seja, um teste montado no caso de 2 métodos passa COM ou
          SEM o conserto e não prova nada.

        SEM sinal forçado de propósito (ao contrário dos dois testes acima
        desta classe): aqui o entrelaçamento acontece sozinho, porque o
        segundo PATCH BLOQUEIA dentro do Postgres no `UPDATE` de
        `_limpar_outros_padroes` (disputando a linha do default antigo com o
        primeiro PATCH) — não é preciso `asyncio.Event` nenhum para forçar a
        ordem. Medido contra o código sem o lock: 20 execuções independentes
        do arquivo inteiro, `GREENS=0 REDS=20`, e as 20 carregam
        `UniqueViolationError`. Sem sensibilidade de invocação: a classe
        sozinha também dá `GREENS=0 REDS=20`.

        Vencedor: o ÚLTIMO a commitar. Medido com o conserto, 50 rodadas,
        50/50 `winner == LAST successful committer` (script de medição em
        task-B9-report.md) — mesma semântica de "quem chegou por último
        manda" que o legacy tem sem lock nenhum.
        """
        primeiro = (
            await client.post(
                "/payment-methods", json=credit_card(), headers=headers_for("student")
            )
        ).json()
        segundo = (
            await client.post("/payment-methods", json=pix(), headers=headers_for("student"))
        ).json()
        terceiro = (
            await client.post(
                "/payment-methods",
                json=credit_card(card_last4="5678"),
                headers=headers_for("student"),
            )
        ).json()
        assert primeiro["is_default"] is True
        assert segundo["is_default"] is False
        assert terceiro["is_default"] is False

        r2, r3 = await asyncio.gather(
            client.patch(
                f"/payment-methods/{segundo['id']}",
                json={"is_default": True},
                headers=headers_for("student"),
            ),
            client.patch(
                f"/payment-methods/{terceiro['id']}",
                json={"is_default": True},
                headers=headers_for("student"),
            ),
        )
        assert r2.status_code == 200, r2.text
        assert r3.status_code == 200, r3.text

        listing = (await client.get("/payment-methods", headers=headers_for("student"))).json()
        defaults = [m for m in listing if m["is_default"]]
        assert len(defaults) == 1, (
            f"esperava exatamente 1 default, achou {len(defaults)}: {listing}"
        )
        assert defaults[0]["id"] in {segundo["id"], terceiro["id"]}, (
            f"o default deveria ser um dos dois alvos do PATCH, veio {defaults[0]}"
        )
