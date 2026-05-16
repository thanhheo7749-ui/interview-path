#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy or create it before deploying." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not available in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available. Install the docker compose plugin." >&2
  exit 1
fi

read_env() {
  local key="$1"
  awk -F= -v key="$key" '
    $0 ~ /^[[:space:]]*#/ { next }
    $1 == key {
      sub(/^[^=]*=/, "")
      gsub(/^["'\'']|["'\'']$/, "")
      print
      exit
    }
  ' "$ENV_FILE"
}

require_value() {
  local key="$1"
  local value
  value="$(read_env "$key")"

  if [[ -z "$value" ]]; then
    echo "Missing required value: $key in $ENV_FILE" >&2
    exit 1
  fi

  case "$value" in
    example.com|*.example.com|change-this*)
      echo "Replace placeholder value for $key in $ENV_FILE: $value" >&2
      exit 1
      ;;
  esac
}

required_keys=(
  PRIMARY_DOMAIN
  SPEAKCV_DOMAIN
  API_DOMAIN
  VITE_SPEAKCV_URL
  NEXT_PUBLIC_API_URL
  CORS_ORIGINS
  MYSQL_DATABASE
  MYSQL_ROOT_PASSWORD
  DATABASE_URL
  SECRET_KEY
  ADMIN_EMAIL
  ADMIN_PASSWORD
)

for key in "${required_keys[@]}"; do
  require_value "$key"
done

echo "Validating production compose file..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/dev/null

echo "Building and starting production services..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

echo "Production services:"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo
echo "Deployment command finished."
echo "Open: https://$(read_env PRIMARY_DOMAIN)"
echo "SpeakCV: https://$(read_env SPEAKCV_DOMAIN)"
echo "API docs: https://$(read_env API_DOMAIN)/docs"
