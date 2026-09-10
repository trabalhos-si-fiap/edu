# Spec C — Fluxo de pedido ponta a ponta — Plano de implementação

> **Para executores agênticos:** SUB-SKILL OBRIGATÓRIA: use
> `superpowers:subagent-driven-development` (recomendado) ou
> `superpowers:executing-plans` para implementar este plano task a task. Os
> passos usam caixa de seleção (`- [ ]`) para rastreamento.

**Objetivo:** Fazer um pedido percorrer `CRIADO` até `ENTREGUE` pelas telas dos
quatro perfis, sem intervenção no banco, com push no perfil certo a cada
transição, posição do entregador andando no mapa do comprador, e o desvio de
falta de estoque funcionando nos dois desfechos.

**Arquitetura:** Nenhum serviço novo. O `commerce-service` ganha o carregamento
(o lote que o entregador acessa), a série temporal de posição, um estado novo na
máquina que já existe, e um scheduler no padrão do `learning-service`. O
`notification-service` ganha um registro de staff alimentado por evento, uma
tabela de destinatário por transição, e o primeiro envio de e-mail do backend
desde a spec A. O gateway ganha uma entrada. O Flutter ganha múltiplas sessões,
login de entregador por código, posição no mapa e uma aba de carregamentos; o
`web-admin` ganha a página equivalente.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.x async + Alembic +
PostgreSQL 17 + APScheduler; RabbitMQ (exchange topic durável, DLX ligada);
Flutter/Dart; Angular 22 (standalone, RxJS).

**Spec:** [`../specs/2026-09-07-spec-c-fluxo-de-pedido-ponta-a-ponta-design.md`](../specs/2026-09-07-spec-c-fluxo-de-pedido-ponta-a-ponta-design.md)

**Registro da spec anterior (leitura obrigatória antes da task 1):**
[`2026-09-08-spec-b-parceiros-estoque-transportadora-execution-record.md`](2026-09-08-spec-b-parceiros-estoque-transportadora-execution-record.md)

---

## Baselines medidos em 2026-09-09

Medidos nesta árvore, neste commit (`38d65a2`), não copiados de documento
anterior. **Nenhuma task pode citar outro número.**

| Alvo | Comando | Medido |
|---|---|---|
| commerce-service | `cd back-end/commerce-service && uv run pytest -q` | **526 passed**, 1 warning |
| notification-service | `cd back-end/notification-service && uv run pytest -q` | **36 passed** |
| api-gateway | `cd back-end/api-gateway && uv run pytest -q` | **37 passed** |
| analytics-service | `cd back-end/analytics-service && uv run pytest -q` | **34 passed** |
| auth-users-service | `cd back-end/auth-users-service && uv run pytest -q` | **72 passed** |
| edu-common | `cd back-end/packages/edu-common && uv run pytest -q` | **62 passed** |
| Flutter | `cd front-end-flutter && flutter test` | **179 passed** |
| Flutter analyze | `cd front-end-flutter && flutter analyze lib/` | **6 avisos `info`, exit 1** |

`learning-service` e `chatbot-service` **não são tocados por este plano**. Não os
rode task a task; só na verificação final (task 15).

Os 6 avisos `info` do `flutter analyze` são pré-existentes e estão em
`logistics_api.dart:217` (`use_null_aware_elements`) e em
`incident_resolution_screen.dart:275,276` (`deprecated_member_use` de
`Radio.groupValue`/`onChanged`), mais três de mesma natureza. **Nenhuma task
deste plano pode aumentar essa contagem**; corrigi-los não é escopo desta spec.

**Critério de teste — relativo, nunca absoluto:** nenhum teste que passava antes
de uma task pode falhar depois dela, e a contagem só sobe. Se uma task precisa
emendar um teste existente, isso está escrito explicitamente na task, com o
motivo. Emenda não declarada é falha da task.

---

## Global Constraints

Valem para toda task. Copiadas da spec e do `CLAUDE.md`.

- **TDD sem exceção.** Teste que falha primeiro, mínimo para passar, refatorar.
- **Regra 1:** nada de SQL concatenado. Sempre `select()` com parâmetro bound.
- **Regra 2:** todo endpoint tem `Depends(get_current_user)`,
  `Depends(requer_papel(...))` ou a dependency de escopo de carregamento
  (task 5). Nenhuma rota nova sem controle de acesso explícito.
- **Regra 3:** read→write em recurso compartilhado é atômico —
  `with_for_update()` ou expressão SQL atômica. Vale para pedido, carregamento
  e ocorrência. Toda transição de status passa por `transicionar_pedido`, que já
  trava a linha.
- **Regra 4:** todo campo de texto tem `max_length` no model **e** no schema
  Pydantic; toda listagem é paginada, inclusive as de administração.
- **Regra 5:** nenhum segredo no código, e **nada de logar segredo**. A senha do
  carregamento não vai para log, não vai para `notificacoes`, e não volta em
  nenhuma listagem — só no corpo da criação e no e-mail.
- **Regra 6:** schemas com campos explícitos. Nenhum endpoint devolve ORM cru.
- **Regra 9:** comparação de segredo com `hmac.compare_digest`, protegida contra
  `None`. Incide diretamente na task 5 (código e senha do carregamento).
- **Lint:** `uv run ruff check .` e `uv run ruff format .` no diretório do
  serviço. `line-length = 100`. Regras `E,F,I,N,UP,B,A,C4,SIM,RUF,ASYNC,S`,
  `ignore = ["S101"]`. Exceção precisa de sufixo `Error` (N818).
- **`loguru.logger`, nunca `print()`.**
- **Idioma dos identificadores:** o agregado que tem cliente é escrito em inglês
  (`products`, `orders`, `carriers`); o que não tem fica em português
  (`fornecedores`, `estoque`, `ocorrencias`, `pedido_status_historico`).
  `carregamentos` e `posicao_entrega` nascem em **português**: o cliente deles é
  o próprio app/painel deste projeto, e a rota exposta (`/shipments`) já traduz
  o que precisa ser traduzido. Isso é decisão registrada (D11), não descuido.
- **Commits:** Conventional Commits, um por unidade lógica, em inglês,
  imperativo, minúsculas. Rodar `git diff --staged` antes de cada commit.
  Terminar cada mensagem com:
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`

### Ambiente local — proibições absolutas

O usuário mantém um stack Docker vivo construído deste checkout, com o mesmo
`COMPOSE_PROJECT_NAME`.

- **Nunca** `docker compose up/down/restart/build/exec`, `make stack-*`,
  `make services-migrate`, `make services-seed`, `make services-seed-demo`.
- **Nunca** `make services-test` nem `make services-lint` — reescrevem
  `uv.lock`. Rode `uv run pytest` / `uv run ruff` dentro de cada serviço.
- **Nunca** `alembic upgrade head` contra `commerce_db` nem contra qualquer
  banco de desenvolvimento (porta 5433).
- **Permitido:** `docker compose -f back-end/docker-compose.yml config --quiet`,
  `make help`, `make -n <alvo>`, e leitura
  (`docker exec -i edu-postgres psql -U edu -d commerce_db -c "..."`).
- **Permitido e usado pela task 1:** aplicar alembic contra
  `postgresql+asyncpg://edu:edu@localhost:5433/commerce_test` e
  `.../notification_test`. Esses são os bancos de scratch das próprias suítes —
  `tests/conftest.py::test_engine` faz `drop_all` + `create_all` neles a cada
  sessão de pytest.
- **Nenhuma chamada de rede real na suíte.** `tests/conftest.py` do commerce já
  bloqueia `httpx.AsyncHTTPTransport`; o envio de e-mail da task 9 nasce com o
  mesmo bloqueio no `notification-service`.

---

## Decisões tomadas antes de escrever as tasks

Cada uma resolve um ponto onde a spec estava incompleta ou onde a árvore
contradizia a spec. D1 a D4 foram decididas pelo usuário em 2026-09-09; as
demais são medição.

### D1 — A credencial vai por e-mail de verdade, e o backend volta a enviar e-mail

A spec diz que o `notification-service` "já fala com o Resend". **Falso, medido:**
`grep -rn "resend\|smtp\|email" back-end/notification-service/app/
back-end/notification-service/pyproject.toml` não devolve nada. O remetente
morreu com o monolito na spec A.

Decisão do usuário: **implementar o envio real** (task 9). O
`notification-service` ganha `app/services/email.py` com dois backends —
`console` (default, escreve no log **sem o segredo**) e `resend` (HTTP, via
`httpx`) —, `EMAIL_BACKEND`, `RESEND_API_KEY` e `EMAIL_FROM`. O domínio
`svemlab.com` já está verificado no Resend desde 2026-06-14 (MX `send`, DKIM
`resend._domainkey`, SPF `send`), então só falta a chave. Remetente
`no-reply@svemlab.com`.

A senha em claro trafega **uma vez**, no payload do evento `shipment.created`, e
morre ali: não é gravada em `notificacoes`, não é logada em nenhum dos dois
backends, e nenhuma rota a devolve depois da criação.

### D2 — A tela de carregamento nasce nos dois clientes

Decisão do usuário: aba nova no Flutter (task 13) **e** página nova no
`web-admin` (task 14), sobre a mesma API. A do Flutter é a que a apresentação
usa (uma pessoa alternando quatro perfis no aparelho); a do Angular é onde o
carregamento fica ao lado de transportadoras e ocorrências, que a spec B já pôs
lá.

### D3 — Não existe `POST /orders/{id}/substitution`

A spec pede a rota e, na frase seguinte, manda resolver a ocorrência pelo
`/occurrences/{id}/resolve` "que já existe". Medido: o resolve **já faz as três
decisões** (`substituir`, `remover_item`, `cancelar_pedido`), o app já tem a tela
(`front-end-flutter/lib/features/marketplace/presentation/incident_resolution_screen.dart`)
e o cliente (`LogisticsApi.resolverOcorrencia`).

Decisão do usuário: **reusar**. O que a task 3 acrescenta ao resolve é a
transição de volta ao fluxo — nada de rota nova, cliente novo ou tela nova.

### D4 — APScheduler dentro do commerce-service

O simulador de posição e o avanço automático precisam rodar sem ninguém
clicando. Decisão do usuário: mesmo padrão do
`back-end/learning-service/app/scheduler.py` (`AsyncIOScheduler`, ligado no
`lifespan`). `apscheduler` entra em `commerce-service/pyproject.toml`.

### D5 — A spec erra sobre `entrega.py`, e o buraco real é outro

A spec afirma: "`entrega.py` não publica nada. As transições para `EM_TRANSITO` e
`ENTREGUE` passam em silêncio."

**Medido, e falso:** `app/routers/entrega.py` chama
`app/routers/separacao.py::transicionar_pedido`, e essa função publica
`order.status_changed` em **toda** transição, no fim do corpo, depois do commit.
Coleta e entrega já publicam hoje.

O buraco real está no consumidor:
`notification-service/app/events/consumer.py::handle_order_status_changed`
escreve uma única linha, sempre para `payload["aluno_id"]`. Ou seja: **todo push
existente vai para o comprador, e nenhum vai para staff**. É isso que a task 8
fecha — e é por isso que ela é uma task de destinatário, não de publicação.

Os outros dois furos da spec conferem: `order.created` e
`order.occurrence_resolved` são publicados e ninguém os consome no
`notification-service` (o `analytics-service` consome os cinco, medido em
`analytics-service/app/events/consumer.py:21-25`).

### D6 — Quem é staff, o notification descobre por evento, não por HTTP

Para avisar "todo separador" o `notification-service` precisa saber quem são os
separadores, e `Notificacao` só tem `aluno_id`. Três caminhos foram considerados:

1. **HTTP para o auth** (`GET /users?role=separador`): exige um token de admin.
   O serviço teria que auto-emitir um (ele tem o `jwt_secret` da frota) — um
   token de admin fabricado por um serviço que não é dono de identidade. Recusado.
2. **Ids no payload**: o commerce sabe `user_id`, `picker_id` e `deliverer_id`,
   mas **não sabe** quem são os admins nem os separadores que ainda não
   reivindicaram o pedido — que é exatamente quem `order.created` precisa avisar.
   Insuficiente.
3. **Registro local alimentado por evento** (escolhido): o
   `auth-users-service` já publica `staff.created`
   (`app/routers/auth.py:122-125`, payload `{user_id, nome, role}`). O
   `notification-service` liga uma fila nova nessa chave e mantém uma tabela
   `staff` (id, papel, nome). Sem chamada entre serviços, sem token fabricado, e
   o dado chega pelo mesmo barramento que o resto.

**Uma correção acompanha:** `admin@demo.edu` é a única conta criada por INSERT
direto (`auth-users-service/app/seeds/demo_accounts.py`, docstring), então ela
nunca publicou `staff.created` e não apareceria no registro. A task 8 faz o
bootstrap publicar o evento como as outras três contas fazem.

### D7 — `AGUARDANDO_SUBSTITUICAO` volta para `EM_SEPARACAO`, não para `SEPARADO`

O diagrama da spec desenha `AGUARDANDO_SUBSTITUICAO → SEPARADO`. Medido, isso
quebra o fluxo: `app/routers/separacao.py::finalizar_separacao` exige
`EM_SEPARACAO` e encadeia `SEPARADO → AGUARDANDO_COLETA`. Um pedido que a
resolução colocasse direto em `SEPARADO` tornaria `/picking/{id}/finish`
inalcançável (`SEPARADO → SEPARADO` não é transição válida) e tiraria o separador
do fluxo — ele ainda precisa pegar o item substituto da prateleira.

Transições desta spec:

```
EM_SEPARACAO → AGUARDANDO_SUBSTITUICAO → EM_SEPARACAO   (aluno decidiu; volta ao separador)
                                       → CANCELADO      (aluno cancelou o pedido)
```

Os dois desfechos que a spec pede continuam de pé; o caminho de volta é que é um
passo mais honesto. No contrato público `AGUARDANDO_SUBSTITUICAO` resolve para
`SEPARATING`, como a spec manda.

### D8 — O token de carregamento não inventa claim nova

`edu_common.security.create_access_token(sub, role, secret, ...)` monta as claims
fixas (`sub`, `role`, `type`, `iat`, `exp`, `jti`) e **não aceita claim extra**.
Esta spec não altera o `edu-common` por causa disso: o token de carregamento é
`create_access_token(sub=str(carregamento.id), role="carregamento", ...)` — o
`sub` **é** o id do lote. A dependency de escopo (task 5) lê o `sub` e compara com
o `carregamento_id` do pedido. `requer_papel("entregador")` continua recusando
esse token, que é o comportamento correto: ele não é um usuário.

### D9 — A coordenada de destino é congelada na coleta

O simulador interpola entre a origem do carregamento e o **endereço de entrega**,
e `addresses` não tem coordenada (medido:
`auth-users-service/app/models/address.py` tem `zip_code..state`, nenhum
`lat`/`lng`). Quem sabe converter endereço em coordenada é
`app/services/directions.py`, a mesma fronteira que `GET /orders/{id}/route` já
usa — e a resposta dela já traz `destination_latitude/longitude`.

Decisão: `orders` ganha `destino_lat`/`destino_lng`, preenchidos **uma vez**, na
coleta (`PATCH /delivery/{id}/collect`), pela mesma chamada. Falha ou chave
ausente não impede a coleta: o pedido segue sem coordenada de destino, o
simulador o ignora, e `GET /orders/{id}/tracking` devolve
`courier_position: null` — que é exatamente o caminho de erro que a spec já
prevê ("Consulta de posição sem posição registrada: 200 com posição nula").

### D10 — Um carregamento, uma origem

O carregamento é "o lote de pedidos que sai junto, **de uma origem**, por uma
transportadora". A origem é congelada a partir do primeiro pedido atribuído
(`orders.origem_*`, que a spec B já grava no checkout). Atribuir um pedido de
outra origem responde **409**, espelhando a regra de origem única do carrinho
(`app/exceptions.py::CarrinhoOrigemMistaError`, spec B task 8). Sem essa regra a
interpolação não teria um ponto de partida definido.

### D11 — Uma revision só, aditiva, no topo da cadeia

Head medido do commerce: `b1a2c3d4e5f6` (spec B). A revision desta spec tem
`down_revision = "b1a2c3d4e5f6"` e só ADICIONA (duas tabelas, três colunas em
`orders`). Nenhuma task posterior cria coluna ou tabela no commerce. O
`notification-service` ganha a sua própria revision, aditiva, sobre o head dele.

### D12 — O rastreio passa a mostrar a transportadora de verdade

`app/services/rastreio_builder.py` devolve `carrier=_CARRIER`, a constante
`"Logistics Intel Express"`. Com carregamento existe transportadora de verdade, e
a atribuição grava `orders.carrier_name`. O builder passa a devolver
`order.carrier_name or _CARRIER` — uma linha, um teste, e a tela do comprador
deixa de mentir.

### D13 — Staff precisa de um sino, senão o critério 3 não é verificável

Critério de pronto 3: "Cada transição gera push no perfil certo, **verificado no
aparelho**". Medido: `grep -rn "notifications"` nas telas de logística e no
`admin_scaffold.dart` não devolve nada — separador, entregador e admin não têm
como abrir a lista de notificações no app. A rota `/notifications` existe e é por
usuário. As tasks 11 e 13 acrescentam o acesso nas telas de staff.

---

## Estrutura de arquivos

### `back-end/commerce-service`

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `app/models/carregamento.py` (novo) | `Carregamento` e `PosicaoEntrega` | 1 |
| `app/models/pedido.py` | `orders.carregamento_id`, `destino_lat`, `destino_lng` | 1 |
| `alembic/versions/c1d2e3f4a5b6_spec_c_schema.py` (novo) | a única revision | 1 |
| `app/services/status_pedido.py` | `AGUARDANDO_SUBSTITUICAO` | 2 |
| `app/routers/ocorrencias.py` | falta de estoque transiciona; resolve volta | 3 |
| `app/services/carregamentos.py` (novo) | criar lote, sortear credencial, atribuir pedido | 4 |
| `app/schemas/carregamento.py` (novo) | contratos de `/shipments` | 4 |
| `app/routers/carregamentos.py` (novo) | `/shipments` (admin) e `/shipments/login` | 4, 5 |
| `app/dependencies.py` | `ator_entrega` — usuário OU carregamento | 5 |
| `app/routers/entrega.py` | as quatro rotas passam a aceitar os dois atores | 5 |
| `app/services/posicao.py` (novo) | `registrar_posicao` — a porta única de escrita | 6 |
| `app/services/simulador_posicao.py` (novo) | interpolação, um chamador de `registrar_posicao` | 6 |
| `app/services/rastreio_builder.py` | `courier_position` e transportadora real | 6 |
| `app/services/avanco_automatico.py` (novo) | rede de segurança | 7 |
| `app/scheduler.py` (novo) | os dois jobs, no padrão do learning | 7 |
| `app/config.py` | `avanco_automatico_segundos`, `simulador_posicao_segundos` | 7 |

### `back-end/notification-service`

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `app/models/staff.py` (novo) | registro de staff, alimentado por `staff.created` | 8 |
| `app/events/consumer.py` | destinatário por transição; três bindings novos | 8, 9 |
| `app/services/destinatarios.py` (novo) | papel(is) por transição, e a resolução para ids | 8 |
| `app/services/email.py` (novo) | backend `console` e `resend` | 9 |
| `alembic/versions/<hash>_staff_registry.py` (novo) | tabela `staff` | 8 |

### Outros

| Arquivo | Responsabilidade | Task |
|---|---|---|
| `back-end/api-gateway/app/routing.py` | `"shipments": "commerce"` | 4 |
| `back-end/auth-users-service/app/seeds/demo_accounts.py` | admin também publica `staff.created` | 8 |
| `front-end-flutter/lib/core/session/session_manager.dart` (novo) | múltiplas sessões | 10 |
| `front-end-flutter/lib/features/logistics/presentation/shipment_login_screen.dart` (novo) | entrada por código | 11 |
| `front-end-flutter/lib/features/order_tracking/...` | posição no mapa | 12 |
| `front-end-flutter/lib/features/admin/presentation/admin_shipments_screen.dart` (novo) | aba de carregamentos | 13 |
| `web-admin/src/app/pages/shipments/` (novo) | página equivalente | 14 |
| `docs/back-end/order-flow.md` (novo) | o fluxo, o simulador declarado como simulação | 15 |

---

## Ordem e dependências

```
1 (schema)
├── 2 (estado novo) ──── 3 (falta de estoque usa o estado)
├── 4 (carregamento) ─── 5 (login e escopo) ─── 6 (posição) ─── 7 (scheduler)
└── 8 (destinatário do push) ─── 9 (e-mail da credencial; depende de 4)

Flutter: 10 (sessões) → 11 (entregador) → 12 (mapa) → 13 (admin)
Angular: 14 (depende de 4)
15 (docs + costura) por último
```

As tasks 2 e 4 podem correr em paralelo depois da 1. A 9 depende da 4 (precisa
do evento `shipment.created`) e da 8 (mexe no mesmo `consumer.py`); execute 8
antes de 9 para não conflitar no arquivo.

---

### Task 1: Schema da spec C — models e a única revision

Todo o schema do commerce nesta spec nasce aqui. Nenhuma task posterior
acrescenta coluna ou tabela ao commerce. Ver D11.

**Files:**
- Criar: `back-end/commerce-service/app/models/carregamento.py`
- Modificar: `back-end/commerce-service/app/models/pedido.py` (classe `Order`)
- Criar: `back-end/commerce-service/alembic/versions/c1d2e3f4a5b6_spec_c_schema.py`
- Modificar: `back-end/commerce-service/tests/conftest.py` (imports de `test_engine`)
- Criar: `back-end/commerce-service/tests/test_spec_c_schema.py`

**Interfaces (o que as tasks seguintes consomem):**

```python
# app/models/carregamento.py
class Carregamento(Base):
    __tablename__ = "carregamentos"
    id: int
    transportadora_id: int          # FK carriers.id, NOT NULL
    origem_rotulo: str              # String(120), NOT NULL, default ""
    origem_lat: Decimal | None      # Numeric(9, 6)
    origem_lng: Decimal | None      # Numeric(9, 6)
    codigo: str                     # String(12), NOT NULL, UNIQUE
    senha_hash: str                 # String(255), NOT NULL
    entregador_nome: str | None     # String(120)
    entregador_contato: str | None  # String(120)
    aberto_em: datetime | None
    criado_por: uuid.UUID           # NOT NULL
    criado_em: datetime

class PosicaoEntrega(Base):
    __tablename__ = "posicao_entrega"
    id: int
    carregamento_id: int            # FK carregamentos.id, NOT NULL, index
    lat: Decimal                    # Numeric(9, 6), NOT NULL
    lng: Decimal                    # Numeric(9, 6), NOT NULL
    registrado_em: datetime         # NOT NULL, index

# app/models/pedido.py
class Order(Base):
    # ... colunas atuais ...
    carregamento_id: int | None     # FK carregamentos.id, nullable, index
    destino_lat: Decimal | None     # Numeric(9, 6)
    destino_lng: Decimal | None     # Numeric(9, 6)
```

`Numeric(9, 6)` nos quatro pares de coordenada, e não `Float`: é o mesmo tipo
que a spec B já usou em `fornecedores.origem_lat`/`origem_lng` e
`orders.origem_lat`/`origem_lng`, com a justificativa registrada lá (6 casas
≈ 11 cm; `Float` acumula erro numa coordenada que atravessa JSON duas vezes).

`senha_hash` com 255: `edu_common.security.hash_password` devolve um bcrypt de
60 caracteres, e a folga é a mesma que `auth-users-service/app/models/user.py`
já usa para a senha do usuário.

