# Codex VPS Deployment Guide

Use this file on the VPS after cloning the private GitHub repository.

## Target Routing

The production stack is configured for one root domain plus two subdomains:

- `https://PRIMARY_DOMAIN` serves `interviewpath-demo` as the main UI.
- `https://SPEAKCV_DOMAIN` serves the SpeakCV Next.js frontend.
- `https://API_DOMAIN` serves the SpeakCV FastAPI backend.

Recommended DNS records:

```txt
A  @        VPS_PUBLIC_IP
A  speakcv  VPS_PUBLIC_IP
A  api      VPS_PUBLIC_IP
```

If the DNS provider uses `@` for the root domain, point it to the VPS public IP.

## Files Used

- `.env.production` - production domains, database URL, JWT/admin settings.
- `docker-compose.prod.yml` - production Docker Compose stack.
- `deploy/Caddyfile` - HTTPS reverse proxy routing.
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

Edit `.env.production` and replace all placeholder values:

```bash
nano .env.production
```

Minimum required changes:

```txt
PRIMARY_DOMAIN=yourdomain.com
SPEAKCV_DOMAIN=speakcv.yourdomain.com
API_DOMAIN=api.yourdomain.com

VITE_SPEAKCV_URL=https://speakcv.yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
CORS_ORIGINS=https://yourdomain.com,https://speakcv.yourdomain.com
VNPAY_RETURN_URL=https://speakcv.yourdomain.com/upgrade/success

MYSQL_ROOT_PASSWORD=<strong-mysql-password>
DATABASE_URL=mysql+pymysql://root:<strong-mysql-password>@db:3306/speakcv
SECRET_KEY=<strong-random-secret>
ADMIN_PASSWORD=<strong-admin-password>
```

Keep `DATABASE_URL` and `MYSQL_ROOT_PASSWORD` in sync.

If Google login is used, set:

```txt
NEXT_PUBLIC_GOOGLE_CLIENT_ID=<google-client-id>
```

The production compose file also loads `SpeakCV/.env`, so existing AI provider keys from the private repository are still passed to the backend.

## Deploy

Run:

```bash
bash scripts/vps-deploy.sh
```

The script validates required values, renders the Compose config, builds images, starts containers, and prints the service URLs.

Equivalent Make command:

```bash
make prod-deploy
```

## Verify

Check containers:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Open:

```txt
https://yourdomain.com
https://speakcv.yourdomain.com
https://api.yourdomain.com/docs
```

From the InterviewPath sidebar, the Candidate Interview Link should open:

```txt
https://speakcv.yourdomain.com/login
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

1. Read `.env.production`.
2. Replace `example.com` and `change-this-*` placeholders with the real VPS/domain values provided by the user.
3. Confirm DNS records point to the VPS public IP.
4. Run `bash scripts/vps-deploy.sh`.
5. Verify with `docker compose --env-file .env.production -f docker-compose.prod.yml ps`.
6. Report the three URLs and any failing container logs.
