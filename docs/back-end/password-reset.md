# Módulo Password Reset (Back-end)

Recuperação de senha por **código de uso único (OTP de 6 dígitos)** enviado por e-mail. Estende o módulo `auth` e introduz uma **camada de adapter de e-mail** (`app/core/email/`) que desacopla o domínio do provedor (Resend em produção, console em dev/test).

> Spec de design (o *porquê* das decisões): [`docs/superpowers/specs/2026-06-14-password-reset-email-design.md`](../superpowers/specs/2026-06-14-password-reset-email-design.md).

---

## 1. Visão geral

O usuário esqueceu a senha. O fluxo tem dois passos, ambos públicos (sem autenticação):

1. **Request** — o usuário informa o e-mail. Se a conta existir, geramos um OTP, guardamos o **hash** dele no Redis (com TTL) e enfileiramos uma task Celery que envia o código por e-mail. A resposta é **sempre 200**, exista ou não o e-mail (anti-enumeração).
2. **Confirm** — o usuário envia e-mail + código + nova senha. Verificamos o OTP em tempo constante, com limite de tentativas; em caso de sucesso gravamos a nova senha (bcrypt) e invalidamos o código.

O código nunca trafega nem é guardado em texto puro no Redis — só o hash. O envio real é assíncrono (Celery), então a rota não bloqueia em I/O de rede.

---

## 2. Estrutura de arquivos

```
back-end/app/
├── core/
│   ├── config.py                  # settings de e-mail + reset (ver §7)
│   └── email/                     # CAMADA DE ADAPTER (Ports & Adapters)
│       ├── __init__.py            # reexporta EmailMessage, EmailSender, get_email_sender
│       ├── base.py                # EmailMessage (DTO), EmailSender (porta), EmailDeliveryError
│       ├── console.py             # ConsoleEmailAdapter  (dev/test, só loga)
│       ├── resend.py              # ResendEmailAdapter   (httpx → API Resend)
│       └── factory.py             # get_email_sender()   (único leitor das settings de provedor)
└── modules/auth/
    ├── password_reset.py          # OTP: geração, hash, store/verify/clear no Redis
    ├── rate_limit.py              # check_password_reset_rate_limit (+ helper _enforce)
    ├── schemas.py                 # PasswordResetRequestIn, PasswordResetConfirmIn
    ├── services.py                # request_password_reset, confirm_password_reset
    ├── tasks.py                   # send_password_reset_email_task (Celery)
    ├── exceptions.py              # InvalidResetCode
    └── routes.py                  # POST /auth/password-reset/{request,confirm}
```

Testes correspondentes em `back-end/tests/core/email/` e `back-end/tests/modules/auth/test_password_reset_*.py`.

---

## 3. Camada de adapter de e-mail

Padrão **Ports & Adapters**: o domínio depende de uma abstração (`EmailSender`), nunca de um SDK/HTTP de provedor. Trocar de provedor = escrever um novo adapter e mudar uma variável de ambiente.

```
        app/modules/auth (domínio)
                 │ depende de
                 ▼
   ┌──────────────────────────────┐
   │  EmailSender (Protocol)       │   ← a "porta"
   │  async send(EmailMessage)     │
   └──────────────────────────────┘
            ▲              ▲
   implementa│              │implementa
   ┌─────────┴────┐   ┌─────┴──────────┐
   │ConsoleAdapter│   │ ResendAdapter  │   ← os "adapters"
   └──────────────┘   └────────────────┘
            ▲
            │ get_email_sender() escolhe por settings.EMAIL_BACKEND
```

- **`EmailMessage`** — DTO neutro de provedor (`to`, `subject`, `html`, `text`). Nenhum campo específico de provedor vaza para o domínio.
- **`EmailSender`** — `Protocol` com `async def send(self, message: EmailMessage) -> None`.
- **`ConsoleEmailAdapter`** — loga a mensagem via `loguru`. Sem rede. Usado em dev e em **todos** os testes.
- **`ResendEmailAdapter`** — `POST https://api.resend.com/emails` via `httpx`, header `Authorization: Bearer <key>`. Levanta `EmailDeliveryError` em status ≥ 400. Aceita um `httpx.AsyncClient` injetado (testes usam `httpx.MockTransport`).
- **`get_email_sender()`** — factory; **único** ponto que lê `EMAIL_BACKEND`/`RESEND_API_KEY`/`EMAIL_FROM`.

