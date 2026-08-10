# Edu IA - Estuda App

Plataforma educacional com app mobile (Flutter) e backend em microservicos (Python + FastAPI).

## Visao Geral da Arquitetura

```
                    +-----------------+
                    |   App Flutter   |
                    |   (mobile/web)  |
                    +--------+--------+
                             |
                             | HTTP/REST
                             |
                    +--------v--------+
                    |       BFF       |
                    | (Backend for    |
                    |  Frontend)      |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
        +-----v----+  +-----v----+  +------v-----+
        | Servico A |  | Servico B |  | Servico C  |
        | (modulo)  |  | (modulo)  |  | (modulo)   |
        +-----+-----+ +-----+-----+ +------+------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------v--------+
                    |   PostgreSQL    |
                    |   Redis         |
                    |   RabbitMQ      |
                    +-----------------+
```

### Frontend (`front-end-flutter/`)

App mobile multiplataforma feito com **Flutter/Dart**. Arquitetura feature-first:

```
lib/
├── core/theme/          # Cores, ThemeData global
├── features/
│   ├── auth/            # Login e cadastro
│   ├── home/            # Dashboard principal
│   └── profile/         # Perfil do usuario
└── main.dart            # Entry point + rotas
```

Docs detalhados: [front-end-flutter/README.md](front-end-flutter/README.md)

### Backend (`back-end/`)

API em **Python 3.12** com **FastAPI** (async), servida pelo **Granian**. A pasta abriga hoje **dois stacks lado a lado**: o monolito modular que serve o app, em `back-end/legacy/`, e os sete microservicos que vao substitui-lo.

```
back-end/
├── legacy/              # Monolito modular — backend de producao do app hoje
│   ├── app/             # core/, bff/, modules/, main.py
│   ├── alembic/
│   └── tests/
├── packages/edu-common/ # JWT/auth + publisher/consumer RabbitMQ
├── api-gateway/         # Proxy por prefixo de path
├── auth-users-service/  # Auth, users, addresses, reset de senha
├── learning-service/    # Diagnostico adaptativo, SM-2, embeddings
├── commerce-service/    # Catalogo, pedidos, separacao, entrega
├── chatbot-service/     # RAG (FAISS + Groq)
├── notification-service/# Notificacoes in-app + device tokens
├── analytics-service/   # Event log, metricas, anomalias
└── docker-compose.yml   # Infra compartilhada + os dois stacks
```

**Infra**: PostgreSQL (banco), Redis (cache/locks), RabbitMQ (mensageria), Celery (tasks async), MinIO (object storage).

Detalhes da arquitetura de microservicos: [docs/back-end/microservices.md](docs/back-end/microservices.md).

---

## Setup do Ambiente

### Pre-requisitos

