#!/usr/bin/env bash
set -euo pipefail

# check_duplicates.sh
# Checks for duplicate:
# - API endpoint definitions
# - File names with similar purpose
# - Exported function/class names

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Checking for duplicates..."

VIOLATIONS=0

# Check for duplicate API route definitions in OpenAPI
echo ""
echo "🔗 Checking for duplicate API endpoints..."
if [ -f "$ROOT_DIR/packages/contracts/openapi/arinar-v1.yaml" ]; then
    # Extract all path definitions and check for duplicates
    duplicate_paths=$(grep -E '^\s+/[^:]+:' "$ROOT_DIR/packages/contracts/openapi/arinar-v1.yaml" | sort | uniq -d || true)
    if [ -n "$duplicate_paths" ]; then
        echo -e "  ${RED}✗${NC} Found duplicate API paths in OpenAPI spec:"
        echo "$duplicate_paths" | sed 's/^/    /'
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
fi

# Check for duplicate route handler files with suspicious names
echo ""
echo "📂 Checking for duplicate file patterns..."
suspicious_patterns=(
    "*_routes_v2.py"
    "*_routes_new.py"
    "*_service2.py"
    "*_service_new.py"
    "utils2.*"
    "helpers2.*"
    "temp_*.py"
    "temp_*.ts"
    "new.py"
    "new.ts"
    "copy_of_*"
    "*_backup.*"
    "*_old.*"
)

for pattern in "${suspicious_patterns[@]}"; do
    found=$(find "$ROOT_DIR/apps" "$ROOT_DIR/packages" -type f -name "$pattern" \
        -not -path "*/.venv/*" -not -path "*/node_modules/*" 2>/dev/null || true)
    if [ -n "$found" ]; then
        echo -e "  ${RED}✗${NC} Found suspicious duplicate file pattern: $pattern"
        echo "$found" | sed 's/^/    /'
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Check for duplicate exported class/function names across modules
echo ""
echo "🏷️  Checking for duplicate exported symbols..."

# TypeScript/JavaScript exports
ts_exports=$(find "$ROOT_DIR/apps" "$ROOT_DIR/packages" -type f \( -name "*.ts" -o -name "*.tsx" \) -not -path "*/node_modules/*" -not -path "*/generated/*" -exec grep -h "export.*\(class\|function\|const\)" {} \; 2>/dev/null | \
    sed -n 's/.*export.*\(class\|function\|const\) \([A-Za-z0-9_]*\).*/\2/p' | \
    sort | uniq -c | awk '$1 > 1 {print $2}' || true)

if [ -n "$ts_exports" ]; then
    echo -e "  ${YELLOW}⚠${NC}  Potentially duplicate TypeScript exports:"
    echo "$ts_exports" | sed 's/^/    /'
    # Don't fail on this, just warn (some duplicates might be intentional)
fi

# Python exports (class/function definitions at module level)
py_exports=$(find "$ROOT_DIR/apps" "$ROOT_DIR/packages" -type f -name "*.py" -not -path "*/generated/*" -not -path "*/__pycache__/*" -exec grep -h "^def \|^class " {} \; 2>/dev/null | \
    sed -n 's/^def \([A-Za-z0-9_]*\).*/\1/p; s/^class \([A-Za-z0-9_]*\).*/\1/p' | \
    sort | uniq -c | awk '$1 > 3 {print $2}' || true)

if [ -n "$py_exports" ]; then
    echo -e "  ${YELLOW}⚠${NC}  Potentially duplicate Python symbols (>3 occurrences):"
    echo "$py_exports" | sed 's/^/    /'
    # Don't fail on this, just warn
fi

# Check for duplicate route definitions in FastAPI
echo ""
echo "🔀 Checking for duplicate FastAPI route decorators..."
if [ -d "$ROOT_DIR/apps/api" ]; then
    duplicate_routes=$(find "$ROOT_DIR/apps/api" -type f -name "*.py" -exec grep -h "@router\.\(get\|post\|put\|patch\|delete\)" {} \; 2>/dev/null | \
        sed 's/@router\.\(get\|post\|put\|patch\|delete\)(\([^)]*\).*/\1 \2/' | \
        sort | uniq -c | awk '$1 > 1 {print $0}' || true)
    
    if [ -n "$duplicate_routes" ]; then
        echo -e "  ${RED}✗${NC} Found duplicate route definitions:"
        echo "$duplicate_routes" | sed 's/^/    /'
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
fi

echo ""
if [ "$VIOLATIONS" -eq 0 ]; then
    echo -e "${GREEN}✅ No critical duplicates found${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $VIOLATIONS duplicate violation(s)${NC}"
    echo ""
    echo "Fix: Remove or consolidate duplicate files/endpoints"
    echo "See: docs/runbooks/ci-gates.md for guidance"
    exit 1
fi