`codigo` com 12: o código é sorteado com 8 caracteres (task 4); 12 dá folga sem
convidar a colar um identificador longo.

- [ ] **Passo 1: escrever o teste que falha**

Criar `back-end/commerce-service/tests/test_spec_c_schema.py`:

```python
"""Trava a forma do schema que a spec C introduz.

Não roda alembic (a suíte monta o schema com `Base.metadata.create_all` — ver
`tests/conftest.py::test_engine`). O que este arquivo garante é que os MODELS
declaram o que as tasks 2..14 consomem. A prova de que a REVISION aplica está
no passo 6, feita à mão contra `commerce_test`, e registrada no relatório.
"""

from app.models.carregamento import Carregamento, PosicaoEntrega
from app.models.pedido import Order


def test_carregamento_carries_a_carrier_an_origin_and_a_credential():
    cols = Carregamento.__table__.columns
    assert cols["transportadora_id"].nullable is False
    assert cols["origem_rotulo"].type.length == 120
    assert cols["origem_rotulo"].nullable is False
    assert (cols["origem_lat"].type.precision, cols["origem_lat"].type.scale) == (9, 6)
    assert cols["codigo"].type.length == 12
    assert cols["codigo"].unique is True
    assert cols["senha_hash"].nullable is False


def test_carregamento_records_who_took_the_load_and_when():
    """Nome e contato do entregador são gravados no PRIMEIRO acesso (task 5),
    então nascem nulos — é isso que distingue um lote ainda não retirado."""
    cols = Carregamento.__table__.columns
    assert cols["entregador_nome"].nullable is True
    assert cols["entregador_nome"].type.length == 120
    assert cols["entregador_contato"].nullable is True
    assert cols["aberto_em"].nullable is True
    assert cols["criado_por"].nullable is False


def test_posicao_entrega_is_a_time_series_not_a_single_field():
    """Série temporal: `carregamento_id` NÃO é único. Um campo único não
    guarda caminho percorrido, e o mapa desenha o caminho."""
    cols = PosicaoEntrega.__table__.columns
    assert cols["carregamento_id"].nullable is False
    assert cols["carregamento_id"].unique is not True
    assert cols["lat"].nullable is False
    assert cols["lng"].nullable is False
    assert cols["registrado_em"].nullable is False


def test_order_points_at_a_shipment_and_freezes_the_destination():
    cols = Order.__table__.columns
    assert cols["carregamento_id"].nullable is True
    assert (cols["destino_lat"].type.precision, cols["destino_lat"].type.scale) == (9, 6)
    assert cols["destino_lng"].nullable is True
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_spec_c_schema.py -q
```

Esperado: `ModuleNotFoundError: No module named 'app.models.carregamento'`.

- [ ] **Passo 3: criar `app/models/carregamento.py`**

```python
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Carregamento(Base):
    """O lote de pedidos que sai junto, de UMA origem, por UMA transportadora.

    Em PORTUGUÊS — tabela e colunas — pelo mesmo critério que deixou
    `fornecedores`, `estoque` e `ocorrencias` em português: o agregado não tem
    cliente externo. Quem tem cliente é a ROTA, e ela é `/shipments`.

    O carregamento é também a CREDENCIAL do entregador: `codigo` identifica o
    lote e `senha_hash` autentica quem o retira. Não há conta de entregador
    pré-cadastrada no caminho normal (o papel `entregador` continua no enum do
    auth-users porque a spec A seeda uma conta de demonstração com ele).

    `entregador_nome`/`entregador_contato`/`aberto_em` nascem nulos e são
    gravados no PRIMEIRO acesso — é o registro de quem pegou a carga, que não
    existia antes desta spec.
    """

    __tablename__ = "carregamentos"

    id = Column(Integer, primary_key=True)
    transportadora_id = Column(
        Integer, ForeignKey("carriers.id"), nullable=False, index=True
    )
    # Origem congelada a partir do PRIMEIRO pedido atribuído (ver D10 e
    # `app/services/carregamentos.py::atribuir_pedido`). Não é lida do
    # fornecedor em tempo de consulta: o estoque pode trocar de fornecedor
    # depois que o lote saiu, e a rota do mapa é registro histórico.
    origem_rotulo = Column(String(120), nullable=False, default="", server_default=text("''"))
    origem_lat = Column(Numeric(9, 6), nullable=True)
    origem_lng = Column(Numeric(9, 6), nullable=True)
    codigo = Column(String(12), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    entregador_nome = Column(String(120), nullable=True)
    entregador_contato = Column(String(120), nullable=True)
    aberto_em = Column(DateTime(timezone=True), nullable=True)
    criado_por = Column(UUID(as_uuid=True), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PosicaoEntrega(Base):
    """Posição do carregamento ao longo do tempo.

    SÉRIE TEMPORAL, não campo único: o mapa desenha o caminho percorrido, e um
    campo único não guarda caminho.

    Quem escreve aqui é `app/services/posicao.py::registrar_posicao` — a porta
    única. O simulador (`app/services/simulador_posicao.py`) é UM chamador
    dela; um GPS de verdade seria outro. Trocar de fonte é acrescentar um
    chamador e desligar este, não reescrever leitura, model ou tela.
    """

    __tablename__ = "posicao_entrega"

    id = Column(Integer, primary_key=True)
    carregamento_id = Column(
        Integer, ForeignKey("carregamentos.id"), nullable=False, index=True
    )
    lat = Column(Numeric(9, 6), nullable=False)
    lng = Column(Numeric(9, 6), nullable=False)
    registrado_em = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
```

- [ ] **Passo 4: acrescentar as três colunas em `Order`**

Em `app/models/pedido.py`, logo abaixo do bloco `origem_*` da spec B:

```python
    # O lote que leva este pedido. Nulo até o admin atribuir (task 4), e nulo
    # para sempre nos pedidos anteriores a esta spec.
    carregamento_id = Column(
        Integer, ForeignKey("carregamentos.id"), nullable=True, index=True
    )

    # Coordenada do endereço de entrega, RESOLVIDA UMA VEZ na coleta e
    # congelada aqui (ver D9). `addresses` não guarda coordenada; quem
    # converte endereço em par lat/lng é `app/services/directions.py`, a mesma
    # fronteira que `GET /orders/{id}/route` já usa.
    #
    # Nulo é estado normal, não erro: pedido sem chave da Google configurada,
    # sem snapshot de endereço, ou anterior a esta spec. Nesse caso o
    # simulador ignora o pedido e o rastreio devolve `courier_position: null`.
    destino_lat = Column(Numeric(9, 6), nullable=True)
    destino_lng = Column(Numeric(9, 6), nullable=True)
```

- [ ] **Passo 5: registrar os models novos no `test_engine`**

Em `tests/conftest.py`, dentro de `test_engine`, na lista de imports
`# noqa: F401` (hoje oito linhas, em ordem alfabética):

```python
        from app.models import carregamento as carregamento_models  # noqa: F401
```

Sem isso `Base.metadata.create_all` não cria `carregamentos` nem
`posicao_entrega`, e o FK de `orders.carregamento_id` falha na criação.

- [ ] **Passo 6: rodar e ver passar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_spec_c_schema.py -q
```

Esperado: 4 passed.

- [ ] **Passo 7: escrever a revision**

Criar `alembic/versions/c1d2e3f4a5b6_spec_c_schema.py`. `down_revision` é
`b1a2c3d4e5f6` (head medido da spec B).

```python
"""spec C schema: carregamentos, posicao_entrega, order shipment and destination

Revision ID: c1d2e3f4a5b6
Revises: b1a2c3d4e5f6
Create Date: 2026-09-09

Aditiva: duas tabelas novas e três colunas nulas em `orders`. Nenhum backfill,
nenhuma coluna existente muda de tipo ou de nulidade — o banco de
desenvolvimento do usuário sobrevive a ela sem tocar em dado nenhum.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b1a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carregamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transportadora_id",
            sa.Integer(),
            sa.ForeignKey("carriers.id"),
            nullable=False,
        ),
        sa.Column(
            "origem_rotulo", sa.String(length=120), nullable=False, server_default=""
        ),
        sa.Column("origem_lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("origem_lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("codigo", sa.String(length=12), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("entregador_nome", sa.String(length=120), nullable=True),
        sa.Column("entregador_contato", sa.String(length=120), nullable=True),
        sa.Column("aberto_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_por", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_carregamentos_codigo", "carregamentos", ["codigo"], unique=True)
    op.create_index(
        "ix_carregamentos_transportadora_id", "carregamentos", ["transportadora_id"]
    )

    op.create_table(
        "posicao_entrega",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "carregamento_id",
            sa.Integer(),
            sa.ForeignKey("carregamentos.id"),
            nullable=False,
        ),
        sa.Column("lat", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("lng", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column(
            "registrado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_posicao_entrega_carregamento_id", "posicao_entrega", ["carregamento_id"]
    )
    op.create_index("ix_posicao_entrega_registrado_em", "posicao_entrega", ["registrado_em"])

    op.add_column("orders", sa.Column("carregamento_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_orders_carregamento_id", "orders", "carregamentos", ["carregamento_id"], ["id"]
    )
    op.create_index("ix_orders_carregamento_id", "orders", ["carregamento_id"])
    op.add_column(
        "orders", sa.Column("destino_lat", sa.Numeric(precision=9, scale=6), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("destino_lng", sa.Numeric(precision=9, scale=6), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("orders", "destino_lng")
    op.drop_column("orders", "destino_lat")
    op.drop_index("ix_orders_carregamento_id", table_name="orders")
    op.drop_constraint("fk_orders_carregamento_id", "orders", type_="foreignkey")
    op.drop_column("orders", "carregamento_id")
    op.drop_index("ix_posicao_entrega_registrado_em", table_name="posicao_entrega")
    op.drop_index("ix_posicao_entrega_carregamento_id", table_name="posicao_entrega")
    op.drop_table("posicao_entrega")
    op.drop_index("ix_carregamentos_transportadora_id", table_name="carregamentos")
    op.drop_index("ix_carregamentos_codigo", table_name="carregamentos")
    op.drop_table("carregamentos")
```

- [ ] **Passo 8: provar que a revision aplica — contra `commerce_test`, nunca contra `commerce_db`**

```bash
cd back-end/commerce-service
DATABASE_URL=postgresql+asyncpg://edu:edu@localhost:5433/commerce_test \
  uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://edu:edu@localhost:5433/commerce_test \
  uv run alembic downgrade -1
DATABASE_URL=postgresql+asyncpg://edu:edu@localhost:5433/commerce_test \
  uv run alembic upgrade head
```

Esperado: os três comandos terminam com exit 0. `commerce_test` é o banco de
scratch da própria suíte (`conftest.py::test_engine` faz `drop_all`+`create_all`
nele) — é o único banco onde alembic pode rodar nesta árvore. Colar a saída dos
três no relatório da task.

- [ ] **Passo 9: suíte inteira e lint**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: **530 passed** (526 do baseline + 4 desta task), ruff limpo.

- [ ] **Passo 10: commit**

```bash
git add back-end/commerce-service/app/models/carregamento.py \
        back-end/commerce-service/app/models/pedido.py \
        back-end/commerce-service/alembic/versions/c1d2e3f4a5b6_spec_c_schema.py \
        back-end/commerce-service/tests/conftest.py \
        back-end/commerce-service/tests/test_spec_c_schema.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): add shipment, delivery position and order destination schema

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: `AGUARDANDO_SUBSTITUICAO` na máquina de estados

Um estado interno novo, o décimo. Ver D7 para por que ele volta a
`EM_SEPARACAO` e não a `SEPARADO`.

**Files:**
- Modificar: `back-end/commerce-service/app/services/status_pedido.py`
- Modificar: `back-end/commerce-service/tests/test_status_pedido.py`

**Interfaces:**
- Consome: nada (primeira task depois da 1 neste ramo).
- Produz: `StatusPedido.AGUARDANDO_SUBSTITUICAO`, entradas em
  `TRANSICOES_VALIDAS` e em `STATUS_CONTRATO` — consumidos pela task 3.

- [ ] **Passo 1: escrever os testes que falham**

Acrescentar a `tests/test_status_pedido.py`:

```python
def test_the_substitution_wait_is_reachable_only_from_picking():
    """Só quem está separando descobre que faltou item. Entrar em
    AGUARDANDO_SUBSTITUICAO de qualquer outro estado seria uma ocorrência
    aberta sobre um pedido que ninguém está separando."""
    origens = [
        s
        for s in StatusPedido
        if StatusPedido.AGUARDANDO_SUBSTITUICAO in TRANSICOES_VALIDAS[s]
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
        status_do_contrato(StatusPedido.AGUARDANDO_SUBSTITUICAO.value)
        == StatusContrato.SEPARATING
    )
```

Os imports do arquivo já trazem `StatusPedido`, `StatusContrato`,
`TRANSICOES_VALIDAS`, `validar_transicao` e `status_do_contrato` — confira o
topo do arquivo antes de acrescentar; se algum faltar, acrescente ao import
existente, não crie um segundo.

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_status_pedido.py -q
```

Esperado: `AttributeError: AGUARDANDO_SUBSTITUICAO`. O teste exaustivo que já
existe (`test_the_mapping_covers_every_internal_state`) passa a falhar assim
que o membro do enum existir sem entrada em `STATUS_CONTRATO` — é para isso
que ele foi escrito.

- [ ] **Passo 3: implementar**

Em `app/services/status_pedido.py`, três edições.

No enum, depois de `EM_SEPARACAO` (a ordem de declaração é o percurso do
fluxo, e o estado só é alcançável de lá):

```python
    AGUARDANDO_SUBSTITUICAO = "AGUARDANDO_SUBSTITUICAO"
```

E ajustar a docstring da classe: "São nove" vira "São dez".

Em `TRANSICOES_VALIDAS`, a linha de `EM_SEPARACAO` ganha o desvio, e o estado
novo ganha a sua:

```python
    StatusPedido.EM_SEPARACAO: [
        StatusPedido.SEPARADO,
        StatusPedido.AGUARDANDO_SUBSTITUICAO,
        StatusPedido.CANCELADO,
    ],
    # Volta a EM_SEPARACAO, não a SEPARADO: o separador ainda precisa pegar o
    # item substituto da prateleira, e `finalizar_separacao` exige EM_SEPARACAO
    # (ela encadeia SEPARADO -> AGUARDANDO_COLETA). Ver D7 do plano da spec C.
    StatusPedido.AGUARDANDO_SUBSTITUICAO: [
        StatusPedido.EM_SEPARACAO,
        StatusPedido.CANCELADO,
    ],
```

Em `STATUS_CONTRATO`:

```python
    StatusPedido.AGUARDANDO_SUBSTITUICAO: StatusContrato.SEPARATING,
```

- [ ] **Passo 4: rodar e ver passar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_status_pedido.py -q
```

Esperado: os quatro novos passam e nenhum antigo quebra.

- [ ] **Passo 5: suíte inteira**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check .
```

Esperado: **534 passed** (530 + 4).

Se algum teste de rastreio quebrar aqui, ele estava afirmando o TAMANHO do
enum e não o mapeamento — corrija o teste para afirmar o mapeamento e registre
a emenda no relatório da task.

- [ ] **Passo 6: commit**

```bash
git add back-end/commerce-service/app/services/status_pedido.py \
        back-end/commerce-service/tests/test_status_pedido.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): add the substitution wait state to the order machine

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: A falta de estoque para o pedido, e a decisão do aluno o devolve ao fluxo

Reaproveita as duas rotas que já existem. Nenhuma rota nova (D3).

**Files:**
- Modificar: `back-end/commerce-service/app/routers/ocorrencias.py`
  (`reportar_falta_estoque` e `resolver_ocorrencia`)
- Modificar: `back-end/commerce-service/tests/test_occurrences_routes.py`

**Interfaces:**
- Consome: `StatusPedido.AGUARDANDO_SUBSTITUICAO` (task 2),
  `app/routers/separacao.py::transicionar_pedido` (já existe).
- Produz: nada que outra task importe — o efeito é de comportamento.

Duas mudanças, e só:

1. `POST /occurrences/stock-shortage`, **depois** de gravar a ocorrência e
   **antes** de publicar `order.stock_issue`, transiciona o pedido para
   `AGUARDANDO_SUBSTITUICAO` — mas **só se** ele estiver em `EM_SEPARACAO`. Um
   admin pode abrir a ocorrência sobre um pedido em qualquer estado (a rota
   aceita `admin`), e nesses casos a transição não se aplica.
2. `POST /occurrences/{id}/resolve`, nos ramos `substituir` e `remover_item`,
   devolve o pedido a `EM_SEPARACAO` se ele estiver em
   `AGUARDANDO_SUBSTITUICAO`. O ramo `cancelar_pedido` já funciona — a task 2
   tornou `AGUARDANDO_SUBSTITUICAO -> CANCELADO` válida.

- [ ] **Passo 1: escrever os testes que falham**

Acrescentar a `tests/test_occurrences_routes.py` (o arquivo já tem
`headers_for` e helpers de seed — reuse os que existem em vez de escrever
outros; leia o topo do arquivo antes):

```python
async def test_stock_shortage_parks_the_order_in_the_substitution_wait(
    client, db_session
):
    pedido = await _seed_pedido_em_separacao(db_session)
    produto = await _seed_produto(db_session)

    response = await client.post(
        "/occurrences/stock-shortage",
        headers=headers_for("separador", sub=str(pedido.picker_id)),
        json={
            "pedido_id": str(pedido.id),
            "produto_id": str(produto.id),
            "motivo": "Prateleira vazia",
        },
    )

    assert response.status_code == 201
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SUBSTITUICAO.value


async def test_stock_shortage_leaves_an_order_outside_picking_alone(
    client, db_session
):
    """Admin pode abrir a ocorrência sobre um pedido em qualquer estado. Só
    EM_SEPARACAO tem para onde ir — o resto seria transição inválida, e a
    ocorrência não pode falhar por causa disso."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)
    produto = await _seed_produto(db_session)

    response = await client.post(
        "/occurrences/stock-shortage",
        headers=headers_for("admin"),
        json={
            "pedido_id": str(pedido.id),
            "produto_id": str(produto.id),
            "motivo": "Conferência do estoque",
        },
    )

    assert response.status_code == 201
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_COLETA.value


async def test_accepting_a_substitute_returns_the_order_to_the_picker(
    client, db_session
):
    pedido, ocorrencia, substituto = await _seed_pedido_aguardando_substituicao(
        db_session
    )

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        headers=headers_for("student", sub=str(pedido.user_id)),
        json={"resolucao": "substituir", "produto_escolhido_id": str(substituto.id)},
    )

    assert response.status_code == 200
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_SEPARACAO.value


async def test_removing_the_item_also_returns_the_order_to_the_picker(
    client, db_session
):
    pedido, ocorrencia, _ = await _seed_pedido_aguardando_substituicao(db_session)

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        headers=headers_for("student", sub=str(pedido.user_id)),
        json={"resolucao": "remover_item"},
    )

    assert response.status_code == 200
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_SEPARACAO.value


async def test_cancelling_from_the_substitution_wait_cancels_the_order(
    client, db_session
):
    pedido, ocorrencia, _ = await _seed_pedido_aguardando_substituicao(db_session)

    response = await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        headers=headers_for("student", sub=str(pedido.user_id)),
        json={"resolucao": "cancelar_pedido"},
    )

    assert response.status_code == 200
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.CANCELADO.value


