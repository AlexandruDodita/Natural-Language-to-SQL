#!/usr/bin/env bash
# ============================================================
# run_all.sh — Execute all test SQL files against the test DB
# Usage:  ./test_db/tests/run_all.sh
# ============================================================
set -uo pipefail

CONTAINER="test-car-rental-db"
DB_NAME="car_rental"
DB_USER="postgres"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

TOTAL=0
PASSED=0
FAILED=0
FAILED_TESTS=()

echo -e "${BOLD}================================================${NC}"
echo -e "${BOLD}  Car Rental DB — Test Suite${NC}"
echo -e "${BOLD}================================================${NC}"
echo ""

# Check container is running
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Container '$CONTAINER' is not running.${NC}"
    echo "  Start it with: ./test_db/init_db.sh"
    exit 1
fi

# Run each test file
for test_file in "$SCRIPT_DIR"/[0-9]*.sql; do
    test_name=$(basename "$test_file" .sql)
    TOTAL=$((TOTAL + 1))

    echo -e "${CYAN}▶ Running: ${test_name}${NC}"

    # Copy file into container and execute
    docker cp "$test_file" "$CONTAINER":/tmp/test.sql >/dev/null 2>&1
    OUTPUT=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -f /tmp/test.sql 2>&1)
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        PASSED=$((PASSED + 1))
        # Print NOTICE lines (the test output)
        echo "$OUTPUT" | grep -E "NOTICE:" | sed 's/.*NOTICE:  /  /' | while IFS= read -r line; do
            if echo "$line" | grep -q "\[PASS\]"; then
                echo -e "  ${GREEN}${line}${NC}"
            elif echo "$line" | grep -q "\[FAIL\]"; then
                echo -e "  ${RED}${line}${NC}"
            else
                echo -e "  ${BOLD}${line}${NC}"
            fi
        done
        echo -e "  ${GREEN}✓ ${test_name} passed${NC}"
    else
        FAILED=$((FAILED + 1))
        FAILED_TESTS+=("$test_name")
        # Show the error
        echo "$OUTPUT" | grep -E "NOTICE:|ERROR:|ASSERT" | sed 's/.*NOTICE:  /  /' | while IFS= read -r line; do
            if echo "$line" | grep -q "\[PASS\]"; then
                echo -e "  ${GREEN}${line}${NC}"
            else
                echo -e "  ${RED}${line}${NC}"
            fi
        done
        echo -e "  ${RED}✗ ${test_name} FAILED${NC}"
    fi
    echo ""
done

# Summary
echo -e "${BOLD}================================================${NC}"
echo -e "${BOLD}  Results: ${PASSED}/${TOTAL} test suites passed${NC}"
echo -e "${BOLD}================================================${NC}"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}  Failed:${NC}"
    for t in "${FAILED_TESTS[@]}"; do
        echo -e "    ${RED}✗ ${t}${NC}"
    done
    echo ""
    exit 1
else
    echo -e "${GREEN}  All tests passed!${NC}"
    echo ""
    exit 0
fi
