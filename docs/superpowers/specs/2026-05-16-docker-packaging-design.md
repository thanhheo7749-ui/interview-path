# Docker packaging design for SpeakCV and interviewpath-demo

## Goal
Provide a single Docker Compose entrypoint at the workspace root so both projects can be started together without port conflicts, while allowing the user to open and use both apps at the same time.

## Scope
- Add one root-level `docker-compose.yml` in the workspace.
- Keep SpeakCV running as its existing multi-service stack: frontend, backend, and database.
- Add `interviewpath/interviewpath-demo` as a separate service in the same Compose file.
- Run `interviewpath-demo` in a development-oriented container.
- Expose each app on its own host port so both can be opened simultaneously.

## Non-goals
- No reverse proxy between the two projects.
- No routing both apps through a single hostname.
- No runtime integration where `interviewpath-demo` calls SpeakCV services unless that is requested later.
- No production hardening for `interviewpath-demo` in this task.

## Current state
### SpeakCV
- Repository already contains a Compose file at `SpeakCV/docker-compose.yml`.
- The Compose file defines `backend`, `frontend`, and `db` services.
- The existing file assumes build contexts under `SpeakCV/src/backend` and `SpeakCV/src/frontend`.
- The frontend is exposed on port 3000 and backend on port 8000.
- Environment variable naming appears slightly inconsistent for the Google client id between build args and runtime env, so this should be checked during implementation.

### interviewpath-demo
- This is a Vite React application under `interviewpath/interviewpath-demo`.
- It currently has no Docker packaging.
- It already supports dev serving on all interfaces through `vite --host 0.0.0.0`.

## Recommended approach
Create a new root-level `docker-compose.yml` at the workspace level and define all services there.

Why this approach:
- One command starts both projects.
- Ports remain explicit and isolated.
- The user can open SpeakCV and interviewpath-demo at the same time without conflicts.
- It avoids coupling interviewpath-demo to SpeakCV's internal project folder structure more than necessary.

## Alternatives considered
### 1. Extend `SpeakCV/docker-compose.yml` to include interviewpath-demo
Pros:
- Reuses the existing SpeakCV Compose file directly.
- Fewer top-level files.

Cons:
- Makes SpeakCV's own project config depend on a sibling project outside its directory.
- Less clear as the workspace grows.

### 2. Keep separate Compose files and add an override for joint startup
Pros:
- Better separation per project.
- Scales well if each project evolves independently.

Cons:
- More files and more commands.
- Adds unnecessary complexity for the current goal.

## Target runtime layout
### Host ports
- SpeakCV frontend: `localhost:3000`
- SpeakCV backend: `localhost:8000`
- interviewpath-demo: `localhost:5173`

### Services
- `speakcv-backend`
- `speakcv-frontend`
- `speakcv-db`
- `interviewpath-demo`

### Network
- Use the default Compose network created by the root Compose file.
- No custom cross-service hostname dependencies are required for interviewpath-demo.

## Container design
### SpeakCV services
- Recreate the existing SpeakCV services in the new root Compose file using workspace-relative build contexts.
- Preserve the current environment variables and port mappings unless a correction is required for the combined setup.
- Preserve the database volume for MySQL persistence.

### interviewpath-demo service
- Add a dedicated `Dockerfile` inside `interviewpath/interviewpath-demo`.
- Base image should be a Node image suitable for Vite development.
- Install dependencies from `package.json` and `package-lock.json`.
- Start the app with the existing dev command so file watching and quick iteration continue to work.
- Expose port 5173 from the container to the host.

### Source mounting
For the dev-oriented `interviewpath-demo` container:
- Mount the project source directory into the container.
- Keep container-managed `node_modules` isolated from the host to avoid Windows path and permission issues.

## Data flow and behavior
- The user runs one command from the workspace root to start all containers.
- Docker Compose starts SpeakCV frontend, backend, database, and interviewpath-demo together.
- The user accesses:
  - SpeakCV at `http://localhost:3000`
  - interviewpath-demo at `http://localhost:5173`
- Since each app binds to a separate port, the user can interact with one while leaving the other open in another tab or window.

## Error handling expectations
- Port collisions should be avoided by explicitly assigning unique host ports.
- If SpeakCV depends on environment variables from `.env`, the root Compose file should either reference the same values or document that startup requires them to exist.
- If Docker Desktop file watching is slow on Windows, that is acceptable for the first version because the goal is operational coexistence, not optimized live-reload performance.

## Testing and verification
Implementation will be considered successful when:
1. `docker compose up --build` from the workspace root starts all services.
2. SpeakCV frontend is reachable on port 3000.
3. SpeakCV backend is reachable on port 8000.
4. interviewpath-demo is reachable on port 5173.
5. No service fails because of conflicting container names, ports, or invalid relative build paths.

## Implementation notes
- Prefer replacing direct reuse of `SpeakCV/docker-compose.yml` with a new workspace-level compose file rather than nesting Compose files.
- Keep changes minimal and limited to Docker packaging.
- If the existing SpeakCV Compose file is left in place, it should remain untouched unless a small consistency fix is required.
- If implementation reveals that SpeakCV's existing Docker build paths or env names are broken, fix only the issues necessary for the shared root compose to run.

## Deliverables
- Root-level `docker-compose.yml`
- Docker support for `interviewpath/interviewpath-demo`
- Any minimal Docker-related adjustments required for SpeakCV to run correctly from the shared root compose
