#!/usr/bin/env bash
# ============================================================
# init_db.sh — Initialize (or reset) the car rental test database
# Usage:
#   ./test_app_db/init_db.sh          # start fresh
#   ./test_app_db/init_db.sh --reset  # destroy volume and re-seed
# ============================================================
set -euo pipefail

COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/docker-compose.yml"
SERVICE="test_app_db"
CONTAINER="test-app-db"
DB_NAME="car_rental"
DB_USER="postgres"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ---- Pre-flight checks ----
command -v docker-compose >/dev/null 2>&1 || command -v docker >/dev/null 2>&1 || fail "Docker is not installed"

# Detect compose command
if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    COMPOSE="docker compose"
fi

# ---- Reset mode ----
if [[ "${1:-}" == "--reset" ]]; then
    warn "Resetting test database — destroying volume..."
    $COMPOSE -f "$COMPOSE_FILE" rm -sf "$SERVICE" 2>/dev/null || true
    docker volume rm licenta_test_app_db_data 2>/dev/null || docker volume rm ai_test_app_db_data 2>/dev/null || true
    ok "Old container and volume removed"
fi

# ---- Start the service ----
info "Starting $SERVICE service..."
$COMPOSE -f "$COMPOSE_FILE" up -d "$SERVICE"

# ---- Wait for healthy ----
info "Waiting for database to be ready..."
MAX_WAIT=60
ELAPSED=0
while true; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "not_found")
    if [[ "$STATUS" == "healthy" ]]; then
        break
    fi
    if (( ELAPSED >= MAX_WAIT )); then
        fail "Database did not become healthy within ${MAX_WAIT}s (status: $STATUS)"
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
ok "Database container is healthy"

# ---- Wait for init scripts to finish ----
info "Waiting for seed data to load..."
for i in $(seq 1 30); do
    TABLE_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
        "SELECT count(*) FROM pg_tables WHERE schemaname='public';" 2>/dev/null || echo "0")
    if (( TABLE_COUNT >= 9 )); then
        # Also check that data is seeded (reservations should have rows)
        ROW_COUNT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
            "SELECT count(*) FROM reservations;" 2>/dev/null || echo "0")
        if (( ROW_COUNT > 0 )); then
            break
        fi
    fi
    sleep 2
done

if (( TABLE_COUNT < 9 )); then
    fail "Expected 9 tables, found $TABLE_COUNT. Check init scripts."
fi

# ---- Summary ----
echo ""
info "Database ready! Connection details:"
echo "  Host:     localhost"
echo "  Port:     5434"
echo "  Database: $DB_NAME"
echo "  User:     $DB_USER"
echo "  Password: postgres"
echo ""

docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT t.table_name, s.n_live_tup AS row_count
FROM information_schema.tables t
JOIN pg_stat_user_tables s ON t.table_name = s.relname
WHERE t.table_schema = 'public'
ORDER BY s.n_live_tup DESC;
"

TOTAL=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc "
SELECT SUM(n_live_tup) FROM pg_stat_user_tables;
")
echo ""
ok "Total rows: $TOTAL"
ok "Test database initialized successfully!"
