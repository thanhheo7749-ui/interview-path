# Docker Packaging for SpeakCV and interviewpath-demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a workspace-level Docker workflow that starts SpeakCV and interviewpath-demo together without port conflicts, plus a root Makefile with simple commands for building and running the stack.

**Architecture:** Introduce a new root `docker-compose.yml` that defines all four services from the workspace root: SpeakCV frontend, SpeakCV backend, SpeakCV MySQL, and interviewpath-demo. Reuse SpeakCV's existing backend and frontend Dockerfiles with corrected root-relative build contexts, add a dev-oriented Dockerfile for interviewpath-demo, and add a root Makefile that wraps the shared Docker Compose commands.

**Tech Stack:** Docker Compose, Docker, FastAPI/Uvicorn, Next.js, MySQL 8, Vite/React, GNU Make

---

## File structure

### Files to create
- `docker-compose.yml` — workspace-level Compose entrypoint for all services.
- `Makefile` — workspace-level shortcuts for build/up/down/logs operations.
- `interviewpath/interviewpath-demo/Dockerfile` — dev-oriented container image for Vite.

### Files to modify
- `SpeakCV/src/backend/Dockerfile` — align container startup command with actual backend package path if current command is incorrect.
- `docs/superpowers/specs/2026-05-16-docker-packaging-design.md` — no content changes expected; reference only.

### Files to verify during implementation
- `SpeakCV/.env` — confirm required env vars exist for Compose substitution.
- `SpeakCV/src/frontend/package.json` — confirms Next.js start/build commands.
- `SpeakCV/src/backend/app/main.py` — confirms backend import path and allowed local origins.
- `interviewpath/interviewpath-demo/package.json` — confirms dev command and port behavior.

## Task 1: Fix the SpeakCV backend Docker startup path

**Files:**
- Modify: `SpeakCV/src/backend/Dockerfile`
- Verify: `SpeakCV/src/backend/app/main.py:1-123`
- Verify: `SpeakCV/src/backend/run_backend.py:1-35`

- [ ] **Step 1: Write the failing verification command**

The current backend Dockerfile ends with this command:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

First verify whether the current image boots successfully from the backend directory:

```bash
docker build -t speakcv-backend-check ./SpeakCV/src/backend && docker run --rm -p 18000:8000 speakcv-backend-check
```

Expected: if the package path is wrong, Uvicorn exits with an import error such as `Could not import module`.

- [ ] **Step 2: Update the Dockerfile to use the actual backend module path**

Replace the final command in `SpeakCV/src/backend/Dockerfile` with:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

If Step 1 already passes exactly as-is, keep the file unchanged and record that no fix was needed. If it fails because the code actually requires a different import path, change only the `CMD` line to the working module path discovered from the error output.

- [ ] **Step 3: Rebuild the backend image to verify it starts**

Run:

```bash
docker build -t speakcv-backend-check ./SpeakCV/src/backend
```

Expected: build succeeds.

- [ ] **Step 4: Run the rebuilt backend image to verify startup**

Run:

```bash
docker run --rm -p 18000:8000 speakcv-backend-check
```

Expected: Uvicorn starts and binds to `0.0.0.0:8000` without import errors.

- [ ] **Step 5: Commit**

```bash
git add SpeakCV/src/backend/Dockerfile
git commit -m "fix: align backend docker startup"
```

## Task 2: Add a Dockerfile for interviewpath-demo dev runtime

**Files:**
- Create: `interviewpath/interviewpath-demo/Dockerfile`
- Verify: `interviewpath/interviewpath-demo/package.json:1-23`

- [ ] **Step 1: Write the failing verification command**

Verify that the project currently has no Dockerfile and cannot yet be built as a Docker image:

```bash
docker build -t interviewpath-demo-dev ./interviewpath/interviewpath-demo
```

Expected: FAIL with `failed to read dockerfile` or equivalent because the file does not exist.

- [ ] **Step 2: Create the minimal development Dockerfile**

