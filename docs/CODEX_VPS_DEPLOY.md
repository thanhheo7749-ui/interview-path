# Codex VPS Deployment Guide

Use this file on the VPS after cloning the private GitHub repository.

## Target Routing

The production stack runs in direct-port mode by default, so it can be copied to a VPS and started without DNS first:

- `http://VPS_PUBLIC_IP:5173` serves `interviewpath-demo` as the main UI.
- `http://VPS_PUBLIC_IP:3000` serves the SpeakCV Next.js frontend.
- `http://VPS_PUBLIC_IP:8000/docs` serves the SpeakCV FastAPI docs.

Optional HTTPS/domain mode is still available by setting `ENABLE_PROXY=1` and filling these values:

- `https://PRIMARY_DOMAIN` serves `interviewpath-demo`.
- `https://SPEAKCV_DOMAIN` serves the SpeakCV frontend.
- `https://API_DOMAIN` serves the FastAPI backend.

Recommended DNS records:

```txt
A  @        VPS_PUBLIC_IP
A  speakcv  VPS_PUBLIC_IP
A  api      VPS_PUBLIC_IP
```

If the DNS provider uses `@` for the root domain, point it to the VPS public IP.

## Files Used

- `.env` - root-level VPS env file with build/runtime keys.
- `docker-compose.prod.yml` - production Docker Compose stack.
- `deploy/Caddyfile` - HTTPS reverse proxy routing.
- `scripts/sync-vps-env.sh` - copies usable keys from `SpeakCV/.env` into `.env`.
- `scripts/vps-deploy.sh` - validation plus build/start command.
- `interviewpath/interviewpath-demo/Dockerfile.prod` - static production image for the main UI.

## First-Time VPS Setup

Install Docker and the Compose plugin if the VPS does not already have them:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker
```

Clone the repository:

```bash
git clone <PRIVATE_GITHUB_REPO_URL> interview-path
cd interview-path
```

## Configure Production Env

The root `.env` is generated with the needed keys:

```bash
bash scripts/sync-vps-env.sh
```

By default it sets:

```txt
ENABLE_PROXY=0
PUBLIC_HOST=auto
INTERVIEWPATH_PORT=5173
SPEAKCV_FRONTEND_PORT=3000
SPEAKCV_BACKEND_PORT=8000
```

`PUBLIC_HOST=auto` lets `scripts/vps-deploy.sh` detect the VPS public IP and generate the build URLs before Docker Compose runs.

To use domain/HTTPS mode, edit `.env`:

```txt
ENABLE_PROXY=1
PRIMARY_DOMAIN=yourdomain.com
SPEAKCV_DOMAIN=speakcv.yourdomain.com
API_DOMAIN=api.yourdomain.com
```

If Google login is used, set this before deploy:

```txt
NEXT_PUBLIC_GOOGLE_CLIENT_ID=<google-client-id>
```

The production compose file reads `.env` only. It no longer depends on `SpeakCV/.env` being present on the VPS.

## Deploy

Run:

```bash
bash scripts/vps-deploy.sh
```

The script validates required values, renders the Compose config, builds images, starts containers, and prints the service URLs.

Build without starting containers:

```bash
bash scripts/vps-deploy.sh build
```

Validate Compose only:

```bash
bash scripts/vps-deploy.sh config
```

Equivalent Make command:

```bash
make prod-deploy
```

## Verify

Check containers:

```bash
docker compose --env-file .env -f docker-compose.prod.yml ps
```

Open:

```txt
http://VPS_PUBLIC_IP:5173
http://VPS_PUBLIC_IP:3000
http://VPS_PUBLIC_IP:8000/docs
```

From the InterviewPath sidebar, the Candidate Interview Link should open:

```txt
http://VPS_PUBLIC_IP:3000/login
```

## Update Deployment

After pulling new code:

```bash
git pull
bash scripts/vps-deploy.sh
```

View logs:

```bash
make prod-logs
```

Stop production containers:

```bash
make prod-down
```

## Notes For Codex On VPS

If asked to deploy autonomously:

1. Read `.env`.
2. Run `bash scripts/sync-vps-env.sh` if keys need to be refreshed from `SpeakCV/.env`.
3. Run `bash scripts/vps-deploy.sh`.
4. Verify with `docker compose --env-file .omx/generated/vps.env -f docker-compose.prod.yml ps`.
5. Report the three URLs and any failing container logs.
