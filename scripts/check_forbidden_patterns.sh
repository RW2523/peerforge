#!/usr/bin/env bash
set -euo pipefail

# check_forbidden_patterns.sh
# Scans for forbidden patterns:
# - Direct OpenAI/Anthropic/Google provider SDK usage (should use OpenRouter gateway)
# - Service key misuse (hardcoded keys, direct embedding)
# - Temporary hack patterns (TODO without issue, FIXME, temp_fix)
# - Silent fallback behavior
# - Undocumented env vars

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Checking for forbidden patterns..."

VIOLATIONS=0
WARNINGS=0

# Check for direct provider SDK usage (OpenRouter policy violation)
echo ""
echo "🚫 Checking for direct provider SDK usage (OpenRouter policy)..."

# OpenAI provider imports (should use OpenRouter instead)
openai_imports=$(grep -rn "from openai import\|import openai\|require.*openai" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
    --include="*.py" --include="*.ts" --include="*.js" \
    --exclude-dir=node_modules --exclude-dir=generated --exclude-dir=.next 2>/dev/null | \
    grep -v "# OpenRouter gateway" | grep -v "openapi" || true)

if [ -n "$openai_imports" ]; then
    echo -e "  ${RED}✗${NC} Found direct OpenAI SDK imports (use OpenRouter instead):"
    echo "$openai_imports" | sed 's/^/    /'
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Anthropic provider imports
anthropic_imports=$(grep -rn "from anthropic import\|import anthropic\|require.*anthropic" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
    --include="*.py" --include="*.ts" --include="*.js" \
    --exclude-dir=node_modules --exclude-dir=generated --exclude-dir=.next 2>/dev/null || true)

if [ -n "$anthropic_imports" ]; then
    echo -e "  ${RED}✗${NC} Found direct Anthropic SDK imports (use OpenRouter instead):"
    echo "$anthropic_imports" | sed 's/^/    /'
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Google AI imports
google_ai_imports=$(grep -rn "from google.generativeai import\|import google.generativeai\|@google/generative-ai" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
    --include="*.py" --include="*.ts" --include="*.js" \
    --exclude-dir=node_modules --exclude-dir=generated 2>/dev/null || true)

if [ -n "$google_ai_imports" ]; then
    echo -e "  ${RED}✗${NC} Found direct Google AI SDK imports (use OpenRouter instead):"
    echo "$google_ai_imports" | sed 's/^/    /'
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Check for hardcoded API keys or secrets
echo ""
echo "🔑 Checking for hardcoded secrets..."

secret_patterns=(
    "sk-[a-zA-Z0-9]{32,}"  # OpenAI-style keys
    "OPENAI_API_KEY\s*=\s*['\"][^'\"]+['\"]"
    "ANTHROPIC_API_KEY\s*=\s*['\"][^'\"]+['\"]"
    "api[_-]?key\s*=\s*['\"][a-zA-Z0-9]{20,}['\"]"
)

for pattern in "${secret_patterns[@]}"; do
    found=$(grep -rn -E "$pattern" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
        --include="*.py" --include="*.ts" --include="*.js" \
        --exclude-dir=node_modules --exclude-dir=generated --exclude-dir=.next \
        --exclude="*.test.*" --exclude="*.spec.*" 2>/dev/null || true)
    
    if [ -n "$found" ]; then
        echo -e "  ${RED}✗${NC} Found potential hardcoded secret:"
        echo "$found" | sed 's/^/    /'
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Check for temporary hacks without issue links
echo ""
echo "🔧 Checking for temporary hacks..."

# TODO/FIXME without issue reference
# Valid formats: TODO(#123), TODO(TICKET-...), TODO(ABC-123), TODO #123, TODO: #TICKET-06
todo_without_issue=$(grep -rn "TODO\|FIXME\|HACK" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
    --include="*.py" --include="*.ts" --include="*.js" \
    --exclude-dir=node_modules --exclude-dir=generated --exclude-dir=.venv --exclude-dir=.next 2>/dev/null | \
    grep -v "TODO.*#[0-9]" | grep -v "FIXME.*#[0-9]" | grep -v "HACK.*#[0-9]" | \
    grep -v "TODO.*TICKET-" | grep -v "FIXME.*TICKET-" | grep -v "HACK.*TICKET-" | \
    grep -v "TODO.*[A-Z]+-[0-9]" | grep -v "FIXME.*[A-Z]+-[0-9]" | grep -v "HACK.*[A-Z]+-[0-9]" || true)

if [ -n "$todo_without_issue" ]; then
    echo -e "  ${YELLOW}⚠${NC}  Found TODO/FIXME/HACK without issue reference:"
    echo "$todo_without_issue" | head -10 | sed 's/^/    /'
    if [ $(echo "$todo_without_issue" | wc -l) -gt 10 ]; then
        echo "    ... and $(($(echo "$todo_without_issue" | wc -l) - 10)) more"
    fi
    WARNINGS=$((WARNINGS + 1))
fi

# Check for temp/temporary in file names or code
temp_patterns=$(grep -rn "temp_fix\|temporary_solution\|quick_hack" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
    --include="*.py" --include="*.ts" --include="*.js" \
    --exclude-dir=node_modules --exclude-dir=generated --exclude-dir=.next 2>/dev/null || true)

if [ -n "$temp_patterns" ]; then
    echo -e "  ${RED}✗${NC} Found temporary fix patterns:"
    echo "$temp_patterns" | sed 's/^/    /'
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Check for silent fallback behavior (bare except, catch-all without logging)
echo ""
echo "🤐 Checking for silent error handling..."

