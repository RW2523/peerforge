# Local Infrastructure and Migrations Runbook

## Overview
This runbook covers setup, management, and troubleshooting of the local Supabase development environment for Arinar V2.

## Quick Start

```bash
# 1. Start infrastructure
make db-up

# 2. Apply migrations
make db-migrate

# 3. Load seed data
make db-seed

# 4. Verify setup
make db-smoke
```

## Architecture

### Stack Components

- **PostgreSQL 15**: Primary database with uuid-ossp and pgcrypto extensions
- **Redis 7**: Caching and session storage
- **MinIO**: S3-compatible object storage for local development
- **Supabase Studio**: Database management UI (optional, via full docker-compose)

### Database Schema

Core tables:
- `tenants` / `workspaces`: Multi-tenancy and organization
- `debates` / `participants` / `events`: Debate sessions and event ledger
- `agents` / `agent_knowledge_units`: Agent definitions and learned knowledge
- `memory_events` / `memory_state` / `memory_chunks` / `memory_access_log`: Memory fabric

## Setup Instructions

### Prerequisites

- Docker and Docker Compose installed
- Ports available: 5432 (PostgreSQL), 6379 (Redis), 9000-9001 (MinIO)
- Minimum 2GB RAM available for containers

### Initial Setup

1. **Copy environment file**:
   ```bash
   cp infra/docker/.env.example infra/docker/.env
   ```

2. **Update environment variables**:
   ```bash
   # Edit infra/docker/.env
   # Update POSTGRES_PASSWORD, JWT_SECRET, OPENROUTER_API_KEY
   ```

3. **Start infrastructure**:
   ```bash
   make db-up
   ```
   
   This starts PostgreSQL, Redis, and MinIO containers.

4. **Apply schema migrations**:
   ```bash
   make db-migrate
   ```
   
   Applies SQL migrations in order from `infra/supabase/migrations/`.
   
   Notes:
   - Migrations are tracked in the DB table `arinar_schema_migrations`.
   - Safe to re-run: already-applied migrations are skipped.
   - If you change a migration file that has already been applied, you must create a new migration instead.

5. **Load seed data** (optional for development):
   ```bash
   make db-seed
   ```
   
   Loads sample data from `infra/supabase/seed/`

6. **Verify setup**:
   ```bash
   make db-smoke
   ```
   
   Runs queries to confirm all tables exist and contain expected data.

## Daily Operations

### Starting/Stopping

```bash
# Start (safe to run multiple times)
make db-up

# Stop (preserves data volumes)
make db-down

# Check status
docker ps | grep arinar
```

### Viewing Logs

```bash
# PostgreSQL logs
make db-logs

# All container logs
cd infra/docker && docker-compose logs -f
```

### Database Access

**Via psql (inside container)**:
```bash
docker exec -it arinar-db psql -U postgres -d postgres
```

**Via psql (from host)**:
```bash
psql -h localhost -p 5432 -U postgres -d postgres
```

**Connection string**:
```
postgresql://postgres:your-password@localhost:5432/postgres
```

## Migration Management

### Migration File Structure

Location: `infra/supabase/migrations/`

Naming convention: `YYYYMMDDHHMMSS_description.sql`

Example: `20260205000001_initial_schema.sql`

### Creating a New Migration

1. **Create migration file**:
   ```bash
   # Use timestamp + descriptive name
   touch infra/supabase/migrations/20260205120000_add_user_preferences.sql
   ```

2. **Write migration SQL**:
   ```sql
   -- Migration: 20260205120000_add_user_preferences.sql
   -- Description: Add user preferences table
   
   CREATE TABLE user_preferences (
       user_id UUID PRIMARY KEY,
       preferences JSONB DEFAULT '{}',
       created_at TIMESTAMPTZ DEFAULT NOW()
   );
   
   CREATE INDEX idx_user_preferences_user_id ON user_preferences(user_id);
   ```

3. **Apply migration**:
   ```bash
   make db-migrate
   ```

