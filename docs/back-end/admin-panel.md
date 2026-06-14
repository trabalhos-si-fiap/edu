# Painel Admin Web (SQLAdmin)

Painel administrativo web, no estilo do Django admin, para **gerenciar e
visualizar** os modelos da aplicação a partir do navegador. É uma ferramenta
interna de operadores — não faz parte do contrato do app mobile.

- **URL:** `/admin`
- **Stack:** [SQLAdmin](https://aminalaee.dev/sqladmin/) sobre o FastAPI/SQLAlchemy existentes.
- **Código:** `app/admin/` (camada de agregação, como o `bff/` — pode importar models de qualquer módulo).

## Como acessar

1. O painel exige um usuário **admin ativo**. Para promover um usuário existente:

   ```sql
   UPDATE auth_users SET is_admin = true WHERE email = '<seu-email>';
   ```

   (Conecte no Postgres com `make back-sh` + `psql`, ou pelo cliente de sua preferência.)

2. Acesse `http://<host>:8000/admin` e faça login com **e-mail e senha** do
   usuário admin. As credenciais são as mesmas do app (tabela `auth_users`,
   hash bcrypt) — não há senha separada.

## Autenticação

Login por formulário com sessão em cookie (`AdminAuth`, em `app/admin/auth.py`):

- **login** valida e-mail/senha contra `auth_users` reusando `verify_password`
  (bcrypt). Quando o e-mail não existe, ainda executa a verificação contra um
  hash dummy para manter o tempo de resposta constante (anti-enumeração). Só
  autoriza se `is_admin=True` **e** `is_active=True`.
- **authenticate** revalida o usuário a **cada request**: se o admin for
  rebaixado (`is_admin=false`) ou desativado, perde o acesso imediatamente —
  não basta o cookie.
- A sessão é assinada com `settings.SECRET_KEY` (Starlette `SessionMiddleware`).

Todo handler do painel é protegido (`@login_required` do SQLAdmin); sem sessão
válida, qualquer rota sob `/admin` redireciona para `/admin/login`.

## Modelos gerenciáveis

CRUD completo (listar, buscar, ordenar, criar, editar, apagar) para os 12
modelos do domínio, definidos em `app/admin/views.py` (`ALL_VIEWS`):

`User`, `Address`, `Product`, `Review`, `Order`, `OrderItem`, `Cart`,
`CartItem`, `PaymentMethod`, `DeviceToken`, `Notification`, `SupportMessage`.

## Notas de segurança

- **Senha de usuário:** o campo `password_hash` nunca aparece em listagem,
  detalhe ou formulário. O form de `User` expõe um campo virtual **"Senha"**;
  ao salvar, o valor é hasheado com bcrypt via `on_model_change`. Em branco na
  edição, mantém o hash atual; em branco na criação, o form rejeita com erro.
- **Dados sensíveis ocultos:** o valor do token FCM (`DeviceToken.token`) não é
  listado; `PaymentMethod` mostra apenas dados mascarados (`card_brand`,
  `card_last4`) — `pix_key` e `cardholder_name` ficam fora da listagem de
  propósito.
- O CRUD de `User` permite alternar `is_admin`/`is_active` — operação sensível,
  restrita a admins por design.

### Melhoria futura sugerida

Hoje o cookie de sessão do painel reusa `SECRET_KEY` (o mesmo do JWT). É
aceitável para uma ferramenta interna, mas o ideal seria uma chave dedicada
(`ADMIN_SESSION_KEY`) para isolar o namespace de assinatura.
