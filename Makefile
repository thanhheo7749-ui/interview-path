.PHONY: docker-build docker-up docker-down docker-logs docker-ps docker-build-speakcv docker-up-speakcv

COMPOSE = docker compose --env-file SpeakCV/.env
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