async def test_the_return_to_picking_is_published_and_recorded(
    client, db_session, _stub_publish_event
):
    """A volta ao fluxo é uma transição como qualquer outra: linha de
    histórico e evento. Sem o evento, o separador não é avisado de que o
    pedido voltou para a fila dele."""
    pedido, ocorrencia, substituto = await _seed_pedido_aguardando_substituicao(
        db_session
    )

    await client.post(
        f"/occurrences/{ocorrencia.id}/resolve",
        headers=headers_for("student", sub=str(pedido.user_id)),
        json={"resolucao": "substituir", "produto_escolhido_id": str(substituto.id)},
    )

    status_changed = [
        payload
        for chave, payload in _stub_publish_event
        if chave == "order.status_changed"
    ]
    assert [p["status"] for p in status_changed] == [
        StatusPedido.EM_SEPARACAO.value
    ]

    historico = (
        (
            await db_session.execute(
                select(PedidoStatusHistorico).where(
                    PedidoStatusHistorico.order_id == pedido.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert StatusPedido.EM_SEPARACAO.value in [h.status for h in historico]
```

O helper `_seed_pedido_aguardando_substituicao` monta o cenário completo
(pedido `AGUARDANDO_SUBSTITUICAO` com `picker_id`, um `OrderItem`, um produto
substituto ativo com estoque, e uma `Ocorrencia` `FALTA_ESTOQUE` `ABERTA`).
Escreva-o junto dos helpers que já existem no arquivo, reusando `_seed_produto`
e `_seed_pedido` se eles já estiverem lá com outro nome — **não duplique
helper**.

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_occurrences_routes.py -q
```

Esperado: os seis novos falham; nenhum antigo falha.

- [ ] **Passo 3: implementar o desvio na abertura**

Em `app/routers/ocorrencias.py`, no topo, o import da função central:

```python
from app.routers.separacao import transicionar_pedido
```

Em `reportar_falta_estoque`, entre `await db.refresh(ocorrencia)` e o
`publish_event("order.stock_issue", ...)`:

```python
    # O pedido para até o aluno decidir. Só de EM_SEPARACAO: a rota também
    # aceita `admin`, que pode abrir a ocorrência sobre um pedido em qualquer
    # estado, e uma transição inválida derrubaria a abertura da ocorrência com
    # 400 — a ocorrência é o registro do fato, e ela não pode depender de o
    # pedido estar num estado específico.
    if pedido.status == StatusPedido.EM_SEPARACAO.value:
        await transicionar_pedido(
            db,
            pedido.id,
            StatusPedido.AGUARDANDO_SUBSTITUICAO.value,
            user["sub"],
            observacao=f"Falta de estoque, ocorrência #{ocorrencia.id}",
        )
```

`transicionar_pedido` publica `order.status_changed` e grava o histórico — os
dois eventos (status e `order.stock_issue`) saem, nessa ordem, e o
`notification-service` decide o que vira push (task 8).

- [ ] **Passo 4: implementar a volta na resolução**

Ainda em `ocorrencias.py`, em `resolver_ocorrencia`. Os ramos `substituir` e
`remover_item` mudam o `order_items` e o total dentro da transação da própria
rota; a volta ao fluxo é uma transição de status e tem que sair pelo mesmo
funil das outras. Como `transicionar_pedido` commita, ela roda **depois** do
`await db.commit()` que a rota já faz:

```python
    ocorrencia.status = "RESOLVIDA"
    ocorrencia.resolucao = resolucao
    ocorrencia.resolvido_em = datetime.now(UTC)

    await db.commit()
    await db.refresh(ocorrencia)

    # Devolve o pedido ao separador. Depois do commit, e pelo mesmo funil das
    # outras transições (`transicionar_pedido` valida, carimba
    # `status_updated_at`, grava histórico e publica) — o caminho de
    # `cancelar_pedido` acima é a exceção documentada, não o padrão.
    if resolucao in ("substituir", "remover_item") and (
        pedido.status == StatusPedido.AGUARDANDO_SUBSTITUICAO.value
    ):
        await transicionar_pedido(
            db,
            pedido.id,
            StatusPedido.EM_SEPARACAO.value,
            aluno_id,
            observacao=f"Substituição decidida na ocorrência #{ocorrencia.id}",
        )
```

Cuidado com a ordem: este bloco vai **antes** dos dois `publish_event` que a
rota já faz no fim (`order.status_changed` de cancelamento e
`order.occurrence_resolved`), para que a sequência de eventos conte a história
na ordem em que ela aconteceu.

- [ ] **Passo 5: rodar e ver passar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_occurrences_routes.py tests/test_picking_routes.py -q
```

`test_picking_routes.py` entra aqui de propósito: `finalizar_separacao` recusa
finalizar com ocorrência aberta, e esta task muda o estado do pedido enquanto a
ocorrência está aberta. Se algum teste de lá quebrar, é sinal real, não ruído.

- [ ] **Passo 6: suíte inteira e lint**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: **540 passed** (534 + 6).

- [ ] **Passo 7: commit**

```bash
git add back-end/commerce-service/app/routers/ocorrencias.py \
        back-end/commerce-service/tests/test_occurrences_routes.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): park an order in the substitution wait and return it on decision

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: Carregamento — serviço, rotas de admin e roteamento no gateway

O lote nasce aqui: criação com credencial sorteada, atribuição de pedido com
origem única (D10), listagem paginada, e o evento que a task 9 transforma em
e-mail.

**Files:**
- Criar: `back-end/commerce-service/app/services/carregamentos.py`
- Criar: `back-end/commerce-service/app/schemas/carregamento.py`
- Criar: `back-end/commerce-service/app/routers/carregamentos.py`
- Modificar: `back-end/commerce-service/app/exceptions.py`
- Modificar: `back-end/commerce-service/app/main.py`
- Modificar: `back-end/commerce-service/tests/conftest.py` (`_stub_publish_event`)
- Criar: `back-end/commerce-service/tests/test_shipments_routes.py`
- Modificar: `back-end/api-gateway/app/routing.py`
- Modificar: `back-end/api-gateway/tests/test_routing.py`

**Interfaces (o que as tasks seguintes consomem):**

```python
# app/services/carregamentos.py
ALFABETO_CODIGO: str          # 32 caracteres, sem I/O/0/1
TAMANHO_CODIGO: int = 8
TAMANHO_SENHA: int = 12

def gerar_codigo() -> str
def gerar_senha() -> str

async def criar_carregamento(
    db: AsyncSession, *, transportadora_id: int, criado_por: uuid.UUID
) -> tuple[Carregamento, str]
    """Devolve o lote e a senha EM CLARO. É a única vez que ela existe fora
    do hash — quem chama manda por e-mail (task 9) e não a guarda."""

async def atribuir_pedido(
    db: AsyncSession, *, carregamento_id: int, pedido_id: uuid.UUID
) -> Order

async def listar_carregamentos(
    db: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Carregamento], int]

async def pedidos_do_carregamento(
    db: AsyncSession, *, carregamento_id: int, limit: int, offset: int
) -> list[Order]

# app/exceptions.py
class CarregamentoNotFoundError(Exception): ...
class CarregamentoOrigemDivergenteError(Exception):
    MENSAGEM: str
class PedidoJaCarregadoError(Exception): ...

# Evento publicado (task 9 consome)
"shipment.created": {
    "carregamento_id": int,
    "codigo": str,
    "senha": str,               # em claro, uma vez, e nunca persistida
    "transportadora_id": int,
    "transportadora_nome": str,
    "transportadora_email": str,
}
```

**Rotas (todas `requer_papel("admin")`):**

| Método | Path | Corpo | Resposta |
|---|---|---|---|
| `POST` | `/shipments` | `{transportadora_id}` | `201 CarregamentoCriadoOut` (inclui `codigo` e `senha`) |
| `GET` | `/shipments` | — | `CarregamentoList` (sem credencial) |
| `GET` | `/shipments/{id}` | — | `CarregamentoOut` (sem credencial) |
| `POST` | `/shipments/{id}/orders` | `{pedido_id}` | `200 PedidoStaffOut` |
| `GET` | `/shipments/{id}/orders` | — | `list[PedidoStaffOut]` |

`POST /shipments/login` é da task 5 e mora no mesmo router.

- [ ] **Passo 1: escrever os testes que falham**

Criar `tests/test_shipments_routes.py`:

```python
import uuid
from decimal import Decimal

from edu_common.security import create_access_token, verify_password
from sqlalchemy import select

from app.config import settings
from app.models.carregamento import Carregamento
from app.models.pedido import Order
from app.models.transportadora import Carrier
from app.services.status_pedido import StatusPedido

ADMIN = "00000000-0000-0000-0000-0000000000a1"


def headers_for(role: str, sub: str = ADMIN) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(sub, role, settings.jwt_secret)}"}


async def _seed_transportadora(db_session) -> Carrier:
    carrier = Carrier(
        name="Expresso Cajamar",
        location="Cajamar, SP",
        email="operacao@expresso.example",
        average_delivery_days=2,
        rating=Decimal("4.5"),
        sla_percentage=Decimal("97.50"),
    )
    db_session.add(carrier)
    await db_session.commit()
    await db_session.refresh(carrier)
    return carrier


async def _seed_pedido(
    db_session,
    *,
    status: str = StatusPedido.AGUARDANDO_COLETA.value,
    origem: tuple[str, str, str] = ("Cajamar, SP", "-23.355800", "-46.876900"),
) -> Order:
    rotulo, lat, lng = origem
    pedido = Order(
        user_id=uuid.uuid4(),
        status=status,
        total=Decimal("100.00"),
        origem_rotulo=rotulo,
        origem_lat=Decimal(lat),
        origem_lng=Decimal(lng),
    )
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)
    return pedido


async def test_creating_a_shipment_requires_admin(client, db_session):
    carrier = await _seed_transportadora(db_session)
    for papel in ("student", "separador", "entregador"):
        response = await client.post(
            "/shipments",
            headers=headers_for(papel),
            json={"transportadora_id": carrier.id},
        )
        assert response.status_code == 403


async def test_creating_a_shipment_returns_the_credential_once(client, db_session):
    carrier = await _seed_transportadora(db_session)

    response = await client.post(
        "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
    )

    assert response.status_code == 201
    corpo = response.json()
    assert len(corpo["codigo"]) == 8
    assert len(corpo["senha"]) == 12

    carregamento = (
        await db_session.execute(
            select(Carregamento).where(Carregamento.id == corpo["id"])
        )
    ).scalar_one()
    # A senha é guardada só como hash, e o hash confere com o que saiu na
    # resposta — regra 5 do CLAUDE.md.
    assert carregamento.senha_hash != corpo["senha"]
    assert verify_password(corpo["senha"], carregamento.senha_hash)


async def test_the_listing_never_carries_the_credential(client, db_session):
    carrier = await _seed_transportadora(db_session)
    await client.post(
        "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
    )

    listagem = await client.get("/shipments", headers=headers_for("admin"))

    assert listagem.status_code == 200
    item = listagem.json()["items"][0]
    assert "senha" not in item
    assert "senha_hash" not in item
    # O código não é segredo (ele identifica o lote); a senha é.
    assert len(item["codigo"]) == 8


async def test_assigning_an_order_freezes_the_shipment_origin(client, db_session):
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    pedido = await _seed_pedido(db_session)

    response = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )

    assert response.status_code == 200
    await db_session.refresh(pedido)
    assert pedido.carregamento_id == criado["id"]
    # A transportadora do lote passa a ser a do pedido: o rastreio do aluno
    # mostra `orders.carrier_name` a partir da task 6 (D12).
    assert pedido.carrier_name == carrier.name

    carregamento = (
        await db_session.execute(
            select(Carregamento).where(Carregamento.id == criado["id"])
        )
    ).scalar_one()
    assert carregamento.origem_rotulo == "Cajamar, SP"
    assert carregamento.origem_lat == Decimal("-23.355800")


async def test_a_shipment_carries_one_origin_only(client, db_session):
    """Um carregamento é o lote que sai de UMA origem. Sem essa regra a
    interpolação da posição (task 6) não teria ponto de partida."""
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    primeiro = await _seed_pedido(db_session)
    outro = await _seed_pedido(
        db_session, origem=("Osasco, SP", "-23.532700", "-46.792000")
    )

    await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(primeiro.id)},
    )
    response = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(outro.id)},
    )

    assert response.status_code == 409
    await db_session.refresh(outro)
    assert outro.carregamento_id is None


async def test_an_order_belongs_to_one_shipment(client, db_session):
    carrier = await _seed_transportadora(db_session)
    um = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    outro = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    pedido = await _seed_pedido(db_session)

    await client.post(
        f"/shipments/{um['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )
    response = await client.post(
        f"/shipments/{outro['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )

    assert response.status_code == 409


async def test_reassigning_to_the_same_shipment_is_idempotent(client, db_session):
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()
    pedido = await _seed_pedido(db_session)

    primeira = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )
    segunda = await client.post(
        f"/shipments/{criado['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )

    assert (primeira.status_code, segunda.status_code) == (200, 200)


async def test_creating_a_shipment_publishes_the_credential_for_the_carrier(
    client, db_session, _stub_publish_event
):
    """A task 9 transforma este evento em e-mail. A senha viaja em claro UMA
    vez, aqui — e não é gravada em notificação nenhuma nem logada."""
    carrier = await _seed_transportadora(db_session)

    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()

    eventos = [p for chave, p in _stub_publish_event if chave == "shipment.created"]
    assert len(eventos) == 1
    assert eventos[0]["codigo"] == criado["codigo"]
    assert eventos[0]["senha"] == criado["senha"]
    assert eventos[0]["transportadora_email"] == carrier.email


async def test_unknown_carrier_is_404(client):
    response = await client.post(
        "/shipments", headers=headers_for("admin"), json={"transportadora_id": 999999}
    )
    assert response.status_code == 404


async def test_the_order_listing_is_paginated(client, db_session):
    carrier = await _seed_transportadora(db_session)
    criado = (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()

    response = await client.get(
        f"/shipments/{criado['id']}/orders?limit=5000", headers=headers_for("admin")
    )

    assert response.status_code == 422
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_shipments_routes.py -q
```

Esperado: erro de import (`app.models.carregamento` existe desde a task 1, mas
`/shipments` ainda não é rota) — as chamadas devolvem 404.

- [ ] **Passo 3: as três exceções**

Em `app/exceptions.py`, no fim, seguindo o estilo do arquivo (docstring que diz
como o router traduz, e a nota de N818):

```python
class CarregamentoNotFoundError(Exception):
    """Nenhum carregamento com o id dado. O router traduz em 404
    "Carregamento não encontrado".

    Sufixo `Error` por N818.
    """


class CarregamentoOrigemDivergenteError(Exception):
    """Tentativa de pôr num carregamento um pedido que sai de outra origem.
    O router traduz em 409 com `MENSAGEM` como `detail`.

    Um carregamento é o lote que sai de UMA origem (spec C, "Carregamento e
    credencial do entregador"). A interpolação de posição (task 6) parte da
    origem do lote; um lote de duas origens não tem ponto de partida. Mesmo
    espírito de `CarrinhoOrigemMistaError`, um nível acima.

    Sufixo `Error` por N818.
    """

    MENSAGEM = (
        "Este carregamento sai de outra origem. "
        "Crie um carregamento separado para os pedidos desta origem."
    )


class PedidoJaCarregadoError(Exception):
    """O pedido já está em OUTRO carregamento. O router traduz em 409.

    Reatribuir ao MESMO carregamento não cai aqui — é idempotente, e o admin
    que clica duas vezes não pode receber erro.

    Sufixo `Error` por N818.
    """
```

- [ ] **Passo 4: o serviço**

Criar `app/services/carregamentos.py`:

```python
"""Carregamento: o lote de pedidos que sai junto, de uma origem, por uma
transportadora — e a credencial com que o entregador o acessa.

A senha existe em claro em exatamente DOIS lugares e por um instante só: o
retorno de `criar_carregamento` e o payload de `shipment.created`. Nada aqui a
loga, e nenhuma leitura posterior a devolve.
"""

import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    CarregamentoNotFoundError,
    CarregamentoOrigemDivergenteError,
    OrderNotFoundError,
    PedidoJaCarregadoError,
    TransportadoraNotFoundError,
)
from app.models.carregamento import Carregamento
from app.models.pedido import Order
from app.models.transportadora import Carrier

# Sem I, O, 0 e 1: o código é ditado por telefone e digitado por quem está com
# a carga na mão. Ambiguidade visual aqui vira uma tentativa de login perdida.
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_CODIGO = 8
TAMANHO_SENHA = 12

# Quantas vezes tentar um código novo diante de colisão. Com 32^8 (~1.1e12)
# combinações e dezenas de lotes, três tentativas é folga absurda; o laço
# existe para o caso patológico, não para o caso normal.
TENTATIVAS_CODIGO = 3


def gerar_codigo() -> str:
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAMANHO_CODIGO))


def gerar_senha() -> str:
    """`secrets`, nunca `random`: `random` é um Mersenne Twister previsível a
    partir de saídas anteriores, e isto é credencial."""
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAMANHO_SENHA))


async def criar_carregamento(
    db: AsyncSession, *, transportadora_id: int, criado_por: uuid.UUID
) -> tuple[Carregamento, str]:
    """Cria o lote e devolve `(carregamento, senha_em_claro)`.

    A colisão de `codigo` é detectada pelo ÍNDICE ÚNICO, não por um SELECT
    prévio: SELECT-depois-INSERT é uma corrida, e o índice é a única coisa que
    resolve duas criações simultâneas. Mesmo idioma de
    `services/produtos.py::criar_produto` com `sku`.
    """
    from edu_common.security import hash_password

    carrier = await db.get(Carrier, transportadora_id)
    if carrier is None:
        raise TransportadoraNotFoundError()

    senha = gerar_senha()
    senha_hash = hash_password(senha)

    for tentativa in range(TENTATIVAS_CODIGO):
        carregamento = Carregamento(
            transportadora_id=carrier.id,
            codigo=gerar_codigo(),
            senha_hash=senha_hash,
            criado_por=criado_por,
        )
        db.add(carregamento)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if tentativa == TENTATIVAS_CODIGO - 1:
                raise
            continue
        await db.refresh(carregamento)
        return carregamento, senha

    raise RuntimeError("inalcançável: o laço acima só sai por return ou raise")


async def atribuir_pedido(
    db: AsyncSession, *, carregamento_id: int, pedido_id: uuid.UUID
) -> Order:
    """Põe o pedido no lote, congelando a origem do lote no primeiro pedido.

    `with_for_update()` nos dois (regra 3 do CLAUDE.md): sem ele, duas
    atribuições concorrentes leem o mesmo `origem_*` vazio, as duas congelam
    origens diferentes e a última vence — o lote passaria a alegar uma origem
    que não é a de todos os seus pedidos.
    """
    carregamento = (
        await db.execute(
            select(Carregamento)
            .where(Carregamento.id == carregamento_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if carregamento is None:
        raise CarregamentoNotFoundError()

    pedido = (
        await db.execute(select(Order).where(Order.id == pedido_id).with_for_update())
    ).scalar_one_or_none()
    if pedido is None:
        raise OrderNotFoundError()

    if pedido.carregamento_id is not None and pedido.carregamento_id != carregamento.id:
        raise PedidoJaCarregadoError()

    if not carregamento.origem_rotulo:
        carregamento.origem_rotulo = pedido.origem_rotulo or ""
        carregamento.origem_lat = pedido.origem_lat
        carregamento.origem_lng = pedido.origem_lng
    elif (carregamento.origem_lat, carregamento.origem_lng) != (
        pedido.origem_lat,
        pedido.origem_lng,
    ):
        raise CarregamentoOrigemDivergenteError()

    carrier = await db.get(Carrier, carregamento.transportadora_id)
    pedido.carregamento_id = carregamento.id
    # O rastreio do aluno mostra este nome a partir da task 6 (D12) — antes
    # dela ele mostrava uma constante para todo pedido do sistema.
    pedido.carrier_name = carrier.name if carrier else pedido.carrier_name

    await db.commit()
    await db.refresh(pedido)
    return pedido


async def listar_carregamentos(
    db: AsyncSession, *, limit: int, offset: int
) -> tuple[list[Carregamento], int]:
    itens = (
        (
            await db.execute(
                select(Carregamento)
                .order_by(Carregamento.criado_em.desc(), Carregamento.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    total = (
        await db.execute(select(func.count()).select_from(Carregamento))
    ).scalar_one()
    return list(itens), total


async def buscar_carregamento(db: AsyncSession, carregamento_id: int) -> Carregamento:
    carregamento = await db.get(Carregamento, carregamento_id)
    if carregamento is None:
        raise CarregamentoNotFoundError()
    return carregamento


async def pedidos_do_carregamento(
    db: AsyncSession, *, carregamento_id: int, limit: int, offset: int
) -> list[Order]:
    resultado = await db.execute(
        select(Order)
        .where(Order.carregamento_id == carregamento_id)
        .order_by(Order.created_at.asc(), Order.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(resultado.scalars().all())
```

O `from edu_common.security import hash_password` fica no topo do módulo, não
dentro da função — a linha acima está dentro só para deixar claro de onde vem;
mova-a para o bloco de imports ao escrever o arquivo.

- [ ] **Passo 5: os schemas**

Criar `app/schemas/carregamento.py`:

```python
"""Contratos de `/shipments`.

`CarregamentoCriadoOut` é o ÚNICO schema desta spec que carrega a senha, e ele
só é usado na resposta da criação. Os demais expõem `codigo` (identifica o
lote, não autentica ninguém) e nunca `senha` nem `senha_hash` — regra 6 do
CLAUDE.md: campos explícitos, nada de `from_attributes` derramando coluna
sensível.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.ids import Int32Id


class CarregamentoIn(BaseModel):
    transportadora_id: Int32Id


class PedidoDoCarregamentoIn(BaseModel):
    pedido_id: str = Field(max_length=36)


class CarregamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transportadora_id: int
    codigo: str
    origem_rotulo: str
    origem_lat: Decimal | None
    origem_lng: Decimal | None
    entregador_nome: str | None
    entregador_contato: str | None
    aberto_em: datetime | None
    criado_em: datetime

    @field_serializer("origem_lat", "origem_lng")
    def _coordenada_como_texto(self, value: Decimal | None) -> str | None:
        # Mesma escolha de `ParceiroOut` (spec B): coordenada atravessa JSON
        # como string para não herdar erro de arredondamento de float.
        return None if value is None else f"{value:.6f}"


class CarregamentoCriadoOut(CarregamentoOut):
    """Resposta de `POST /shipments` — a única que traz a senha.

    Ela existe porque o admin precisa poder ler a credencial na tela quando o
    e-mail demora ou não chega. Nenhuma leitura posterior a devolve: a senha
    não é recuperável depois desta resposta, só redefinível criando outro
    carregamento.
    """

    senha: str


class CarregamentoList(BaseModel):
    items: list[CarregamentoOut]
    total: int
    limit: int
    offset: int
```

- [ ] **Passo 6: o router**

Criar `app/routers/carregamentos.py` (a rota de login entra na task 5, neste
mesmo arquivo):

```python
"""Rotas do carregamento. Prefixo `/shipments` — inglês na ROTA, português no
agregado, mesmo critério de `/partners` sobre `fornecedores` (spec B)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import requer_papel
from app.events.publisher import publish_event
from app.exceptions import (
    CarregamentoNotFoundError,
    CarregamentoOrigemDivergenteError,
    OrderNotFoundError,
    PedidoJaCarregadoError,
    TransportadoraNotFoundError,
)
from app.ids import Int32Id
from app.models.transportadora import Carrier
from app.schemas.carregamento import (
    CarregamentoCriadoOut,
    CarregamentoIn,
    CarregamentoList,
    CarregamentoOut,
    PedidoDoCarregamentoIn,
)
from app.schemas.pedido import PedidoStaffOut
from app.services import carregamentos as services

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.post("", response_model=CarregamentoCriadoOut, status_code=status.HTTP_201_CREATED)
async def criar_carregamento(
    payload: CarregamentoIn,
    user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> CarregamentoCriadoOut:
    try:
        carregamento, senha = await services.criar_carregamento(
            db,
            transportadora_id=payload.transportadora_id,
            criado_por=uuid.UUID(user["sub"]),
        )
    except TransportadoraNotFoundError as exc:
        raise HTTPException(404, "Transportadora não encontrada") from exc

    carrier = await db.get(Carrier, carregamento.transportadora_id)
    # A senha em claro sai daqui para o barramento UMA vez, para a task 9
    # transformar em e-mail. Nenhum log deste módulo a menciona.
    await publish_event(
        "shipment.created",
        {
            "carregamento_id": carregamento.id,
            "codigo": carregamento.codigo,
            "senha": senha,
            "transportadora_id": carrier.id,
            "transportadora_nome": carrier.name,
            "transportadora_email": carrier.email,
        },
    )
    return CarregamentoCriadoOut(
        **CarregamentoOut.model_validate(carregamento).model_dump(), senha=senha
    )


@router.get("", response_model=CarregamentoList)
async def listar_carregamentos(
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CarregamentoList:
    itens, total = await services.listar_carregamentos(db, limit=limit, offset=offset)
    return CarregamentoList(
        items=[CarregamentoOut.model_validate(c) for c in itens],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{carregamento_id}", response_model=CarregamentoOut)
async def detalhe_carregamento(
    carregamento_id: Int32Id,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> CarregamentoOut:
    try:
        carregamento = await services.buscar_carregamento(db, carregamento_id)
    except CarregamentoNotFoundError as exc:
        raise HTTPException(404, "Carregamento não encontrado") from exc
    return CarregamentoOut.model_validate(carregamento)


@router.post("/{carregamento_id}/orders", response_model=PedidoStaffOut)
async def atribuir_pedido(
    carregamento_id: Int32Id,
    payload: PedidoDoCarregamentoIn,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
) -> PedidoStaffOut:
    try:
        pedido = await services.atribuir_pedido(
            db,
            carregamento_id=carregamento_id,
            pedido_id=uuid.UUID(payload.pedido_id),
        )
    except ValueError as exc:  # uuid malformado no corpo
        raise HTTPException(422, "pedido_id inválido") from exc
    except CarregamentoNotFoundError as exc:
        raise HTTPException(404, "Carregamento não encontrado") from exc
    except OrderNotFoundError as exc:
        raise HTTPException(404, "Pedido não encontrado") from exc
    except CarregamentoOrigemDivergenteError as exc:
        raise HTTPException(409, CarregamentoOrigemDivergenteError.MENSAGEM) from exc
    except PedidoJaCarregadoError as exc:
        raise HTTPException(409, "Este pedido já está em outro carregamento") from exc
    return PedidoStaffOut.de_order(pedido)


@router.get("/{carregamento_id}/orders", response_model=list[PedidoStaffOut])
async def listar_pedidos_do_carregamento(
    carregamento_id: Int32Id,
    _user: dict = Depends(requer_papel("admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PedidoStaffOut]:
    pedidos = await services.pedidos_do_carregamento(
        db, carregamento_id=carregamento_id, limit=limit, offset=offset
    )
    return [PedidoStaffOut.de_order(p) for p in pedidos]
```

Registrar no `app/main.py`: `from app.routers import ... carregamentos ...` e
`app.include_router(carregamentos.router)`.

- [ ] **Passo 7: o stub de eventos precisa conhecer o chamador novo**

`tests/conftest.py::_stub_publish_event` remenda o `publish_event` **no
namespace de cada chamador**. Há um chamador novo. Acrescentar:

```python
    monkeypatch.setattr("app.routers.carregamentos.publish_event", _capturar)
```

e atualizar a docstring da fixture, que hoje diz "Há TRÊS chamadores,
confirmados com `grep -rn "publish_event" app/`" — passam a ser quatro. Sem
esta linha, `POST /shipments` estoura
`RuntimeError: EventPublisher not connected` depois de já ter gravado o lote.

- [ ] **Passo 8: o gateway**

Em `back-end/api-gateway/app/routing.py`, no `SERVICE_MAP`, junto das outras
entradas de commerce:

```python
    "shipments": "commerce",
```

E o teste, em `back-end/api-gateway/tests/test_routing.py`, ao lado de
`test_partners_and_carriers_route_to_commerce`:

```python
def test_shipments_route_to_commerce():
    """O carregamento e o login do entregador moram no commerce, não no
    auth: o lote e o hash da senha são dado de comércio, e validar o código
    no serviço de identidade obrigaria uma chamada entre serviços em todo
    login para consultar uma tabela que ele não é dono."""
    assert SERVICE_MAP["shipments"] == "commerce"
```

Acrescentar também `("shipments/1/orders", "commerce")` à lista
parametrizada de `test_first_segment_resolves_to_expected_service`.

- [ ] **Passo 9: rodar tudo**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd ../api-gateway && uv run pytest -q && uv run ruff check .
```

Esperado: commerce **550 passed** (540 + 10), gateway **39 passed** (37 + 2).

- [ ] **Passo 10: commit**

Dois commits, um por unidade lógica:

```bash
git add back-end/commerce-service/app/services/carregamentos.py \
        back-end/commerce-service/app/schemas/carregamento.py \
        back-end/commerce-service/app/routers/carregamentos.py \
        back-end/commerce-service/app/exceptions.py \
        back-end/commerce-service/app/main.py \
        back-end/commerce-service/tests/conftest.py \
        back-end/commerce-service/tests/test_shipments_routes.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): create shipments with a generated credential and one origin

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"

git add back-end/api-gateway/app/routing.py back-end/api-gateway/tests/test_routing.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(gateway): route shipments to the commerce service

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Login do entregador por carregamento, e o escopo que ele autoriza

O entregador entra com **código, senha, nome e contato** e recebe um token cujo
escopo é aquele lote. Não há conta pré-cadastrada no caminho normal.

**Files:**
- Modificar: `back-end/commerce-service/app/services/carregamentos.py`
- Modificar: `back-end/commerce-service/app/schemas/carregamento.py`
- Modificar: `back-end/commerce-service/app/routers/carregamentos.py`
- Modificar: `back-end/commerce-service/app/dependencies.py`
- Modificar: `back-end/commerce-service/app/routers/entrega.py`
- Criar: `back-end/commerce-service/tests/test_shipment_login.py`
- Modificar: `back-end/commerce-service/tests/test_delivery_routes.py` (só
  acréscimos)

**Interfaces:**

```python
# app/dependencies.py
@dataclass(frozen=True)
class AtorEntrega:
    """Quem está operando uma rota de `/delivery`."""
    tipo: str                 # "usuario" | "carregamento"
    id: str                   # `sub` do token: uuid do usuário, ou id do lote
    carregamento_id: int | None

async def ator_entrega(user: dict = Depends(get_current_user)) -> AtorEntrega

# app/services/carregamentos.py
async def autenticar_carregamento(
    db: AsyncSession, *, codigo: str, senha: str, nome: str, contato: str
) -> Carregamento
    """Levanta `CredencialCarregamentoInvalidaError` para código OU senha
    errados — a mesma exceção, no mesmo tempo."""
```

**Regras de segurança desta task (não negociáveis):**

- Código errado e senha errada respondem **igual** (401, mesma mensagem) e
  gastam **o mesmo tempo**: quando o código não existe, verifica-se a senha
  contra `edu_common.security.DUMMY_PASSWORD_HASH`, que é um bcrypt do mesmo
  custo. Mesmo idioma de `auth-users-service/app/routers/auth.py::login`.
- A comparação do código usa `hmac.compare_digest`, protegida contra `None`
  (regra 9 do CLAUDE.md). A da senha é `verify_password`, que já é
  tempo-constante por dentro do bcrypt.
- Nome e contato são gravados **no primeiro acesso** e não sobrescritos depois:
  o registro é de quem pegou a carga, e a segunda pessoa a digitar não
  reescreve a história da primeira.
- Um token de carregamento em pedido de **outro** lote responde **403**, e o
  teste usa um pedido real de outro lote — não um token forjado.

- [ ] **Passo 1: escrever os testes que falham**

Criar `tests/test_shipment_login.py`:

```python
import time

from edu_common.security import decode_token

from app.config import settings
from app.services.status_pedido import StatusPedido

# Reusa os helpers da task 4 em vez de reescrevê-los.
from tests.test_shipments_routes import _seed_pedido, _seed_transportadora, headers_for


async def _criar_carregamento(client, db_session) -> dict:
    carrier = await _seed_transportadora(db_session)
    return (
        await client.post(
            "/shipments", headers=headers_for("admin"), json={"transportadora_id": carrier.id}
        )
    ).json()


CREDENCIAL = {"nome": "Maria da Silva", "contato": "11999990000"}


async def test_login_with_the_right_credential_returns_a_scoped_token(
    client, db_session
):
    lote = await _criar_carregamento(client, db_session)

    response = await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
    )

    assert response.status_code == 200
    corpo = response.json()
    claims = decode_token(
        corpo["access_token"], settings.jwt_secret, expected_type="access"
    )
    # O `sub` É o id do lote: `edu_common.security` não aceita claim extra, e
    # esta spec não o altera por causa disso (D8).
    assert claims["sub"] == str(lote["id"])
    assert claims["role"] == "carregamento"


async def test_the_first_access_records_who_took_the_load(client, db_session):
    lote = await _criar_carregamento(client, db_session)

    await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
    )

    detalhe = (
        await client.get(f"/shipments/{lote['id']}", headers=headers_for("admin"))
    ).json()
    assert detalhe["entregador_nome"] == "Maria da Silva"
    assert detalhe["entregador_contato"] == "11999990000"
    assert detalhe["aberto_em"] is not None


async def test_a_second_access_does_not_rewrite_the_first(client, db_session):
    lote = await _criar_carregamento(client, db_session)
    await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
    )

    await client.post(
        "/shipments/login",
        json={
            "codigo": lote["codigo"],
            "senha": lote["senha"],
            "nome": "Outra Pessoa",
            "contato": "11888880000",
        },
    )

    detalhe = (
        await client.get(f"/shipments/{lote['id']}", headers=headers_for("admin"))
    ).json()
    assert detalhe["entregador_nome"] == "Maria da Silva"


async def test_a_wrong_password_is_refused(client, db_session):
    lote = await _criar_carregamento(client, db_session)

    response = await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": "SENHAERRADA1", **CREDENCIAL},
    )

    assert response.status_code == 401


async def test_a_wrong_code_answers_exactly_like_a_wrong_password(client, db_session):
    """Mesma resposta e mesmo tempo: um código inexistente não pode ser
    distinguível de uma senha errada, senão o endpoint vira um oráculo de
    quais lotes existem."""
    lote = await _criar_carregamento(client, db_session)

    inicio = time.monotonic()
    codigo_errado = await client.post(
        "/shipments/login",
        json={"codigo": "ZZZZZZZZ", "senha": lote["senha"], **CREDENCIAL},
    )
    tempo_codigo = time.monotonic() - inicio

    inicio = time.monotonic()
    senha_errada = await client.post(
        "/shipments/login",
        json={"codigo": lote["codigo"], "senha": "SENHAERRADA1", **CREDENCIAL},
    )
    tempo_senha = time.monotonic() - inicio

    assert codigo_errado.status_code == senha_errada.status_code == 401
    assert codigo_errado.json()["detail"] == senha_errada.json()["detail"]
    # Os dois caminhos rodam UM bcrypt de custo 12. A folga é larga de
    # propósito: isto é uma trava contra o caminho que retorna cedo sem
    # verificar hash nenhum (que seria ordens de grandeza mais rápido), não
    # uma medição de microbenchmark.
    assert min(tempo_codigo, tempo_senha) > 0.5 * max(tempo_codigo, tempo_senha)


async def test_the_shipment_token_cannot_use_a_staff_route(client, db_session):
    """`requer_papel("separador"|"entregador"|"admin")` continua recusando o
    token de lote: ele não é um usuário."""
    lote = await _criar_carregamento(client, db_session)
    token = (
        await client.post(
            "/shipments/login",
            json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
        )
    ).json()["access_token"]

    response = await client.get(
        "/picking/queue", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


async def test_the_shipment_token_sees_only_its_own_orders(client, db_session):
    meu = await _criar_carregamento(client, db_session)
    outro = await _criar_carregamento(client, db_session)
    pedido_meu = await _seed_pedido(db_session)
    pedido_alheio = await _seed_pedido(db_session)
    for lote, pedido in ((meu, pedido_meu), (outro, pedido_alheio)):
        await client.post(
            f"/shipments/{lote['id']}/orders",
            headers=headers_for("admin"),
            json={"pedido_id": str(pedido.id)},
        )

    token = (
        await client.post(
            "/shipments/login",
            json={"codigo": meu["codigo"], "senha": meu["senha"], **CREDENCIAL},
        )
    ).json()["access_token"]
    cabecalho = {"Authorization": f"Bearer {token}"}

    fila = await client.get("/delivery/queue", headers=cabecalho)
    assert fila.status_code == 200
    assert [p["id"] for p in fila.json()] == [str(pedido_meu.id)]

    # Pedido REAL de outro lote, não um id inventado: é a diferença entre
    # provar autorização e provar validação de entrada.
    proibido = await client.patch(
        f"/delivery/{pedido_alheio.id}/collect", headers=cabecalho
    )
    assert proibido.status_code == 403


async def test_the_shipment_token_can_collect_and_deliver_its_order(
    client, db_session
):
    lote = await _criar_carregamento(client, db_session)
    pedido = await _seed_pedido(db_session)
    await client.post(
        f"/shipments/{lote['id']}/orders",
        headers=headers_for("admin"),
        json={"pedido_id": str(pedido.id)},
    )
    token = (
        await client.post(
            "/shipments/login",
            json={"codigo": lote["codigo"], "senha": lote["senha"], **CREDENCIAL},
        )
    ).json()["access_token"]
    cabecalho = {"Authorization": f"Bearer {token}"}

    coleta = await client.patch(f"/delivery/{pedido.id}/collect", headers=cabecalho)
    entrega = await client.patch(f"/delivery/{pedido.id}/deliver", headers=cabecalho)

    assert (coleta.status_code, entrega.status_code) == (200, 200)
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.ENTREGUE.value
```

Acrescentar em `tests/test_delivery_routes.py` (o caminho antigo continua
vivo — a spec mantém o papel `entregador` no enum):

```python
async def test_a_deliverer_user_still_collects_the_old_way(client, db_session):
    """O papel `entregador` deixa de ser o caminho normal, mas não morre: a
    spec A seeda uma conta com ele, e a suíte de entrega inteira depende
    dele. Esta task não pode quebrar esse caminho."""
    pedido = await _seed_pedido(db_session, StatusPedido.AGUARDANDO_COLETA.value)

    response = await client.patch(
        f"/delivery/{pedido.id}/collect", headers=headers_for("entregador", DELIVERER_A)
    )

    assert response.status_code == 200
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_shipment_login.py -q
```

Esperado: 404 em `/shipments/login`.

- [ ] **Passo 3: a autenticação, no serviço**

Em `app/exceptions.py`:

```python
class CredencialCarregamentoInvalidaError(Exception):
    """Código ou senha de carregamento que não conferem. UMA exceção para os
    dois casos, de propósito: o router traduz em 401 com a mesma mensagem, e
    o serviço gasta o mesmo tempo nos dois caminhos (bcrypt contra
    `DUMMY_PASSWORD_HASH` quando o código não existe). Distinguir os dois
    transformaria a rota num oráculo de quais lotes existem.

    Sufixo `Error` por N818.
    """
```

Em `app/services/carregamentos.py`:

```python
import hmac
from datetime import UTC, datetime

from edu_common.security import DUMMY_PASSWORD_HASH, verify_password


async def autenticar_carregamento(
    db: AsyncSession, *, codigo: str, senha: str, nome: str, contato: str
) -> Carregamento:
    """Valida a credencial e registra quem pegou a carga no primeiro acesso.

    O SELECT é por código exato. A comparação com `hmac.compare_digest` logo
    abaixo parece redundante depois de um `WHERE codigo = :codigo` — e é, para
    o resultado; ela está lá porque a regra 9 do CLAUDE.md pede comparação em
    tempo constante de segredo, e porque uma reescrita futura que troque o
    filtro por uma busca case-insensitive ou por prefixo herdaria a proteção
    em vez de perdê-la em silêncio.
    """
    carregamento = (
        await db.execute(
            select(Carregamento).where(Carregamento.codigo == codigo).with_for_update()
        )
    ).scalar_one_or_none()

    if carregamento is None or not hmac.compare_digest(carregamento.codigo, codigo):
        # Gasta um bcrypt do MESMO custo antes de recusar: sem isto, um código
        # inexistente responderia em microssegundos e um código válido com
        # senha errada em ~100 ms, o que basta para enumerar lotes.
        verify_password(senha, DUMMY_PASSWORD_HASH)
        raise CredencialCarregamentoInvalidaError()

    if not verify_password(senha, carregamento.senha_hash):
        raise CredencialCarregamentoInvalidaError()

    if carregamento.aberto_em is None:
        carregamento.entregador_nome = nome
        carregamento.entregador_contato = contato
        carregamento.aberto_em = datetime.now(UTC)
        await db.commit()
        await db.refresh(carregamento)

    return carregamento
```

- [ ] **Passo 4: a rota de login**

Em `app/schemas/carregamento.py`:

```python
class CarregamentoLoginIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    codigo: str = Field(min_length=1, max_length=12)
    senha: str = Field(min_length=1, max_length=128)
    nome: str = Field(min_length=1, max_length=120)
    contato: str = Field(min_length=1, max_length=120)


class CarregamentoLoginOut(BaseModel):
    """Só o access token: o carregamento não tem refresh.

    Um lote é de uma jornada, e um refresh de sete dias sobre uma senha que
    circula por e-mail é vida longa demais para uma credencial compartilhada.
    Expiração e revogação sofisticadas estão explicitamente fora do escopo da
    spec; o que existe é o `exp` de 12 horas abaixo.
    """

    access_token: str
    token_type: str = "bearer"
    carregamento_id: int
    codigo: str
    origem_rotulo: str
```

Em `app/routers/carregamentos.py`:

```python
from edu_common.security import create_access_token

from app.config import settings

# Uma jornada, não uma semana. Ver `CarregamentoLoginOut`.
_EXPIRACAO_TOKEN_MINUTOS = 12 * 60


@router.post("/login", response_model=CarregamentoLoginOut)
async def login_carregamento(
    payload: CarregamentoLoginIn,
    db: AsyncSession = Depends(get_db),
) -> CarregamentoLoginOut:
    """Rota PÚBLICA por construção — é o ponto de entrada de quem ainda não
    tem credencial nenhuma, como `POST /auth/login`. A autorização que ela
    concede é estreita: um token de escopo de UM carregamento (ver
    `app/dependencies.py::ator_entrega`), nunca um papel da frota.
    """
    try:
        carregamento = await services.autenticar_carregamento(
            db,
            codigo=payload.codigo,
            senha=payload.senha,
            nome=payload.nome,
            contato=payload.contato,
        )
    except CredencialCarregamentoInvalidaError as exc:
        raise HTTPException(401, "Código ou senha inválidos") from exc

    token = create_access_token(
        str(carregamento.id),
        "carregamento",
        settings.jwt_secret,
        settings.jwt_algorithm,
        expires_minutes=_EXPIRACAO_TOKEN_MINUTOS,
    )
    return CarregamentoLoginOut(
        access_token=token,
        carregamento_id=carregamento.id,
        codigo=carregamento.codigo,
        origem_rotulo=carregamento.origem_rotulo,
    )
```

- [ ] **Passo 5: a dependency de escopo**

Em `app/dependencies.py`:

```python
from dataclasses import dataclass

from fastapi import Depends, HTTPException

PAPEL_CARREGAMENTO = "carregamento"


@dataclass(frozen=True)
class AtorEntrega:
    """Quem está operando uma rota de `/delivery`.

    Dois atores, um contrato. `requer_papel` do `edu-common` não serve aqui:
    ele responde "este token tem um destes papéis?", e a pergunta desta spec é
    "este token pode mexer NESTE pedido?" — que para o token de lote depende
    do `carregamento_id` do pedido, não do papel.
    """

    tipo: str
    id: str
    carregamento_id: int | None

    def autoriza(self, pedido) -> bool:
        if self.tipo == PAPEL_CARREGAMENTO:
            return pedido.carregamento_id == self.carregamento_id
        # Usuário: mantém a regra que já existia — claim-on-first-action na
        # coleta, posse obrigatória na entrega (ver os docstrings das rotas).
        return pedido.deliverer_id is None or str(pedido.deliverer_id) == self.id


async def ator_entrega(user: dict = Depends(get_current_user)) -> AtorEntrega:
    papel = user.get("role")
    if papel == PAPEL_CARREGAMENTO:
        try:
            carregamento_id = int(user["sub"])
        except (TypeError, ValueError) as exc:
            # Token com role de lote e `sub` que não é id de lote: recusa como
            # credencial inválida, não como 500.
            raise HTTPException(401, "Token inválido ou expirado") from exc
        return AtorEntrega(
            tipo=PAPEL_CARREGAMENTO, id=user["sub"], carregamento_id=carregamento_id
        )
    if papel in ("entregador", "admin"):
        return AtorEntrega(tipo="usuario", id=user["sub"], carregamento_id=None)
    raise HTTPException(403, "Sem permissão para esta ação")
```

- [ ] **Passo 6: as rotas de entrega passam a aceitar os dois atores**

Em `app/routers/entrega.py`, as quatro rotas trocam
`user: dict = Depends(requer_papel(...))` por
`ator: AtorEntrega = Depends(ator_entrega)`, e as checagens de posse passam a
usar `ator`:

- `GET /delivery/queue`: quando `ator.tipo == "carregamento"`, filtra por
  `Order.carregamento_id == ator.carregamento_id` **em vez de** por status —
  o entregador do lote quer ver o lote inteiro, não a fila global. Para
  usuário, o filtro por `AGUARDANDO_COLETA` continua igual.
- `GET /delivery/mine`: para lote, é o mesmo filtro por `carregamento_id` com
  `status == EM_TRANSITO`; para usuário, continua `deliverer_id == ator.id`.
- `PATCH /delivery/{id}/collect`: depois de carregar o pedido com
  `with_for_update()`, `if not ator.autoriza(pedido): raise HTTPException(403, ...)`.
  Para usuário, `pedido.deliverer_id = ator.id` como hoje; para lote,
  `deliverer_id` fica nulo (não há usuário) e a posse é o próprio
  `carregamento_id`.
- `PATCH /delivery/{id}/deliver`: mesma checagem, e para usuário a posse
  continua **obrigatória** (`deliverer_id` já definido na coleta), o que a
  função `autoriza` acima já entrega — mas a rota mantém a exigência
  explícita para o ator usuário, porque `autoriza` aceita `deliverer_id is
  None` (o caso da coleta) e entregar um pedido sem dono não pode passar:

```python
    if ator.tipo != PAPEL_CARREGAMENTO and str(pedido.deliverer_id) != ator.id:
        raise HTTPException(
            403, "Apenas o entregador responsável por este pedido pode confirmar a entrega"
        )
    if not ator.autoriza(pedido):
        raise HTTPException(403, "Este pedido não pertence a este carregamento")
```

As mensagens de 403 existentes **não mudam** para o ator usuário: há testes que
as afirmam.

- [ ] **Passo 7: rodar e ver passar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_shipment_login.py tests/test_delivery_routes.py -q
```

Todos os testes antigos de `/delivery` continuam verdes — se algum quebrar, o
ator usuário perdeu comportamento e a task está errada.

- [ ] **Passo 8: suíte inteira e lint**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: **559 passed** (550 + 8 do login + 1 do delivery).

- [ ] **Passo 9: commit**

```bash
git add back-end/commerce-service/app/services/carregamentos.py \
        back-end/commerce-service/app/schemas/carregamento.py \
        back-end/commerce-service/app/routers/carregamentos.py \
        back-end/commerce-service/app/routers/entrega.py \
        back-end/commerce-service/app/dependencies.py \
        back-end/commerce-service/app/exceptions.py \
        back-end/commerce-service/tests/test_shipment_login.py \
        back-end/commerce-service/tests/test_delivery_routes.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): let a courier sign in with a shipment code and act on that lot only

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: Posição — uma porta de escrita, um simulador, e o rastreio que a mostra

A interface é desenhada para o dia em que a posição vier de um aparelho: quem
escreve é `registrar_posicao`, e o simulador é **um** chamador dela.

**Files:**
- Criar: `back-end/commerce-service/app/services/posicao.py`
- Criar: `back-end/commerce-service/app/services/simulador_posicao.py`
- Modificar: `back-end/commerce-service/app/services/rastreio_builder.py`
- Modificar: `back-end/commerce-service/app/schemas/rastreio.py`
- Modificar: `back-end/commerce-service/app/routers/rastreio.py`
- Modificar: `back-end/commerce-service/app/routers/entrega.py` (congela o destino)
- Criar: `back-end/commerce-service/tests/test_delivery_position.py`
- Modificar: `back-end/commerce-service/tests/test_tracking_builders.py`

**Interfaces:**

```python
# app/services/posicao.py
async def registrar_posicao(
    db: AsyncSession, carregamento_id: int, lat: Decimal, lng: Decimal
) -> None
    """A ÚNICA porta de escrita de posição. Um GPS real seria outro chamador."""

async def ultima_posicao(db: AsyncSession, carregamento_id: int) -> PosicaoEntrega | None

async def congelar_destino(db: AsyncSession, order: Order) -> None
    """Resolve e grava `orders.destino_lat/lng` uma vez. Nunca levanta."""

# app/services/simulador_posicao.py
def fracao_percorrida(inicio: datetime, agora: datetime, duracao: timedelta) -> float
def interpolar(
    origem: tuple[Decimal, Decimal], destino: tuple[Decimal, Decimal], fracao: float
) -> tuple[Decimal, Decimal]
async def avancar_carregamentos(db: AsyncSession, agora: datetime) -> int
    """Grava uma posição por carregamento com pedido EM_TRANSITO. Devolve
    quantos carregamentos avançaram."""

# app/schemas/rastreio.py
class TrackingPositionOut(BaseModel):
    latitude: float
    longitude: float
    updated_at: datetime

class OrderTrackingOut(BaseModel):
    # ... campos atuais ...
    courier_position: TrackingPositionOut | None = None

# app/services/rastreio_builder.py
def build_order_tracking(
    order: Order, posicao: PosicaoEntrega | None = None
) -> OrderTrackingOut
```

`build_order_tracking` continua **pura** — o parâmetro novo é dado pronto,
lido pelo router. Quem carrega do banco é a camada de serviço, como já era.

- [ ] **Passo 1: escrever os testes que falham**

Criar `tests/test_delivery_position.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.carregamento import PosicaoEntrega
from app.services.posicao import registrar_posicao, ultima_posicao
from app.services.status_pedido import StatusPedido
from app.services.simulador_posicao import (
    avancar_carregamentos,
    fracao_percorrida,
    interpolar,
)

ORIGEM = (Decimal("-23.355800"), Decimal("-46.876900"))
DESTINO = (Decimal("-23.561414"), Decimal("-46.655881"))


def test_the_fraction_is_zero_at_the_start_and_one_at_the_end():
    inicio = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    duracao = timedelta(minutes=10)
    assert fracao_percorrida(inicio, inicio, duracao) == 0.0
    assert fracao_percorrida(inicio, inicio + duracao, duracao) == 1.0


def test_the_fraction_never_passes_the_destination():
    """Depois do prazo o entregador chegou; ele não continua andando para
    além do endereço."""
    inicio = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    assert fracao_percorrida(
        inicio, inicio + timedelta(hours=5), timedelta(minutes=10)
    ) == 1.0


def test_the_interpolation_is_monotonic_between_origin_and_destination():
    anterior = ORIGEM
    for passo in range(1, 11):
        atual = interpolar(ORIGEM, DESTINO, passo / 10)
        # O destino está a sudeste da origem: latitude cai, longitude sobe.
        assert atual[0] < anterior[0]
        assert atual[1] > anterior[1]
        anterior = atual
    assert interpolar(ORIGEM, DESTINO, 1.0) == DESTINO


async def test_registrar_posicao_is_the_write_door_and_needs_no_simulator(
    db_session, seed_carregamento
):
    """Chamada DIRETO, sem passar pelo simulador — é isso que prova que a
    interface serve a um GPS de verdade. Trocar de fonte é acrescentar um
    chamador, não reescrever leitura, model ou tela."""
    carregamento = await seed_carregamento()

    await registrar_posicao(
        db_session, carregamento.id, Decimal("-23.400000"), Decimal("-46.800000")
    )

    gravadas = (
        (
            await db_session.execute(
                select(PosicaoEntrega).where(
                    PosicaoEntrega.carregamento_id == carregamento.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(gravadas) == 1
    assert gravadas[0].lat == Decimal("-23.400000")


async def test_positions_accumulate_as_a_path(db_session, seed_carregamento):
    """Série temporal, não campo único: o mapa desenha o caminho."""
    carregamento = await seed_carregamento()

    for lat in ("-23.40", "-23.45", "-23.50"):
        await registrar_posicao(
            db_session, carregamento.id, Decimal(lat), Decimal("-46.80")
        )

    todas = (
        (
            await db_session.execute(
                select(PosicaoEntrega).where(
                    PosicaoEntrega.carregamento_id == carregamento.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(todas) == 3
    ultima = await ultima_posicao(db_session, carregamento.id)
    assert ultima.lat == Decimal("-23.500000")


async def test_the_simulator_only_moves_shipments_in_transit(
    db_session, seed_carregamento_com_pedido
):
    parado, _ = await seed_carregamento_com_pedido(
        status=StatusPedido.AGUARDANDO_COLETA.value
    )
    andando, _ = await seed_carregamento_com_pedido(
        status=StatusPedido.EM_TRANSITO.value
    )

    avancados = await avancar_carregamentos(db_session, datetime.now(UTC))

    assert avancados == 1
    assert await ultima_posicao(db_session, parado.id) is None
    assert await ultima_posicao(db_session, andando.id) is not None


async def test_the_simulator_skips_an_order_without_a_frozen_destination(
    db_session, seed_carregamento_com_pedido
):
    """Sem coordenada de destino não há segmento para interpolar. O pedido é
    ignorado e o rastreio devolve posição nula — o caminho de degradação que
    a spec prevê, não uma exceção."""
    carregamento, _ = await seed_carregamento_com_pedido(
        status=StatusPedido.EM_TRANSITO.value, destino=None
    )

    avancados = await avancar_carregamentos(db_session, datetime.now(UTC))

    assert avancados == 0
    assert await ultima_posicao(db_session, carregamento.id) is None
```

E, para a leitura, em `tests/test_tracking_routes.py`:

```python
async def test_tracking_answers_with_a_null_position_when_none_was_recorded(
    client, db_session
):
    """200 com posição nula, nunca tela de erro: o mapa mostra origem e
    destino sem o marcador móvel."""
    pedido = await _seed_pedido_do_aluno(db_session)

    corpo = (
        await client.get(
            f"/orders/{pedido.id}/tracking", headers=headers_for("student", str(pedido.user_id))
        )
    ).json()

    assert corpo["courier_position"] is None


async def test_tracking_carries_the_last_recorded_position(client, db_session):
    pedido, carregamento = await _seed_pedido_em_transito_com_carregamento(db_session)
    await registrar_posicao(
        db_session, carregamento.id, Decimal("-23.450000"), Decimal("-46.700000")
    )

    corpo = (
        await client.get(
            f"/orders/{pedido.id}/tracking", headers=headers_for("student", str(pedido.user_id))
        )
    ).json()

    assert corpo["courier_position"]["latitude"] == -23.45
    assert corpo["courier_position"]["longitude"] == -46.7
```

E, para a D12, em `tests/test_tracking_builders.py`:

```python
def test_the_tracking_shows_the_real_carrier_when_there_is_one():
    order = _order(status=StatusPedido.EM_TRANSITO.value, carrier_name="Expresso Cajamar")
    assert build_order_tracking(order).carrier == "Expresso Cajamar"


def test_the_tracking_falls_back_to_the_house_carrier():
    """Pedido sem carregamento continua mostrando a constante — não uma
    string vazia, que a tela renderizaria como um campo em branco."""
    order = _order(status=StatusPedido.CRIADO.value, carrier_name=None)
    assert build_order_tracking(order).carrier == "Logistics Intel Express"
```

As fixtures `seed_carregamento` e `seed_carregamento_com_pedido` vão para
`tests/conftest.py` (são usadas pelas tasks 6 e 7):

```python
@pytest.fixture
def seed_carregamento(db_session):
    """Um carregamento pronto, com origem congelada. `senha_hash` é um hash
    qualquer — nenhum teste desta fixture faz login."""

    async def _seed(**kwargs):
        from edu_common.security import hash_password

        from app.models.carregamento import Carregamento
        from app.models.transportadora import Carrier

        carrier = Carrier(
            name=kwargs.get("carrier_name", "Expresso Cajamar"),
            location="Cajamar, SP",
            email="operacao@expresso.example",
            average_delivery_days=2,
            rating=Decimal("4.5"),
            sla_percentage=Decimal("97.50"),
        )
        db_session.add(carrier)
        await db_session.flush()
        carregamento = Carregamento(
            transportadora_id=carrier.id,
            codigo=kwargs.get("codigo", "ABCD2345"),
            senha_hash=hash_password("nao-usada-nesta-fixture"),
            criado_por=uuid.uuid4(),
            origem_rotulo="Cajamar, SP",
            origem_lat=Decimal("-23.355800"),
            origem_lng=Decimal("-46.876900"),
        )
        db_session.add(carregamento)
        await db_session.commit()
        await db_session.refresh(carregamento)
        return carregamento

    return _seed
```

`seed_carregamento_com_pedido` monta o mesmo e acrescenta um `Order` com
`carregamento_id`, `status` parametrizado, `status_updated_at` explícito e
`destino_lat/lng` (ou `None`, quando o teste pede).

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_delivery_position.py -q
```

Esperado: `ModuleNotFoundError: No module named 'app.services.posicao'`.

- [ ] **Passo 3: a porta de escrita**

Criar `app/services/posicao.py`:

```python
"""Posição do carregamento: a porta de escrita, a leitura, e o congelamento do
destino.

`registrar_posicao` é a ÚNICA função que escreve em `posicao_entrega`. O
simulador (`app/services/simulador_posicao.py`) é um chamador dela; um aparelho
com GPS seria outro, chamando exatamente esta assinatura. Trocar de fonte é
acrescentar um chamador e desligar o simulador — não reescrever a leitura, o
model nem a tela.
"""

from decimal import Decimal

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.carregamento import Carregamento, PosicaoEntrega
from app.models.pedido import Order
from app.services import directions


async def registrar_posicao(
    db: AsyncSession, carregamento_id: int, lat: Decimal, lng: Decimal
) -> None:
    db.add(PosicaoEntrega(carregamento_id=carregamento_id, lat=lat, lng=lng))
    await db.commit()


async def ultima_posicao(
    db: AsyncSession, carregamento_id: int
) -> PosicaoEntrega | None:
    resultado = await db.execute(
        select(PosicaoEntrega)
        .where(PosicaoEntrega.carregamento_id == carregamento_id)
        .order_by(PosicaoEntrega.registrado_em.desc(), PosicaoEntrega.id.desc())
        .limit(1)
    )
    return resultado.scalars().first()


async def congelar_destino(db: AsyncSession, order: Order) -> None:
    """Resolve a coordenada do endereço de entrega e a grava no pedido.

    Roda UMA vez, na coleta. `addresses` não guarda coordenada (medido em
    `auth-users-service/app/models/address.py`), e quem sabe converter
    endereço em par lat/lng é a mesma fronteira que `GET /orders/{id}/route`
    já usa.

    **Nunca levanta.** Sem chave, sem endereço, provedor fora do ar: o pedido
    segue sem coordenada, o simulador o ignora, e o rastreio devolve
    `courier_position: null`. Impedir uma coleta porque a Google não
    respondeu seria trocar um mapa parado por uma operação parada.
    """
    if order.destino_lat is not None or not order.ship_street:
        return
    carregamento = (
        await db.get(Carregamento, order.carregamento_id)
        if order.carregamento_id
        else None
    )
    if carregamento is None or carregamento.origem_lat is None:
        return
    if not settings.google_maps_api_key:
        logger.info("posicao: sem chave da Google, pedido {} fica sem destino", order.id)
        return

    try:
        async with httpx.AsyncClient() as client:
            resultado = await directions.fetch_directions(
                client,
                origin=(float(carregamento.origem_lat), float(carregamento.origem_lng)),
                destination=_endereco_do_pedido(order),
                api_key=settings.google_maps_api_key,
            )
    except Exception:
        # Sem `str(exc)` no log: o detalhe do provedor pode carregar a chave
        # da API ou o endereço completo do aluno (regra 5 do CLAUDE.md, mesma
        # razão registrada em `app/routers/rastreio.py`).
        logger.warning("posicao: destino não resolvido para o pedido {}", order.id)
        return

    order.destino_lat = Decimal(str(resultado.destination_latitude))
    order.destino_lng = Decimal(str(resultado.destination_longitude))
    await db.commit()
```

`_endereco_do_pedido` é a mesma montagem que
`app/services/rastreio.py::_destination_query` já faz. **Não duplique**:
importe-a de lá (`from app.services.rastreio import _destination_query`) ou,
se o executor preferir não importar um nome privado entre módulos, mova a
função para `app/services/posicao.py` e faça `rastreio.py` importá-la — uma
das duas, nunca duas cópias. Registre no relatório qual foi escolhida.

- [ ] **Passo 4: o simulador**

Criar `app/services/simulador_posicao.py`:

```python
"""SIMULAÇÃO. Não há entregador real nem GPS neste sistema.

Este módulo interpola uma posição entre a origem do carregamento e o destino
do pedido, conforme o tempo desde a entrada em EM_TRANSITO, e a grava pela
MESMA função que uma posição vinda de um aparelho gravaria
(`app/services/posicao.py::registrar_posicao`).

Como trocar por GPS real: acrescente o chamador novo de `registrar_posicao` e
desligue este job no `app/scheduler.py`. Nada da leitura, do model ou da tela
muda — é por isso que a porta de escrita é separada do simulador.

O relatório de entrega desta spec lista esta simulação como simulação
(`docs/back-end/order-flow.md`, task 15).
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carregamento import Carregamento
from app.models.pedido import Order
from app.services.posicao import registrar_posicao
from app.services.status_pedido import StatusPedido

# Quanto tempo o percurso inteiro leva, na simulação. Não é a ETA do rastreio
# (essa vem de `previsao_entrega`/Directions): é o relógio da animação, e ele
# é curto porque a apresentação inteira dura minutos.
DURACAO_PERCURSO = timedelta(minutes=6)


def fracao_percorrida(
    inicio: datetime, agora: datetime, duracao: timedelta = DURACAO_PERCURSO
) -> float:
    """0.0 na largada, 1.0 na chegada, e nunca mais que 1.0 — o entregador não
    passa do endereço."""
    if duracao.total_seconds() <= 0:
        return 1.0
    decorrido = (agora - inicio).total_seconds() / duracao.total_seconds()
    return max(0.0, min(1.0, decorrido))


def interpolar(
    origem: tuple[Decimal, Decimal], destino: tuple[Decimal, Decimal], fracao: float
) -> tuple[Decimal, Decimal]:
    """Interpolação linear, com o resultado quantizado nas 6 casas decimais da
    coluna — gravar mais casas do que a coluna guarda faria a leitura devolver
    um valor diferente do que o cálculo produziu."""
    passo = Decimal(str(fracao))
    lat = origem[0] + (destino[0] - origem[0]) * passo
    lng = origem[1] + (destino[1] - origem[1]) * passo
    casas = Decimal("0.000001")
    return lat.quantize(casas), lng.quantize(casas)


async def avancar_carregamentos(db: AsyncSession, agora: datetime) -> int:
    """Uma posição por carregamento com pedido em trânsito.

    Por CARREGAMENTO, não por pedido: o lote anda junto, é isso que ele é. O
    destino usado é o do primeiro pedido do lote que tem coordenada congelada
    — com uma parada por lote (roteirização com várias paradas está fora do
    escopo da spec), esse é o destino.
    """
    linhas = (
        await db.execute(
            select(Carregamento, Order)
            .join(Order, Order.carregamento_id == Carregamento.id)
            .where(
                Order.status == StatusPedido.EM_TRANSITO.value,
                Order.destino_lat.is_not(None),
                Carregamento.origem_lat.is_not(None),
            )
            .order_by(Carregamento.id, Order.created_at)
        )
    ).all()

    vistos: set[int] = set()
    avancados = 0
    for carregamento, pedido in linhas:
        if carregamento.id in vistos:
            continue
        vistos.add(carregamento.id)
        fracao = fracao_percorrida(pedido.status_updated_at, agora)
        lat, lng = interpolar(
            (carregamento.origem_lat, carregamento.origem_lng),
            (pedido.destino_lat, pedido.destino_lng),
            fracao,
        )
        await registrar_posicao(db, carregamento.id, lat, lng)
        avancados += 1
    return avancados
```

- [ ] **Passo 5: o rastreio devolve a posição e a transportadora real**

Em `app/schemas/rastreio.py`:

```python
class TrackingPositionOut(BaseModel):
    """Última posição conhecida do carregamento que leva o pedido.

    `None` no payload é estado normal: pedido que ainda não saiu, lote sem
    posição registrada, ou destino não resolvido. O app desenha origem e
    destino sem o marcador móvel — nunca uma tela de erro.
    """

    latitude: float = Field(..., ge=_LAT_MIN, le=_LAT_MAX)
    longitude: float = Field(..., ge=_LNG_MIN, le=_LNG_MAX)
    updated_at: datetime
```

e, em `OrderTrackingOut`, um campo novo com default — o app antigo, que não
conhece a chave, continua lendo o payload sem quebrar:

```python
    courier_position: TrackingPositionOut | None = None
```

Em `app/services/rastreio_builder.py`, a assinatura ganha o parâmetro e as duas
linhas finais mudam:

```python
def build_order_tracking(
    order: Order, posicao: "PosicaoEntrega | None" = None
) -> OrderTrackingOut:
    ...
        carrier=order.carrier_name or _CARRIER,
        map_url=None,
        status=status,
        courier_position=(
            None
            if posicao is None
            else TrackingPositionOut(
                latitude=float(posicao.lat),
                longitude=float(posicao.lng),
                updated_at=posicao.registrado_em,
            )
        ),
    )
```

A função continua **pura**: recebe a posição já carregada. Em
`app/routers/rastreio.py::rastreio_pedido`, antes do `return`:

```python
    posicao = (
        await ultima_posicao(db, order.carregamento_id)
        if order.carregamento_id is not None
        else None
    )
    return build_order_tracking(order, posicao)
```

- [ ] **Passo 6: a coleta congela o destino**

Em `app/routers/entrega.py::confirmar_coleta`, depois da transição para
`EM_TRANSITO` e no mesmo bloco protegido onde a estimativa de prazo já roda:

```python
    # Uma vez por pedido, e nunca bloqueando a coleta (ver
    # `congelar_destino`, que não levanta).
    await congelar_destino(db, pedido_atualizado)
```

- [ ] **Passo 7: rodar e ver passar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_delivery_position.py \
  tests/test_tracking_routes.py tests/test_tracking_builders.py tests/test_delivery_routes.py -q
```

Atenção ao `_block_real_network_calls` do `conftest.py`: nenhum teste desta
task pode alcançar a Google. Os testes de coleta que **não** remendam
`directions.fetch_directions` exercitam o caminho degradado (destino fica
nulo), e isso é intencional — escreva pelo menos um que remenda a função e
afirma que `destino_lat` foi gravado.

- [ ] **Passo 8: suíte inteira e lint**

```bash
cd back-end/commerce-service && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

Esperado: **571 passed** (559 + 12).

- [ ] **Passo 9: commit**

```bash
git add back-end/commerce-service/app/services/posicao.py \
        back-end/commerce-service/app/services/simulador_posicao.py \
        back-end/commerce-service/app/services/rastreio_builder.py \
        back-end/commerce-service/app/schemas/rastreio.py \
        back-end/commerce-service/app/routers/rastreio.py \
        back-end/commerce-service/app/routers/entrega.py \
        back-end/commerce-service/tests/conftest.py \
        back-end/commerce-service/tests/test_delivery_position.py \
        back-end/commerce-service/tests/test_tracking_routes.py \
        back-end/commerce-service/tests/test_tracking_builders.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): record delivery position behind one write door and show it on tracking

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: Scheduler — o simulador andando, e o avanço automático como rede de segurança

**Files:**
- Criar: `back-end/commerce-service/app/services/avanco_automatico.py`
- Criar: `back-end/commerce-service/app/scheduler.py`
- Modificar: `back-end/commerce-service/app/config.py`
- Modificar: `back-end/commerce-service/app/main.py`
- Modificar: `back-end/commerce-service/pyproject.toml`
- Modificar: `back-end/commerce-service/.env.example`
- Modificar: `back-end/docker-compose.yml`
- Criar: `back-end/commerce-service/tests/test_avanco_automatico.py`
- Modificar: `back-end/commerce-service/tests/test_config.py`

**Interfaces:**

```python
# app/config.py
    avanco_automatico_segundos: int = 0   # 0 = DESLIGADO (o default)
    simulador_posicao_segundos: int = 10

# app/services/avanco_automatico.py
PROXIMO_ESTADO: dict[StatusPedido, StatusPedido]

async def avancar_parados(
    db: AsyncSession, agora: datetime, prazo_segundos: int
) -> list[uuid.UUID]
    """Avança quem está no mesmo estado há mais que `prazo_segundos`.
    `prazo_segundos <= 0` não avança nada."""

# app/scheduler.py
def start_scheduler() -> None
def stop_scheduler() -> None
```

**As três regras da spec, e como cada uma é testada:**

1. **Desligado por padrão.** `AVANCO_AUTOMATICO_SEGUNDOS` ausente ⇒ `0` ⇒
   `avancar_parados` devolve lista vazia sem tocar em nada.
2. **Prazo bem maior que três minutos.** O `.env.example` sugere `600` (dez
   minutos) e o comentário explica: uma pessoa alternando quatro perfis leva
   mais que três minutos só para trocar de sessão, e um pedido correndo na
   frente do apresentador é exatamente o acidente a evitar.
3. **Ação manual sempre vence.** O critério é `status_updated_at`, que
   `transicionar_pedido` carimba em toda transição — qualquer ação manual
   reinicia a contagem sem precisar cancelar nada.

`AGUARDANDO_SUBSTITUICAO` **não** avança: é o único estado que espera uma
decisão humana que é o ponto da demonstração. `ENTREGUE` e `CANCELADO` são
terminais.

- [ ] **Passo 1: escrever os testes que falham**

Criar `tests/test_avanco_automatico.py`:

```python
from datetime import UTC, datetime, timedelta

from app.services.avanco_automatico import PROXIMO_ESTADO, avancar_parados
from app.services.status_pedido import TRANSICOES_VALIDAS, StatusPedido


def test_every_hop_is_a_valid_transition():
    """Um destino fora de TRANSICOES_VALIDAS faria o job levantar 400 em
    silêncio a cada varredura, para sempre."""
    for origem, destino in PROXIMO_ESTADO.items():
        assert destino in TRANSICOES_VALIDAS[origem]


def test_the_substitution_wait_never_advances_on_its_own():
    """É o único estado que espera decisão do aluno — e essa decisão é o que
    a apresentação está mostrando."""
    assert StatusPedido.AGUARDANDO_SUBSTITUICAO not in PROXIMO_ESTADO


def test_terminal_states_never_advance():
    assert StatusPedido.ENTREGUE not in PROXIMO_ESTADO
    assert StatusPedido.CANCELADO not in PROXIMO_ESTADO


async def test_it_is_off_by_default(db_session, seed_pedido_parado):
    """`AVANCO_AUTOMATICO_SEGUNDOS` ausente vale 0, e 0 é desligado. Critério
    de pronto 6 da spec."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(hours=3)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 0)

    assert avancados == []
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value


async def test_it_does_not_fire_before_the_deadline(db_session, seed_pedido_parado):
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(seconds=30)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == []
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.AGUARDANDO_SEPARACAO.value


async def test_it_fires_after_the_deadline(db_session, seed_pedido_parado):
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == [pedido.id]
    await db_session.refresh(pedido)
    assert pedido.status == StatusPedido.EM_SEPARACAO.value


async def test_a_manual_action_restarts_the_clock(db_session, seed_pedido_parado):
    """Ação manual sempre vence: `transicionar_pedido` carimba
    `status_updated_at`, e a contagem recomeça dali. Nada precisa ser
    cancelado."""
    pedido = await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )
    from app.routers.separacao import transicionar_pedido

    await transicionar_pedido(
        db_session, pedido.id, StatusPedido.EM_SEPARACAO.value, str(pedido.user_id)
    )

    avancados = await avancar_parados(db_session, datetime.now(UTC), 600)

    assert avancados == []