# Python bare except
bare_except=$(grep -rn "except:" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
    --include="*.py" \
    --exclude-dir=node_modules --exclude-dir=generated --exclude-dir=.venv --exclude-dir=.next 2>/dev/null | \
    grep -v "except Exception" | grep -v "except.*as" || true)

if [ -n "$bare_except" ]; then
    echo -e "  ${RED}✗${NC} Found bare except clauses (silent error handling):"
    echo "$bare_except" | head -5 | sed 's/^/    /'
    if [ $(echo "$bare_except" | wc -l) -gt 5 ]; then
        echo "    ... and $(($(echo "$bare_except" | wc -l) - 5)) more"
    fi
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# TypeScript/JavaScript empty catch blocks (using Python helper for accuracy)
if command -v python3 >/dev/null 2>&1; then
    # Use Python script for accurate multiline detection
    empty_catch_output=$(python3 "$SCRIPT_DIR/check_empty_catches.py" 2>&1 || true)
    if echo "$empty_catch_output" | grep -q "Found empty catch blocks"; then
        echo -e "  ${RED}✗${NC} Empty catch blocks detected:"
        echo "$empty_catch_output" | sed 's/^/    /'
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
else
    # Fallback to simpler shell detection (single-line only)
    empty_catch=$(grep -rn "catch\s*([^)]*)\s*{\s*}" "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
        --include="*.ts" --include="*.js" \
        --exclude-dir=node_modules --exclude-dir=generated 2>/dev/null || true)
    
    if [ -n "$empty_catch" ]; then
        echo -e "  ${RED}✗${NC} Found empty catch blocks:"
        echo "$empty_catch" | head -10 | sed 's/^/    /'
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
fi

# Check for undocumented environment variables (improved detection)
echo ""
echo "🌍 Checking for undocumented environment variables..."

# Find all env var usages with improved regex patterns
env_vars=$(grep -rhE "process\.env\.[A-Z_][A-Z0-9_]*|process\.env\[[\"\']([A-Z_][A-Z0-9_]*)[\"\']|os\.getenv\([\"\']([A-Z_][A-Z0-9_]*)|os\.environ\[[\"\']([A-Z_][A-Z0-9_]*)" \
    "$ROOT_DIR/apps" "$ROOT_DIR/packages" \
    --include="*.py" --include="*.ts" --include="*.js" \
    --exclude-dir=node_modules --exclude-dir=generated --exclude-dir=.next --exclude-dir=.venv --exclude-dir=.pytest_cache --exclude-dir=__pycache__ 2>/dev/null | \
    sed -E "s/.*process\.env\.([A-Z_][A-Z0-9_]*).*/\1/; s/.*process\.env\[[\"\']([A-Z_][A-Z0-9_]*)[\"\'].*/\1/; s/.*os\.getenv\([\"\']([A-Z_][A-Z0-9_]*).*/\1/; s/.*os\.environ\[[\"\']([A-Z_][A-Z0-9_]*).*/\1/" | \
    sort | uniq || true)

if [ -n "$env_vars" ]; then
    # Check if .env.example exists
    if [ ! -f "$ROOT_DIR/.env.example" ]; then
        echo -e "  ${YELLOW}⚠${NC}  Found env var usage but no .env.example file"
        echo -e "  ${YELLOW}ℹ${NC}  Environment variables detected:"
        echo "$env_vars" | head -10 | sed 's/^/    /'
        if [ $(echo "$env_vars" | wc -l) -gt 10 ]; then
            echo "    ... and $(($(echo "$env_vars" | wc -l) - 10)) more"
        fi
        WARNINGS=$((WARNINGS + 1))
    else
        # Check if vars are documented
        undocumented=""
        for var in $env_vars; do
            if ! grep -q "^$var=" "$ROOT_DIR/.env.example"; then
                undocumented="$undocumented$var"$'\n'
            fi
        done
        if [ -n "$undocumented" ]; then
            echo -e "  ${YELLOW}⚠${NC}  Found undocumented environment variables:"
            echo "$undocumented" | head -10 | sed 's/^/    /'
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
fi

# Check for copy-pasted code (simple heuristic: identical function bodies)
echo ""
echo "📋 Checking for potential code duplication..."

# Find suspiciously similar function definitions (same line count and similar structure)
# This is a simple check; more sophisticated tools like jscpd could be used
function_dupes=$(find "$ROOT_DIR/apps" "$ROOT_DIR/packages" -type f \( -name "*.ts" -o -name "*.js" \) \
    -not -path "*/node_modules/*" -not -path "*/generated/*" \
    -exec grep -l "function\|const.*=.*=>.*{" {} \; 2>/dev/null | head -20 || true)

# Just warn, don't fail on this
if [ -n "$function_dupes" ]; then
    echo -e "  ${YELLOW}ℹ${NC}  Run a code duplication tool (jscpd, simian) for detailed analysis"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$VIOLATIONS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}✅ No forbidden patterns found${NC}"
    exit 0
elif [ "$VIOLATIONS" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No critical violations, but $WARNINGS warning(s)${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $VIOLATIONS critical violation(s) and $WARNINGS warning(s)${NC}"
    echo ""
    echo "Critical violations found:"
    echo "- Direct provider SDK usage: Use OpenRouter gateway instead"
    echo "- Hardcoded secrets: Use environment variables"
    echo "- Temporary fixes: Create issues and link them"
    echo "- Silent error handling: Add proper logging"
    echo ""
    echo "See: docs/runbooks/ci-gates.md for guidance"
    exit 1
fi
