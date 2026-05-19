.PHONY: docker-build docker-up docker-down docker-logs docker-ps docker-build-speakcv docker-up-speakcv docker-restart

COMPOSE = docker compose --env-file SpeakCV/.env

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build -d

docker-down:
	$(COMPOSE) down

docker-restart:
	$(COMPOSE) down && $(COMPOSE) up --build -d

docker-logs:
	$(COMPOSE) logs -f

docker-ps:
	$(COMPOSE) ps
