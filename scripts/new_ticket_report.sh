#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/new_ticket_report.sh TICKET-05
#   bash scripts/new_ticket_report.sh TICKET-03.1-TICKET-04

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/new_ticket_report.sh <TICKET-ID>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports/tickets"
TEMPLATE="$REPORT_DIR/TEMPLATE.md"
DATE_STR="$(date +%F)"
TICKET_ID="$1"
SAFE_TICKET_ID="$(echo "$TICKET_ID" | tr ' ' '-' | tr '/' '-')"

if [ ! -f "$TEMPLATE" ]; then
  echo "Template not found: $TEMPLATE"
  exit 1
fi

mkdir -p "$REPORT_DIR"

version=1
while [ -f "$REPORT_DIR/${SAFE_TICKET_ID}-${DATE_STR}-v${version}.md" ]; do
  version=$((version + 1))
done

OUT_FILE="$REPORT_DIR/${SAFE_TICKET_ID}-${DATE_STR}-v${version}.md"
cp "$TEMPLATE" "$OUT_FILE"

echo "Created report template:"
echo "$OUT_FILE"