Create `interviewpath/interviewpath-demo/Dockerfile` with this content:

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
```

- [ ] **Step 3: Build the new interviewpath-demo image**

Run:

```bash
docker build -t interviewpath-demo-dev ./interviewpath/interviewpath-demo
```

Expected: build succeeds.

- [ ] **Step 4: Run the image and verify the Vite server starts**

Run:

```bash
docker run --rm -p 15173:5173 interviewpath-demo-dev
```

Expected: Vite starts and prints a local/network URL listening on port `5173`.

- [ ] **Step 5: Commit**

```bash
git add interviewpath/interviewpath-demo/Dockerfile
git commit -m "feat: dockerize interviewpath demo dev server"
```

## Task 3: Create the root docker-compose.yml for both projects

**Files:**
- Create: `docker-compose.yml`
- Verify: `SpeakCV/docker-compose.yml:4-52`
- Verify: `SpeakCV/src/frontend/Dockerfile:1-24`
- Verify: `SpeakCV/src/backend/Dockerfile`
- Verify: `interviewpath/interviewpath-demo/Dockerfile`

- [ ] **Step 1: Write the failing verification command**

Before creating the new root Compose file, verify that no workspace-level compose entrypoint exists:

```bash
docker compose -f ./docker-compose.yml config
```

Expected: FAIL with `no such file` or equivalent.

- [ ] **Step 2: Create the root Compose file**

Create `docker-compose.yml` at the workspace root with this content:

```yaml
services:
  speakcv-backend:
    build:
      context: ./SpeakCV/src/backend
    container_name: speakcv_backend
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL}
      OPENAI_MODEL_GPT4O_MINI: ${OPENAI_MODEL_GPT4O_MINI}
      OPENAI_MODEL_GPT4O: ${OPENAI_MODEL_GPT4O}
      GROQ_API_KEY: ${GROQ_API_KEY}
      ADMIN_EMAIL: ${ADMIN_EMAIL:-admin@gmail.com}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:-admin123}
      ADMIN_NAME: ${ADMIN_NAME:-Admin}

  speakcv-frontend:
    build:
      context: ./SpeakCV/src/frontend
      args:
        NEXT_PUBLIC_API_URL: http://localhost:8000
        NEXT_PUBLIC_GOOGLE_CLIENT_ID: ${NEXT_PUBLIC_GOOGLE_CLIENT_ID}
    container_name: speakcv_frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NEXT_PUBLIC_GOOGLE_CLIENT_ID: ${NEXT_PUBLIC_GOOGLE_CLIENT_ID}
      NODE_ENV: production
    depends_on:
      - speakcv-backend

  speakcv-db:
    image: mysql:8.0
    container_name: speakcv_db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-123}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-speakcv}
    ports:
      - "3306:3306"
    volumes:
      - speakcv_db_data:/var/lib/mysql

  interviewpath-demo:
    build:
      context: ./interviewpath/interviewpath-demo
    container_name: interviewpath_demo
    restart: unless-stopped
    ports:
      - "5173:5173"
    volumes:
      - ./interviewpath/interviewpath-demo:/app
      - interviewpath_node_modules:/app/node_modules
    command: ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

volumes:
  speakcv_db_data:
  interviewpath_node_modules:
```

- [ ] **Step 3: Render the Compose config to verify syntax**

Run:

```bash
docker compose config
```

Expected: outputs the fully rendered config with four services and two named volumes.

- [ ] **Step 4: Build all services from the root Compose file**

Run:

```bash
docker compose build
```

Expected: image builds succeed for `speakcv-backend`, `speakcv-frontend`, and `interviewpath-demo`.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add workspace docker compose"
```

## Task 4: Add a root Makefile for shared Docker commands

**Files:**
- Create: `Makefile`
- Verify: `SpeakCV/Makefile:1-87`
- Verify: `docker-compose.yml`

- [ ] **Step 1: Write the failing verification command**

Before creating the root Makefile, verify that workspace-level make targets do not exist:

```bash
make docker-up
```

Expected: FAIL with `No rule to make target 'docker-up'` or equivalent because there is no root Makefile yet.

- [ ] **Step 2: Create the root Makefile with Docker shortcuts**

Create `Makefile` at the workspace root with this content:

```makefile
.PHONY: docker-build docker-up docker-down docker-logs docker-ps

docker-build:
	docker compose build

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

docker-ps:
	docker compose ps
```

- [ ] **Step 3: Run the Makefile build target**

Run:

```bash
make docker-build
```

Expected: delegates to `docker compose build` and succeeds.

- [ ] **Step 4: Run the Makefile status target after startup**

Run:

```bash
make docker-up && make docker-ps
```

Expected: containers are created and `docker compose ps` lists all four services.

- [ ] **Step 5: Commit**

```bash
git add Makefile
git commit -m "feat: add root docker make targets"
```

## Task 5: Verify the shared runtime end-to-end

**Files:**
- Verify: `docker-compose.yml`
- Verify: `Makefile`
- Verify: `interviewpath/interviewpath-demo/Dockerfile`
- Verify: `SpeakCV/src/backend/Dockerfile`

- [ ] **Step 1: Start the full stack from the workspace root**

Run:

```bash
make docker-up
```

Expected: Compose builds any missing images and starts all services detached.

- [ ] **Step 2: Verify container status**

Run:

```bash
make docker-ps
```

Expected: `speakcv_backend`, `speakcv_frontend`, `speakcv_db`, and `interviewpath_demo` all appear in the status table.

- [ ] **Step 3: Verify each HTTP endpoint**

Run:

```bash
curl -I http://localhost:3000 && curl -I http://localhost:8000/docs && curl -I http://localhost:5173
```

Expected:
- `http://localhost:3000` returns an HTTP response from Next.js.
- `http://localhost:8000/docs` returns an HTTP response from FastAPI docs.
- `http://localhost:5173` returns an HTTP response from the Vite dev server.

- [ ] **Step 4: Shut the stack down cleanly**

Run:

```bash
make docker-down
```

Expected: all four containers stop and are removed; named volumes remain.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Makefile interviewpath/interviewpath-demo/Dockerfile SpeakCV/src/backend/Dockerfile
git commit -m "chore: verify shared docker workflow"
```

## Spec coverage check
- Single root Compose entrypoint: covered by Task 3.
- SpeakCV preserved as frontend/backend/db stack: covered by Task 3 and Task 5.
- interviewpath-demo added as a separate dev-oriented service on port 5173: covered by Task 2, Task 3, and Task 5.
- No reverse proxy or cross-app integration: preserved by Task 3 service definitions.
- Root Makefile with convenient commands: covered by Task 4.
- Startup verification from workspace root: covered by Task 5.

## Self-review notes
- No placeholders such as TBD/TODO remain.
- Every code-changing step includes concrete file content.
- The plan keeps scope limited to Docker packaging and root command ergonomics.
