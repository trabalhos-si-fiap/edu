# Password Reset — Telas Flutter — Design

**Data:** 2026-06-14
**Escopo desta iteração:** Frontend apenas (Flutter). O backend já está pronto e
mergeado na `main` — nenhuma mudança de backend.

## Objetivo

Implementar o fluxo de "esqueci minha senha" no app Flutter, ligado aos endpoints
de password reset que já existem. Dois passos, ambos pré-autenticação:

1. **Esqueci a senha** — usuário informa o e-mail → chama `request` → confirmação
   neutra (anti-enumeração) → navega para a tela de código.
2. **Redefinir senha** — usuário informa código (6 dígitos) + nova senha → chama
   `confirm` → em sucesso volta ao login; em falha mostra mensagem de erro.

Referências:
- Contrato do backend: [`docs/back-end/password-reset.md`](../../back-end/password-reset.md)
- Spec do backend: [`2026-06-14-password-reset-email-design.md`](./2026-06-14-password-reset-email-design.md)
- Convenções Flutter: [`docs/front-end/archtecture.md`](../../front-end/archtecture.md),
  [`docs/front-end/visual_guide.md`](../../front-end/visual_guide.md)

## Contrato do backend (prefixo `/api`)

| Endpoint | Body | Respostas |
|---|---|---|
| `POST /auth/password-reset/request` | `{email}` | `200` sempre · `429` + `Retry-After` · `422` |
| `POST /auth/password-reset/confirm` | `{email, code, new_password}` | `200` · `400` (genérico) · `422` |

- `request` retorna **200 sempre** (anti-enumeração) — nunca revelar se o e-mail existe.
- `confirm` `400` é **genérico**: código errado/expirado/travado ou e-mail inexistente.
- `422`: `code` ≠ 6 dígitos, ou `new_password` < 8 chars / sem caractere especial.

## Decisões-chave (UX, confirmadas no brainstorming)

- **E-mail pré-preenchido e travado** na tela de redefinir: passado via route
  arguments e exibido read-only. Garante que o `confirm` use o mesmo e-mail do
  `request` e evita erro de digitação.
- **Código em 6 caixas separadas** (estilo OTP) com auto-avanço de foco. Extraído
  como widget público testável (`OtpInput`).
- **"Reenviar código" com cooldown visível** (60s): inicia ao entrar na tela
  (um código acabou de ser enviado), botão desabilitado mostrando contagem
  regressiva, reabilita em 0.

---

## 1. Camada de dados — `lib/features/auth/data/auth_api.dart`

Dois métodos novos em `AuthApi`, no mesmo estilo fino de `login`/`register`. **Não**
persistem tokens (fluxo pré-autenticação, sem `_persistAuth`). Mensagens de
`AuthException` em PT-BR por status code.

```dart
Future<void> requestPasswordReset({required String email}) async { ... }
Future<void> confirmPasswordReset({
  required String email,
  required String code,
  required String newPassword,
}) async { ... }
```

**`requestPasswordReset`** → `POST ${ApiConfig.baseUrl}/auth/password-reset/request`,
body `{"email": email}`:

| Status | Ação |
|---|---|
| `200` | retorna normalmente (caller mostra copy neutra) |
| `429` | `AuthException('Muitas tentativas. Tente novamente mais tarde')` |
| `422` | `AuthException('Verifique os dados informados')` |
| outro | `AuthException('Falha ao solicitar o código (código $status)')` |
| erro de conexão | `AuthException('Não foi possível conectar ao servidor')` |

**`confirmPasswordReset`** → `POST ${ApiConfig.baseUrl}/auth/password-reset/confirm`,
body `{"email": email, "code": code, "new_password": newPassword}`:

| Status | Ação |
|---|---|
| `200` | retorna normalmente |
| `400` | `AuthException('Código inválido ou expirado')` |
| `422` | `AuthException('Verifique os dados informados')` |
| outro | `AuthException('Falha ao redefinir a senha (código $status)')` |
| erro de conexão | `AuthException('Não foi possível conectar ao servidor')` |

