FRONT_DIR = front-end-flutter
BACK_ROOT = back-end
COMPOSE = docker compose
ADB = adb

# Resolve the Flutter binary in an environment-agnostic way:
#   1. honor an explicit override (env var or `make front FLUTTER=/path/to/flutter`)
#   2. otherwise pick it up from PATH
#   3. otherwise scan common install locations across Linux/macOS
#   4. fall back to the literal `flutter` so the error message is obvious
FLUTTER ?= $(shell \
	command -v flutter 2>/dev/null || \
	for p in "$$HOME/flutter/bin/flutter" "$$HOME/Documents/flutter/bin/flutter" \
	         "$$HOME/development/flutter/bin/flutter" "$$HOME/fvm/default/bin/flutter" \
	         "/opt/flutter/bin/flutter" "/usr/local/bin/flutter" "/snap/bin/flutter"; do \
		[ -x "$$p" ] && { echo "$$p"; break; }; \
	done)
FLUTTER := $(or $(FLUTTER),flutter)

# Host port the API Gateway is published on — the port the Flutter app talks
# to. Read from $(BACK_ROOT)/.env (GATEWAY_PORT_EXTERNAL), which is 8100 both
# in the working .env and in .env.example. Override with: make front API_PORT=8100
#
# The literal below is only reached when back-end/.env is missing entirely. It
# is 8100 to match the compose default. Never make it 8000: another project on
# this machine holds that port, so falling back to it would reach a different
# backend and return wrong data instead of failing to connect.
API_PORT := $(shell sed -n 's/^GATEWAY_PORT_EXTERNAL=//p' $(BACK_ROOT)/.env 2>/dev/null | tr -d '[:space:]')
API_PORT := $(or $(API_PORT),8100)

# Host LAN IP, auto-detected for the current OS (Linux or macOS). Every target
# on the same Wi-Fi — physical iPhone/Android, iOS simulator, Android emulator,
# desktop — can reach the host at this address, so a single `make front` works
# everywhere. Override manually with: make front HOST_IP=192.168.x.y
HOST_IP := $(shell \
	if [ "$$(uname)" = "Darwin" ]; then \
		ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null; \
	else \
		ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($$i=="src"){print $$(i+1); exit}}'; \
	fi)
HOST_API_URL = http://$(HOST_IP):$(API_PORT)/api

# Base URL used by physical devices: adb reverse maps the device's localhost
# back to the host over USB, so the app talks to http://localhost:$(API_PORT).
DEVICE_API_URL = http://localhost:$(API_PORT)/api

# ── Frontend ──────────────────────────────────────────────

.PHONY: front front-demo front-web front-linux front-device adb-reverse front-devices front-analyze front-clean front-test

front: ## Run Flutter app on any device over Wi-Fi (auto-detects host LAN IP)
	@test -n "$(HOST_IP)" || { echo "Could not auto-detect the host LAN IP. Run: make front HOST_IP=192.168.x.y"; exit 1; }
	@echo "→ API_BASE_URL=$(HOST_API_URL)"
	cd $(FRONT_DIR) && $(FLUTTER) run --dart-define=API_BASE_URL=$(HOST_API_URL)

front-demo: ## Run the Flutter app with the presentation-only demo flags
	@test -n "$(HOST_IP)" || { echo "Could not auto-detect the host LAN IP. Run: make front-demo HOST_IP=192.168.x.y"; exit 1; }
	cd $(FRONT_DIR) && $(FLUTTER) run \
		--dart-define=API_BASE_URL=$(HOST_API_URL) \
		--dart-define=DEMO_MULTI_SESSAO=true

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

# ── Microservices stack ───────────────────────────────────
#
# Host ports: gateway on GATEWAY_PORT_EXTERNAL (8100 here), the six services
# fixed on 8101-8106.

SERVICES := packages/edu-common api-gateway auth-users-service learning-service commerce-service chatbot-service notification-service analytics-service
DB_SERVICES := auth-users-service learning-service commerce-service notification-service analytics-service chatbot-service

.PHONY: stack-up stack-rebuild stack-down stack-logs services-env services-dbs services-migrate services-seed services-seed-demo services-test services-lint services-sync

stack-rebuild: ## Rebuild every service image (needed after pulling code changes — see docs/back-end/microservices.md §5)
	cd $(BACK_ROOT) && $(COMPOSE) build

stack-up: ## Start the whole backend stack (run stack-rebuild first if the images may be stale)
	@echo "→ R2_PUBLIC_ENDPOINT_URL host: $(if $(HOST_IP),$(HOST_IP),10.0.2.2 (emulator fallback — set HOST_IP for physical devices))"
	cd $(BACK_ROOT) && HOST_IP=$(HOST_IP) $(COMPOSE) up -d

stack-down: ## Stop the whole backend stack
	cd $(BACK_ROOT) && $(COMPOSE) down

