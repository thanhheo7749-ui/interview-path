#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
RESOLVED_ENV_FILE="${RESOLVED_ENV_FILE:-.omx/generated/vps.env}"
MODE="${1:-deploy}"

case "$MODE" in
  deploy|--deploy) MODE="deploy" ;;
  build|--build|--build-only) MODE="build" ;;
  config|--config|--config-only) MODE="config" ;;
  *)
    echo "Usage: $0 [deploy|build|config]" >&2
    exit 1
    ;;
esac

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Creating it from available local env values..." >&2
fi

bash scripts/sync-vps-env.sh >/dev/null

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
  local file="${2:-$ENV_FILE}"

  awk -F= -v key="$key" '
    $0 ~ /^[[:space:]]*#/ { next }
    $1 == key {
      sub(/^[^=]*=/, "")
      gsub(/^["'\'']|["'\'']$/, "")
      print
      exit
    }
  ' "$file"
}

is_placeholder() {
  local value="${1:-}"

  [[ -z "$value" ]] && return 0
  [[ "$value" == "auto" ]] && return 0
  [[ "$value" == "example.com" ]] && return 0
  [[ "$value" == *".example.com" ]] && return 0
  [[ "$value" == *change-this* ]] && return 0
  [[ "$value" == *your-* ]] && return 0
  [[ "$value" == *sk-your-* ]] && return 0
  [[ "$value" == *gsk_your-* ]] && return 0
  [[ "$value" == "YOUR_GOOGLE_CLIENT_ID" ]] && return 0

  return 1
}

require_value() {
  local key="$1"
  local value
  value="$(read_env "$key")"

  if is_placeholder "$value"; then
    echo "Missing required value: $key in $ENV_FILE" >&2
    exit 1
  fi
}

detect_public_host() {
  local host

  host="$(read_env PUBLIC_HOST)"
  if ! is_placeholder "$host"; then
    printf '%s\n' "$host"
    return 0
  fi

  if command -v curl >/dev/null 2>&1; then
    host="$(curl -4fsS --max-time 4 https://api.ipify.org 2>/dev/null || true)"
    if [[ -n "$host" ]]; then
      printf '%s\n' "$host"
      return 0
    fi
  fi

  host="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -n "$host" ]]; then
    printf '%s\n' "$host"
    return 0
  fi

  printf '%s\n' "localhost"
}

write_resolved_env() {
  local enable_proxy public_host demo_port frontend_port backend_port
  local primary_domain speakcv_domain api_domain
  local vite_speakcv_url next_public_api_url cors_origins vnpay_return_url

  enable_proxy="$(read_env ENABLE_PROXY)"
  demo_port="$(read_env INTERVIEWPATH_PORT)"
  frontend_port="$(read_env SPEAKCV_FRONTEND_PORT)"
  backend_port="$(read_env SPEAKCV_BACKEND_PORT)"

  [[ -n "$demo_port" ]] || demo_port="5173"
  [[ -n "$frontend_port" ]] || frontend_port="3000"
  [[ -n "$backend_port" ]] || backend_port="8000"

  if [[ "$enable_proxy" == "1" ]]; then
    primary_domain="$(read_env PRIMARY_DOMAIN)"
    speakcv_domain="$(read_env SPEAKCV_DOMAIN)"
    api_domain="$(read_env API_DOMAIN)"

    for key in PRIMARY_DOMAIN SPEAKCV_DOMAIN API_DOMAIN; do
      require_value "$key"
    done

    public_host="$primary_domain"
    vite_speakcv_url="https://${speakcv_domain}"
    next_public_api_url="https://${api_domain}"
    cors_origins="https://${primary_domain},https://${speakcv_domain}"
    vnpay_return_url="https://${speakcv_domain}/upgrade/success"
  else
    public_host="$(detect_public_host)"
    vite_speakcv_url="http://${public_host}:${frontend_port}"
    next_public_api_url="http://${public_host}:${backend_port}"
    cors_origins="http://${public_host}:${frontend_port},http://${public_host}:${demo_port}"
    vnpay_return_url="http://${public_host}:${frontend_port}/upgrade/success"
  fi

  mkdir -p "$(dirname "$RESOLVED_ENV_FILE")"
  cp "$ENV_FILE" "$RESOLVED_ENV_FILE"
  chmod 600 "$RESOLVED_ENV_FILE"

  set_key() {
    local key="$1"
    local value="$2"

    if grep -qE "^${key}=" "$RESOLVED_ENV_FILE"; then
      perl -0pi -e "s#^${key}=.*#${key}=${value}#m" "$RESOLVED_ENV_FILE"
    else
      printf '%s=%s\n' "$key" "$value" >>"$RESOLVED_ENV_FILE"
    fi
  }

  set_key PUBLIC_HOST "$public_host"
  set_key INTERVIEWPATH_PORT "$demo_port"
  set_key SPEAKCV_FRONTEND_PORT "$frontend_port"
  set_key SPEAKCV_BACKEND_PORT "$backend_port"
  set_key VITE_SPEAKCV_URL "$vite_speakcv_url"
  set_key NEXT_PUBLIC_API_URL "$next_public_api_url"
  set_key CORS_ORIGINS "$cors_origins"
  set_key VNPAY_RETURN_URL "$vnpay_return_url"
}