---

## 4. Fluxo OTP

```
Request:
  cliente ──POST /auth/password-reset/request {email}──▶ rota
     rota: rate-limit (IP + email)
     service.request_password_reset:
        usuário existe? ──não──▶ no-op silencioso
                        ──sim──▶ gera OTP, store hash no Redis (TTL),
                                 enfileira task Celery
     rota responde 200 (sempre)
  task Celery ──get_email_sender().send(EmailMessage)──▶ provedor

Confirm:
  cliente ──POST /auth/password-reset/confirm {email, code, new_password}──▶ rota
     service.confirm_password_reset:
        usuário existe?      ──não──▶ InvalidResetCode → 400
        verify_reset_code()  ──falha─▶ InvalidResetCode → 400
        sucesso ──▶ grava bcrypt(new_password), commit, limpa código do Redis
     rota responde 200
```

O código **não** é consumido na verificação; só é limpo **após** o commit da nova senha — assim uma falha no passo de gravação não queima o único código do usuário.

---

## 5. Endpoints

Todos montados sob `API_PREFIX` (`/api`).

### `POST /api/auth/password-reset/request`

Solicita um código de recuperação.

**Request:**
```json
{ "email": "maria@example.com" }
```

**Respostas:**

| Status | Corpo | Quando |
|---|---|---|
| `200` | `{"detail": "If the email exists, a reset code was sent."}` | **Sempre** (existindo ou não o e-mail) |
| `429` | `{"detail": "Too many attempts"}` + header `Retry-After` | Rate limit por IP ou e-mail estourado |
| `422` | erro de validação Pydantic | `email` ausente/maior que 254 chars |

> O 200 é idêntico para e-mail existente e inexistente — **anti-enumeração**.

### `POST /api/auth/password-reset/confirm`

Confirma o código e troca a senha.

**Request:**
```json
{ "email": "maria@example.com", "code": "123456", "new_password": "NovaSenha!9" }
```

**Respostas:**

| Status | Corpo | Quando |
|---|---|---|
| `200` | `{"detail": "Password updated."}` | Código válido; senha trocada |
| `400` | `{"detail": "Invalid or expired code"}` | Código errado, expirado, inexistente, e-mail desconhecido **ou** tentativas esgotadas |
| `422` | erro de validação Pydantic | `code` não tem exatamente 6 dígitos, ou `new_password` viola a política |

> O 400 é **genérico**: não distingue a causa (errado vs expirado vs travado vs e-mail inexistente).

**Validações de schema:**
- `email` — normalizado para minúsculas, máx. 254 chars.
- `code` — exatamente 6 dígitos (`^\d{6}$`).
- `new_password` — 8–128 chars e ao menos um caractere especial (mesma política do registro).

---

## 6. Armazenamento no Redis

| Chave | Conteúdo | TTL |
|---|---|---|
| `pwreset:code:{user_id}` | hash HMAC-SHA256 do OTP | `PASSWORD_RESET_CODE_TTL_SECONDS` (600) |
| `pwreset:attempts:{user_id}` | contador de tentativas de verificação | igual ao do código |
| `pwreset:req:ip:{ip}` | rate-limit de requests por IP | janela de rate-limit |
| `pwreset:req:email:{email}` | rate-limit de requests por e-mail | janela de rate-limit |

- Só existe **um** código ativo por usuário: um novo request sobrescreve o anterior e zera o contador de tentativas.
- O contador de tentativas usa pipeline atômico (`INCR` + `EXPIRE NX`); ao atingir `PASSWORD_RESET_MAX_ATTEMPTS`, mesmo o código correto passa a ser rejeitado até expirar.

---

## 7. Configuração

Em `app/core/config.py` (defaults seguros; valores reais via `.env`):