| Ferramenta | Versao | Windows | macOS | Linux |
|-----------|--------|---------|-------|-------|
| **Git** | 2.x+ | [git-scm.com](https://git-scm.com) | `brew install git` | `sudo apt install git` |
| **Docker Desktop** | 4.x+ | [docker.com](https://www.docker.com/products/docker-desktop) | [docker.com](https://www.docker.com/products/docker-desktop) | Ver abaixo |
| **Flutter SDK** | 3.x+ | [flutter.dev](https://docs.flutter.dev/get-started/install/windows) | [flutter.dev](https://docs.flutter.dev/get-started/install/macos) | [flutter.dev](https://docs.flutter.dev/get-started/install/linux) |
| **Make** | - | Via [chocolatey](https://chocolatey.org): `choco install make` | Ja incluso (Xcode CLI) | `sudo apt install make` |

> **Linux (Docker)**: Instale o Docker Engine + Docker Compose plugin:
> ```bash
> sudo apt install docker.io docker-compose-v2
> sudo usermod -aG docker $USER  # logout/login depois
> ```

### 1. Clonar o repositorio

```bash
git clone <url-do-repo> estuda_app
cd estuda_app
```

### 2. Setup do Backend

```bash
# Copiar variaveis de ambiente
cp back-end/.env.example back-end/.env

# Subir toda a stack (infra + legacy + os 7 microservicos)
make stack-up

# Criar os bancos por servico e aplicar as migracoes
make services-dbs
make services-migrate

# Verificar logs
make stack-logs SVC=api-gateway
```

A API do monolito, que e a que o app consome, fica em `http://localhost:8001`
(porta `API_PORT_EXTERNAL` do `back-end/.env`). O gateway dos microservicos
fica em `http://localhost:8100` e os servicos em 8101-8106 — veja
[docs/back-end/microservices.md](docs/back-end/microservices.md).

> Para mexer so no monolito, `make back-up` sobe a stack antiga sozinha. Nao
> misture com `make stack-up`: os dois compartilham infra, e `make back-down`
> derruba o Postgres/Redis/RabbitMQ debaixo dos servicos novos.

### 3. Setup do Frontend

```bash
# Instalar dependencias do Flutter
cd front-end-flutter
flutter pub get
cd ..

# Rodar o app
make front              # dispositivo padrao
make front-web          # Chrome
make front-linux        # Linux desktop
```

### 4. Verificar tudo

```bash
# Backend — monolito
make back-test          # testes
make back-lint          # linter

# Backend — microservicos
make services-test      # suite dos 8 projetos
make services-lint      # ruff em cada projeto

# Frontend
make front-analyze      # analise estatica
make front-test         # testes
```

---

## Comandos Disponiveis (Makefile)

Rode `make help` para ver todos. Resumo:

### Frontend

| Comando | Descricao |
|---------|-----------|
| `make front` | Roda o app Flutter (dispositivo padrao) |
| `make front-web` | Roda no Chrome |
| `make front-linux` | Roda no Linux desktop |
| `make front-analyze` | Analise estatica |
| `make front-test` | Testes |
| `make front-clean` | Limpa build |

### Backend

| Comando | Descricao |
|---------|-----------|
| `make back-up` | Sobe a stack (postgres, redis, rabbitmq, api, worker) |
| `make back-down` | Para a stack |
| `make back-logs` | Logs da API (use `SVC=worker` para o worker) |
| `make back-test` | Roda testes |
| `make back-lint` | Roda ruff check |
| `make back-format` | Roda ruff format |
| `make back-migrate` | Aplica migracoes Alembic |
| `make back-revision` | Cria nova migracao (`M="descricao"`) |
| `make back-sh` | Shell dentro do container da API |
| `make back-sync` | Sync deps no host (para IDE) |

### Microservicos

| Comando | Descricao |
|---------|-----------|
| `make stack-up` | Sobe o stack inteiro (legacy + microservicos) |
| `make stack-down` | Para o stack inteiro |
| `make stack-logs` | Logs de um servico (`SVC=analytics-service`) |
| `make services-dbs` | Cria os bancos por servico num volume existente |
| `make services-migrate` | Aplica as migracoes de cada servico com banco |
| `make services-seed` | Popula o catalogo do commerce (nunca executado — veja `docs/back-end/phase-2-debt.md`) |
| `make services-env` | Cria cada `.env` a partir do `.env.example` (obrigatorio num clone limpo) |
| `make services-test` | Roda a suite dos 8 projetos |
| `make services-lint` | Roda ruff em cada projeto |
| `make services-sync` | Sync deps de cada projeto no host (para IDE) |

---

## Stack Completa

Portas publicadas no host. A porta interna de todo container de API e 8000.

| Camada | Tecnologia | Porta |
|--------|-----------|-------|
| App mobile | Flutter/Dart | - |
| API do monolito (legacy) | FastAPI + Granian | 8001 |
| API Gateway | FastAPI | 8100 |
| Microservicos (6) | FastAPI | 8101-8106 |
| Banco de dados | PostgreSQL 17 | 5433 |
| Cache / Locks | Redis 8 | 6380 |
| Mensageria | RabbitMQ 4 | 5673 (AMQP), 15673 (UI) |
| Object storage | MinIO | 9000 (API), 9001 (console) |
| Tasks async | Celery 5 | - |

---

## Estrutura de Pastas

```
estuda_app/
├── front-end-flutter/       # App Flutter
│   ├── lib/                 # Codigo Dart
│   ├── assets/              # Imagens
│   ├── docs/                # Docs do frontend
│   └── pubspec.yaml
├── back-end/                # Backend Python (dois stacks lado a lado)
│   ├── legacy/              # Monolito modular — serve o app hoje
│   │   ├── app/             # Codigo da aplicacao
│   │   ├── alembic/         # Migracoes de banco
│   │   ├── tests/           # Testes
│   │   └── pyproject.toml
│   ├── packages/edu-common/ # JWT/auth + eventos RabbitMQ
│   ├── api-gateway/         # Proxy por prefixo de path
│   ├── auth-users-service/  # Um projeto uv por servico:
│   ├── learning-service/    #   pyproject.toml, alembic/, tests/, Dockerfile
│   ├── commerce-service/
│   ├── chatbot-service/
│   ├── notification-service/
│   ├── analytics-service/
│   ├── docker-compose.yml   # Infra compartilhada + os dois stacks
│   └── .env.example         # Contrato de variaveis (o .env nunca vai pro git)
├── Makefile                 # Comandos centralizados
├── CLAUDE.md                # Guidelines para AI/dev
└── README.md                # Este arquivo
```
