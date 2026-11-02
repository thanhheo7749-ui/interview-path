.PHONY: eval-brain eval-discrimination eval-stt seed-samples docker-build docker-up docker-down docker-logs docker-ps docker-build-speakcv docker-up-speakcv docker-restart test test-mysql reembed simulate-hiring

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

# Starts a throwaway mysql:8.0 container on a free port, runs tests/mysql against it, and always removes it.
test-mysql:
	bash scripts/test-mysql.sh

# Calls the configured embedding vendor. Limit to one company with COMPANY=<slug>.
reembed:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.cli reembed $(if $(COMPANY),--company $(COMPANY))

# Creates the two fictional sample companies. Pass ARGS=--auto-approve to publish them, ARGS="--only sori-labs" for one.
seed-samples:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.cli seed-samples $(ARGS)

# Replaces a sample company's labelled simulated hiring data. No AI calls, and refused for any other company.
# Pass COMPANY=<slug> (default sori-labs) and SEED=<number> (default 42).
simulate-hiring:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.cli simulate-hiring --company $(or $(COMPANY),sori-labs) --seed $(or $(SEED),42)

# Measures the Company Brain against labelled ground truth. Prints an estimated cost first and asks before spending.
# Pass ARGS=--dry-run, ARGS=--yes or ARGS="--profile fake".
eval-brain:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m eval.brain.run $(ARGS)

# Measures the discrimination guard (rules, then rules plus classifier) on labelled statements in Vietnamese, English and Korean.
# Prints an estimated cost first and asks before spending. Pass ARGS=--dry-run, ARGS=--yes or ARGS="--profile fake".
eval-discrimination:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m eval.discrimination.run $(ARGS)

# Benchmarks speech-to-text on the clips in eval/stt/clips. Prints an estimated cost first and asks before spending.
# Pass ARGS=--dry-run, ARGS=--yes or ARGS="--profile fake" (the fake profile measures nothing).
eval-stt:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m eval.stt.run $(ARGS)

.PHONY: e2e eval-plan-overlap

# Compares the question plans for the same CV at both sample companies. Prints an estimated cost first and asks before spending.
# Pass ARGS=--dry-run, ARGS=--yes or ARGS="--profile fake" (the fake profile shows templates only).
eval-plan-overlap:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m eval.plans.run $(ARGS)

# The full hiring loop in a real browser: candidate app, HR portal and backend on the fake AI provider.
# Needs the backend venv, `npm ci` in interviewpath/interviewpath-demo and SpeakCV/src/frontend, and `npx playwright install chromium`.
e2e:
	cd interviewpath/interviewpath-demo && npx playwright test --reporter=line
