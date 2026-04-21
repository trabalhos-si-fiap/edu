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

API em **Python 3.12** com **FastAPI** (async), servida pelo **Granian**. Estrutura modular preparada para microservicos:

```
app/
├── core/                # Config, database, celery, logging
├── bff/                 # Backend for Frontend (agregacao)
├── modules/             # Modulos de dominio (futuros microservicos)
└── main.py              # Entry point FastAPI
```

**Infra**: PostgreSQL (banco), Redis (cache/locks), RabbitMQ (mensageria), Celery (tasks async).

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

# Subir toda a stack (postgres, redis, rabbitmq, api, worker)
make back-up

# Rodar migracoes do banco
make back-migrate

# Verificar logs
make back-logs
```

A API estara disponivel em `http://localhost:8000`.

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
# Backend
make back-test          # testes
make back-lint          # linter

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

---

## Stack Completa

| Camada | Tecnologia | Porta |
|--------|-----------|-------|
| App mobile | Flutter/Dart | - |
| API | FastAPI + Granian | 8000 |
| Banco de dados | PostgreSQL 17 | 5432 |
| Cache / Locks | Redis 8 | 6379 |
| Mensageria | RabbitMQ 4 | 5672 (AMQP), 15672 (UI) |
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
├── back-end/                # API Python
│   ├── app/                 # Codigo da aplicacao
│   ├── alembic/             # Migracoes de banco
│   ├── tests/               # Testes
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── pyproject.toml
├── Makefile                 # Comandos centralizados
├── CLAUDE.md                # Guidelines para AI/dev
└── README.md                # Este arquivo
```