async def test_it_publishes_through_the_same_funnel(
    db_session, seed_pedido_parado, monkeypatch
):
    """Escreve pela mesma função de transição que as rotas usam — nunca
    UPDATE direto —, então validação, histórico e evento acontecem de um jeito
    só."""
    eventos: list[tuple[str, dict]] = []

    async def _capturar(chave, payload):
        eventos.append((chave, payload))

    monkeypatch.setattr("app.routers.separacao.publish_event", _capturar)
    await seed_pedido_parado(
        status=StatusPedido.AGUARDANDO_SEPARACAO.value, parado_ha=timedelta(minutes=20)
    )

    await avancar_parados(db_session, datetime.now(UTC), 600)

    assert [chave for chave, _ in eventos] == ["order.status_changed"]
```

E em `tests/test_config.py`:

```python
def test_the_automatic_advance_is_off_unless_configured():
    assert Settings(**_campos_obrigatorios()).avanco_automatico_segundos == 0
```

(`_campos_obrigatorios` é o helper que o arquivo já usa para instanciar
`Settings` — reuse-o; se ele tiver outro nome, use o que estiver lá.)

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/commerce-service && uv run pytest tests/test_avanco_automatico.py -q
```

- [ ] **Passo 3: a config**

Em `app/config.py`, no fim da classe `Settings`:

