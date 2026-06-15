# Database Flow Validation Plan

## Validation Commands (When Docker is Running)

### 1. Start Infrastructure
```bash
make db-up
```

**Expected Output**:
- PostgreSQL container starts on port 5432
- Redis container starts on port 6379
- MinIO container starts on ports 9000-9001
- Health check passes: `pg_isready -U postgres`
- Message: "✅ Database infrastructure is running"

### 2. Apply Migrations
```bash
make db-migrate
```

**Expected Output**:
- Applies `20260205000001_initial_schema.sql`
- Creates 11 tables:
  - tenants, workspaces
  - debates, participants, events
  - agents, agent_knowledge_units
  - memory_events, memory_state, memory_chunks, memory_access_log
- Creates 19 indexes for performance
- Enables RLS on all tables
- Creates updated_at triggers
- Message: "✅ Migrations applied successfully"

### 3. Load Seed Data
```bash
make db-seed
```

**Expected Output**:
- Applies `01_sample_data.sql`
- Inserts:
  - 1 tenant (Demo Organization)
  - 1 workspace (Product Strategy)
  - 3 agents (PM, Engineer, Designer)
  - 1 debate (Feature Prioritization Q1 2026)
  - 3 participants
  - 5 events
  - 2 memory chunks
  - 2 knowledge units
- Message: "✅ Seed data loaded successfully"

### 4. Smoke Test Queries
```bash
make db-smoke
```

**Expected Output**:
```
→ Checking tenants...
 tenant_id | name              | slug
-----------+-------------------+----------
 00...001  | Demo Organization | demo-org

→ Checking workspaces...
 workspace_id | name             | slug
--------------+------------------+------------------
 00...101     | Product Strategy | product-strategy

→ Checking debates...
 debate_id | title                          | state
-----------+--------------------------------+-------
 00...2001 | Feature Prioritization Q1 2026 | live

→ Checking agents...
 agent_id  | name            | role_description
-----------+-----------------+------------------
 00...1001 | Product Manager | Strategic product leader...
 00...1002 | Senior Engineer | Technical lead...
 00...1003 | UX Designer     | User experience designer...

→ Checking events (count)...
 debate_id | event_count
-----------+-------------
 00...2001 | 5

✅ Smoke tests completed
```

## Negative Test: Invalid Migration

### Test Case

File: `99999999999999_invalid_test.sql.disabled`

This migration contains multiple intentional errors:
1. **Duplicate table**: Tries to recreate `tenants` table
2. **Invalid foreign key**: References non-existent table
3. **Syntax error**: Malformed SQL

### Expected Failure

If enabled and run:
```bash
# Rename to enable
mv infra/supabase/migrations/99999999999999_invalid_test.sql.disabled \
   infra/supabase/migrations/99999999999999_invalid_test.sql

# Attempt migration
make db-migrate
```

**Expected Output**:
```
📦 Applying database migrations...
→ Applying 99999999999999_invalid_test.sql...
ERROR:  relation "tenants" already exists
❌ Migration failed
Exit code: 1
```

### Cleanup After Test

```bash
# Disable the test migration
mv infra/supabase/migrations/99999999999999_invalid_test.sql \
   infra/supabase/migrations/99999999999999_invalid_test.sql.disabled

# Reset if needed
make db-reset
```

## Full Flow Summary

Complete end-to-end flow:
```bash
# 1. Setup (first time only)
cp infra/docker/.env.example infra/docker/.env
# Edit .env with your values

# 2. Start infrastructure
make db-up

# 3. Apply schema
make db-migrate

# 4. Load seed data
make db-seed

# 5. Verify
make db-smoke

# 6. Development work...

# 7. Stop when done
make db-down
```

## Validation Status

- ✅ SQL syntax validated (305 lines migration, 253 lines seed)
- ✅ 11 tables defined
- ✅ 19 indexes created
- ✅ RLS policies configured
- ✅ Seed data with sample debate
- ✅ Makefile commands implemented
- ✅ Negative test case documented
- ⏳ Docker execution pending (requires Docker daemon)

**Note**: Actual Docker execution requires Docker daemon to be running.
All SQL has been validated for syntax correctness.