## 2. Widget OTP — `lib/features/auth/presentation/widgets/otp_input.dart`

A entrada de 6 caixas com auto-avanço é complexa o suficiente (> 50 linhas) para
ser extraída e testada isoladamente, conforme a convenção do projeto (extrair
quando passar de ~50 linhas).

`OtpInput` (widget público, `StatefulWidget`):
- 6 `TextField`s de um dígito, cada um com seu `FocusNode`.
- Digitar um dígito avança o foco para a próxima caixa; backspace numa caixa
  vazia volta para a anterior.
- `FilteringTextInputFormatter.digitsOnly` + `maxLength: 1` por caixa.
- Callback `onChanged(String code)` emite o valor concatenado (0–6 dígitos).
- Estilizado com `AppColors` (mesma paleta dos demais inputs).
- `length` fixo em 6 (constante do widget; sem parametrização especulativa — YAGNI).
- Dispõe todos os controllers e focus nodes em `dispose`.

## 3. Telas

Ambas espelham `login_screen`/`register_screen`: `Container` com
`AppColors.headerGradient`, `_Header` + card branco arredondado, flag
`_submitting`, `try/catch (AuthException)` → `SnackBar`, widgets privados
compostos (`_Header`, etc.).

### 3.1 `lib/features/auth/presentation/forgot_password_screen.dart` (rota `/forgot-password`)

- `StatefulWidget` com `AuthApi` **injetável e opcional**:
  `ForgotPasswordScreen({super.key, AuthApi? authApi}) : authApi = authApi ?? AuthApi();`
  (mesmo padrão de injeção opcional que `AuthApi` usa para seu `http.Client`).
- Campo de e-mail (`TextFormField`), validação client-side: não vazio e contém `@`
  (mesma checagem leve do `register_screen`).
- Ao enviar: `setState(_submitting = true)` → `authApi.requestPasswordReset(email:)`
  → em sucesso mostra `SnackBar('Se o e-mail existir, enviamos um código.')` e
  `Navigator.pushNamed(context, '/reset-password', arguments: email)`.
- `AuthException` → `SnackBar(e.message)`.
- Link "Voltar para o login" (`Navigator.pop` ou `pushReplacementNamed('/login')`).

### 3.2 `lib/features/auth/presentation/reset_password_screen.dart` (rota `/reset-password`)

- `StatefulWidget` com `AuthApi` injetável e opcional (idem acima).
- Lê o e-mail de `ModalRoute.of(context)!.settings.arguments as String` e o exibe
  **read-only** no topo do card (ex.: rótulo "Código enviado para" + e-mail).
- Estado: código atual (string vinda do `OtpInput`), controllers de nova senha e
  confirmação, `_obscurePassword`/`_obscureConfirm`, `_submitting`,
  `_cooldownSeconds` (int) e `Timer? _timer`.
- Campos: `OtpInput(onChanged: ...)`, nova senha (`TextFormField` + toggle obscure),
  confirmar senha (+ toggle).
- Validação client-side (espelha o backend):
  - código com **exatamente 6 dígitos**;
  - senha ≥ 8 chars e ≥ 1 caractere especial (regex `[!@#$%^&*(),.?":{}|<>]`,
    reusada do `register_screen`);
  - confirmação igual à senha.
- Ao enviar: `authApi.confirmPasswordReset(email:, code:, newPassword:)`:
  - `200` → `Navigator.pushNamedAndRemoveUntil(context, '/login', (r) => false,
    arguments: {'passwordReset': true})`.
  - `AuthException` (400/422/etc.) → `SnackBar(e.message)`.
