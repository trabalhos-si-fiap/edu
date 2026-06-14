# Painel Admin Web (SQLAdmin) — Design

**Data:** 2026-06-14
**Status:** Aprovado para planejamento
**Módulo:** Backend (`back-end/app/admin/`)

## Objetivo

Prover um painel administrativo web, no estilo do Django admin, que permita
**gerenciar (CRUD completo) e visualizar** os modelos da aplicação a partir do
navegador. O painel é para uso interno da equipe/operadores, não faz parte do
contrato do app mobile.

## Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Escopo de operações | CRUD completo (criar, editar, apagar) |
| Abordagem técnica | **SQLAdmin** (biblioteca, a mais próxima do Django admin) |
| Autenticação | Reusar `auth_users` + flag `is_admin` (sem credenciais novas) |

## Contexto do código existente

- Modular monolith FastAPI + SQLAlchemy 2.0 async + PostgreSQL, servido por Granian.
- `AsyncEngine` já existe em `app/core/database.py` (`engine`).
- Auth já tem: `verify_password`/`hash_password` (bcrypt) e `DUMMY_PASSWORD_HASH`
  para defesa de timing em `app/modules/auth/security.py`; flag `is_admin` no
  model `User` e dependency `require_admin` em `app/modules/auth/dependencies.py`.
- `settings.SECRET_KEY` disponível em `app/core/config.py`.
- ~12 model classes em 9 módulos:
  - `auth.User` (`auth_users`)
  - `addresses` (`auth_addresses`)
  - `products` (`products_products`, `products_reviews`)
  - `cart` (`cart_carts`, `cart_items`)
  - `orders` (`orders_orders`, `orders_items`)
  - `payment_methods` (`payment_methods_methods`)
  - `notifications` (`notifications_device_tokens`, `notifications_notifications`)
  - `support` (`support_messages`)

## Arquitetura

Novo pacote `app/admin/`, tratado como **camada de agregação** (mesmo status do
`bff/`): pode importar models de todos os módulos. Não é um módulo de domínio,
portanto não viola a regra de isolamento entre módulos.

```
app/admin/
  __init__.py
  setup.py        # cria o Admin, instala SessionMiddleware, registra views
  auth.py         # AdminAuth(AuthenticationBackend): login / logout / authenticate
  views.py        # uma ModelView por modelo (~12)
```

Montagem no app existente em `app/main.py`:

```python
from app.admin.setup import setup_admin
setup_admin(app)   # internamente: Admin(app, engine, authentication_backend=AdminAuth(...))
```

Acessível em **`/admin`** (UI HTML server-side do próprio SQLAdmin).

## Componentes

### `app/admin/auth.py` — AdminAuth

`AdminAuth(AuthenticationBackend)` com formulário de login próprio e sessão por
cookie. Três métodos:

- **`login(request)`**: lê e-mail/senha do form. Busca o usuário em `auth_users`
  pelo e-mail. Valida a senha com `verify_password`; quando o e-mail não existe,
  ainda chama `verify_password` contra `DUMMY_PASSWORD_HASH` para manter o tempo
  constante (evita enumeração de usuários). **Só autoriza se `is_admin=True` E
  `is_active=True`.** Em sucesso, grava `user_id` (str) na `request.session`.
- **`authenticate(request)`**: a cada request relê o usuário pelo `user_id` da
  sessão e **revalida `is_admin` e `is_active`**. Não confia apenas na presença
  do cookie — se o admin for rebaixado/desativado, perde o acesso imediatamente.
  Sem sessão válida → redireciona para o login.
- **`logout(request)`**: limpa a sessão.

`SessionMiddleware` instalado em `setup.py` usando `settings.SECRET_KEY`.

### `app/admin/views.py` — ModelViews

