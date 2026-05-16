.PHONY: docker-build docker-up docker-down docker-logs docker-ps docker-build-speakcv docker-up-speakcv prod-deploy prod-ps prod-logs prod-down

COMPOSE = docker compose --env-file SpeakCV/.env
COMPOSE_PROD = docker compose --env-file .env.production -f docker-compose.prod.yml
SPEAKCV_SERVICES = db speakcv-backend speakcv-frontend

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