- **Reenviar código com cooldown**:
  - `initState`: inicia cooldown em 60s e dispara `Timer.periodic(1s)` que
    decrementa `_cooldownSeconds` até 0 (então cancela o timer).
  - Botão "Reenviar código" desabilitado enquanto `_cooldownSeconds > 0`,
    exibindo "Reenviar em ${_cooldownSeconds}s"; habilitado em 0.
  - Ao tocar: `authApi.requestPasswordReset(email:)` → `SnackBar` neutro →
    reinicia o cooldown.
  - `dispose`: cancela o `Timer` e dispõe controllers.

## 4. Wiring

### `login_screen.dart`
- Ligar o `GestureDetector` existente de "Esqueceu sua senha?" (hoje `onTap: () {}`,
  em `_LoginCard`) para navegar: `Navigator.pushNamed(context, '/forgot-password')`.
  Como `_LoginCard` é stateless, expor um callback `onForgotPassword` passado pelo
  `_LoginScreenState` (mesmo estilo dos demais callbacks do card).
- Mostrar `SnackBar('Senha redefinida! Faça login com a nova senha.')` quando a
  `LoginScreen` for construída com `arguments {'passwordReset': true}`, via
  `WidgetsBinding.instance.addPostFrameCallback` (lê `ModalRoute` settings uma vez).

### `main.dart`
- Importar `forgot_password_screen.dart` e `reset_password_screen.dart`.
- Registrar no mapa `routes:`:
  ```dart
  '/forgot-password': (_) => ForgotPasswordScreen(),
  '/reset-password': (_) => ResetPasswordScreen(),
  ```
  (não `const`, pois o construtor instancia `AuthApi` por padrão).

## 5. Testes (TDD — escrever antes da implementação)

Estrutura espelha o código em `test/features/auth/`. API testada com `MockClient`
de `package:http/testing.dart` (padrão de `notifications_api_test.dart`); telas com
`testWidgets` (padrão de `support_screen_test.dart`).

### `test/features/auth/auth_api_password_reset_test.dart`
- `requestPasswordReset` faz `POST` no path `/auth/password-reset/request` com body
  `{email}`; `200` resolve sem erro.
- `requestPasswordReset` lança `AuthException` em `429`.
- `confirmPasswordReset` faz `POST` no path `/auth/password-reset/confirm` com body
  `{email, code, new_password}`; `200` resolve.
- `confirmPasswordReset` lança `AuthException('Código inválido ou expirado')` em `400`.
- `confirmPasswordReset` lança `AuthException` em `422`.

### `test/features/auth/otp_input_test.dart`
- Digitar dígitos preenche as caixas e auto-avança o foco.
- `onChanged` emite o código concatenado completo (6 dígitos).

### `test/features/auth/forgot_password_screen_test.dart`
- Validação: e-mail vazio mostra erro e não navega.
- Sucesso (`MockClient` → 200): mostra confirmação neutra e navega para
  `/reset-password` (verificado via rota/`NavigatorObserver`).
- `429`: mostra `SnackBar` de erro.

### `test/features/auth/reset_password_screen_test.dart`
- Renderiza o e-mail (recebido por argumento) read-only.
- `400`: mostra "Código inválido ou expirado".
- Sucesso: navega para `/login`.
- Botão "Reenviar código" desabilitado durante o cooldown.

Critério de pronto: `flutter test` e `flutter analyze` **ambos** passam.

## Fora de escopo

- Deep linking / abrir o app por link de e-mail.
- Qualquer mudança no backend.
- "Lembrar de mim".
- Cooldown sincronizado com `Retry-After` do servidor (o cooldown é client-side de
  60s; o servidor continua sendo a fonte de verdade via `429`).

## Trabalho de fechamento

- Atualizar `docs/back-end/password-reset.md` §11: mover "Telas Flutter" de "Fora de
  escopo" para entregue.
- Commits pequenos em Conventional Commits (inglês, imperativo), na sequência TDD.
- Worktree isolada; ao final, finishing-a-development-branch.
