#!/usr/bin/env bash
# Starts the real backend on SQLite with fake AI. Creates a sample company and one HR user.
set -euo pipefail
E2E_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$E2E_DIR/../../../SpeakCV/src/backend"
E2E_TMP="${E2E_TMP:-$(mktemp -d)}"
mkdir -p "$E2E_TMP"
E2E_DB="$E2E_TMP/portal_e2e.db"
rm -f "$E2E_DB"
export APP_ENV=test
export SECRET_KEY=e2e-only-secret-key-0123456789abcdef-e2e
export DATABASE_URL="sqlite:///$E2E_DB"
export ALLOWED_ORIGINS=http://localhost:${E2E_WEB_PORT:-5199}
export ADMIN_EMAIL= ADMIN_PASSWORD=
for slot in REASONING BULK EMBEDDING STT TTS; do export "AI_${slot}_PROVIDER=fake"; done
PY=.venv/bin/python
$PY -m app.cli migrate
if [ "${E2E_SEED_SAMPLES:-}" = "1" ]; then
  # Sample users get this known test password, so specs can sign in without the forced password change.
  export SAMPLE_USER_PASSWORD=e2e-sample-password-123
  $PY -m app.cli seed-samples --auto-approve
fi
HR_PASSWORD=$($PY -m app.cli create-company --slug e2e --name "E2E Company" --hr-email hr@e2e.test --hr-name "E2E HR" --sample | awk '/Temporary password/ {print $NF}')
printf '%s' "$HR_PASSWORD" > "$E2E_TMP/portal_e2e_password"
# A second company for the knowledge specs, so they do not disturb the password flow tested in login.spec.js.
BRAIN_PASSWORD=$($PY -m app.cli create-company --slug brain --name "Brain Company" --hr-email brain-hr@e2e.test --hr-name "Brain HR" | awk '/Temporary password/ {print $NF}')
printf '%s' "$BRAIN_PASSWORD" > "$E2E_TMP/portal_e2e_brain_password"
# One user in two companies, to test that nothing from the previous company survives a switch.
SWITCH_PASSWORD=$($PY -m app.cli create-company --slug switch-a --name "Switch Alpha" --hr-email switch-hr@e2e.test --hr-name "Switch HR" | awk '/Temporary password/ {print $NF}')
printf '%s' "$SWITCH_PASSWORD" > "$E2E_TMP/portal_e2e_switch_password"
$PY -m app.cli create-company --slug switch-b --name "Switch Beta" --hr-email switch-hr@e2e.test --hr-name "Switch HR" > /dev/null
exec env PYTHONPATH=. $PY "$E2E_DIR/serve-backend.py" "${E2E_API_PORT:-8099}"