stack-logs: ## Tail logs of one stack service (use SVC=analytics-service)
	cd $(BACK_ROOT) && $(COMPOSE) logs -f $(or $(SVC),api-gateway)

services-dbs: ## Create the per-service databases on an existing volume
	cd $(BACK_ROOT) && $(COMPOSE) exec -T postgres bash < scripts/create-service-databases.sh

services-migrate: ## Apply alembic migrations on every service that has a database
	@for s in $(DB_SERVICES); do \
		echo "→ $$s"; \
		(cd $(BACK_ROOT) && $(COMPOSE) exec -T $$s uv run alembic upgrade head) || exit 1; \
	done

services-seed: ## Seed the commerce catalog and partners (idempotent; downloads photos into MinIO)
	cd $(BACK_ROOT) && $(COMPOSE) exec -T commerce-service uv run python -m app.seeds.products
	cd $(BACK_ROOT) && $(COMPOSE) exec -T commerce-service uv run python -m app.seeds.parceiros

services-seed-demo: ## Seed the four demo accounts (needs DEMO_ACCOUNTS_PASSWORD)
	@test -n "$(DEMO_ACCOUNTS_PASSWORD)" || \
	  { echo "defina DEMO_ACCOUNTS_PASSWORD antes de rodar"; exit 1; }
	@cd $(BACK_ROOT) && $(COMPOSE) exec -T \
	  -e DEMO_ACCOUNTS_PASSWORD='$(DEMO_ACCOUNTS_PASSWORD)' \
	  auth-users-service uv run python -m app.seeds.demo_accounts

# Cada serviço lê o .env do próprio diretório quando roda no host (fora do
# compose, que injeta tudo por environment). Os campos obrigatórios não têm
# default, então num clone limpo `uv run pytest` estoura no import — não numa
# assertion, o que torna o sintoma confuso. Este alvo cria o que falta a partir
# do .env.example e NUNCA sobrescreve um .env existente.
services-env: ## Create each service's .env from its .env.example (never overwrites)
	@for s in $(SERVICES); do \
		if [ -f $(BACK_ROOT)/$$s/.env.example ] && [ ! -f $(BACK_ROOT)/$$s/.env ]; then \
			cp $(BACK_ROOT)/$$s/.env.example $(BACK_ROOT)/$$s/.env; \
			echo "criado  $$s/.env"; \
		else \
			echo "mantido $$s/.env"; \
		fi; \
	done

services-test: ## Run every service test suite on the host (run services-env first on a clean clone)
	@for s in $(SERVICES); do \
		echo "→ $$s"; \
		(cd $(BACK_ROOT)/$$s && uv run pytest -q) || exit 1; \
	done

services-lint: ## Run ruff across every service
	@for s in $(SERVICES); do \
		echo "→ $$s"; \
		(cd $(BACK_ROOT)/$$s && uv run ruff check .) || exit 1; \
	done

services-sync: ## Sync deps of every service on the host (for IDE support)
	@for s in $(SERVICES); do (cd $(BACK_ROOT)/$$s && uv sync) || exit 1; done

# ── Demo ──────────────────────────────────────────────────

.PHONY: demo demo-web demo-test

# ARGS repassa opções ao roteiro, ex.: make demo ARGS="--skip-build --pausa 3"
# O uv instala o uiautomator2 (a leitura rápida da tela) num ambiente à parte.
demo: ## Run the whole demo script on a connected Android (needs DEMO_ACCOUNTS_PASSWORD)
	@test -n "$(DEMO_ACCOUNTS_PASSWORD)" || \
	  { echo "defina DEMO_ACCOUNTS_PASSWORD antes de rodar"; exit 1; }
	@cd scripts && DEMO_ACCOUNTS_PASSWORD='$(DEMO_ACCOUNTS_PASSWORD)' \
	  uv run --no-project --with uiautomator2==3.7.0 python -m demo_roteiro $(ARGS)

# Precisa do painel no ar (cd web-admin && npm start). O uv instala o Playwright
# na versão cujo Chromium já está no cache; noutra máquina, o script diz como baixar.
demo-web: ## Run the web admin panel demo in a visible Chromium (needs DEMO_ACCOUNTS_PASSWORD)
	@test -n "$(DEMO_ACCOUNTS_PASSWORD)" || \
	  { echo "defina DEMO_ACCOUNTS_PASSWORD antes de rodar"; exit 1; }
	@cd scripts && DEMO_ACCOUNTS_PASSWORD='$(DEMO_ACCOUNTS_PASSWORD)' \
	  uv run --no-project --with playwright==1.61.0 python -m demo_web $(ARGS)

demo-test: ## Run the demo script unit tests
	cd scripts && python3 -m unittest discover -s tests -t .

# ── Help ──────────────────────────────────────────────────

.DEFAULT_GOAL := help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