### Rollback Strategy

**Option 1: Manual Rollback**

Create a rollback migration:
```sql
-- Migration: 20260205120001_rollback_user_preferences.sql
DROP TABLE IF EXISTS user_preferences;
```

**Option 2: Full Reset**

Reset entire database (WARNING: destroys all data):
```bash
make db-reset
```

This drops volumes, recreates containers, reapplies all migrations, and reloads seed data.

## Seed Data Management

### Seed File Structure

Location: `infra/supabase/seed/`

Files: `01_sample_data.sql`, `02_additional_data.sql`, etc.

### Loading Seed Data

```bash
# Load all seed files
make db-seed

# Load specific seed file
docker exec -i arinar-db psql -U postgres -d postgres < infra/supabase/seed/01_sample_data.sql
```

### Creating Custom Seed Data

1. Create new file: `infra/supabase/seed/02_custom_data.sql`
2. Add `ON CONFLICT ... DO NOTHING` to make idempotent
3. Run `make db-seed`

## Troubleshooting

### Problem: Database won't start

**Symptoms**:
```
Error: Cannot start service db: port is already allocated
```

**Solutions**:
1. Check if PostgreSQL is already running on port 5432:
   ```bash
   lsof -i :5432
   # Kill conflicting process or change port in docker-compose.yml
   ```

2. Remove stale containers:
   ```bash
   docker rm -f arinar-db
   make db-up
   ```

### Problem: Migrations fail with "relation already exists"

**Symptoms**:
```
ERROR: relation "tenants" already exists
```

**Solutions**:
1. Migrations were partially applied. Reset database:
   ```bash
   make db-reset
   ```

2. Or manually drop and recreate:
   ```bash
   docker exec -it arinar-db psql -U postgres -d postgres -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
   make db-migrate
   ```

### Problem: Permission denied errors

**Symptoms**:
```
ERROR: permission denied for table tenants
```

**Solutions**:
1. Check RLS policies are correct
2. Use service_role key for backend operations
3. Verify user roles and grants

### Problem: Connection refused

**Symptoms**:
```
psql: error: connection to server at "localhost" (::1), port 5432 failed: Connection refused
```

**Solutions**:
1. Ensure database is running:
   ```bash
   docker ps | grep arinar-db
   ```

2. Check container health:
   ```bash
   docker logs arinar-db
   ```

3. Restart infrastructure:
   ```bash
   make db-down && make db-up
   ```

### Problem: Seed data doesn't load

**Symptoms**:
```
ERROR: duplicate key value violates unique constraint
```

**Solutions**:
1. Seed data uses `ON CONFLICT DO NOTHING` - safe to run multiple times
2. Check for data conflicts if custom seed data added
3. Reset and reload:
   ```bash
   make db-reset
   ```

## Performance Tips

### Query Optimization

1. **Use indexes**: All major query paths have indexes
2. **Batch inserts**: Use `INSERT ... VALUES (...), (...)` for multiple rows
3. **Limit results**: Always use LIMIT for large result sets
4. **Explain plans**: Use `EXPLAIN ANALYZE` to understand query performance

### Connection Pooling

For production, use connection pooling:
- PgBouncer (recommended)
- Application-level pooling (SQLAlchemy, Prisma)

### Monitoring

```bash
# Check active connections
docker exec arinar-db psql -U postgres -d postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check table sizes
docker exec arinar-db psql -U postgres -d postgres -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

## Security Notes

### Local Development

- Default passwords are in `.env` file (NOT in git)
- Service role key has full access - protect carefully
- RLS policies are enabled but permissive for local dev

### Production Checklist

Before deploying to production:
1. ✅ Change all default passwords
2. ✅ Enable strict RLS policies
3. ✅ Review and restrict service role usage
4. ✅ Enable SSL/TLS connections
5. ✅ Configure backup strategy
6. ✅ Set up monitoring and alerting
7. ✅ Review and harden network access

## Backup and Restore

### Manual Backup

```bash
# Backup entire database
docker exec arinar-db pg_dump -U postgres postgres > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup specific tables
docker exec arinar-db pg_dump -U postgres -t events -t debates postgres > events_backup.sql
```

### Restore from Backup

```bash
# Restore full backup
docker exec -i arinar-db psql -U postgres postgres < backup_20260205_120000.sql

