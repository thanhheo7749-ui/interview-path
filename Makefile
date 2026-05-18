.PHONY: build up down logs ps docker-build docker-up docker-down docker-logs docker-ps docker-build-speakcv docker-up-speakcv prod-deploy prod-ps prod-logs prod-down

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
