# Backlog da migração — o que a fase 1 mediu e adiou

Data: 2026-08-04
Estado: fase 1 mergeada na `main` (merge `3128c3a`)

Este documento existe porque o ledger da fase 1 (`.superpowers/sdd/`) era
git-ignored e foi removido junto com o worktree. Tudo abaixo foi **medido
durante a fase 1**, não é especulação — a maior parte veio de mutação
comprovada ou de reprodução ponta a ponta.

O design das fases está em
[2026-08-02-microservices-migration-design.md](2026-08-02-microservices-migration-design.md).
O que existe hoje está em [../../back-end/microservices.md](../back-end/microservices.md).

---

## Fase 2 — paridade do commerce

### Falhas vendorizadas (vieram no import; congeladas pela regra de não reescrever de memória)

**Auto-autorização do gabarito.** Em `learning-service/app/routers/diagnostico.py`,
`POST /diagnostic/answer` seleciona `Questao.id.in_(questao_ids)` sem amarrar ao
`payload.tema_id`, e grava um `DiagnosticoResposta` para qualquer id existente —
que é exatamente a linha que o portão do gabarito checa. **Um aluno vê a resposta
certa de qualquer questão em duas requisições.** Reproduzido ponta a ponta na
revisão final (403 → `POST /answer` com questão de outro tema → 200 → gabarito).
Há um `TODO(fase 2)` no arquivo. O docstring que garantia o contrário foi
corrigido — garantia falsa impede que alguém olhe.

**Preço do pedido vem do cliente.** `commerce-service/app/routers/pedidos.py:32`
usa o `preco_unitario` enviado na requisição para compor o total, e o model
`Produto` nunca é importado ali. O preço nunca é conferido contra o catálogo.

**Dois 500 não autenticados em `POST /auth/register`:** `birth_date` em ISO
escapa do validador (`auth.py:59-61`, `dia, mes, ano = valor.split("/")` levanta
`ValueError` não tratado); e nenhum campo de texto do auth tem `max_length`.

**Read→write não atômicos** (regra 3 do CLAUDE.md): `ocorrencias.py:216-274`,
`admin.py:99-109` (permite estoque negativo, falta `ge=0`), `diagnostico.py:98-128`.

**`/auth/refresh` nunca consulta o banco**, então desativar ou rebaixar um usuário
não tem efeito até o token expirar.

**Leitura de ocorrências é staff-wide** (`ocorrencias.py:146,196`).

**Gateway bufferiza corpo sem limite** (`api-gateway/app/main.py:51`) — comprovado
com um POST não autenticado de 9,6 MB.

**Eventos publicados antes do commit** (`diagnostico.py:184` vs `:209`;
`ocorrencias.py:295` vs `:308`).

**`revision.scheduled` dispara uma vez por subtema** enquanto o handler ignora
`subtema_id` e emite string constante → N notificações idênticas por diagnóstico.
O scheduler nunca escreve `ultima_revisao`, então renotifica todo dia para sempre.

**`nome` e `email` gravados literalmente e para sempre** em `analytics_db.event_log`,
sem caminho de leitura — passivo puro.

### Contrato com o Flutter

A tabela de divergências medidas está no design doc, seção "Divergências de
contrato medidas na fase 1". Os pontos que mais importam:

- O **envelope** é contrato, não formatação: o app faz `jsonDecode(body)['items']`
  e `as String` sobre o `id`. Array puro ou id inteiro levantam `TypeError` que o
  tratamento de erro do app não captura — a tela quebra sem virar mensagem.
- A fase 1 **trocou 404 limpo por quase-acerto**: `products` e `orders` respondem,
  falham por forma (405/422/envelope). Só `cart`, `payment-methods` e `support`
  realmente não existem.
- `"addresses": "auth"` no `SERVICE_MAP` do gateway é **entrada morta** — ninguém
  serve `/addresses`; os dois backends montam `/auth/addresses`.

### Divergência interna de contrato

`/analytics/summary` e `/analytics/deliveries` expressam "sem status" de dois
jeitos: sentinel string (`sem_status`) e `null` JSON (`StatusContagemOut.status:
str | None`). Unificar exige remodelar o contrato público de `/summary`.

### Limpeza de frota

- `edu-common/pyproject.toml` nunca recebeu quatro blocos da Recipe A
  (per-file-ignores, os dois loop scopes, marker `slow`, pytest-cov), e carrega
  dois `# noqa` escritos à mão que só existem por causa disso.
- `api-gateway/pyproject.toml:43` tem `asyncio_default_fixture_loop_scope` sem o
  par obrigatório `asyncio_default_test_loop_scope`.