```python
    # Rede de segurança da apresentação: avança um pedido parado no mesmo
    # estado há mais que este prazo. AUSENTE (0) É DESLIGADO — o default, e o
    # critério de pronto 6 da spec C.
    #
    # Se ligar, use um valor BEM maior que três minutos: a apresentação é
    # conduzida por uma pessoa alternando entre quatro perfis, e trocar de
    # sessão já leva mais que isso. Um prazo curto faz o pedido correr na
    # frente do apresentador, que é exatamente o acidente a evitar.
    avanco_automatico_segundos: int = 0
    # De quanto em quanto tempo o simulador grava uma posição nova. Dez
    # segundos casa com o polling do app (`OrderProvider`, 8s).
    simulador_posicao_segundos: int = 10
```

- [ ] **Passo 4: o serviço**

Criar `app/services/avanco_automatico.py`:

```python
"""Rede de segurança da apresentação: avança um pedido esquecido.

Não é um simulador de pipeline. Ele existe para o caso de o apresentador ficar
preso numa tela — e por isso é DESLIGADO por padrão, tem prazo longo, e perde
para qualquer ação manual.

Escreve pela MESMA função de transição que as rotas usam
(`app/routers/separacao.py::transicionar_pedido`), nunca por UPDATE direto:
validação de transição, carimbo de `status_updated_at`, linha de histórico e
evento acontecem de um jeito só, e não de dois.
"""

import uuid
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pedido import Order
from app.routers.separacao import transicionar_pedido
from app.services.status_pedido import StatusPedido

# O passo seguinte de cada estado que pode ser avançado sozinho.
#
# `AGUARDANDO_SUBSTITUICAO` está FORA de propósito: é o único estado que espera
# uma decisão do aluno, e essa decisão é o que a apresentação está mostrando.
# `SEPARADO` também está fora: `finalizar_separacao` já encadeia
# SEPARADO -> AGUARDANDO_COLETA na mesma chamada, então um pedido nunca
# repousa nele em operação normal.
PROXIMO_ESTADO: dict[StatusPedido, StatusPedido] = {
    StatusPedido.CRIADO: StatusPedido.CONFIRMADO,
    StatusPedido.CONFIRMADO: StatusPedido.AGUARDANDO_SEPARACAO,
    StatusPedido.AGUARDANDO_SEPARACAO: StatusPedido.EM_SEPARACAO,
    StatusPedido.EM_SEPARACAO: StatusPedido.SEPARADO,
    StatusPedido.AGUARDANDO_COLETA: StatusPedido.EM_TRANSITO,
    StatusPedido.EM_TRANSITO: StatusPedido.ENTREGUE,
}

OBSERVACAO = "Avanço automático (rede de segurança da apresentação)"


async def avancar_parados(
    db: AsyncSession, agora: datetime, prazo_segundos: int
) -> list[uuid.UUID]:
    if prazo_segundos <= 0:
        return []

    limite = agora - timedelta(seconds=prazo_segundos)
    pedidos = (
        (
            await db.execute(
                select(Order).where(
                    Order.status.in_([e.value for e in PROXIMO_ESTADO]),
                    Order.status_updated_at < limite,
                )
            )
        )
        .scalars()
        .all()
    )

    avancados: list[uuid.UUID] = []
    for pedido in pedidos:
        destino = PROXIMO_ESTADO[StatusPedido(pedido.status)]
        await transicionar_pedido(db, pedido.id, destino.value, None, observacao=OBSERVACAO)
        avancados.append(pedido.id)
        logger.info("avanco_automatico: pedido {} avançou para {}", pedido.id, destino.value)
    return avancados
```

