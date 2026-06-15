# Supabase Migrations

## Structure

This directory contains SQL migration files applied in sequential order.

## Naming Convention

Format: `YYYYMMDDHHMMSS_description.sql`

Example: `20260205000001_initial_schema.sql`

## Migration Files

1. `20260205000001_initial_schema.sql` - Initial database schema
   - Tenants and workspaces
   - Debates, participants, and events
   - Agents and agent knowledge
   - Memory fabric tables
   - Indexes and RLS policies

## Applying Migrations

```bash
# Apply all migrations
make db-migrate

# Apply specific migration (manual)
docker exec -i arinar-db psql -U postgres -d postgres < infra/supabase/migrations/20260205000001_initial_schema.sql
```

## Creating New Migrations

1. Create new file with timestamp + description
2. Write forward migration SQL
3. Test in local environment
4. Consider rollback strategy
5. Apply with `make db-migrate`

## Rollback Strategy

### Option 1: Forward-only Migrations

Create a new migration to undo changes:
```sql
-- 20260205120000_add_feature.sql
CREATE TABLE feature (...);

-- 20260205130000_remove_feature.sql
DROP TABLE feature;
```

### Option 2: Full Reset

Reset database and reapply migrations:
```bash
make db-reset
```

## Best Practices

1. **Idempotent**: Use `IF NOT EXISTS`, `IF EXISTS` clauses
2. **Transactional**: Keep migrations small and focused
3. **Tested**: Test in local environment before deploying
4. **Documented**: Add comments explaining purpose
5. **Backwards Compatible**: Avoid breaking changes when possible

## Supabase-Specific Notes

### Extensions

Enable required extensions at top of migration:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

### Row Level Security

Enable RLS and create policies:
```sql
ALTER TABLE my_table ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable read for authenticated users" ON my_table
    FOR SELECT USING (auth.role() = 'authenticated');
```

### Realtime

Enable realtime for tables that need subscriptions:
```sql
ALTER PUBLICATION supabase_realtime ADD TABLE events;
```

## References

- [Supabase Migrations](https://supabase.com/docs/guides/database/migrations)
- [PostgreSQL DDL](https://www.postgresql.org/docs/current/ddl.html)
