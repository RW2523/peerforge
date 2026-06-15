#!/usr/bin/env bash
set -euo pipefail

# test_gate_detections.sh
# Proves that gate hardening improvements work correctly

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🧪 Testing Gate Detection Improvements"
echo "======================================"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

# Create test directory
TEST_DIR="$ROOT_DIR/apps/api/.test_violations"
mkdir -p "$TEST_DIR"

cleanup() {
    rm -rf "$TEST_DIR"
}

trap cleanup EXIT

# Test 1: Empty catch - single line
echo "Test 1: Empty catch block (single line)"
cat > "$TEST_DIR/test1.ts" << 'EOF'
try {
    doSomething();
} catch(e) {}
EOF

output=$(bash "$SCRIPT_DIR/check_forbidden_patterns.sh" 2>&1 || true)
if echo "$output" | grep -q "Found empty catch blocks"; then
    echo -e "${GREEN}✅ PASS${NC} - Single-line empty catch detected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC} - Single-line empty catch NOT detected"
    echo "Output: $output" | grep -A2 "Checking for silent"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
rm -f "$TEST_DIR/test1.ts"
echo ""

# Test 2: Empty catch - multiline with whitespace
echo "Test 2: Empty catch block (multiline with whitespace)"
cat > "$TEST_DIR/test2.ts" << 'EOF'
try {
    doSomething();
} catch(error) {
    
    
}
EOF

output=$(bash "$SCRIPT_DIR/check_forbidden_patterns.sh" 2>&1 || true)
if echo "$output" | grep -q "Found empty catch blocks"; then
    echo -e "${GREEN}✅ PASS${NC} - Multiline empty catch detected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC} - Multiline empty catch NOT detected"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
rm -f "$TEST_DIR/test2.ts"
echo ""

# Test 3: Empty catch - with only comments
echo "Test 3: Empty catch block (with only comments)"
cat > "$TEST_DIR/test3.ts" << 'EOF'
try {
    doSomething();
} catch(e) {
    // TODO: handle this
}
EOF

output=$(bash "$SCRIPT_DIR/check_forbidden_patterns.sh" 2>&1 || true)
if echo "$output" | grep -q "Found empty catch blocks"; then
    echo -e "${GREEN}✅ PASS${NC} - Comment-only catch detected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC} - Comment-only catch NOT detected"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
rm -f "$TEST_DIR/test3.ts"
echo ""

# Test 4: Valid catch with logging (should not trigger)
echo "Test 4: Valid catch block with logging (should NOT trigger)"
cat > "$TEST_DIR/test4.ts" << 'EOF'
try {
    doSomething();
} catch(error) {
    console.error('Error:', error);
    throw error;
}
EOF

output=$(bash "$SCRIPT_DIR/check_forbidden_patterns.sh" 2>&1 || true)
if echo "$output" | grep -q "Found empty catch blocks"; then
    echo -e "${RED}❌ FAIL${NC} - Valid catch incorrectly flagged as empty"
    TESTS_FAILED=$((TESTS_FAILED + 1))
else
    echo -e "${GREEN}✅ PASS${NC} - Valid catch correctly allowed"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi
rm -f "$TEST_DIR/test4.ts"
echo ""

# Clean test files before env var tests
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"

# Test 5: Environment variable - process.env.VAR
echo "Test 5: Environment variable detection (process.env.VAR)"
cat > "$TEST_DIR/test5.ts" << 'EOF'
const apiKey = process.env.API_KEY;
const dbUrl = process.env.DATABASE_URL;
EOF

output=$(bash "$SCRIPT_DIR/check_forbidden_patterns.sh" 2>&1 || true)
if echo "$output" | grep -q "Found env var usage\|Environment variables detected"; then
    echo -e "${GREEN}✅ PASS${NC} - process.env.VAR detected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC} - process.env.VAR NOT detected"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
rm -f "$TEST_DIR/test5.ts"
echo ""

# Test 6: Environment variable - process.env["VAR"]
echo "Test 6: Environment variable detection (process.env['VAR'])"
cat > "$TEST_DIR/test6.ts" << 'EOF'
const secret = process.env["SECRET_KEY"];
const port = process.env['PORT'];
EOF

output=$(bash "$SCRIPT_DIR/check_forbidden_patterns.sh" 2>&1 || true)
if echo "$output" | grep -q "Found env var usage\|Environment variables detected"; then
    echo -e "${GREEN}✅ PASS${NC} - process.env['VAR'] detected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC} - process.env['VAR'] NOT detected"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
rm -f "$TEST_DIR/test6.ts"
echo ""

# Test 7: Environment variable - os.getenv
echo "Test 7: Environment variable detection (os.getenv)"
cat > "$TEST_DIR/test7.py" << 'EOF'
import os
api_key = os.getenv("OPENROUTER_API_KEY")
db_host = os.environ["DB_HOST"]
EOF

output=$(bash "$SCRIPT_DIR/check_forbidden_patterns.sh" 2>&1 || true)
if echo "$output" | grep -q "Found env var usage\|Environment variables detected"; then
    echo -e "${GREEN}✅ PASS${NC} - Python env vars detected"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC} - Python env vars NOT detected"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
rm -f "$TEST_DIR/test7.py"
echo ""

# Summary
echo "======================================"
echo "Test Results:"
echo -e "  ${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "  ${RED}Failed: $TESTS_FAILED${NC}"
echo "======================================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All gate detection tests passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some gate detection tests failed!${NC}"
    exit 1
fi