`user_id=None` na transição é deliberado: não foi uma pessoa. A coluna
`pedido_status_historico.user_id` já é nullable.

- [ ] **Passo 5: o scheduler**

Criar `app/scheduler.py`, no padrão de
`back-end/learning-service/app/scheduler.py`:

```python
"""Os dois jobs periódicos do commerce.

Mesmo padrão do `learning-service/app/scheduler.py`: um `AsyncIOScheduler`
global, ligado e desligado pelo `lifespan` do app.
"""

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from app.config import settings
from app.database import async_session
from app.services.avanco_automatico import avancar_parados
from app.services.simulador_posicao import avancar_carregamentos

_scheduler: AsyncIOScheduler | None = None


async def tick_posicao() -> None:
    async with async_session() as db:
        await avancar_carregamentos(db, datetime.now(UTC))


async def tick_avanco_automatico() -> None:
    async with async_session() as db:
        await avancar_parados(db, datetime.now(UTC), settings.avanco_automatico_segundos)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        tick_posicao, "interval", seconds=settings.simulador_posicao_segundos
    )
    if settings.avanco_automatico_segundos > 0:
        # O job só é REGISTRADO quando o avanço está ligado. Registrar um job
        # que sempre devolve lista vazia gastaria uma conexão de banco por
        # minuto para não fazer nada, e esconderia no log a diferença entre
        # "ligado e nada a fazer" e "desligado".
        _scheduler.add_job(tick_avanco_automatico, "interval", seconds=60)
        logger.info(
            "scheduler: avanço automático LIGADO, prazo de {}s",
            settings.avanco_automatico_segundos,
        )
    else:
        logger.info("scheduler: avanço automático desligado (padrão)")
    _scheduler.start()


def stop_scheduler() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)
```

No `app/main.py`:

```python
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_publisher()
    start_scheduler()
    yield
    stop_scheduler()
    await close_publisher()
```

Em `pyproject.toml`, na lista `dependencies`:

```toml
    "apscheduler>=3.10.4",
```

(mesma versão-piso que o `learning-service` já usa — confirme com
`grep -n apscheduler back-end/learning-service/pyproject.toml` e copie o valor
de lá em vez de escolher outro.)

- [ ] **Passo 6: `.env.example` e compose**

Em `back-end/commerce-service/.env.example`, na seção de opcionais:

```
# Rede de segurança da apresentação. AUSENTE = DESLIGADO, que é o padrão e o
# que a spec C pede. Se ligar, use um prazo BEM maior que três minutos — dez
# minutos é o valor sugerido:
# AVANCO_AUTOMATICO_SEGUNDOS=600
# SIMULADOR_POSICAO_SEGUNDOS=10
```

Em `back-end/docker-compose.yml`, no bloco `commerce-service`, junto das outras
variáveis explícitas:

```yaml
      AVANCO_AUTOMATICO_SEGUNDOS: ${AVANCO_AUTOMATICO_SEGUNDOS:-0}
```

Não crie um `.env` novo e não edite o `.env` do usuário — só o `.env.example`.

- [ ] **Passo 7: rodar e ver passar**

```bash
cd back-end/commerce-service && uv sync && uv run pytest -q && uv run ruff check .
docker compose -f ../docker-compose.yml config --quiet
```

Esperado: **580 passed** (571 + 9), `config --quiet` com exit 0.

O `uv sync` aqui é o único da spec e existe porque uma dependência entrou; ele
altera `uv.lock` **deste serviço**, o que é esperado e deve ir no commit.

- [ ] **Passo 8: commit**

```bash
git add back-end/commerce-service/app/services/avanco_automatico.py \
        back-end/commerce-service/app/scheduler.py \
        back-end/commerce-service/app/config.py \
        back-end/commerce-service/app/main.py \
        back-end/commerce-service/pyproject.toml \
        back-end/commerce-service/uv.lock \
        back-end/commerce-service/.env.example \
        back-end/docker-compose.yml \
        back-end/commerce-service/tests/test_avanco_automatico.py \
        back-end/commerce-service/tests/test_config.py
git diff --staged
git commit -m "$(cat <<'MSG'
feat(commerce): run the position simulator and an off-by-default automatic advance

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 8: Push no perfil certo — destinatário por transição

Hoje **todo** push vai para o comprador: `handle_order_status_changed` escreve
uma linha para `payload["aluno_id"]` e nada mais (D5). Esta task põe a tabela
de destinatário por transição no `notification-service`, junto do resto da
decisão de notificação, e liga as duas chaves que ninguém consumia.

**Files:**
- Criar: `back-end/notification-service/app/models/staff.py`
- Criar: `back-end/notification-service/app/services/destinatarios.py`
- Modificar: `back-end/notification-service/app/events/consumer.py`
- Criar: `back-end/notification-service/alembic/versions/d4c5b6a7e8f9_staff_registry.py`
- Modificar: `back-end/notification-service/tests/conftest.py`
- Modificar: `back-end/notification-service/tests/test_consumer.py`
- Modificar: `back-end/auth-users-service/app/seeds/demo_accounts.py`
- Modificar: `back-end/auth-users-service/tests/test_demo_accounts.py`

**Interfaces:**

```python
# app/models/staff.py
class Staff(Base):
    __tablename__ = "staff"
    user_id: uuid.UUID   # PK — o id do auth-users
    papel: str           # String(20): admin | separador | entregador
    nome: str            # String(150)
    criado_em: datetime

# app/services/destinatarios.py
PAPEIS_POR_STATUS: dict[str, tuple[str, ...]]
"""Quem é avisado de cada transição. `"aluno"` é o comprador do pedido; os
demais são papéis de staff resolvidos no registro local."""

async def resolver(db, papeis: tuple[str, ...], aluno_id: str) -> list[str]
```

**A tabela de destinatário (é isto que a task instala):**

| Evento / transição | Quem é avisado |
|---|---|
| `order.created` | `admin`, `separador` |
| `AGUARDANDO_SEPARACAO` | `aluno`, `separador` |
| `EM_SEPARACAO` | `aluno` |
| `AGUARDANDO_SUBSTITUICAO` | `aluno` |
| `SEPARADO` | `aluno` |
| `AGUARDANDO_COLETA` | `aluno`, `entregador` |
| `EM_TRANSITO` | `aluno` |
| `ENTREGUE` | `aluno`, `admin` |
| `CANCELADO` | `aluno`, `admin` |
| `order.stock_issue` | `aluno` |
| `order.delivery_delayed` | `aluno` |
| `order.occurrence_resolved` | `separador` |
| `CONFIRMADO` | ninguém (supressão que já existe — ver o comentário no handler) |

`order.occurrence_resolved` avisa o **separador**: é ele quem estava esperando a
decisão do aluno para poder finalizar a separação.

- [ ] **Passo 1: escrever os testes que falham**

Em `tests/test_consumer.py`:

```python
async def test_staff_created_registers_the_person(db_session, test_session_factory, monkeypatch):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_staff_created(
        fake_message({"user_id": SEPARADOR_ID, "nome": "Separador Demo", "role": "separador"})
    )

    registrados = (await db_session.execute(select(Staff))).scalars().all()
    assert [(str(s.user_id), s.papel) for s in registrados] == [
        (SEPARADOR_ID, "separador")
    ]


async def test_staff_created_is_idempotent(db_session, test_session_factory, monkeypatch):
    """A fila é durável e a entrega é ao-menos-uma-vez: a mesma mensagem pode
    chegar duas vezes depois de um restart do broker."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    mensagem = {"user_id": SEPARADOR_ID, "nome": "Separador Demo", "role": "separador"}

    await consumer_module.handle_staff_created(fake_message(mensagem))
    await consumer_module.handle_staff_created(fake_message(mensagem))

    registrados = (await db_session.execute(select(Staff))).scalars().all()
    assert len(registrados) == 1


async def test_order_created_notifies_staff_and_not_the_student(
    db_session, test_session_factory, monkeypatch
):
    """`order.created` era publicado e ninguém consumia. Quem precisa saber
    que entrou pedido é a operação, não o aluno — ele acabou de clicar em
    comprar."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    await _registrar_staff(test_session_factory)

    await consumer_module.handle_order_created(
        fake_message({"pedido_id": PEDIDO_ID, "aluno_id": STUDENT_ID, "valor_total": 99.9})
    )

    destinatarios = {
        str(n.aluno_id) for n in (await db_session.execute(select(Notificacao))).scalars()
    }
    assert destinatarios == {ADMIN_ID, SEPARADOR_ID}


async def test_pickup_ready_notifies_the_student_and_every_courier(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    await _registrar_staff(test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message(
            {"pedido_id": PEDIDO_ID, "aluno_id": STUDENT_ID, "status": "AGUARDANDO_COLETA"}
        )
    )

    destinatarios = {
        str(n.aluno_id) for n in (await db_session.execute(select(Notificacao))).scalars()
    }
    assert destinatarios == {STUDENT_ID, ENTREGADOR_ID}


async def test_delivery_notifies_the_student_and_the_admin(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    await _registrar_staff(test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"pedido_id": PEDIDO_ID, "aluno_id": STUDENT_ID, "status": "ENTREGUE"})
    )

    destinatarios = {
        str(n.aluno_id) for n in (await db_session.execute(select(Notificacao))).scalars()
    }
    assert destinatarios == {STUDENT_ID, ADMIN_ID}


async def test_the_substitution_wait_notifies_only_the_buyer(
    db_session, test_session_factory, monkeypatch
):
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    await _registrar_staff(test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message(
            {
                "pedido_id": PEDIDO_ID,
                "aluno_id": STUDENT_ID,
                "status": "AGUARDANDO_SUBSTITUICAO",
            }
        )
    )

    notificacoes = (await db_session.execute(select(Notificacao))).scalars().all()
    assert [str(n.aluno_id) for n in notificacoes] == [STUDENT_ID]
    assert "falta" in notificacoes[0].descricao.lower()


async def test_confirmed_still_notifies_nobody(
    db_session, test_session_factory, monkeypatch
):
    """A supressão de CONFIRMADO já existia e continua: é um estado que
    `confirmar_pagamento` atravessa na MESMA chamada."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    await _registrar_staff(test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"pedido_id": PEDIDO_ID, "aluno_id": STUDENT_ID, "status": "CONFIRMADO"})
    )

    assert (await db_session.execute(select(Notificacao))).scalars().all() == []


async def test_occurrence_resolved_tells_the_picker_to_carry_on(
    db_session, test_session_factory, monkeypatch
):
    """Publicado desde a fase 2, consumido por ninguém. É o separador que
    está bloqueado esperando a decisão do aluno."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    await _registrar_staff(test_session_factory)

    await consumer_module.handle_occurrence_resolved(
        fake_message(
            {
                "pedido_id": PEDIDO_ID,
                "aluno_id": STUDENT_ID,
                "ocorrencia_id": 7,
                "resolucao": "substituir",
            }
        )
    )

    notificacoes = (await db_session.execute(select(Notificacao))).scalars().all()
    assert [str(n.aluno_id) for n in notificacoes] == [SEPARADOR_ID]


async def test_a_transition_with_no_staff_registered_still_reaches_the_student(
    db_session, test_session_factory, monkeypatch
):
    """Registro vazio (frota nova, ou evento de staff ainda na fila) não pode
    engolir a notificação do comprador."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)

    await consumer_module.handle_order_status_changed(
        fake_message({"pedido_id": PEDIDO_ID, "aluno_id": STUDENT_ID, "status": "EM_TRANSITO"})
    )

    notificacoes = (await db_session.execute(select(Notificacao))).scalars().all()
    assert [str(n.aluno_id) for n in notificacoes] == [STUDENT_ID]


def test_every_internal_status_has_a_recipient_rule():
    """Exaustivo por construção, igual ao `STATUS_CONTRATO` do commerce: um
    estado novo sem regra aqui quebra a suíte em vez de virar um push
    silencioso para ninguém.

    A lista é escrita como LITERAL de propósito — importar o enum do commerce
    faria este teste seguir uma renomeação em vez de detectá-la (mesma razão
    registrada em `edu_common/contracts.py`).
    """
    internos = {
        "CRIADO",
        "CONFIRMADO",
        "AGUARDANDO_SEPARACAO",
        "EM_SEPARACAO",
        "AGUARDANDO_SUBSTITUICAO",
        "SEPARADO",
        "AGUARDANDO_COLETA",
        "EM_TRANSITO",
        "ENTREGUE",
        "CANCELADO",
    }
    assert internos <= set(PAPEIS_POR_STATUS)
```

`_registrar_staff` insere um admin, um separador e um entregador via
`test_session_factory`. `ADMIN_ID`, `SEPARADOR_ID`, `ENTREGADOR_ID` e
`PEDIDO_ID` são constantes de módulo, como `STUDENT_ID` já é.

E em `back-end/auth-users-service/tests/test_demo_accounts.py`:

```python
async def test_the_bootstrap_admin_announces_itself_like_the_others(...):
    """`admin@demo.edu` é a única conta criada por INSERT direto, então ela
    nunca publicou `staff.created` — e o registro de staff do
    notification-service (spec C, task 8) nasceria sem o admin, deixando as
    transições que avisam admin sem destinatário nenhum."""
    ...
    assert ("staff.created", {"user_id": ANY, "nome": "Admin Demo", "role": "admin"}) in eventos
```

Adapte a montagem ao que o arquivo de teste já faz para capturar eventos do
seed; se ele ainda não captura, use o mesmo padrão de monkeypatch de
`publish_event` usado nos outros testes do serviço.

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/notification-service && uv run pytest -q
```

- [ ] **Passo 3: o model e a revision**

`app/models/staff.py`:

```python
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Staff(Base):
    """Quem é staff, na visão deste serviço.

    Réplica local mantida por EVENTO (`staff.created`), não por consulta ao
    auth-users. O serviço precisa saber "quem são os separadores" para
    endereçar um push, e as alternativas eram piores: chamar
    `GET /users?role=` exigiria um token de admin fabricado aqui — um serviço
    que não é dono de identidade emitindo credencial de admin —, e pôr os ids
    no payload do commerce não resolveria `order.created`, que precisa avisar
    gente que ainda não tocou no pedido. Ver D6 do plano da spec C.

    `user_id` é a PK: o id vem do auth-users e é único lá.
    """

    __tablename__ = "staff"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    papel = Column(String(20), nullable=False, index=True)
    nome = Column(String(150), nullable=False, default="", server_default="")
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

A revision `d4c5b6a7e8f9_staff_registry.py` tem
`down_revision = "886205d547cc"` (head medido do notification) e cria a tabela
com o índice em `papel`. Provar aplicando contra `notification_test`, com os
mesmos três comandos da task 1 (upgrade, downgrade -1, upgrade).

Registrar o model em `tests/conftest.py::test_engine`, junto dos dois imports
`# noqa: F401` que já estão lá.

- [ ] **Passo 4: a tabela de destinatário**

`app/services/destinatarios.py`:

```python
"""Quem é avisado de quê.

A regra mora AQUI, e não no commerce, porque o destinatário depende da
TRANSIÇÃO e não do evento — e porque quem sabe endereçar push é este serviço.
O commerce publica o fato; este módulo decide a audiência.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff import Staff

ALUNO = "aluno"

# Exaustivo sobre os dez estados internos do commerce. Um estado novo sem
# entrada aqui quebra `test_every_internal_status_has_a_recipient_rule` — que
# é o comportamento desejado: um push endereçado a ninguém é indistinguível,
# em produção, de um push que não foi publicado.
PAPEIS_POR_STATUS: dict[str, tuple[str, ...]] = {
    # Estado transitório que `confirmar_pagamento` atravessa na mesma chamada:
    # avisar aqui daria duas notificações por um clique. A supressão já
    # existia no handler e continua, agora escrita como dado.
    "CRIADO": (),
    "CONFIRMADO": (),
    "AGUARDANDO_SEPARACAO": (ALUNO, "separador"),
    "EM_SEPARACAO": (ALUNO,),
    "AGUARDANDO_SUBSTITUICAO": (ALUNO,),
    "SEPARADO": (ALUNO,),
    "AGUARDANDO_COLETA": (ALUNO, "entregador"),
    "EM_TRANSITO": (ALUNO,),
    "ENTREGUE": (ALUNO, "admin"),
    "CANCELADO": (ALUNO, "admin"),
}

PAPEIS_ORDER_CREATED: tuple[str, ...] = ("admin", "separador")
PAPEIS_STOCK_ISSUE: tuple[str, ...] = (ALUNO,)
PAPEIS_DELIVERY_DELAYED: tuple[str, ...] = (ALUNO,)
# O separador é quem está bloqueado esperando a decisão do aluno
# (`finalizar_separacao` recusa com ocorrência aberta).
PAPEIS_OCCURRENCE_RESOLVED: tuple[str, ...] = ("separador",)


async def resolver(db: AsyncSession, papeis: tuple[str, ...], aluno_id: str) -> list[str]:
    """Traduz papéis em ids de destinatário, sem repetir ninguém.

    Um registro de staff vazio devolve só o aluno — nunca uma lista vazia
    quando `aluno` está entre os papéis. Notificação de comprador não pode
    depender de um evento de staff ter chegado antes.
    """
    ids: list[str] = []
    if ALUNO in papeis:
        ids.append(aluno_id)

    papeis_staff = tuple(p for p in papeis if p != ALUNO)
    if papeis_staff:
        encontrados = (
            (await db.execute(select(Staff.user_id).where(Staff.papel.in_(papeis_staff))))
            .scalars()
            .all()
        )
        ids.extend(str(uid) for uid in encontrados)

    vistos: set[str] = set()
    return [i for i in ids if not (i in vistos or vistos.add(i))]
```

- [ ] **Passo 5: os handlers**

Em `app/events/consumer.py`:

- `handle_staff_created`: `INSERT ... ON CONFLICT DO NOTHING` sobre `user_id`
  (idempotente e atômico, mesmo idioma de `registrar_device` em
  `app/routers/notificacoes.py`).
- `handle_order_created`: título `Pedido #<id curto>` e descrição
  `"Um pedido novo entrou na fila."`, `tipo="order_status"`, uma linha por
  destinatário de `PAPEIS_ORDER_CREATED`.
- `handle_order_status_changed`: mesma tabela de mensagens que já existe, mais
  a entrada de `AGUARDANDO_SUBSTITUICAO`
  (`"Um item do seu pedido está em falta. Toque para escolher um substituto ou cancelar."`),
  e o laço sobre `resolver(db, PAPEIS_POR_STATUS.get(status, (ALUNO,)), aluno_id)`.
  A supressão de `CONFIRMADO` passa a ser consequência da tabela (tupla vazia);
  **mantenha o comentário existente** movido para junto da entrada, ele
  explica um porquê que ninguém redescobre sozinho.
- `handle_occurrence_resolved`: novo, com `PAPEIS_OCCURRENCE_RESOLVED`.
- `BINDINGS` ganha três linhas:

```python
    ("notification.staff_created", "staff.created", handle_staff_created),
    ("notification.order_created", "order.created", handle_order_created),
    (
        "notification.occurrence_resolved",
        "order.occurrence_resolved",
        handle_occurrence_resolved,
    ),
```

Cada handler continua com `async with message.process():` e sem `except` — a
DLX da spec A recolhe o que falhar.

- [ ] **Passo 6: o seed do admin publica o evento**

Em `back-end/auth-users-service/app/seeds/demo_accounts.py`, no bootstrap que
faz o INSERT direto do admin, publicar depois do commit:

```python
    # As outras três contas nascem por rota e publicam `student.created` /
    # `staff.created` por conta própria. O admin é INSERT direto (é o que
    # rompe o ciclo do ovo e da galinha), então o evento sai daqui — sem ele,
    # o registro de staff do notification-service (spec C) nunca conhece o
    # admin, e toda transição que avisa admin fica sem destinatário.
    await publish_event(
        "staff.created",
        {"user_id": str(admin.id), "nome": admin.nome, "role": admin.role},
    )
```

- [ ] **Passo 7: rodar e ver passar**

```bash
cd back-end/notification-service && uv run pytest -q && uv run ruff check .
cd ../auth-users-service && uv run pytest -q && uv run ruff check .
```

