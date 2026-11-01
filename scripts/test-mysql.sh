#!/usr/bin/env bash
# Runs tests/mysql against a throwaway MySQL 8.0 container on a free port, and removes it even on failure.
# It only ever touches the one container it starts.
set -euo pipefail

cd "$(dirname "$0")/../SpeakCV/src/backend"
PYTHON=.venv/bin/python
[ -x "$PYTHON" ] || PYTHON=python3

name="speakcv-test-mysql-$$"
password="$("$PYTHON" -c 'import secrets; print(secrets.token_hex(16))')"

cleanup() {
    docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

docker run -d --name "$name" \
    -e MYSQL_ROOT_PASSWORD="$password" \
    -e MYSQL_DATABASE=speakcv_test \
    -p 127.0.0.1::3306 \
    --tmpfs /var/lib/mysql \
    mysql:8.0 >/dev/null

port="$(docker port "$name" 3306/tcp | head -n 1 | sed 's/.*://')"

# Connect over TCP: the temporary server the image runs during its setup does not listen on the network.
echo "Waiting for MySQL on port $port..."
for _ in $(seq 1 120); do
    if "$PYTHON" -c "import pymysql, sys; pymysql.connect(host='127.0.0.1', port=$port, user='root', password=sys.argv[1], database='speakcv_test', connect_timeout=2).close()" "$password" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
if [ -z "${ready:-}" ]; then
    echo "MySQL did not start in time." >&2
    exit 1
fi

TEST_MYSQL_URL="mysql+pymysql://root:$password@127.0.0.1:$port/speakcv_test?charset=utf8mb4" \
    "$PYTHON" -m pytest -q tests/mysql "$@"
