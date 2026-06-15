#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_CONTAINER="${DB_CONTAINER:-arinar-db}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"

if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
  echo "❌ Database container '${DB_CONTAINER}' is not running. Run 'make db-up' first."
  exit 1
fi

echo "📦 Applying migrations with tracking..."

# Migration tracking table (minimal, avoids false 'success' when reapplying).
docker exec "${DB_CONTAINER}" psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" -c "
CREATE TABLE IF NOT EXISTS arinar_schema_migrations (
  filename TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);"

shopt -s nullglob
files=()
while IFS= read -r f; do
  files+=("$f")
done < <(ls -1 "${ROOT_DIR}/infra/supabase/migrations/"*.sql 2>/dev/null | sort || true)

if [ "${#files[@]}" -eq 0 ]; then
  echo "ℹ️  No migration files found."
  exit 0
fi

for file in "${files[@]}"; do
  base="$(basename "${file}")"
  applied="$(docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT 1 FROM arinar_schema_migrations WHERE filename='${base}'" || true)"
  if [ "${applied}" = "1" ]; then
    echo "↪︎ Skipping ${base} (already applied)"
    continue
  fi

  # If this DB already has the initial schema (common when reusing volumes),
  # don't try to re-apply the baseline migration. Just mark it as applied.
  if [[ "${base}" == *"_initial_schema.sql" ]]; then
    has_tenants="$(docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT to_regclass('public.tenants') IS NOT NULL" || true)"
    has_debates="$(docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT to_regclass('public.debates') IS NOT NULL" || true)"
    if [ "${has_tenants}" = "t" ] && [ "${has_debates}" = "t" ]; then
      echo "↪︎ Marking ${base} as applied (schema already present)"
      docker exec "${DB_CONTAINER}" psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" -c "INSERT INTO arinar_schema_migrations (filename) VALUES ('${base}') ON CONFLICT DO NOTHING;"
      continue
    fi
  fi

  # If the debate state constraint is already canonical, mark the alignment migration as applied.
  if [[ "${base}" == *"_align_debate_states.sql" ]]; then
    canonical="$(docker exec "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -tAc "SELECT pg_get_constraintdef(c.oid) LIKE '%pending%' AND pg_get_constraintdef(c.oid) LIKE '%running%' AND pg_get_constraintdef(c.oid) LIKE '%paused%' AND pg_get_constraintdef(c.oid) LIKE '%ended%' FROM pg_constraint c WHERE c.conname='debates_state_check' LIMIT 1" || true)"
    if [ "${canonical}" = "t" ]; then
      echo "↪︎ Marking ${base} as applied (constraint already canonical)"
      docker exec "${DB_CONTAINER}" psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" -c "INSERT INTO arinar_schema_migrations (filename) VALUES ('${base}') ON CONFLICT DO NOTHING;"
      continue
    fi
  fi

  echo "→ Applying ${base}..."
  cat "${file}" | docker exec -i "${DB_CONTAINER}" psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}"
  docker exec "${DB_CONTAINER}" psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" -c "INSERT INTO arinar_schema_migrations (filename) VALUES ('${base}');"
done

echo "✅ Migrations applied successfully"
