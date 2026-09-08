# Spec A — O corte e a consolidação — Design

**Data:** 2026-09-07
**Status:** Aprovado para planejamento
**Módulos:** `back-end/` (frota inteira), repositório `mobile_hybrid_app`
**Depende de:** nada. É a fundação das specs B, C e D.

## Objetivo

Deixar a plataforma rodando sobre **um único backend** (os microsserviços
Python) e **um único repositório** (`edu`). Hoje existem três backends vivos ao
mesmo tempo — os microsserviços, o monolito `back-end/legacy/`, e a API Java do
repositório `mobile_hybrid_app` — e dois apps Flutter que duplicam telas.

Nada de funcionalidade nova entra nesta spec. O que ela entrega é a condição
para que as specs B, C e D não sejam escritas duas vezes.

## Decisões tomadas no brainstorming

| Decisão | Escolha |
|---|---|
| Monolito `back-end/legacy/` | Apagado. Todos os módulos já foram portados na fase 2. |
| API Java (`api/` do repo 2) | Eliminada. Regras de negócio portadas na spec B. |
| `mobile-flutter` (repo 2) | Descontinuado. As telas dele já existem no `front-end-flutter`. |
| `web-angular` (repo 2) | Migra para `edu/web-admin/`, preservando histórico. |
| Repositório `mobile_hybrid_app` | Arquivado depois da migração. |
| Dívida da fase 2 | Triada: três itens corrigidos aqui, quatro registrados como dívida. |

## Contexto do código existente

### O que já está pronto e não deve ser refeito

- **O app já fala com o gateway.** `front-end-flutter/lib/core/network/api_config.dart:33`
  aponta para a porta 8100 desde o commit `7c6eb6a` (2026-08-05). O prompt de
  origem desta entrega afirma que o app consome o legacy na porta 8001 — isso é
  falso desde aquela data.
- **Todos os módulos do legacy foram portados.** `docs/back-end/microservices.md`
  registra a tabela módulo a módulo; `support` foi o último, na fase 2d.
- **O gateway já roteia tudo que o app chama.** `api-gateway/app/routing.py`
  mapeia os vinte primeiros segmentos de path usados pelo Flutter.
- **539 testes passam nos serviços novos**: commerce 217, learning 80,
  auth-users 66, edu-common 57, analytics 36, notification 33, chatbot 32,
  gateway 18.

### O que ainda está de pé e precisa sair

- `back-end/legacy/` — 193 arquivos `.py`.
- `back-end/docker-compose.yml` — serviços `api` (linha 140) e `worker`
  (linha 171), que sobem o monolito e seu Celery.
- Repositório `mobile_hybrid_app`, três aplicações:
  - `api/` — Spring Boot. Entidades `Product`, `Inventory`,
    `InventoryAdjustment`, `Carrier`, `CarrierStatus`, `CarrierOccurrence`,
    `OccurrenceType`, `OccurrenceStatus`, `AdminUser`. Seis controllers.
  - `mobile-flutter/` — fork do `front-end-flutter`. O arquivo
    `lib/core/network/app_http.dart` é byte a byte idêntico ao do `edu`;
    `admin_api.dart`, `auth_api.dart` e `delivery_queue_screen.dart` divergiram
    apenas para acompanhar o contrato Java. Aponta para
    `localhost:8080/api/v1`.
  - `web-angular/` — Angular 22 standalone. Páginas `dashboard`, `login`,
    `products-stock`, `carriers`, `occurrences`.

### A dívida que vence no dia do corte

`docs/back-end/phase-2-debt.md` §1 lista sete itens escritos exatamente para
este momento. A triagem desta spec:

