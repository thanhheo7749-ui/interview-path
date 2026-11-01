.PHONY: seed-samples docker-build docker-up docker-down docker-logs docker-ps docker-build-speakcv docker-up-speakcv docker-restart test reembed

BACKEND_DIR = SpeakCV/src/backend
BACKEND_PY = $(if $(wildcard $(BACKEND_DIR)/.venv/bin/python),.venv/bin/python,python3)

COMPOSE = docker compose --env-file .env
PROD_ENV ?= .omx/generated/vps.env
COMPOSE_PROD = docker compose --env-file $(PROD_ENV) -f docker-compose.prod.yml
SPEAKCV_SERVICES = db speakcv-backend speakcv-frontend

build: docker-build

up: docker-up

down: docker-down

logs: docker-logs

ps: docker-ps

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build -d

docker-build-speakcv:
	$(COMPOSE) build $(SPEAKCV_SERVICES)

docker-up-speakcv:
	$(COMPOSE) up --build -d $(SPEAKCV_SERVICES)

docker-down:
	$(COMPOSE) down

docker-restart:
	$(COMPOSE) down && $(COMPOSE) up --build -d

docker-logs:
	$(COMPOSE) logs -f

docker-ps:
	$(COMPOSE) ps

prod-deploy:
	bash scripts/vps-deploy.sh

prod-ps:
	$(COMPOSE_PROD) ps

prod-logs:
	$(COMPOSE_PROD) logs -f

prod-down:
	$(COMPOSE_PROD) down

test:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m pytest -q

# Calls the configured embedding vendor. Limit to one company with COMPANY=<slug>.
reembed:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.cli reembed $(if $(COMPANY),--company $(COMPANY))

# Creates the two fictional sample companies. Pass ARGS=--auto-approve to publish them, ARGS="--only sori-labs" for one.
seed-samples:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.cli seed-samples $(ARGS)
