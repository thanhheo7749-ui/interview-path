#!/usr/bin/env bash
# Starts the real backend on SQLite with fake AI. Creates a sample company and one HR user.
set -euo pipefail
cd "$(dirname "$0")/../../../SpeakCV/src/backend"
E2E_TMP="${E2E_TMP:-$(mktemp -d)}"
mkdir -p "$E2E_TMP"
E2E_DB="$E2E_TMP/portal_e2e.db"
rm -f "$E2E_DB"
export APP_ENV=test
export SECRET_KEY=e2e-only-secret-key-0123456789abcdef-e2e
export DATABASE_URL="sqlite:///$E2E_DB"
export ALLOWED_ORIGINS=http://localhost:5199
export ADMIN_EMAIL= ADMIN_PASSWORD=
for slot in REASONING BULK EMBEDDING STT TTS; do export "AI_${slot}_PROVIDER=fake"; done
PY=.venv/bin/python
$PY -m app.cli migrate
HR_PASSWORD=$($PY -m app.cli create-company --slug e2e --name "E2E Company" --hr-email hr@e2e.test --hr-name "E2E HR" --sample | awk '/Temporary password/ {print $NF}')
printf '%s' "$HR_PASSWORD" > "$E2E_TMP/portal_e2e_password"
exec $PY -m uvicorn app.main:app --port 8099