Esperado: notification **46 passed** (36 + 10), auth-users **73 passed**
(72 + 1).

- [ ] **Passo 8: commit**

Dois commits:

```bash
git add back-end/notification-service/app/models/staff.py \
        back-end/notification-service/app/services/destinatarios.py \
        back-end/notification-service/app/events/consumer.py \
        back-end/notification-service/alembic/versions/d4c5b6a7e8f9_staff_registry.py \
        back-end/notification-service/tests/
git diff --staged
git commit -m "$(cat <<'MSG'
feat(notification): address each order transition to the profile that needs it

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"

git add back-end/auth-users-service/app/seeds/demo_accounts.py \
        back-end/auth-users-service/tests/test_demo_accounts.py
git diff --staged
git commit -m "$(cat <<'MSG'
fix(auth): publish staff.created for the bootstrap admin account

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 9: O e-mail da credencial — o backend volta a enviar e-mail

Primeiro envio de e-mail do backend desde a spec A, que apagou o remetente
junto com o monolito. Ver D1.

**Files:**
- Criar: `back-end/notification-service/app/services/email.py`
- Modificar: `back-end/notification-service/app/config.py`
- Modificar: `back-end/notification-service/app/events/consumer.py`
- Modificar: `back-end/notification-service/pyproject.toml` (httpx sai de dev)
- Modificar: `back-end/notification-service/.env.example`
- Modificar: `back-end/.env.example`
- Modificar: `back-end/docker-compose.yml`
- Criar: `back-end/notification-service/tests/test_email.py`
- Modificar: `back-end/notification-service/tests/conftest.py` (bloqueio de rede)

**Interfaces:**

```python
# app/config.py
    email_backend: str = "console"        # console | resend
    resend_api_key: str = ""
    email_from: str = "no-reply@svemlab.com"

# app/services/email.py
class EmailNaoEnviadoError(Exception): ...

async def enviar_email(*, para: str, assunto: str, texto: str) -> None
    """Despacha pelo backend configurado. `console` escreve UMA linha de log
    com destinatário e assunto — nunca o corpo, que carrega a senha."""
```

**Regras de segurança desta task:**

- O corpo do e-mail **nunca** é logado, em nenhum dos dois backends: ele contém
  a senha do carregamento.
- A senha **não** vira linha em `notificacoes`. O handler de
  `shipment.created` manda o e-mail e para por aí.
- `RESEND_API_KEY` não tem default com valor: vazio significa "backend
  console", e o backend `resend` com chave vazia levanta na inicialização do
  envio, não silenciosamente.
- A suíte não fala com a rede: `tests/conftest.py` do notification ganha o
  mesmo bloqueio de `httpx.AsyncHTTPTransport` que o commerce já tem, copiado
  de lá com a mesma docstring adaptada.

- [ ] **Passo 1: escrever os testes que falham**

Criar `tests/test_email.py`:

```python
import httpx
import pytest

from app.services.email import EmailNaoEnviadoError, enviar_email


async def test_the_console_backend_never_logs_the_body(monkeypatch, caplog):
    """O corpo carrega a senha do carregamento. Regra 5 do CLAUDE.md."""
    monkeypatch.setattr("app.services.email.settings.email_backend", "console")

    await enviar_email(
        para="operacao@expresso.example",
        assunto="Carregamento #12",
        texto="Código ABCD2345, senha SEGREDO123",
    )

    registrado = "\n".join(r.message for r in caplog.records)
    assert "operacao@expresso.example" in registrado
    assert "SEGREDO123" not in registrado


async def test_the_resend_backend_posts_to_the_api(monkeypatch):
    chamadas = []

    async def _fake_post(self, url, **kwargs):
        chamadas.append((url, kwargs))
        return httpx.Response(200, json={"id": "re_1"})

    monkeypatch.setattr("app.services.email.settings.email_backend", "resend")
    monkeypatch.setattr("app.services.email.settings.resend_api_key", "re_test")
    monkeypatch.setattr(httpx.AsyncClient, "post", _fake_post)

    await enviar_email(para="a@b.example", assunto="Assunto", texto="Corpo")

    url, kwargs = chamadas[0]
    assert url == "https://api.resend.com/emails"
    assert kwargs["headers"]["Authorization"] == "Bearer re_test"
    assert kwargs["json"]["from"] == "no-reply@svemlab.com"


async def test_the_resend_backend_refuses_to_run_without_a_key(monkeypatch):
    monkeypatch.setattr("app.services.email.settings.email_backend", "resend")
    monkeypatch.setattr("app.services.email.settings.resend_api_key", "")

    with pytest.raises(EmailNaoEnviadoError):
        await enviar_email(para="a@b.example", assunto="x", texto="y")
```

E, em `tests/test_consumer.py`:

```python
async def test_shipment_created_emails_the_carrier(
    db_session, test_session_factory, monkeypatch
):
    enviados = []

    async def _capturar(*, para, assunto, texto):
        enviados.append((para, assunto, texto))

    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    monkeypatch.setattr(consumer_module, "enviar_email", _capturar)

    await consumer_module.handle_shipment_created(
        fake_message(
            {
                "carregamento_id": 12,
                "codigo": "ABCD2345",
                "senha": "SEGREDO12345",
                "transportadora_id": 3,
                "transportadora_nome": "Expresso Cajamar",
                "transportadora_email": "operacao@expresso.example",
            }
        )
    )

    para, assunto, texto = enviados[0]
    assert para == "operacao@expresso.example"
    assert "ABCD2345" in texto and "SEGREDO12345" in texto


async def test_shipment_created_does_not_store_the_password(
    db_session, test_session_factory, monkeypatch
):
    """A senha vive no e-mail e em lugar nenhum mais. Uma linha de
    `notificacoes` é lida por rota autenticada de USUÁRIO — a transportadora
    não é usuária deste sistema, e a senha não tem por que ficar no banco."""
    monkeypatch.setattr(consumer_module, "async_session", test_session_factory)
    monkeypatch.setattr(consumer_module, "enviar_email", _noop_email)

    await consumer_module.handle_shipment_created(fake_message(_payload_shipment()))

    assert (await db_session.execute(select(Notificacao))).scalars().all() == []
```

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd back-end/notification-service && uv run pytest tests/test_email.py -q
```

- [ ] **Passo 3: config e dependência**

Em `app/config.py`:

```python
    # E-mail. O backend volta a existir nesta spec (spec C, D1): a spec A
    # apagou o remetente junto com o monolito.
    #
    # `console` é o default e não fala com a rede — é o que roda em
    # desenvolvimento e na suíte. `resend` exige `RESEND_API_KEY`; o domínio
    # `svemlab.com` está verificado no Resend (MX `send`, DKIM
    # `resend._domainkey`, SPF `send`), e `no-reply@` não precisa de caixa
    # postal real por ser só de saída.
    email_backend: str = "console"
    resend_api_key: str = ""
    email_from: str = "no-reply@svemlab.com"
```

Em `pyproject.toml`, `httpx` sai de `[dependency-groups] dev` e entra em
`[project] dependencies` (o serviço passa a falar HTTP em produção):

```toml
    "httpx>=0.28.0",
```

- [ ] **Passo 4: o adapter**

Criar `app/services/email.py`:

```python
"""Envio de e-mail — duas implementações atrás de uma função.

`console` escreve no log que um e-mail SERIA enviado, com destinatário e
assunto e **sem o corpo**; `resend` faz um POST na API do Resend. O corpo fica
de fora do log nos dois porque ele carrega a senha do carregamento (regra 5 do
CLAUDE.md).

Trocar de provedor é acrescentar um ramo aqui. Nenhum chamador conhece o
Resend.
"""

import httpx
from loguru import logger

from app.config import settings

_RESEND_URL = "https://api.resend.com/emails"
_TIMEOUT_SEGUNDOS = 10.0


class EmailNaoEnviadoError(Exception):
    """O envio não aconteceu: backend desconhecido, chave ausente, ou o
    provedor recusou. Quem chama decide o que fazer — no consumer, deixar a
    exceção subir manda a mensagem para a dead-letter exchange, que é onde ela
    deve ficar até alguém drenar.

    Sufixo `Error` por N818.
    """


async def enviar_email(*, para: str, assunto: str, texto: str) -> None:
    if settings.email_backend == "console":
        logger.info("email[console]: para={} assunto={}", para, assunto)
        return

    if settings.email_backend != "resend":
        raise EmailNaoEnviadoError(f"backend de e-mail desconhecido: {settings.email_backend}")

    if not settings.resend_api_key:
        raise EmailNaoEnviadoError("RESEND_API_KEY não configurada")

    async with httpx.AsyncClient(timeout=_TIMEOUT_SEGUNDOS) as client:
        resposta = await client.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.email_from,
                "to": [para],
                "subject": assunto,
                "text": texto,
            },
        )
    if resposta.status_code >= 400:
        # Sem o corpo da resposta no log: a mensagem de erro do provedor pode
        # ecoar o payload, e o payload tem a senha.
        raise EmailNaoEnviadoError(f"provedor recusou o envio ({resposta.status_code})")
    logger.info("email[resend]: enviado para={} assunto={}", para, assunto)
```

- [ ] **Passo 5: o handler e o binding**

Em `app/events/consumer.py`:

```python
async def handle_shipment_created(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """Manda a credencial do carregamento para a transportadora.

    NÃO grava linha de notificação: a transportadora não é usuária deste
    sistema, e a senha não tem por que existir no banco depois do envio. O
    `Carregamento` guarda só o hash (commerce, task 4).
    """
    async with message.process():
        payload = json.loads(message.body)
        texto = (
            f"Carregamento #{payload['carregamento_id']} liberado para "
            f"{payload['transportadora_nome']}.\n\n"
            f"Código: {payload['codigo']}\n"
            f"Senha: {payload['senha']}\n\n"
            "O entregador entra no app com este código, esta senha, o nome e um "
            "contato. O acesso vale apenas para os pedidos deste carregamento."
        )
        await enviar_email(
            para=payload["transportadora_email"],
            assunto=f"Carregamento #{payload['carregamento_id']} — código de acesso",
            texto=texto,
        )
```

e o binding:

```python
    ("notification.shipment_created", "shipment.created", handle_shipment_created),
```

- [ ] **Passo 6: bloqueio de rede na suíte**

Em `back-end/notification-service/tests/conftest.py`, copiar a fixture
`_block_real_network_calls` de `back-end/commerce-service/tests/conftest.py`,
adaptando a docstring para dizer o que ela protege aqui: **nenhum teste pode
mandar e-mail de verdade**. O teste do backend `resend` remenda
`httpx.AsyncClient.post` diretamente, então não passa pelo transporte
bloqueado.

- [ ] **Passo 7: `.env.example` e compose**

Em `back-end/notification-service/.env.example`, na seção de opcionais:

```
# E-mail (spec C). `console` é o default e não fala com a rede.
# EMAIL_BACKEND=resend
# RESEND_API_KEY=re_xxx
# EMAIL_FROM=no-reply@svemlab.com
```

O mesmo bloco em `back-end/.env.example`, porque o compose carrega o `.env` da
raiz do back-end via `env_file`. No `docker-compose.yml`, no bloco
`notification-service`:

```yaml
      EMAIL_BACKEND: ${EMAIL_BACKEND:-console}
      RESEND_API_KEY: ${RESEND_API_KEY:-}
      EMAIL_FROM: ${EMAIL_FROM:-no-reply@svemlab.com}
```

Nunca edite o `.env` do usuário.

- [ ] **Passo 8: rodar tudo**

```bash
cd back-end/notification-service && uv sync && uv run pytest -q && uv run ruff check .
docker compose -f ../docker-compose.yml config --quiet
```

Esperado: **51 passed** (46 + 5).

- [ ] **Passo 9: commit**

```bash
git add back-end/notification-service/ back-end/.env.example back-end/docker-compose.yml
git diff --staged
git commit -m "$(cat <<'MSG'
feat(notification): email the shipment credential to the carrier

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 10: Flutter — múltiplas sessões guardadas, atrás de uma flag de compilação

Recurso de **demonstração**, isolado: guardar quatro sessões ativas num aparelho
é conveniência de apresentação, não postura de segurança para um app de
estudante. A compilação padrão não o inclui.

**Files:**
- Criar: `front-end-flutter/lib/core/session/session_manager.dart`
- Criar: `front-end-flutter/lib/core/session/session_switcher.dart`
- Modificar: `front-end-flutter/lib/features/auth/presentation/login_screen.dart`
- Criar: `front-end-flutter/test/core/session/session_manager_test.dart`
- Modificar: `Makefile` (alvo `front-demo`)

**Interfaces:**

```dart
// lib/core/session/session_manager.dart
class SessaoGuardada {
  const SessaoGuardada({required this.papel, required this.nome});
  final String papel;   // student | separador | entregador | admin | carregamento
  final String nome;
}

class SessionManager {
  SessionManager({FlutterSecureStorage? storage, TokenStore? tokenStore});

  /// `--dart-define=DEMO_MULTI_SESSAO=true`. Mesmo padrão de
  /// `demoItensMock` (`features/logistics/data/demo_itens.dart`): constante de
  /// compilação, então o código morto some no tree-shaking do build normal.
  static const bool habilitado = bool.fromEnvironment('DEMO_MULTI_SESSAO');

  Future<void> guardarSessaoAtual({required String papel, required String nome});
  Future<List<SessaoGuardada>> listar();
  Future<bool> ativar(String papel);   // false se não havia sessão guardada
  Future<void> remover(String papel);
  Future<void> limpar();
}
```

O `SessionManager` guarda um único valor JSON na `flutter_secure_storage`
(chave `demo_sessions`): `papel -> {access, refresh, nome}`. Ativar copia o par
para o `TokenStore`, que é de onde `appAuthClient` lê — nada mais no app
precisa saber que existem várias sessões.

- [ ] **Passo 1: escrever o teste que falha**

Criar `test/core/session/session_manager_test.dart`:

```dart
import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/core/session/session_manager.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeTokenStore extends TokenStore {
  String? access;
  String? refresh;

  @override
  Future<void> save({required String accessToken, required String refreshToken}) async {
    access = accessToken;
    refresh = refreshToken;
  }

  @override
  Future<String?> readAccessToken() async => access;

  @override
  Future<String?> readRefreshToken() async => refresh;

  @override
  Future<void> clear() async {
    access = null;
    refresh = null;
  }
}

/// Armazenamento em memória com a mesma superfície que o manager usa.
class _MemoriaSegura implements SecureStorageLike {
  final Map<String, String> _valores = {};

  @override
  Future<String?> read({required String key}) async => _valores[key];

  @override
  Future<void> write({required String key, required String? value}) async {
    if (value == null) {
      _valores.remove(key);
    } else {
      _valores[key] = value;
    }
  }

  @override
  Future<void> delete({required String key}) async => _valores.remove(key);
}

void main() {
  late _FakeTokenStore tokenStore;
  late SessionManager manager;

  setUp(() {
    tokenStore = _FakeTokenStore();
    manager = SessionManager(storage: _MemoriaSegura(), tokenStore: tokenStore);
  });

  test('guarda a sessão ativa sob o papel', () async {
    await tokenStore.save(accessToken: 'a1', refreshToken: 'r1');

    await manager.guardarSessaoAtual(papel: 'separador', nome: 'Separador Demo');

    final sessoes = await manager.listar();
    expect(sessoes.map((s) => s.papel), ['separador']);
    expect(sessoes.single.nome, 'Separador Demo');
  });

  test('trocar de sessão preserva as demais', () async {
    await tokenStore.save(accessToken: 'a-aluno', refreshToken: 'r-aluno');
    await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');
    await tokenStore.save(accessToken: 'a-sep', refreshToken: 'r-sep');
    await manager.guardarSessaoAtual(papel: 'separador', nome: 'Separador Demo');

    final trocou = await manager.ativar('student');

    expect(trocou, isTrue);
    expect(tokenStore.access, 'a-aluno');
    // A sessão de onde saímos continua guardada — é o ponto do recurso.
    expect((await manager.listar()).map((s) => s.papel), containsAll(['student', 'separador']));
  });

  test('ativar um papel sem sessão guardada não derruba a sessão atual', () async {
    await tokenStore.save(accessToken: 'a-aluno', refreshToken: 'r-aluno');
    await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');

    final trocou = await manager.ativar('admin');

    expect(trocou, isFalse);
    expect(tokenStore.access, 'a-aluno');
  });

  test('remover apaga só a sessão pedida', () async {
    await tokenStore.save(accessToken: 'a1', refreshToken: 'r1');
    await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');
    await manager.guardarSessaoAtual(papel: 'admin', nome: 'Admin Demo');

    await manager.remover('admin');

    expect((await manager.listar()).map((s) => s.papel), ['student']);
  });

  test('um valor corrompido no armazenamento não derruba o app', () async {
    final memoria = _MemoriaSegura();
    await memoria.write(key: 'demo_sessions', value: 'isto não é json');
    manager = SessionManager(storage: memoria, tokenStore: tokenStore);

    expect(await manager.listar(), isEmpty);
  });
}
```

`SecureStorageLike` é uma interface mínima declarada no próprio
`session_manager.dart` (`read`/`write`/`delete`), com `FlutterSecureStorage`
satisfazendo-a por composição — é o que torna o teste possível sem plugin de
plataforma. `TokenStore` já é sobrescrevível assim nos testes que existem
(`test/core/network/auth_http_client_test.dart::_FakeTokenStore`).

- [ ] **Passo 2: rodar e ver falhar**

```bash
cd front-end-flutter && flutter test test/core/session/session_manager_test.dart
```

- [ ] **Passo 3: implementar o manager**

`lib/core/session/session_manager.dart`, com a docstring dizendo o que é e o
que não é:

```dart
/// Guarda várias sessões (uma por papel) e troca a ativa sem redigitar senha.
///
/// RECURSO DE DEMONSTRAÇÃO. A apresentação é conduzida por uma pessoa
/// alternando entre os quatro perfis, e redigitar senha a cada troca é o que
/// esta classe evita. Guardar quatro sessões ativas num aparelho não é postura
/// de segurança para um app de estudante — por isso [habilitado] é uma
/// constante de compilação, falsa em qualquer build normal, e todo o caminho
/// que a usa some no tree-shaking. Mesmo padrão de `demoItensMock`.
```

- [ ] **Passo 4: ligar no login**

Em `login_screen.dart`, dentro de `_redirecionarPorPapel`, antes do
`Navigator.pushReplacement...`:

```dart
    if (SessionManager.habilitado && role != null) {
      await SessionManager().guardarSessaoAtual(papel: role, nome: nome ?? role);
    }
```

e, no `_Header` da tela, o seletor (`SessionSwitcher`), que só se desenha
quando `SessionManager.habilitado` é verdadeiro e há pelo menos uma sessão
guardada. Ao escolher um papel, o switcher chama `ativar` e reusa **a mesma**
função de roteamento por papel que o login já tem — extraia
`_redirecionarPorPapel` para uma função de nível superior
(`Future<void> irParaTelaDoPapel(BuildContext, String?)` em
`lib/core/session/session_switcher.dart`) e faça o login chamá-la, em vez de
duplicar o `switch`.

- [ ] **Passo 5: um alvo de Makefile para a apresentação**

```make
front-demo: ## Run the Flutter app with the presentation-only demo flags
	@test -n "$(HOST_IP)" || { echo "Could not auto-detect the host LAN IP. Run: make front-demo HOST_IP=192.168.x.y"; exit 1; }
	cd $(FRONT_DIR) && $(FLUTTER) run \
		--dart-define=API_BASE_URL=$(HOST_API_URL) \
		--dart-define=DEMO_MULTI_SESSAO=true
```

Acrescentar `front-demo` à linha `.PHONY` da seção de frontend.

- [ ] **Passo 6: rodar e ver passar**

```bash
cd front-end-flutter && flutter test && flutter analyze lib/
```

Esperado: **184 passed** (179 + 5); `analyze` continua com **6** avisos `info`.

- [ ] **Passo 7: commit**

```bash
git add front-end-flutter/lib/core/session/ \
        front-end-flutter/lib/features/auth/presentation/login_screen.dart \
        front-end-flutter/test/core/session/ Makefile
git diff --staged
git commit -m "$(cat <<'MSG'
feat(app): keep one session per role behind a demo compile flag

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 11: Flutter — o entregador entra por código, e vê só o seu carregamento

**Files:**
- Modificar: `front-end-flutter/lib/features/logistics/data/logistics_api.dart`
- Criar: `front-end-flutter/lib/features/logistics/presentation/shipment_login_screen.dart`
- Modificar: `front-end-flutter/lib/features/logistics/presentation/delivery_queue_screen.dart`
- Modificar: `front-end-flutter/lib/features/auth/presentation/login_screen.dart`
- Modificar: `front-end-flutter/lib/main.dart` (rota `/shipment-login`)
- Criar: `front-end-flutter/test/features/logistics/shipment_login_test.dart`

**Interfaces:**

```dart
// logistics_api.dart
class SessaoCarregamento {
  const SessaoCarregamento({
    required this.accessToken,
    required this.carregamentoId,
    required this.codigo,
    required this.origemRotulo,
  });
}

Future<SessaoCarregamento> entrarNoCarregamento({
  required String codigo,
  required String senha,
  required String nome,
  required String contato,
});
```

`entrarNoCarregamento` faz `POST /shipments/login` **sem** header de
autorização (é o ponto de entrada de quem não tem credencial), grava o token
no `TokenStore` (`save`, com o refresh vazio — o carregamento não tem refresh)
e devolve a sessão.

**Cuidado com o `AuthHttpClient`:** ele tenta refresh no 401 e, falhando,
chama `onSessionExpired`, que joga para `/login`. Um token de carregamento não
tem refresh; quando ele expirar (12 h), o app vai cair na tela de login normal.
Isso é aceitável e é o comportamento certo — a sessão do lote acabou —, mas a
tela de login precisa oferecer o caminho de volta: um botão **"Entrar com
código de carregamento"** que leva a `/shipment-login`. Sem esse botão o
entregador fica preso num formulário de e-mail e senha que ele não tem.

- [ ] **Passo 1: escrever os testes que falham**

Criar `test/features/logistics/shipment_login_test.dart`:

```dart
void main() {
  test('entra com código e guarda o token', () async {
    final client = MockClient((req) async {
      expect(req.url.path, endsWith('/shipments/login'));
      expect(req.headers['Authorization'], isNull);
      expect(jsonDecode(req.body)['codigo'], 'ABCD2345');
      return http.Response(
        jsonEncode({
          'access_token': 'tok',
          'token_type': 'bearer',
          'carregamento_id': 12,
          'codigo': 'ABCD2345',
          'origem_rotulo': 'Cajamar, SP',
        }),
        200,
      );
    });
    final store = _FakeTokenStore();
    final api = LogisticsApi(client: client, tokenStore: store);

    final sessao = await api.entrarNoCarregamento(
      codigo: 'ABCD2345', senha: 'SEGREDO12345', nome: 'Maria', contato: '11999990000',
    );

    expect(sessao.carregamentoId, 12);
    expect(store.access, 'tok');
  });

  test('credencial errada vira mensagem legível, não código HTTP', () async {
    final client = MockClient(
      (_) async => http.Response(jsonEncode({'detail': 'Código ou senha inválidos'}), 401),
    );
    final api = LogisticsApi(client: client, tokenStore: _FakeTokenStore());

    expect(
      () => api.entrarNoCarregamento(
        codigo: 'X', senha: 'Y', nome: 'Maria', contato: '11999990000',
      ),
      throwsA(isA<LogisticsException>().having((e) => e.message, 'message', contains('inválidos'))),
    );
  });

  testWidgets('a tela de login por código monta e valida os quatro campos', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ShipmentLoginScreen()));

    await tester.tap(find.text('Entrar'));
    await tester.pump();

    expect(find.text('Informe o código'), findsOneWidget);
    expect(find.text('Informe a senha'), findsOneWidget);
    expect(find.text('Informe seu nome'), findsOneWidget);
    expect(find.text('Informe um contato'), findsOneWidget);
  });

  testWidgets('a tela de login normal oferece o caminho do carregamento', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: const LoginScreen(),
      routes: {'/shipment-login': (_) => const ShipmentLoginScreen()},
    ));

    expect(find.text('Entrar com código de carregamento'), findsOneWidget);
  });
}
```