| Item | Decisão | Porque |
|---|---|---|
| Idempotência do seed é read-then-write | **Corrigir aqui** | `make services-seed` nunca foi executado. O corte é a primeira execução. |
| Nenhuma fila tem dead-letter exchange | **Corrigir aqui** | Foi o mecanismo que engoliu notificações em silêncio durante o bloco C. A spec C depende de push confiável. |
| Título de notificação mostra UUID de 36 caracteres | **Corrigir aqui** | Visível ao aluno no primeiro push, e a apresentação exibe push. |
| `put_object` antes do `commit()` | Dívida | Deixa objeto órfão no MinIO num rollback. Não quebra demonstração. |
| `DeadlockDetectedError` ~1/200 em formas de pagamento | Dívida | Frequência baixa por requisição; volume de demonstração não alcança. |
| `/support` não tem teto de linhas | Dívida | Piora com tráfego real, que não existe antes da apresentação. |
| Aluno desativado mantém suporte por até 60 minutos | Dívida | Divergência de comportamento contra um módulo que deixa de existir. |

Os quatro itens de dívida continuam registrados em `phase-2-debt.md` e ganham
uma nota dizendo que a triagem desta spec os adiou deliberadamente.

## Arquitetura

### Estado final do repositório `edu`

```
edu/
  back-end/
    api-gateway/
    auth-users-service/
    learning-service/
    commerce-service/
    chatbot-service/
    notification-service/
    analytics-service/
    packages/edu-common/
    docker-compose.yml        # sem `api`, sem `worker`
  front-end-flutter/          # os quatro perfis
  web-admin/                  # Angular, vindo do repo 2
  docs/
```

`back-end/legacy/` deixa de existir.

### Estado final do repositório `mobile_hybrid_app`

Arquivado no GitHub, com um `README.md` final apontando para o `edu` e
explicando onde cada aplicação foi parar. Nada é apagado do histórico: o
repositório continua legível como registro acadêmico.

### Migração do `web-angular` preservando histórico

A migração usa `git subtree` a partir de um clone do repositório 2, não uma
cópia de arquivos:

```bash
git remote add repo2 https://github.com/trabalhos-si-fiap/mobile_hybrid_app.git
git fetch repo2
git subtree add --prefix=web-admin repo2 main
```

Isso traz os commits do Angular para dentro do `edu`. Uma cópia simples
perderia a autoria dos colegas, que é justamente o que uma entrega acadêmica
precisa preservar.

O Angular chega apontando para `localhost:8080/api/v1`. **Ele continua
apontando para lá ao fim desta spec** — só passa a falar com o gateway na
spec B, quando os endpoints equivalentes existirem. Enquanto isso, `web-admin`
não sobe no compose e está marcado no README como não funcional.

### Contas de demonstração

A apresentação é conduzida por uma pessoa alternando entre quatro perfis. O
seed passa a criar quatro contas fixas, uma por papel, com senha conhecida e
documentada em `docs/back-end/demo-accounts.md`:

| Papel | E-mail |
|---|---|
| `student` | `aluno@demo.edu` |
| `separador` | `separador@demo.edu` |
| `entregador` | `entregador@demo.edu` |
| `admin` | `admin@demo.edu` |

As contas são criadas pelo mesmo caminho de código que o cadastro normal
(`/auth/register` e `/auth/register-staff`), nunca por `INSERT` direto — um
seed que contorna a rota deixa de testar a rota.

A senha vive em variável de ambiente (`DEMO_ACCOUNTS_PASSWORD`), com o seed
recusando-se a rodar se ela não estiver definida. Nenhuma senha entra no
repositório, nem mesmo uma de demonstração.

## Componentes

### 1. Correção dos três itens de dívida

Cada um é uma unidade independente, com teste que falha primeiro.

- **Seed idempotente.** Trocar o `SELECT` seguido de `INSERT` por
  `INSERT ... ON CONFLICT DO NOTHING`, ou equivalente na camada ORM. O teste
  roda o seed duas vezes e afirma que a segunda passada não duplica nem
  levanta erro.
- **Dead-letter exchange.** `packages/edu-common/src/edu_common/events.py`
  ganha a declaração de DLX no `EventConsumer.bind`. A mudança fica no pacote
  compartilhado, então vale para os cinco consumidores de uma vez. O teste
  afirma que uma mensagem rejeitada aparece na fila morta em vez de sumir.
