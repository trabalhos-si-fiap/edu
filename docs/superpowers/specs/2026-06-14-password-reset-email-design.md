# Password Reset via E-mail (OTP) — Design

**Data:** 2026-06-14
**Escopo desta iteração:** Backend apenas. As telas Flutter ficam para uma iteração seguinte.

## Objetivo

Permitir que um usuário recupere o acesso à conta quando esquece a senha, via
um código de uso único (OTP de 6 dígitos) enviado por e-mail. Isso exige duas
peças novas no backend:

1. Uma **camada de adapter de e-mail** entre o núcleo da aplicação e os
   provedores externos (Resend agora; trocável depois sem tocar no domínio).
2. O **fluxo de reset de senha** em si (geração, envio, verificação do OTP e
   troca de senha), estendendo o módulo `auth`.

Provedor escolhido: **Resend** (free tier suficiente para o contexto
acadêmico/demo, DX enxuta). Em dev e testes usamos um adapter de console que
não envia nada real.

## Decisões-chave

- **OTP de 6 dígitos**, não link. Evita configurar deep linking / página web no
  app mobile.
- **Armazenamento em Redis, não Postgres.** O código é efêmero e single-use:
  Redis dá TTL automático e operações atômicas, sem migration nem job de
  limpeza.
- **Guarda-se o hash do código, nunca o texto puro.** Comparação constant-time
  via `compare_secret` (já existe em `auth/security.py`).
- **Anti-enumeração:** `request` sempre retorna 200, exista ou não o e-mail —
  fiel à defesa de timing que o login já adota.
- **Limite de tentativas obrigatório:** 6 dígitos = só 10⁶ combinações, então a
  verificação trava após N tentativas erradas por usuário.

---

## 1. Camada de adapter de e-mail (`app/core/email/`)

Padrão **Ports & Adapters**: o núcleo da aplicação depende de uma abstração
(`EmailSender`), nunca de um SDK/HTTP de provedor. Cada provedor é um adapter
concreto que traduz a interface comum para a API específica dele. Trocar de
provedor = escrever um novo adapter e mudar uma variável de ambiente; o domínio
(serviços de reset, tasks) não muda uma linha.

```
            app/modules/auth (núcleo / domínio)
                       │ depende de
                       ▼
        ┌──────────────────────────────┐
        │  EmailSender (Protocol/ABC)   │   ← a "porta"
        │  async send(message) -> None  │
        └──────────────────────────────┘
                 ▲              ▲
     implementa  │              │  implementa
     ┌───────────┴───┐   ┌──────┴────────────┐
     │ ConsoleAdapter│   │  ResendAdapter    │   ← os "adapters"
     │ (dev/test)    │   │  (httpx → Resend) │
     └───────────────┘   └───────────────────┘
                 ▲
                 │ seleciona por settings.EMAIL_BACKEND
        ┌────────┴─────────┐
        │ get_email_sender │   ← factory
        └──────────────────┘
```

### Estrutura de arquivos

```
app/core/email/
    __init__.py        # exporta EmailSender, EmailMessage, get_email_sender
    base.py            # EmailMessage (dataclass) + EmailSender (Protocol/ABC)
    console.py         # ConsoleEmailAdapter
    resend.py          # ResendEmailAdapter
    factory.py         # get_email_sender()
```

### A porta (`base.py`)

```python
@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str

class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None: ...
```

`EmailMessage` é um contrato neutro de provedor — nenhum campo específico de
Resend/SES vaza para o domínio. Se um provedor futuro precisar de algo extra
(ex.: tags, template id), isso entra como detalhe interno do adapter, não na
porta.

### Adapter de console (`console.py`)

`ConsoleEmailAdapter.send()` apenas loga o destinatário, assunto e corpo via
`loguru.logger`. Usado em dev e em todos os testes. Nunca faz I/O de rede.

### Adapter Resend (`resend.py`)

`ResendEmailAdapter` recebe `api_key` e `sender` (from) no construtor (injeção
de dependência — não lê `settings` direto, para ser testável). `send()` faz
`POST https://api.resend.com/emails` com `httpx.AsyncClient`, header
`Authorization: Bearer <api_key>`, body `{from, to, subject, html, text}`.
Levanta uma exceção do módulo (`EmailDeliveryError`) em status != 2xx, para a
task Celery poder logar/retentar.

### Factory (`factory.py`)

```python
def get_email_sender() -> EmailSender:
    if settings.EMAIL_BACKEND == "resend":
        return ResendEmailAdapter(api_key=settings.RESEND_API_KEY,
                                  sender=settings.EMAIL_FROM)
    return ConsoleEmailAdapter()
```

Única função que conhece `settings`. O resto do código pede `get_email_sender()`
e recebe a porta.

---

## 2. Fluxo de reset (módulo `auth`)

### Chaves no Redis

| Chave | Conteúdo | TTL |
|---|---|---|
| `pwreset:code:{user_id}` | hash do OTP | `PASSWORD_RESET_CODE_TTL_SECONDS` (600) |
| `pwreset:attempts:{user_id}` | contador de tentativas de verificação | mesmo TTL do código |
| `pwreset:req:ip:{ip}` | rate-limit de requests por IP | janela de rate-limit |
| `pwreset:req:email:{email}` | rate-limit de requests por e-mail | janela de rate-limit |