- `auth-users-service/app/config.py:19` declara `cors_origins` sem nenhum
  middleware; `commerce-service/app/config.py:17` declara `google_maps_api_key`
  que **nada lê**, enquanto o compose injeta a chave real do legacy no container.
- `httpx` declarado como dependência **de runtime** em learning, commerce e
  notification, mas usado só em teste. Mover reescreve lockfile — vale revisar à parte.
- Duas variantes incompatíveis de `Dockerfile.dockerignore` (6 iguais + a do analytics).
- `chatbot-service/pyproject.toml:47-51` whitelista `app.dependencies.requer_papel`,
  que o chatbot não define.
- Três arquivos `test_health.py` que na verdade testam OpenAPI; dois serviços sem
  teste de health.
- `get_current_user_id` / `get_current_student_id` / `get_current_student`: três
  nomes para uma função.
- `/subtopics/{id}/questions` usa `limite` (não `limit`) e não tem `offset`.
- Os cinco serviços com banco usam `sessionmaker(..., class_=AsyncSession)` legado
  em `app/database.py` e `async_sessionmaker` moderno nos conftests.

---

## Fase 3 — paridade de plataforma

**Rate limiting não é apenas frágil, é inexistente.** Nenhum serviço depende de
Redis, embora o Redis suba no compose. Consequências medidas:

- O OTP de 6 dígitos do reset de senha é **força-brutável**, sem teto de tentativas
  nem cooldown.
- `POST /auth/password-reset/request` é um **amplificador de CPU não autenticado**
  (bcrypt custo 12).

Inerte enquanto o Flutter fala com o legacy, mas os serviços novos **estão
publicados em 8101-8106** e alcançáveis da rede do host.

**Idempotência dos consumidores** (regra 10 do CLAUDE.md). Os seis handlers
inserem incondicionalmente; RabbitMQ entrega pelo menos uma vez. A correção não é
local: o `EventPublisher` do `edu-common` não carimba id de mensagem, então não há
nada estável para deduplicar. Deduplicar por chave de negócio seria pior — duas
notificações do mesmo tipo para o mesmo pedido podem ser legítimas.

**Consumidores rejeitam sem requeue e não há DLQ** — portanto **backlog zero no
RabbitMQ não é evidência de saúde**. Mensagem que falha some. Também não há
`set_qos` (prefetch).

**`UNIQUE(aluno_id, token)` em `device_tokens`** permite o mesmo token físico sob
dois alunos. Inofensivo sem push real; relevante no instante em que houver.

**`EventConsumer.bind()` descarta o `ConsumerTag`** de `queue.consume()`, que um
shutdown gracioso precisaria.

---

## Fase 4 — desligamento

**Tempos de token divergem em silêncio.** O `.env` compartilhado é o do legacy:
`ACCESS_TOKEN_EXPIRE_MINUTES=15` e `REFRESH_TOKEN_EXPIRE_DAYS=14` sobrescrevem os
`60` / `7` do `auth-users-service`. Confirmado no container em execução. A
varredura de todos os campos de settings dos 7 serviços contra o env efetivo
mostrou que **essas duas são as únicas mudanças silenciosas de comportamento**.

**`data.order_id` muda de tipo:** o legacy manda UUID em string, o
notification-service manda inteiro. Mesma chave, tipo diferente. Inerte hoje
porque o model do Flutter não lê esse campo.

**O monolito não emite `role` no token** e usa 15min/14d contra 60min/7d do
`edu-common`. Só importa no corte.

**Reconciliação campo a campo é obrigatória.** Apontar o app para o gateway e ver
se responde não basta — ver a seção de contrato da fase 2.

---

## Armadilhas de processo que custaram caro na fase 1

Registradas porque cada uma se repetiu mais de uma vez:

1. **Teste que não pode falhar.** Apareceu em 5 tasks. O antídoto virou constraint:
   todo teste de regressão precisa ser provado quebrando o que ele trava.
2. **Nunca alimentar o teste com a própria constante da implementação.**
3. **Instrumento mentindo.** O `compare_server_default` ausente tornou **todos** os
   sync-checks do Alembic anteriores vazios de significado. O comando do próprio
   plano para "sem `print()`/`utcnow()`" era cego ao `edu-common`. Desconfie do
   instrumento antes de concluir que o código está limpo.
4. **Monkeypatch no módulo que define, não no que importa.** `from x import y`
   cria um nome novo.
5. **`default=` do SQLAlchemy é client-side** e não cria DEFAULT no banco.
6. **Padrões de `.dockerignore` precisam de prefixo `**/`.**
7. **Comentário que era verdade e virou mentira.** Seis casos. Invisível a revisão
   de task única, por construção.
8. **`docker ps` reporta saudável container que não serve.** O watcher `--reload`
   do granian trava se arquivos somem debaixo dele.