| Variável | Default | Descrição |
|---|---|---|
| `EMAIL_BACKEND` | `console` | `console` (só loga) ou `resend` (envia de verdade) |
| `RESEND_API_KEY` | `None` | Chave da API Resend (obrigatória se `EMAIL_BACKEND=resend`) |
| `EMAIL_FROM` | `Edu <no-reply@edu.app>` | Remetente; o domínio precisa estar verificado no Resend |
| `PASSWORD_RESET_CODE_TTL_SECONDS` | `600` | Validade do OTP (10 min) |
| `PASSWORD_RESET_MAX_ATTEMPTS` | `5` | Tentativas de verificação antes de travar o código |
| `PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS` | `5` | Requests permitidos por janela |
| `PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS` | `900` | Janela do rate-limit de request (15 min) |
| `EMAIL_SEND_TIME_LIMIT` | `30` | `time_limit` da task Celery de envio |
| `EMAIL_SEND_SOFT_TIME_LIMIT` | `25` | `soft_time_limit` da task |

### Ligar o envio real (console → resend)

1. No `back-end/.env`: `EMAIL_BACKEND=resend` e `RESEND_API_KEY=re_...`.
2. Ajuste `EMAIL_FROM` para um remetente cujo **domínio esteja verificado** no painel da Resend.
3. Reinicie api e worker (`docker compose restart api worker`).

Em dev/teste mantenha `console`: o código aparece nos logs (`email[console] ...`), sem enviar nada.

---

## 8. Task Celery

`auth.send_password_reset_email(email, code)` (em `auth/tasks.py`):
- Não toca no banco; só pede `get_email_sender()` e chama `send()` com um `EmailMessage` (assunto + corpo HTML/texto contendo o código e o tempo de expiração).
- Declara `time_limit` e `soft_time_limit` (config).
- Idempotente: reenviar o mesmo código é inócuo.
- Trade-off conhecido: o OTP trafega em texto na mensagem do broker — aceitável para o contexto atual.

---

## 9. Segurança

- **Anti-enumeração:** `request` responde 200 idêntico para e-mail existente e inexistente.
- **Erro genérico:** `confirm` retorna o mesmo 400 para todas as causas de falha.
- **Hash do OTP:** só o hash HMAC-SHA256 (sob `SECRET_KEY`) vai pro Redis; o texto puro nunca é persistido nem logado.
- **Comparação em tempo constante:** `compare_secret` (`hmac.compare_digest`) ao verificar o código (regra 9 do CLAUDE.md).
- **Rate limit + lockout:** request limitado por IP/e-mail; confirm limitado por contador de tentativas atômico.
- **Senha:** gravada com bcrypt (`hash_password`) e commitada antes de limpar o código.
- **SQL:** ORM com parâmetros bind, sem f-string.

---

## 10. Testes

| Arquivo | Cobre |
|---|---|
| `tests/core/email/test_base.py` | `EmailMessage` (frozen), `EmailDeliveryError` |
| `tests/core/email/test_console.py` | console loga, sem rede |
| `tests/core/email/test_resend.py` | payload/headers corretos, erro em status ≥ 400, exige API key |
| `tests/core/email/test_factory.py` | factory escolhe o adapter por `EMAIL_BACKEND` |
| `tests/core/test_config_email.py` | defaults declarados (independente do `.env`) |
| `tests/modules/auth/test_password_reset_store.py` | OTP gen/hash, store/verify/clear, lockout |
| `tests/modules/auth/test_password_reset_rate_limit.py` | rate-limit de request + isolamento das chaves de login |
| `tests/modules/auth/test_password_reset_schemas.py` | validações dos schemas |
| `tests/modules/auth/test_password_reset_task.py` | montagem da mensagem + envio com sender injetado |
| `tests/modules/auth/test_password_reset_flow.py` | fluxo ponta a ponta (200 anti-enum, troca de senha, código single-use, 400 genérico) |

Os testes de fluxo capturam o `.delay()` da task (monkeypatch) para ficarem offline; nenhum e-mail real é enviado.

---

## 11. Fora de escopo (futuro)

- **Revogar sessões ativas após o reset** — os refresh tokens são JWT stateless sem denylist; invalidá-los exigiria `token_version`/`password_changed_at` no usuário.
- **Telas Flutter** ("esqueci a senha" / "digite o código + nova senha").
- **Rate-limit no endpoint `confirm`** (hoje a proteção é o lockout por código) e **retry/backoff** da task de envio.