required_keys=(
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

if is_placeholder "$(read_env OPENAI_API_KEY)" && is_placeholder "$(read_env GEMINI_API_KEY)"; then
  echo "Missing AI provider key: set OPENAI_API_KEY or GEMINI_API_KEY in $ENV_FILE" >&2
  exit 1
fi

write_resolved_env

compose_args=(--env-file "$RESOLVED_ENV_FILE" -f "$COMPOSE_FILE")
enable_proxy="$(read_env ENABLE_PROXY "$RESOLVED_ENV_FILE")"

echo "Validating production compose file..."
if [[ "$enable_proxy" == "1" ]]; then
  COMPOSE_PROFILES=proxy docker compose "${compose_args[@]}" config >/dev/null
else
  COMPOSE_PROFILES= docker compose "${compose_args[@]}" config >/dev/null
fi

if [[ "$MODE" == "config" ]]; then
  echo "Compose config is valid."
  exit 0
fi

if [[ "$MODE" == "build" ]]; then
  echo "Building production images..."
  if [[ "$enable_proxy" == "1" ]]; then
    COMPOSE_PROFILES=proxy docker compose "${compose_args[@]}" build
  else
    COMPOSE_PROFILES= docker compose "${compose_args[@]}" build
  fi
  echo "Production images built."
  exit 0
fi

echo "Building and starting production services..."
if [[ "$enable_proxy" == "1" ]]; then
  COMPOSE_PROFILES=proxy docker compose "${compose_args[@]}" up -d --build
else
  COMPOSE_PROFILES= docker compose "${compose_args[@]}" up -d --build
fi

echo "Production services:"
if [[ "$enable_proxy" == "1" ]]; then
  COMPOSE_PROFILES=proxy docker compose "${compose_args[@]}" ps
else
  COMPOSE_PROFILES= docker compose "${compose_args[@]}" ps
fi

echo
echo "Deployment command finished."
if [[ "$enable_proxy" == "1" ]]; then
  echo "Open: https://$(read_env PRIMARY_DOMAIN "$RESOLVED_ENV_FILE")"
  echo "SpeakCV: https://$(read_env SPEAKCV_DOMAIN "$RESOLVED_ENV_FILE")"
  echo "API docs: https://$(read_env API_DOMAIN "$RESOLVED_ENV_FILE")/docs"
else
  echo "Open: http://$(read_env PUBLIC_HOST "$RESOLVED_ENV_FILE"):$(read_env INTERVIEWPATH_PORT "$RESOLVED_ENV_FILE")"
  echo "SpeakCV: http://$(read_env PUBLIC_HOST "$RESOLVED_ENV_FILE"):$(read_env SPEAKCV_FRONTEND_PORT "$RESOLVED_ENV_FILE")"
  echo "API docs: http://$(read_env PUBLIC_HOST "$RESOLVED_ENV_FILE"):$(read_env SPEAKCV_BACKEND_PORT "$RESOLVED_ENV_FILE")/docs"
fi