- **Título da notificação.** O consumidor que monta o título passa a usar um
  identificador curto de pedido, não o UUID. O teste afirma o formato do
  título contra uma string esperada.

### 2. Remoção do legacy

Ordem importa: o compose sai antes dos arquivos, para que uma parada no meio
deixe a árvore num estado que ainda sobe.

1. Remover `api` e `worker` de `back-end/docker-compose.yml` e as variáveis de
   ambiente que só eles usavam.
2. Remover os alvos do `Makefile` que apontam para o monolito.
3. Apagar `back-end/legacy/`.
4. Atualizar `docs/back-end/start-here.md`, que documenta o monolito, e a §9 de
   `docs/back-end/microservices.md`, que afirma que o Flutter aponta para a
   porta 8001 — uma afirmação já falsa antes desta spec.

### 3. Absorção do repositório 2

1. `git subtree add` do `web-angular` como `web-admin/`.
2. Nada é trazido do `mobile-flutter`: cada tela dele já tem equivalente em
   `front-end-flutter/lib/features/`. A verificação é explícita — para cada
   arquivo em `mobile-flutter/lib/features/`, apontar o arquivo correspondente
   no `edu` ou registrar o que foi perdido.
3. Nada é trazido do `api/` nesta spec. As regras de negócio dele são escopo da
   spec B, e o código Java continua disponível no histórico do repositório
   arquivado, que é a referência que a spec B usa.
4. Abrir o pull request de arquivamento no repositório 2 com o README final.

### 4. Contas e seed de demonstração

`back-end/scripts/` ganha o seed das quatro contas, chamado pelo alvo de seed
existente. Teste: rodar o seed duas vezes e afirmar quatro contas, uma por
papel, com os papéis corretos no claim do token.

## Fluxo de dados

Não muda nada. O app já fala com o gateway, o gateway já fala com os seis
serviços pela rede interna do compose. O que muda é o que deixa de existir ao
lado disso.

Ao fim da spec, as portas 8101 a 8106 podem deixar de ser publicadas para o
host: só o gateway precisa ser alcançável de fora. Essa mudança fica **fora**
desta spec — ela dificultaria a depuração durante as specs B, C e D, e o ganho
só aparece em produção, que este projeto não tem.

## Tratamento de erros

O único caminho de erro novo é o seed recusando-se a rodar sem
`DEMO_ACCOUNTS_PASSWORD`. Ele falha com mensagem explícita nomeando a variável,
antes de abrir transação.

A dead-letter exchange muda o comportamento de erro de toda a frota: uma
mensagem que o consumidor rejeita passa a ser observável em vez de sumir. Isso
é o objetivo, não um efeito colateral.

## Testes

- Seed idempotente: duas passadas, sem duplicação, sem erro.
- Dead-letter: mensagem rejeitada chega na fila morta.
- Título de notificação: formato afirmado contra string esperada.
- Contas de demonstração: quatro papéis, criados pela rota pública.
- Regressão da frota: `make services-test` verde, com a contagem registrada
  antes e depois. A contagem antes desta spec é 539.
- `make front-analyze` e `make front-test` verdes.

Os testes de `back-end/legacy/` desaparecem junto com o diretório. A contagem
final registra isso explicitamente, para que a queda no número não seja lida
como regressão.

## Critério de pronto

1. `make services-test` verde.
2. `docker compose up` sobe a frota sem nenhum container de monolito ou Java.
3. O app Flutter completa um pedido de ponta a ponta contra o gateway.
4. `back-end/legacy/` não existe.
5. `web-admin/` existe no `edu` com o histórico do Angular preservado.
6. O repositório 2 está arquivado com README final.
7. Os quatro itens de dívida adiados estão marcados como tal em
   `phase-2-debt.md`.

## Fora de escopo

- Portar qualquer regra de negócio do Java. É a spec B.
- Fazer o `web-admin` falar com o gateway. É a spec B.
- Padronização global de respostas de erro. Registrado como dívida; o prompt de
  origem desta entrega desprioriza polimento explicitamente.
- Despublicar as portas 8101 a 8106.