# Restore specific tables
docker exec -i arinar-db psql -U postgres postgres < events_backup.sql
```

## Integration with Application

### Connection Configuration

**Python (FastAPI)**:
```python
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://postgres:password@localhost:5432/postgres"
engine = create_engine(DATABASE_URL)
```

**TypeScript (Prisma)**:
```typescript
// DATABASE_URL="postgresql://postgres:password@localhost:5432/postgres"
```

**Environment Variables**:
```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/postgres
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

## Testing

### Integration Test Setup

```bash
# 1. Start test database
TEST_DB_NAME=arinar_test make db-up

# 2. Run migrations
make db-migrate

# 3. Run tests (with automatic cleanup)
pytest tests/integration/

# 4. Clean up
make db-down
```

### Test Data Isolation

Use transactions for test isolation:
```python
@pytest.fixture
def db_transaction():
    connection = engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()
```

## Troubleshooting

### Port Conflicts
**Symptom:** `db-up` fails with "Address already in use"  
**Solution:** Check for existing services on ports 5432, 54321, 54323-54327
```bash
lsof -i :5432  # Check who's using port 5432
docker ps      # Check for existing Supabase containers
```

### Database Connection Failed from API
**Symptom:** `password authentication failed for user "postgres"`  
**Root Cause:** API `.env` file doesn't match actual database credentials

**Solution:**
1. Check actual password in `infra/docker/.env`:
   ```bash
   grep POSTGRES_PASSWORD infra/docker/.env
   ```
2. Update `apps/api/.env.local` to match:
   ```env
   DATABASE_URL=postgresql://postgres:<PASSWORD_FROM_STEP_1>@127.0.0.1:5432/postgres
   ```
3. Restart API server

**Why 127.0.0.1 instead of localhost?**  
macOS/Linux may resolve `localhost` to IPv6 `::1`, causing connection issues if Docker only binds to IPv4.

### Migration Errors
**Symptom:** SQL errors during `make db-migrate`  
**Solution:** Check `infra/supabase/migrations/*.sql` for syntax errors. Run individual migration manually:
```bash
docker exec -i arinar-db psql -U postgres -d postgres < infra/supabase/migrations/FILENAME.sql
```

### Seed Data Errors
**Symptom:** FK constraint violations during `make db-seed`  
**Solution:** Verify FK relationships in `infra/supabase/seed/*.sql`. Ensure parent records (tenants, workspaces) exist before children (debates, agents).

### Invalid Debate State Enum Error
**Symptom:** API returns `'draft' is not a valid DebateState` or `'live' is not a valid DebateState`  
**Root Cause:** Database schema constraint doesn't match application DebateState enum

**Solution:**
This indicates schema drift. Check if migration `20260206000001_align_debate_states.sql` exists and is applied:
```bash
docker exec arinar-db psql -U postgres -d postgres -c "\d debates" | grep state_check
```

If constraint shows `draft|live|closed` instead of `pending|running|paused|ended`, apply alignment migration (see `reports/DEMO-01-2026-02-06-v1.md` for migration SQL).

## References

- [Supabase Documentation](https://supabase.com/docs)
- [PostgreSQL 15 Documentation](https://www.postgresql.org/docs/15/)
- [Engineering Standards](../../2026-goals-codex/15-engineering-standards-and-anti-chaos-rules.md)
- [Memory Fabric Architecture](../../2026-goals-codex/06-memory-fabric-architecture-2026.md)

## Support

For issues or questions:
1. Check this runbook first
2. Review application logs
3. Check database logs with `make db-logs`
4. Create an issue with reproduction steps