Um novo request sobrescreve o código anterior (só um OTP ativo por usuário).

### Endpoints (`auth/routes.py`)

**`POST /auth/password-reset/request`** — body `{ email }`
1. Aplica rate-limit (IP + e-mail), mesmo padrão atômico de `rate_limit.py`.
2. Busca o usuário. Se **não** existe → retorna 200 mesmo assim (anti-enumeração).
3. Se existe: gera OTP de 6 dígitos, grava hash em `pwreset:code:{user_id}` com
   TTL, zera o contador de tentativas, e enfileira
   `auth.send_password_reset_email(email, code)`.
4. Sempre retorna `200 {"detail": "If the email exists, a code was sent."}`.

**`POST /auth/password-reset/confirm`** — body `{ email, code, new_password }`
1. Busca usuário; resolve `user_id`.
2. Lê `pwreset:attempts`; se ≥ `PASSWORD_RESET_MAX_ATTEMPTS` → erro genérico
   (código inválido/expirado).
3. Lê `pwreset:code`; ausente (expirou ou nunca existiu) → incrementa tentativas
   → erro genérico.
4. Compara via `compare_secret(hash(code_recebido), hash_guardado)`. Mismatch →
   incrementa tentativas → erro genérico.
5. Match: grava `hash_password(new_password)` no usuário, deleta
   `pwreset:code` e `pwreset:attempts`. Retorna 200.

Todos os erros de verificação são **genéricos e idênticos** — não revelam se o
e-mail existe, se o código expirou ou se está errado.

### Schemas (`auth/schemas.py`)

- `PasswordResetRequestIn` → `email` (reusa o validador/normalizador existente).
- `PasswordResetConfirmIn` → `email`, `code` (exatamente 6 dígitos, regex),
  `new_password` (mesma política de senha do registro — `max_length` no schema).

---

## 3. Task Celery (`auth/tasks.py`)

`auth.send_password_reset_email(email: str, code: str)`:
- Não toca no banco; só pede `get_email_sender()` e chama `send()` com um
  `EmailMessage` (assunto + corpo HTML/texto com o código).
- `time_limit=settings.EMAIL_SEND_TIME_LIMIT`,
  `soft_time_limit=settings.EMAIL_SEND_SOFT_TIME_LIMIT`.
- Idempotente: reenviar o mesmo código é inócuo.
- O OTP trafega em texto na mensagem do broker — aceitável para o contexto
  demo; anotado como trade-off consciente.

---

## 4. Config novo (`app/core/config.py`)

```python
EMAIL_BACKEND: str = "console"            # "console" | "resend"
RESEND_API_KEY: str | None = None
EMAIL_FROM: str = "Edu <no-reply@edu.app>"
PASSWORD_RESET_CODE_TTL_SECONDS: int = 600
PASSWORD_RESET_MAX_ATTEMPTS: int = 5
PASSWORD_RESET_REQUEST_RATE_LIMIT_ATTEMPTS: int = 5
PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW_SECONDS: int = 900
EMAIL_SEND_TIME_LIMIT: int = 30
EMAIL_SEND_SOFT_TIME_LIMIT: int = 25
```

Segue o padrão existente: secrets como `str | None = None`, defaults seguros
(`console`), `# noqa: S105` quando aplicável.

---

## 5. Testes (TDD — escrever antes da implementação)

**Adapter de e-mail** (`tests/core/test_email.py`):
- `ConsoleEmailAdapter.send()` loga e não faz rede.
- `ResendEmailAdapter.send()` monta o payload e headers corretos e dá `POST` na
  URL certa — usando `httpx.MockTransport` (built-in, sem dep nova).
- `ResendEmailAdapter` levanta `EmailDeliveryError` em status != 2xx.
- `get_email_sender()` devolve o adapter certo conforme `EMAIL_BACKEND`.

**Fluxo de reset** (`tests/modules/auth/test_password_reset.py`):
- `request` retorna 200 para e-mail existente **e** inexistente.
- `request` só enfileira a task quando o usuário existe.
- `request` respeita o rate-limit (IP e e-mail).
- `confirm` com código válido troca a senha e invalida o código (não reusa).
- `confirm` com código errado incrementa tentativas; trava após
  `MAX_ATTEMPTS` com erro genérico.
- `confirm` com código expirado é rejeitado.
- A nova senha autentica no `login` em seguida; a antiga não.

Testes de integração usam banco real + Redis real (padrão do projeto) e o
adapter de console.

---

## Fora de escopo (anotado para o futuro)

- **Revogar sessões ativas após o reset.** Os refresh tokens são JWT stateless
  sem denylist hoje; invalidá-los exigiria `token_version` ou
  `password_changed_at` no usuário, checado na validação do token. Fica para
  uma iteração futura.
- **Telas Flutter** ("esqueci a senha" / "digite o código + nova senha"):
  próxima iteração.
- **Retry/backoff da task de e-mail** além do limite de tempo: o MVP só loga a
  falha; política de retentativa pode ser adicionada depois.