- [ ] **Passo 2 a 5: implementar**

- `entrarNoCarregamento` no `LogisticsApi`, reusando `_mensagemErro` (que já lê
  `detail`) em vez de escrever outro mapeamento de erro.
- `ShipmentLoginScreen`: quatro campos (código, senha, nome, contato), com
  `maxLength` batendo com o schema (12/128/120/120), erro em caixa vermelha no
  mesmo estilo de `login_screen.dart`, e navegação para `EntregadorFilaScreen`
  no sucesso.
- `EntregadorFilaScreen`: quando a sessão é de carregamento, o título mostra
  `codigo` e `origem_rotulo`, e a lista vem de `/delivery/queue` — que, com
  token de lote, já devolve só os pedidos do lote (task 5). Nenhuma lógica de
  filtro no cliente: **nada inventado no cliente** é a fronteira que a spec
  declara.
- Sino de notificações no `AppBar` das telas de separação e entrega (D13),
  navegando para `/notifications`.
- Rota `/shipment-login` no `main.dart` e o botão na `LoginScreen`.

- [ ] **Passo 6: rodar**

```bash
cd front-end-flutter && flutter test && flutter analyze lib/
```

Esperado: **188 passed** (184 + 4), 6 avisos `info`.

- [ ] **Passo 7: commit**

```bash
git add front-end-flutter/lib/features/logistics/ \
        front-end-flutter/lib/features/auth/presentation/login_screen.dart \
        front-end-flutter/lib/main.dart \
        front-end-flutter/test/features/logistics/shipment_login_test.dart
git diff --staged
git commit -m "$(cat <<'MSG'
feat(app): let a courier sign in with a shipment code

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 12: Flutter — a posição andando no mapa do comprador

**Files:**
- Modificar: `front-end-flutter/lib/features/order_tracking/domain/order_model.dart`
- Modificar: `front-end-flutter/lib/features/order_tracking/presentation/route_provider.dart`
- Modificar: `front-end-flutter/lib/features/order_tracking/presentation/order_map_screen.dart`
- Modificar: `front-end-flutter/test/features/order_tracking/order_provider_test.dart`
- Criar: `front-end-flutter/test/features/order_tracking/courier_position_test.dart`

**Interfaces:**

```dart
// order_model.dart
class CourierPosition {
  const CourierPosition({required this.latitude, required this.longitude, required this.updatedAt});
  final double latitude;
  final double longitude;
  final DateTime updatedAt;
  static CourierPosition? fromJson(Map<String, dynamic>? json);
  LatLng get latLng;
}

class OrderModel {
  // ... campos atuais ...
  final CourierPosition? courierPosition;
}

// route_provider.dart
class RouteProvider extends ChangeNotifier {
  RouteProvider({RouteService? service, OrderService? orderService, Duration? positionInterval});
  CourierPosition? get courierPosition;
  Future<void> load(String orderId);   // carrega a rota e começa a seguir a posição
}
```

`RouteProvider` passa a fazer duas coisas: a rota (uma vez, como hoje) e a
posição (a cada dez segundos, via `OrderService.fetchTracking` — a mesma rota
que a tela de rastreio já consulta). Dez segundos é o que a spec pede; o
`OrderProvider` do rastreio continua com os 8 s dele, e os dois não se
coordenam de propósito: são telas diferentes, e uma não pode travar a outra.

O polling **para** quando o pedido é entregue ou cancelado, exatamente como
`OrderProvider._startPolling` já faz — reuse o critério (`isDelivered`,
`isCancelled`), não invente outro.

- [ ] **Passo 1: escrever os testes que falham**

`test/features/order_tracking/courier_position_test.dart`:

```dart
void main() {
  test('posição ausente no payload vira null, não exceção', () {
    final model = OrderModel.fromJson(_payloadSemPosicao());
    expect(model.courierPosition, isNull);
  });

  test('posição presente é lida com latitude e longitude', () {
    final model = OrderModel.fromJson({
      ..._payloadSemPosicao(),
      'courier_position': {
        'latitude': -23.45,
        'longitude': -46.7,
        'updated_at': '2026-09-09T12:00:00Z',
      },
    });
    expect(model.courierPosition!.latitude, -23.45);
  });

  test('o provider do mapa segue a posição enquanto o pedido anda', () async {
    var chamadas = 0;
    final provider = RouteProvider(
      service: _FakeRouteService(),
      orderService: _FakeOrderService(() {
        chamadas++;
        return _pedidoEmTransitoCom(latitude: -23.4 - chamadas * 0.01);
      }),
      positionInterval: const Duration(milliseconds: 10),
    );

    await provider.load('pedido-1');
    await Future<void>.delayed(const Duration(milliseconds: 35));

    expect(chamadas, greaterThan(1));
    expect(provider.courierPosition!.latitude, lessThan(-23.4));
    provider.dispose();
  });

  test('o provider para de seguir quando o pedido é entregue', () async {
    final provider = RouteProvider(
      service: _FakeRouteService(),
      orderService: _FakeOrderService(() => _pedidoEntregue()),
      positionInterval: const Duration(milliseconds: 10),
    );

    await provider.load('pedido-1');
    await Future<void>.delayed(const Duration(milliseconds: 40));
    final chamadasApos = _FakeOrderService.chamadas;
    await Future<void>.delayed(const Duration(milliseconds: 40));

    expect(_FakeOrderService.chamadas, chamadasApos);
    provider.dispose();
  });

  test('falha de rede no polling preserva a última posição boa', () async {
    // ... mesma forma do `_poll` do OrderProvider: erro não derruba a tela.
  });
}
```

- [ ] **Passo 2 a 4: implementar**

- `CourierPosition` no `order_model.dart`, com `fromJson` tolerante (chave
  ausente, valores não numéricos ⇒ `null`), no mesmo estilo defensivo que o
  arquivo já usa (`(json['x'] as num?)?.toDouble() ?? 0`).
- `RouteProvider` com o timer, o `dispose` cancelando, e o mesmo tratamento
  silencioso de falha do `OrderProvider._poll`.
- `order_map_screen.dart`: um terceiro `Marker` (`MarkerId('courier')`),
  desenhado só quando `courierPosition != null`, com o ícone de caminhão que
  `marker_icons.dart` já produz; a câmera continua enquadrando origem e
  destino, sem perseguir o marcador (perseguir tiraria o destino da tela).

- [ ] **Passo 5: rodar**

```bash
cd front-end-flutter && flutter test && flutter analyze lib/
```

Esperado: **193 passed** (188 + 5).

- [ ] **Passo 6: commit**

```bash
git add front-end-flutter/lib/features/order_tracking/ \
        front-end-flutter/test/features/order_tracking/
git diff --staged
git commit -m "$(cat <<'MSG'
feat(app): show the courier position moving on the order map

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 13: Flutter — a aba de carregamentos do admin

Ver D2: esta é a tela que a apresentação usa; a do Angular (task 14) é a mesma
API vista do painel.

**Files:**
- Modificar: `front-end-flutter/lib/features/admin/data/admin_api.dart`
- Criar: `front-end-flutter/lib/features/admin/domain/shipment.dart`
- Criar: `front-end-flutter/lib/features/admin/presentation/admin_shipments_screen.dart`
- Modificar: `front-end-flutter/lib/features/admin/presentation/widgets/admin_scaffold.dart`
- Criar: `front-end-flutter/test/features/admin/admin_shipments_test.dart`

**Interfaces:**

```dart
// admin_api.dart
Future<List<Shipment>> fetchCarregamentos();
Future<ShipmentCriado> criarCarregamento(int transportadoraId);
Future<void> atribuirPedido({required int carregamentoId, required String pedidoId});
Future<List<Pedido>> fetchPedidosDoCarregamento(int carregamentoId);
Future<List<Carrier>> fetchTransportadoras();   // GET /carriers, admin-only
```

`ShipmentCriado` carrega `codigo` **e** `senha`, e a tela a mostra **uma vez**,
num cartão copiável, com a frase: *"A transportadora também recebeu estes dados
por e-mail. Esta senha não pode ser consultada depois."* Isso não substitui o
e-mail (D1) — é a rede de segurança de quando ele demora, e é o que salva a
apresentação sem acesso à caixa postal.

`AdminTab` passa de duas para três abas (`dashboard`, `painel`, `carregamentos`).

- [ ] **Passo 1: escrever os testes que falham**

```dart
testWidgets('a tela lista carregamentos e não mostra senha na listagem', ...);
testWidgets('criar carregamento mostra código e senha uma vez', ...);
testWidgets('atribuir pedido de outra origem mostra a mensagem do servidor', (tester) async {
  // 409 com `detail` do servidor: a mensagem é contrato de UI (mesma regra
  // que a spec B fixou para `CarrinhoOrigemMistaError` — o app exibe verbatim,
  // não reescreve).
});
testWidgets('o scaffold do admin tem três abas', ...);
```

- [ ] **Passo 2 a 4: implementar**, seguindo o estilo de
  `admin_analytics_screen.dart` (mesmo `AdminScaffold`, mesmos widgets de
  `admin_widgets.dart`, mesmo tratamento de erro/loading).

- [ ] **Passo 5: rodar**

```bash
cd front-end-flutter && flutter test && flutter analyze lib/
```

Esperado: **197 passed** (193 + 4).

- [ ] **Passo 6: commit**

```bash
git add front-end-flutter/lib/features/admin/ front-end-flutter/test/features/admin/
git diff --staged
git commit -m "$(cat <<'MSG'
feat(app): add the admin shipments tab

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 14: `web-admin` — a página de carregamentos

O painel Angular já tem transportadoras, estoque e ocorrências (spec B). O
carregamento entra ao lado, sobre a mesma API da task 4.

**Files:**
- Criar: `web-admin/src/app/core/models/shipment.model.ts`
- Criar: `web-admin/src/app/core/services/shipment.service.ts`
- Criar: `web-admin/src/app/pages/shipments/shipments.component.{ts,html,scss}`
- Modificar: `web-admin/src/app/app.routes.ts`
- Modificar: `web-admin/src/app/layout/sidebar/sidebar.component.html`

**Interfaces:**

```typescript
// shipment.model.ts
export interface Shipment {
  id: number;
  transportadora_id: number;
  codigo: string;
  origem_rotulo: string;
  origem_lat: string | null;   // string, não number — o backend serializa
  origem_lng: string | null;   // coordenada como texto (mesma regra de ParceiroOut)
  entregador_nome: string | null;
  entregador_contato: string | null;
  aberto_em: string | null;
  criado_em: string;
}

export interface ShipmentCreated extends Shipment {
  senha: string;   // só na resposta da criação
}

export interface ShipmentList { items: Shipment[]; total: number; limit: number; offset: number; }
```

```typescript
// shipment.service.ts — mesmo formato de carrier.service.ts
listShipments(limit = 10, offset = 0): Observable<ShipmentList>
createShipment(carrierId: number): Observable<ShipmentCreated>
assignOrder(shipmentId: number, orderId: string): Observable<void>
listOrders(shipmentId: number): Observable<StaffOrder[]>
```

**A página faz três coisas, e só:**

1. Lista carregamentos, com quem retirou (`entregador_nome`/`aberto_em`) — a
   coluna que responde "esta carga já saiu?".
2. Cria carregamento escolhendo a transportadora, e mostra `codigo` + `senha`
   **uma vez**, num modal, com o aviso de que a senha não é consultável depois.
3. Atribui pedido por id, exibindo **a mensagem do servidor** no 409 de origem
   divergente — verbatim, sem reescrever (mesma regra que o painel já segue
   para os erros da spec B).

- [ ] **Passo 1: modelo e serviço**, copiando a forma de
  `carrier.model.ts`/`carrier.service.ts` (inclusive o escape de `%`/`_` se
  houver busca — esta página não tem busca, então não copie o que não usa).

- [ ] **Passo 2: a página**, no estilo de `pages/carriers/`, com o modal de
  credencial no estilo de `shared/new-carrier-modal/`.

- [ ] **Passo 3: rota e menu**

```typescript
      {
        path: 'carregamentos',
        loadComponent: () =>
          import('./pages/shipments/shipments.component').then(
            m => m.ShipmentsComponent
          )
      },
```

e o item correspondente no `sidebar.component.html`, ao lado de
"Transportadoras".

- [ ] **Passo 4: verificar**

```bash
cd web-admin && npm run build
```

Esperado: exit 0. O `web-admin` **não tem suíte de teste** (decisão D11 da
spec B, que continua valendo — esta spec não cria uma), então a verificação é
o build mais uma passada manual pela página com o backend no ar, registrada no
relatório da task.

- [ ] **Passo 5: commit**

```bash
git add web-admin/src/app/
git diff --staged
git commit -m "$(cat <<'MSG'
feat(web-admin): add the shipments page

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 15: Documentação, costura e verificação final

**Files:**
- Criar: `docs/back-end/order-flow.md`
- Modificar: `docs/back-end/microservices.md`
- Modificar: `docs/smoke-test.md`
- Modificar: `CLAUDE.md` (tabela de documentação)
- Criar: `docs/superpowers/plans/2026-09-09-spec-c-fluxo-de-pedido-ponta-a-ponta-execution-record.md`

- [ ] **Passo 1: `docs/back-end/order-flow.md`**

O documento que faltava: o fluxo inteiro, dos quatro perfis, com o que é real e
o que é simulado. Seções obrigatórias:

1. **A máquina de estados**, com o diagrama dos dez estados internos e do
   desvio de substituição, e a nota de que `AGUARDANDO_SUBSTITUICAO` resolve
   para `SEPARATING` no contrato público.
2. **Carregamento e credencial**: como o admin cria, como a transportadora
   recebe (e-mail, task 9), como o entregador entra, e o que o token de lote
   autoriza — e o que ele **não** autoriza.
3. **Posição — declarada como simulação.** Em texto explícito: *não há
   entregador real nem GPS; a posição é interpolada no backend por
   `app/services/simulador_posicao.py` e gravada pela mesma função que um
   aparelho usaria (`registrar_posicao`). Trocar por GPS real é acrescentar um
   chamador e desligar o job.* A spec exige que o relatório final da entrega
   liste a simulação como tal — é aqui.
4. **Avanço automático**: desligado por padrão, como ligar, por que o prazo é
   longo, e por que ação manual sempre vence.
5. **Push por transição**: a tabela de destinatário da task 8, com a nota de
   que o registro de staff é alimentado por `staff.created`.
6. **O que continua fora**: GPS real, WebSocket, expiração/revogação
   sofisticadas do código, roteirização com várias paradas, cálculo de rota por
   serviço externo além do que já existe.

- [ ] **Passo 2: costurar os documentos que já existem**

- `docs/back-end/microservices.md`: acrescentar `shipments` à tabela de
  roteamento do gateway, e a linha do scheduler do commerce na descrição do
  serviço.
- `docs/smoke-test.md`: o roteiro dos quatro perfis passa a incluir o login do
  entregador por código e a conferência do push em cada perfil. As "lacunas
  conhecidas que não são bug" perdem as que esta spec fechou — releia a lista
  inteira e remova só o que de fato fechou, deixando o resto.
- `CLAUDE.md`: uma linha na tabela de documentação apontando para
  `order-flow.md`.

- [ ] **Passo 3: o registro de execução**

Criar o `-execution-record.md`, no formato do da spec B: o que foi feito task a
task, as divergências entre plano e execução, as contagens medidas no fim, e o
que ficou de dívida.

- [ ] **Passo 4: verificação de costura — os sete pontos do critério de pronto**

Rodar, na ordem, e colar a saída no registro:

```bash
# 1. Backend inteiro
for s in packages/edu-common api-gateway auth-users-service learning-service \
         commerce-service chatbot-service notification-service analytics-service; do
  echo "→ $s"; (cd back-end/$s && uv run pytest -q | tail -1) || exit 1
done

# 2. Lint de tudo que a spec tocou
for s in commerce-service notification-service api-gateway auth-users-service; do
  (cd back-end/$s && uv run ruff check . && uv run ruff format --check .) || exit 1
done

# 3. Flutter
cd front-end-flutter && flutter test && flutter analyze lib/

# 4. Painel
cd ../web-admin && npm run build

# 5. Compose ainda é válido
docker compose -f ../back-end/docker-compose.yml config --quiet
```

Note que o laço acima é `uv run pytest` serviço a serviço — **não**
`make services-test`, que reescreve `uv.lock`.

**Contagens esperadas no fim** (baseline + o que cada task acrescenta):

| Alvo | Baseline | Esperado |
|---|---|---|
| commerce-service | 526 | **580** |
| notification-service | 36 | **51** |
| api-gateway | 37 | **39** |
| auth-users-service | 72 | **73** |
| analytics-service | 34 | **34** (intocado) |
| edu-common | 62 | **62** (intocado) |
| learning-service | — | intocado |
| chatbot-service | — | intocado |
| Flutter | 179 | **197** |
| Flutter analyze | 6 `info` | **6 `info`** |

Divergência para MAIS é aceitável e deve ser explicada no registro; para
MENOS, não: significa que um teste foi perdido no caminho.

- [ ] **Passo 5: os sete critérios de pronto, conferidos à mão**

Com o stack do usuário no ar (sem subir nada você mesmo — peça ao usuário, ou
faça em outro momento), percorrer:

1. Um pedido de `CRIADO` a `ENTREGUE` pelas quatro telas, sem tocar no banco.
2. O desvio de falta de estoque nos dois desfechos.
3. Push no perfil certo em cada transição, visto no aparelho.
4. O mapa do comprador com a posição andando durante o trânsito.
5. O entregador entrando só com código, senha, nome e contato.
6. Com `AVANCO_AUTOMATICO_SEGUNDOS` ausente, nada avança sozinho.
7. As três suítes verdes (passo 4).

Cada item vira uma linha no registro de execução com o resultado observado —
não com a expectativa.

- [ ] **Passo 6: commit**

```bash
git add docs/ CLAUDE.md
git diff --staged
git commit -m "$(cat <<'MSG'
docs: describe the end-to-end order flow and record the spec C execution

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Auto-revisão do plano contra a spec

Feita depois de escrever as quinze tasks, relendo a spec seção a seção.

### Cobertura

| Exigência da spec | Onde é atendida |
|---|---|
| Estado `AGUARDANDO_SUBSTITUICAO` entre `EM_SEPARACAO` e `SEPARADO` | Task 2 (com a divergência D7 declarada) |
| Mapeamento público resolve para `SEPARATING` | Task 2 |
| `/occurrences/stock-shortage` transiciona e anexa sugestões | Task 3 (as sugestões já eram anexadas desde a fase 2) |
| Decisão do comprador volta ao fluxo | Task 3, via `/occurrences/{id}/resolve` (D3) |
| `substituicao_ia.py` degrada sem bloquear | Já existe; nenhuma task o altera, e a task 3 não introduz caminho que dependa dele |
| Carregamento com código, senha, entregador, `aberto_em` | Tasks 1 e 4 |
| Admin cria e atribui pedidos | Task 4 (API), 13 (Flutter) e 14 (Angular) |
| E-mail à transportadora | Task 9 (D1: o envio é escrito do zero) |
| Login no commerce, não no auth | Task 5, com o motivo no docstring e no teste do gateway |
| Token de escopo, `require_role` não serve | Task 5, `ator_entrega` |
| Gateway com `shipments` | Task 4 |
| `posicao_entrega` como série temporal | Tasks 1 e 6 |
| `registrar_posicao` como porta única, simulador como um chamador | Task 6, com teste que chama a porta direto |
| Rastreio devolve a última posição | Task 6 |
| Consulta a cada dez segundos no app | Task 12 |
| Avanço automático desligado por padrão, prazo longo, manual vence | Task 7 |
| Roda como tarefa periódica no padrão do learning | Task 7 (D4) |
| Escreve pela mesma função de transição | Task 7, com teste que afirma o evento publicado |
| Múltiplas sessões atrás de `DEMO_MULTI_SESSAO` | Task 10 |
| `entrega.py` publica evento | **Já publicava** — D5 mostra a medição; o que a spec queria está na task 8 |
| Bindings de `order.created` e `order.occurrence_resolved` | Task 8 |
| Destinatário por transição no notification-service | Task 8 |
| Transição inválida ⇒ 409 com o estado atual | **Divergência**: `transicionar_pedido` responde **400** hoje, com o estado atual na mensagem. Nenhuma task muda isso — trocar para 409 quebraria testes existentes de `/picking` e `/delivery` sem nenhum cliente pedindo. Registrado aqui, e no registro de execução, como divergência deliberada |
| Token de outro lote ⇒ 403, testado com pedido real | Task 5 |
| Código errado com resposta e tempo iguais a senha errada | Task 5 |
| Posição ausente ⇒ 200 com posição nula | Tasks 6 e 12 |
| Push que falha vai para a DLX | Já é assim desde a spec A (`EventConsumer` declara a DLX); as tasks 8 e 9 não põem `except` em handler nenhum, o que preserva a propriedade |
| Testes: máquina, carregamento, posição, avanço, push, Flutter | Tasks 2, 4, 5, 6, 7, 8, 10-13 |
| Critérios de pronto 1-7 | Task 15, passo 5 |

### Fora de escopo, confirmado

GPS real, WebSocket, expiração/revogação sofisticadas do código, roteirização
com várias paradas e cálculo de rota por serviço externo continuam fora — e
nenhuma task acima os introduz pela porta dos fundos. `/orders/{id}/route` e
`previsao_entrega.py` são reaproveitados como estão; a única coisa nova que os
toca é a leitura da coordenada de destino na coleta (D9), que usa a fronteira
que já existia.

### Riscos que o executor deve vigiar

1. **`transicionar_pedido` commita.** Toda task que a chama dentro de outra
   transação precisa saber disso — a task 3 depende dessa ordem, e a 7 também.
   Chamar no meio de uma transação aberta commita o que estava pendente.
2. **O stub de eventos da suíte remenda por chamador.** Um `publish_event` novo
   em um módulo novo precisa da linha correspondente em
   `tests/conftest.py::_stub_publish_event` (task 4, passo 7), senão o teste
   quebra com `EventPublisher not connected` **depois** de já ter escrito no
   banco — sintoma confuso.
3. **Nenhum teste pode falar com a rede.** O commerce já bloqueia; o
   notification passa a bloquear na task 9. Um teste de e-mail mal remendado
   manda e-mail de verdade.
4. **A senha do carregamento não pode vazar** para log, para `notificacoes`,
   nem para qualquer listagem. Três testes a vigiam (tasks 4 e 9); se um deles
   for enfraquecido durante a execução, isso é achado de revisão, não ajuste.
5. **`AGUARDANDO_SUBSTITUICAO` não pode entrar no avanço automático.** A task 7
   tem um teste só para isso, e ele é o que impede a rede de segurança de
   atropelar a decisão do aluno no meio da apresentação.
