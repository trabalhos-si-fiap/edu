FLUTTER = /home/elias/Documents/flutter/bin/flutter
FRONT_DIR = front-end-flutter
BACK_DIR = back-end
COMPOSE = docker compose
ADB = adb
# Host port the API is published on (see back-end/.env API_PORT_EXTERNAL).
API_PORT = 8001
# Base URL used by physical devices: adb reverse maps the device's localhost
# back to the host over USB, so the app talks to http://localhost:$(API_PORT).
DEVICE_API_URL = http://localhost:$(API_PORT)/api

# ── Frontend ──────────────────────────────────────────────

.PHONY: front front-web front-linux front-device adb-reverse front-devices front-analyze front-clean front-test

front: ## Run Flutter app (default device)
	cd $(FRONT_DIR) && $(FLUTTER) run

adb-reverse: ## Forward host API port to a USB device (re-run after replugging)
	$(ADB) reverse tcp:$(API_PORT) tcp:$(API_PORT)

front-device: adb-reverse ## Run Flutter on a USB phone, reaching the host API via adb reverse
	cd $(FRONT_DIR) && $(FLUTTER) run --dart-define=API_BASE_URL=$(DEVICE_API_URL)

front-web: ## Run Flutter app on Chrome
	cd $(FRONT_DIR) && $(FLUTTER) run -d chrome

front-linux: ## Run Flutter app on Linux desktop
	cd $(FRONT_DIR) && $(FLUTTER) run -d linux

front-devices: ## List available devices
	$(FLUTTER) devices

front-analyze: ## Run static analysis
	cd $(FRONT_DIR) && $(FLUTTER) analyze lib/

front-clean: ## Clean build artifacts
	cd $(FRONT_DIR) && $(FLUTTER) clean

front-test: ## Run Flutter tests
	cd $(FRONT_DIR) && $(FLUTTER) test

# ── Backend ───────────────────────────────────────────────

.PHONY: back-up back-down back-logs back-sh back-test back-test-e2e back-lint back-format back-migrate back-seed back-revision back-sync

back-up: ## Start backend stack (postgres, redis, rabbitmq, api, worker)
	cd $(BACK_DIR) && $(COMPOSE) up -d

back-down: ## Stop backend stack
	cd $(BACK_DIR) && $(COMPOSE) down

back-logs: ## Tail backend api logs (use SVC=worker for worker)
	cd $(BACK_DIR) && $(COMPOSE) logs -f $(or $(SVC),api)

back-sh: ## Open shell inside api container
	cd $(BACK_DIR) && $(COMPOSE) exec api bash

back-test: ## Run backend unit + integration tests inside the container (excludes e2e)
	cd $(BACK_DIR) && $(COMPOSE) exec api uv run pytest

back-test-e2e: ## Run e2e tests against the live stack (stack must be up via back-up)
	cd $(BACK_DIR) && $(COMPOSE) exec -e E2E_BASE_URL=http://localhost:8000 api uv run pytest -m e2e tests/e2e/

back-lint: ## Run ruff check
	cd $(BACK_DIR) && $(COMPOSE) exec api uv run ruff check .

back-format: ## Run ruff format
	cd $(BACK_DIR) && $(COMPOSE) exec api uv run ruff format .

back-migrate: ## Apply alembic migrations
	cd $(BACK_DIR) && $(COMPOSE) exec api uv run alembic upgrade head

back-seed: ## Seed the products catalog (idempotent)
	cd $(BACK_DIR) && $(COMPOSE) exec api uv run python -m app.seeds.products

back-revision: ## Create new alembic revision (use M="message")
	cd $(BACK_DIR) && $(COMPOSE) exec api uv run alembic revision --autogenerate -m "$(M)"

back-sync: ## Sync deps on host (for IDE support)
	cd $(BACK_DIR) && uv sync

# ── Help ──────────────────────────────────────────────────

.DEFAULT_GOAL := help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
