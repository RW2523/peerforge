#!/usr/bin/env bash
set -euo pipefail

# check_file_sizes.sh
# Enforces file size limits from engineering standards:
# - Max 300 lines for UI components
# - Max 400 lines for service files
# - Max 500 lines for route/controller files
# Exception: generated files (must be in */generated/* path)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Checking file sizes..."

VIOLATIONS=0

# Function to count lines excluding comments and blank lines (for better measurement)
count_significant_lines() {
    local file="$1"
    local ext="${file##*.}"
    
    case "$ext" in
        ts|tsx|js|jsx)
            # Count non-blank, non-comment-only lines
            grep -v '^\s*$' "$file" | grep -v '^\s*//' | wc -l | tr -d ' '
            ;;
        py)
            # Count non-blank, non-comment-only lines
            grep -v '^\s*$' "$file" | grep -v '^\s*#' | wc -l | tr -d ' '
            ;;
        *)
            wc -l < "$file" | tr -d ' '
            ;;
    esac
}

# Check UI components (max 300 lines)
echo ""
echo "📱 Checking UI components (max 300 lines)..."
ui_components=$(find "$ROOT_DIR/apps/web" "$ROOT_DIR/packages/ui" -type f \( -name "*.tsx" -o -name "*.jsx" \) 2>/dev/null || true)

for file in $ui_components; do
    # Skip generated files
    if [[ "$file" == *"/generated/"* ]]; then
        continue
    fi
    
    lines=$(wc -l < "$file" | tr -d ' ')
    if [ "$lines" -gt 300 ]; then
        echo -e "  ${RED}✗${NC} $file: $lines lines (max 300)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Check service files (max 400 lines)
echo ""
echo "⚙️  Checking service files (max 400 lines)..."
service_files=$(find "$ROOT_DIR/apps" "$ROOT_DIR/packages" -type f \( -name "*_service.py" -o -name "*Service.ts" -o -name "*_service.ts" \) 2>/dev/null || true)

for file in $service_files; do
    # Skip generated files
    if [[ "$file" == *"/generated/"* ]]; then
        continue
    fi
    
    lines=$(wc -l < "$file" | tr -d ' ')
    if [ "$lines" -gt 400 ]; then
        echo -e "  ${RED}✗${NC} $file: $lines lines (max 400)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Check route/controller files (max 500 lines)
echo ""
echo "🛣️  Checking route/controller files (max 500 lines)..."
route_files=$(find "$ROOT_DIR/apps" -type f \( -name "*_routes.py" -o -name "*.routes.ts" -o -name "*_controller.py" -o -name "*.controller.ts" \) 2>/dev/null || true)

for file in $route_files; do
    # Skip generated files
    if [[ "$file" == *"/generated/"* ]]; then
        continue
    fi
    
    lines=$(wc -l < "$file" | tr -d ' ')
    if [ "$lines" -gt 500 ]; then
        echo -e "  ${RED}✗${NC} $file: $lines lines (max 500)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

echo ""
if [ "$VIOLATIONS" -eq 0 ]; then
    echo -e "${GREEN}✅ All files are within size limits${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $VIOLATIONS file(s) exceeding size limits${NC}"
    echo ""
    echo "Fix: Refactor oversized files into smaller modules"
    echo "See: docs/runbooks/ci-gates.md for guidance"
    exit 1
fi
