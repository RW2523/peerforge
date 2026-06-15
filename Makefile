.PHONY: help lint typecheck test api-test verify clean install db-up db-down db-reset db-migrate db-seed db-smoke db-logs

# Default target
help:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Arinar V2 - Development Commands"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Application:"
	@echo "  make install    - Install all dependencies"
	@echo "  make lint       - Run linters (format check)"
	@echo "  make typecheck  - Run type checkers"
	@echo "  make test       - Run contract tests"
	@echo "  make api-test   - Run API tests (apps/api)"
	@echo "  make verify     - Run all quality gates (includes api-test)"
	@echo "  make clean      - Clean build artifacts"
	@echo ""
	@echo "Database (Supabase Local):"
	@echo "  make db-up      - Start local database infrastructure"
	@echo "  make db-down    - Stop local database infrastructure"
	@echo "  make db-reset   - Reset database (drop + migrate + seed)"
	@echo "  make db-migrate - Apply migrations"
	@echo "  make db-seed    - Load seed data"
	@echo "  make db-smoke   - Run smoke test queries"
	@echo "  make db-logs    - Show database logs"
	@echo ""
	@echo "CI equivalent:"
	@echo "  make verify     - Runs all checks (lint + typecheck + test + api-test + gates)"
	@echo ""

# Install dependencies
install:
	@echo "📦 Installing dependencies..."
	@cd packages/contracts && npm install
	@echo "✅ Dependencies installed"

# Lint checks
lint:
	@echo "🔍 Running lint checks..."
	@echo ""
	@echo "→ Linting contracts package..."
	@cd packages/contracts && npm run validate:all || exit 1
	@echo ""
	@echo "✅ Lint checks passed"

# Type checks
typecheck:
	@echo "🔍 Running type checks..."
	@echo ""
	@echo "→ Checking contracts types..."
	@cd packages/contracts && npm run generate:types || exit 1
	@echo ""
	@echo "✅ Type checks passed"

# Run contract tests
test:
	@echo "🧪 Running contract tests..."
	@echo ""
	@echo "→ Testing contracts..."
	@cd packages/contracts && npm test || exit 1
	@echo ""
	@echo "✅ Contract tests passed"

# Run API tests (apps/api)
api-test:
	@echo "🧪 Running API tests..."
	@echo ""
	@echo "→ Running pytest..."
	@cd apps/api && \
		if [ -x .venv/bin/python3.11 ]; then \
			.venv/bin/python3.11 -m pytest tests/ -v || exit 1; \
		elif [ -x .venv/bin/python ]; then \
			.venv/bin/python -m pytest tests/ -v || exit 1; \
		elif command -v python3.11 >/dev/null 2>&1; then \
			python3.11 -m pytest tests/ -v || exit 1; \
		elif command -v python3 >/dev/null 2>&1; then \
			python3 -m pytest tests/ -v || exit 1; \
		else \
			echo "❌ No python interpreter found. Install Python 3.11+ and/or create apps/api/.venv."; \
			exit 1; \
		fi
	@echo ""
	@echo "✅ API tests passed"

# Run all quality gates (full verify)
verify: lint typecheck test api-test
	@echo ""
	@echo "🚀 Running quality gates..."
	@echo ""
	@bash scripts/check_file_sizes.sh || exit 1
	@echo ""
	@bash scripts/check_duplicates.sh || exit 1
	@echo ""
	@bash scripts/check_forbidden_patterns.sh || exit 1
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ All quality gates passed!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	@find . -type d -name "node_modules" -prune -exec rm -rf {} \; 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} \; 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} \; 2>/dev/null || true
	@find . -type d -name "dist" -exec rm -rf {} \; 2>/dev/null || true
	@find . -type d -name "build" -exec rm -rf {} \; 2>/dev/null || true
	@echo "✅ Clean complete"

# ============================================================================
# DATABASE COMMANDS (Supabase Local)
# ============================================================================

# Start local database infrastructure
db-up:
	@echo "🚀 Starting local database infrastructure..."
	@cd infra/docker && docker-compose up -d db redis minio
	@echo "⏳ Waiting for PostgreSQL to be ready..."
	@sleep 5
	@docker exec arinar-db pg_isready -U postgres || (echo "❌ Database not ready" && exit 1)
	@echo "✅ Database infrastructure is running"
	@echo ""
	@echo "PostgreSQL: localhost:5432"
	@echo "Redis: localhost:6379"
	@echo "MinIO: localhost:9000 (console: localhost:9001)"
	@echo ""
	@echo "Run 'make db-migrate' to apply schema migrations"

# Stop local database infrastructure
db-down:
	@echo "🛑 Stopping local database infrastructure..."
	@cd infra/docker && docker-compose down
	@echo "✅ Database infrastructure stopped"

# Reset database (drop all + migrate + seed)
db-reset:
	@echo "🔄 Resetting database..."
	@echo "⚠️  This will destroy all data!"
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(MAKE) db-down; \
		docker volume rm arinar-db-data 2>/dev/null || true; \
		$(MAKE) db-up; \
		sleep 3; \
		$(MAKE) db-migrate; \
		$(MAKE) db-seed; \
		echo "✅ Database reset complete"; \
	else \
		echo "❌ Reset cancelled"; \
		exit 1; \
	fi

# Apply migrations
db-migrate:
	@echo "📦 Applying database migrations..."
	@if ! docker ps | grep -q arinar-db; then \
		echo "❌ Database is not running. Run 'make db-up' first."; \
		exit 1; \
	fi
	@bash scripts/db_apply_migrations.sh

# Load seed data
db-seed:
	@echo "🌱 Loading seed data..."
	@if ! docker ps | grep -q arinar-db; then \
		echo "❌ Database is not running. Run 'make db-up' first."; \
		exit 1; \
	fi
	@for file in infra/supabase/seed/*.sql; do \
		echo "→ Loading $$(basename $$file)..."; \
		docker exec -i arinar-db psql -U postgres -d postgres < $$file || exit 1; \
	done
	@echo "✅ Seed data loaded successfully"

# Run smoke test queries
db-smoke:
	@echo "🔍 Running database smoke tests..."
	@if ! docker ps | grep -q arinar-db; then \
		echo "❌ Database is not running. Run 'make db-up' first."; \
		exit 1; \
	fi
	@echo ""
	@echo "→ Checking tenants..."
	@docker exec arinar-db psql -U postgres -d postgres -c "SELECT tenant_id, name, slug FROM tenants;"
	@echo ""
	@echo "→ Checking workspaces..."
	@docker exec arinar-db psql -U postgres -d postgres -c "SELECT workspace_id, name, slug FROM workspaces;"
	@echo ""
	@echo "→ Checking debates..."
	@docker exec arinar-db psql -U postgres -d postgres -c "SELECT debate_id, title, state FROM debates;"
	@echo ""
	@echo "→ Checking agents..."
	@docker exec arinar-db psql -U postgres -d postgres -c "SELECT agent_id, name, role_description FROM agents;"
	@echo ""
	@echo "→ Checking events (count)..."
	@docker exec arinar-db psql -U postgres -d postgres -c "SELECT debate_id, COUNT(*) as event_count FROM events GROUP BY debate_id;"
	@echo ""
	@echo "✅ Smoke tests completed"

# Show database logs
db-logs:
	@docker logs arinar-db --tail 100 -f