Uma `ModelView` por modelo, com colunas, busca e ordenação **explícitas** (nunca
expor todos os campos automaticamente — alinhado com a regra de segurança #6).

**Regra de segurança crítica — campos sensíveis nunca renderizados:**

- `UserAdmin` (`User`): `password_hash` **excluído** de `column_list`,
  `column_details_list` e `form_columns`. Definir/trocar senha é feito via hook
  `on_model_change(data, model, is_created)` que recebe uma senha em texto puro
  (campo virtual do form) e aplica `hash_password` — **nunca** grava hash raw nem
  expõe o existente. Campos editáveis incluem flags (`is_admin`, `is_active`,
  `is_verified`) e dados de perfil.
- `DeviceTokenAdmin` (`notifications_device_tokens`): o valor do token fica
  oculto das listagens (potencialmente sensível); exibir apenas metadados.
- Demais views (`products`, `reviews`, `orders`, `order_items`, `cart`,
  `cart_items`, `addresses`, `payment_methods`, `notifications`,
  `support_messages`): CRUD completo, com `column_list`,
  `column_searchable_list` e `column_sortable_list` definidos caso a caso.

### `app/admin/setup.py`

`setup_admin(app)`:
1. instancia `AdminAuth(secret_key=settings.SECRET_KEY)`;
2. cria `Admin(app, engine, authentication_backend=auth)` usando o `AsyncEngine`
   existente;
3. registra todas as ModelViews via `admin.add_view(...)`.

## Fluxo de dados

1. Operador acessa `/admin` → `authenticate` não acha sessão → redireciona a
   `/admin/login`.
2. Submete e-mail/senha → `login` valida contra `auth_users` + `is_admin` →
   grava `user_id` na sessão.
3. Requests seguintes → `authenticate` relê e revalida o usuário → libera as
   ModelViews.
4. Cada ModelView usa o `AsyncEngine` para listar/criar/editar/apagar registros.

## Segurança (regras do projeto)

- Toda a superfície `/admin` fica atrás do `AuthenticationBackend`; sem sessão
  válida + `is_admin`, não há acesso.
- Nenhum segredo no código: reusa `SECRET_KEY` do ambiente.
- Nenhum campo sensível (`password_hash`, tokens) renderizado em lista, detalhe
  ou formulário.
- Senha sempre via `hash_password`; comparação via bcrypt (constante).
- `authenticate` revalida `is_admin`/`is_active` a cada request (não confia no
  cookie isoladamente).

## Tratamento de erros

- Login inválido (senha errada, e-mail inexistente, não-admin, inativo): retorna
  `False` em `login` → SQLAdmin reexibe o form com erro genérico (sem revelar
  qual condição falhou).
- Sessão expirada/ausente: redirect para login.
- Hook de senha: senha vazia em edição não altera o hash; em criação é
  obrigatória.

## Testes (TDD — escrever antes da implementação)

Estrutura espelha o código: `tests/admin/`.

- `tests/admin/test_auth.py`:
  - login OK com usuário admin ativo;
  - senha incorreta → rejeitado;
  - usuário sem `is_admin` → rejeitado;
  - usuário `is_admin` mas inativo → rejeitado;
  - e-mail inexistente → rejeitado (e exercita o caminho do `DUMMY_PASSWORD_HASH`);
  - `authenticate` rejeita quando o usuário foi rebaixado/desativado após login;
  - `logout` limpa a sessão.
- `tests/admin/test_setup.py`:
  - `/admin` redireciona para login sem sessão;
  - as ~12 ModelViews estão registradas no `Admin`.
- `tests/admin/test_user_view.py`:
  - `password_hash` não está em `column_list`/`form_columns`;
  - `on_model_change` hasheia senha nova na criação;
  - senha vazia na edição preserva o hash existente.

## Dependências

- Adicionar `sqladmin` ao `back-end/pyproject.toml` via `uv add sqladmin`.
- `itsdangerous` (dependência transitiva do `SessionMiddleware` do Starlette) —
  confirmar que vem junto; caso contrário, adicionar.

## Fora de escopo (YAGNI)

- Sem dashboard de métricas/gráficos — apenas CRUD/listagem dos modelos.
- Sem auditoria/log de alterações nesta fase.
- Sem permissões granulares por modelo (todo admin vê tudo); refinar depois se
  necessário.
- Nenhuma mudança no Flutter nem no contrato do app mobile.
```