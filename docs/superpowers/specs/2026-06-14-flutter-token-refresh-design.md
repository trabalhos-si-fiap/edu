# Flutter — Auto-refresh de token JWT

**Data:** 2026-06-14
**Branch base:** `origin/main`
**Escopo:** front-end (Flutter)

## Problema

O usuário toma `401` após ~15 minutos sem interação. Causa raiz: o backend já
expõe um fluxo de refresh completo (`POST /api/auth/refresh`, access token de
15 min, refresh token de 14 dias, e o login já devolve os dois tokens), mas o
app Flutter **nunca usa o refresh token**.

Estado atual no Flutter:

- O refresh token é salvo no `TokenStore` (secure storage) no login/registro,
  mas nunca é consumido.
- Cada service usa o pacote `http` puro e monta o header `Bearer` na mão
  (`{http.Client? client, TokenStore? tokenStore}` → default `http.Client()`).
- Não há interceptor/middleware: nenhum ponto central trata `401`.
- Quando expira, o request estoura um erro genérico (`"Falha ... (401)"`). Não
  há re-autenticação, retry, nem logout automático.
- Não existe `navigatorKey` no `MaterialApp` (só rotas nomeadas) nem um
  `AuthStore` global.

## Objetivo

Renovar o access token automaticamente e de forma transparente quando expira,
reusando o refresh token. Quando o refresh também falhar (refresh token
expirado/inválido), encerrar a sessão e levar o usuário ao `/login`.

## Decisões de design

1. **Wrapper sobre o pacote `http`** (não migrar para `dio`). Um
   `AuthHttpClient extends http.BaseClient` centraliza injeção do `Bearer` e o
   tratamento de `401`. Sem nova dependência; idiomático ao que o app já usa.
2. **Refresh reativo** (no `401`), não proativo. Nada de parsear `exp` do JWT —
   reagir ao `401` é mais simples e robusto (KISS).
3. **Escopo mínimo / baixo risco.** Não reescrever o `_headers()` de cada
   service. O wrapper sobrescreve o `Authorization` em todo `send`, então o
   token renovado é usado no retry de qualquer forma. Limpeza desse código
   redundante fica para um refactor separado, se desejado (YAGNI).
4. **Redirect via `navigatorKey`.** Adicionar `GlobalKey<NavigatorState>` ao
   `MaterialApp` é a forma padrão do Flutter de navegar fora de um `context`.
5. **Corrigir o bug do logout** (não limpa tokens) junto, por ser o par natural
   deste trabalho.

## Componentes

Todos em `lib/core/network/`.

### `TokenRefresher`

Responsável apenas por trocar o refresh token por um par novo.

- Deps: um `http.Client` **simples** (não o wrapper, para não recursar) +
  `TokenStore` + base URL (`ApiConfig.baseUrl`).
- `Future<bool> refresh()`:
  - lê o refresh token; se `null` → `false`;
  - `POST /auth/refresh` com `{ "refresh_token": <token> }`;
  - em `200`: salva o novo par no `TokenStore` e retorna `true`;
  - qualquer outro status / erro de rede → `false`.

### `AuthHttpClient extends http.BaseClient`

O ponto central de autenticação.

- Deps: inner `http.Client`, `TokenStore`, `TokenRefresher`, callback
  `onSessionExpired`.
- `send(request)`:
  1. injeta `Authorization: Bearer <accessAtual>` (se houver token);
  2. envia pelo inner client;
  3. se a resposta **não** for `401`, devolve como está;
  4. se for `401`: dispara o refresh **single-flight** (um
     `Future<bool>? _refreshing` compartilhado — `401`s concorrentes, como o
     polling da lista de pedidos, compartilham um único refresh);
  5. se o refresh teve sucesso: **clona** a request original com o token novo e
     reenvia **uma única vez**;
  6. se o refresh falhou: `tokenStore.clear()` + `onSessionExpired()`, e devolve
     a resposta `401` original.
- Reenvia no máximo uma vez (se o retry também der `401`, devolve sem loop).
- Clonagem cobre `http.Request` (copia `bodyBytes`, headers, `encoding`,
  `followRedirects`, `maxRedirects`, `persistentConnection`) — que é o que o app
  usa (JSON + GET). Tipos não clonáveis (streamed/multipart) não são reenviados.

### Instância compartilhada + wiring

- Singleton `appAuthClient` em `lib/core/network/app_http.dart` — precisa ser
  **único** para o single-flight funcionar entre services diferentes.
- Trocar o default de cada service de `http.Client()` → `appAuthClient`:
  cart, checkout, product, order_list, notifications, support, addresses,
  order_tracking (order/route). As assinaturas `{http.Client? client}`
  permanecem, então testes que injetam um client/fake seguem funcionando.
- **`AuthApi` fica de fora**: login/registro/reset não têm token, e `401` no
  login significa credencial inválida, não expiração.

### Redirect no fim da sessão

- `GlobalKey<NavigatorState>` adicionado ao `MaterialApp` em `lib/main.dart`.
- `onSessionExpired` do `appAuthClient` usa essa key para
  `pushNamedAndRemoveUntil('/login', ...)`, limpando a pilha de navegação.

### Bug do logout

- `profile_screen.dart`: o logout passa a chamar `TokenStore.clear()` (e
  `SessionStore.clear()`) antes de navegar para `/login`.

## Fluxo de dados

```
Service.get/post  →  appAuthClient.send(req)
                        │  injeta Bearer <access>
                        ▼
                     inner.send(req) ── 200/4xx (≠401) ──▶ retorna
                        │ 401
                        ▼
                     refresh single-flight (TokenRefresher.refresh)
                        ├─ true  → clona req c/ novo Bearer → inner.send → retorna
                        └─ false → TokenStore.clear() + onSessionExpired() → retorna 401
```

## Plano de testes (TDD)

Com `MockClient` (de `package:http/testing.dart`) como inner client e fakes de
`TokenStore`/`TokenRefresher`.

**`AuthHttpClient`:**
- injeta `Authorization: Bearer` a partir do `TokenStore`;
- `401` → refresh com sucesso → retry com o token novo → devolve a resposta do
  retry;
- single-flight: dois `send` concorrentes que recebem `401` disparam **um** só
  refresh;
- refresh falho → `TokenStore.clear()` + `onSessionExpired()` chamados → devolve
  o `401` original;
- resposta não-`401` passa direto, sem tentar refresh;
- retry único: se o retry também der `401`, devolve sem loop infinito.

**`TokenRefresher`:**
- sem refresh token → `false`, sem requisição;
- `200` → salva o novo par no `TokenStore` → `true`;
- não-`200` / erro de rede → `false`.

## Fora de escopo

- Migração para `dio`.
- Refresh proativo baseado em `exp`.
- Revogação de token (jti) no backend.
- Reescrita do `_headers()` dos services (refactor de limpeza separado).
