.PHONY: docker-build docker-up docker-down docker-logs docker-ps

COMPOSE = docker compose --env-file SpeakCV/.env

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build -d

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f

docker-ps:
	$(COMPOSE) ps
