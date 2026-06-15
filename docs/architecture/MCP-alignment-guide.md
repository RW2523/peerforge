# MCP Alignment Guide for Supabase Integration

## Purpose
This document describes how Model Context Protocol (MCP) can be integrated with Supabase for AI agent data access, while keeping runtime application access direct and performant.

## Architecture Principle

**Dual Access Pattern**:
- **Runtime application** (apps/api): Direct PostgreSQL access via SQLAlchemy/Prisma
- **AI agents** (future MCP integration): Query via MCP Supabase server

This separation provides:
- Performance: App doesn't pay MCP overhead
- Security: MCP can enforce additional guardrails
- Flexibility: Agents can query without app code changes

## Runtime Application Access (Current)

### apps/api (FastAPI)

Direct database access for production performance:

```python
# apps/api/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_size=20)
SessionLocal = sessionmaker(bind=engine)

# Direct queries for performance
def get_debate_events(debate_id: UUID) -> List[Event]:
    with SessionLocal() as session:
        return session.query(Event).filter(
            Event.debate_id == debate_id
        ).order_by(Event.created_at).all()
```

### apps/web (Next.js)

Calls FastAPI endpoints, never direct DB access:

```typescript
// apps/web/lib/api.ts
export async function getDebateEvents(debateId: string) {
  const response = await fetch(`${API_URL}/debates/${debateId}/events`);
  return response.json();
}
```

## MCP Agent Access (Future)

### Use Case: AI Agents Querying Context

AI coding agents or conversational agents can query Supabase via MCP for:
- Retrieving debate history
- Searching memory chunks
- Analyzing agent knowledge
- Audit trail queries

### MCP Server Configuration

**Example: Supabase MCP Server Config**

```json
{
  "mcpServers": {
    "supabase-arinar": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-supabase",
        "--url", "postgresql://postgres:password@localhost:5432/postgres",
        "--schema", "public"
      ],
      "env": {
        "SUPABASE_URL": "http://localhost:8000",
        "SUPABASE_SERVICE_KEY": "your-service-role-key-here"
      }
    }
  }
}
```

### Agent Query Examples

**Example 1: Retrieve debate history**

Agent prompt:
```
Query the database for all events from debate_id='abc-123' ordered by created_at.
Include event_type, sender_type, and content fields.
```

MCP query (generated):
```sql
SELECT event_id, event_type, sender_type, content, created_at
FROM events
WHERE debate_id = 'abc-123'
ORDER BY created_at ASC
LIMIT 100;
```

**Example 2: Search agent knowledge**

Agent prompt:
```
Find all knowledge units for agent 'Product Manager' related to 'user onboarding'.
```

MCP query (generated):
```sql
SELECT ku.content, ku.confidence_score, a.name, ku.created_at
FROM agent_knowledge_units ku
JOIN agents a ON ku.agent_id = a.agent_id
WHERE a.name = 'Product Manager'
  AND ku.content ILIKE '%user onboarding%'
ORDER BY ku.confidence_score DESC
LIMIT 20;
```

**Example 3: Memory retrieval**

Agent prompt:
```
Search memory chunks for agent_id='xyz-456' containing 'API design patterns'.
```

MCP query (generated):
```sql
SELECT chunk_id, chunk_text, chunk_metadata, created_at
FROM memory_chunks
WHERE agent_id = 'xyz-456'
  AND chunk_text ILIKE '%API design patterns%'
ORDER BY created_at DESC
LIMIT 10;
```

## Security Boundaries

### MCP Access Control

**Recommended MCP policies**:

1. **Read-only by default**: MCP queries should be SELECT-only
2. **Tenant scoping**: Always filter by tenant_id/workspace_id
3. **Rate limiting**: Enforce query rate limits per agent
4. **Audit logging**: Log all MCP queries to memory_access_log

### Example: Tenant-scoped MCP Query

```sql
-- Safe: Always scoped to tenant
SELECT d.title, COUNT(e.event_id) as event_count
FROM debates d
JOIN workspaces w ON d.workspace_id = w.workspace_id
JOIN events e ON d.debate_id = e.debate_id
WHERE w.tenant_id = :tenant_id
GROUP BY d.debate_id, d.title;
```

### Example: Unsafe Query (Don't Allow)

```sql
-- Unsafe: No tenant scoping, could leak data
SELECT * FROM events LIMIT 1000;
```

## Performance Considerations

### When to Use MCP vs Direct Access

**Use Direct Access** (apps/api):
- ✅ High-frequency queries
- ✅ Transaction-critical operations
- ✅ Bulk data processing
- ✅ Real-time event writes

**Use MCP** (AI agents):
- ✅ Exploratory queries
- ✅ Context retrieval for agent reasoning
- ✅ Audit trail analysis
- ✅ Ad-hoc research queries

### MCP Query Optimization

```sql
-- Good: Indexed query with limit
SELECT * FROM events
WHERE debate_id = :debate_id
ORDER BY created_at DESC
LIMIT 50;

-- Bad: Full table scan without limit
SELECT * FROM events
WHERE content::text LIKE '%keyword%';
```

## Integration Checklist

When adding MCP integration:

1. ✅ Configure MCP server with Supabase connection
2. ✅ Test read-only queries work
3. ✅ Verify tenant isolation in queries
4. ✅ Add audit logging for MCP access
5. ✅ Document available query patterns
6. ✅ Set query timeout limits
7. ✅ Enable rate limiting

## Example: Memory Fabric Query via MCP

**Agent workflow**:

1. Agent needs context about prior debate
2. Agent asks: "What did we decide about API rate limiting in the last architecture review?"
3. MCP server queries:
   ```sql
   SELECT e.content, e.created_at, d.title
   FROM events e
   JOIN debates d ON e.debate_id = d.debate_id
   WHERE d.workspace_id = :workspace_id
     AND d.title ILIKE '%architecture%'
     AND e.content::text ILIKE '%rate limiting%'
   ORDER BY e.created_at DESC
   LIMIT 10;
   ```
4. Agent receives results and formulates answer with citations

## Future Enhancements

### Vector Search (pgvector)

When enabled:
```sql
-- Add vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to memory_chunks
ALTER TABLE memory_chunks ADD COLUMN embedding vector(1536);

-- Create index for similarity search
CREATE INDEX ON memory_chunks USING ivfflat (embedding vector_cosine_ops);

-- Similarity search query
SELECT chunk_text, 1 - (embedding <=> :query_embedding) as similarity
FROM memory_chunks
WHERE agent_id = :agent_id
ORDER BY embedding <=> :query_embedding
LIMIT 10;
```

### Full-Text Search

```sql
-- Add tsvector column
ALTER TABLE memory_chunks ADD COLUMN search_vector tsvector;

-- Create GIN index
CREATE INDEX idx_memory_chunks_search ON memory_chunks USING GIN(search_vector);

-- Update trigger for automatic tsvector updates
CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE
ON memory_chunks FOR EACH ROW EXECUTE FUNCTION
tsvector_update_trigger(search_vector, 'pg_catalog.english', chunk_text);

-- Full-text search query
SELECT chunk_text
FROM memory_chunks
WHERE search_vector @@ to_tsquery('english', 'API & design');
```

## Supabase-Specific Features

### Real-time Subscriptions

Supabase provides real-time subscriptions for table changes:

```typescript
// Subscribe to new events in a debate
const subscription = supabase
  .from('events')
  .on('INSERT', payload => {
    console.log('New event:', payload.new);
  })
  .filter('debate_id', 'eq', debateId)
  .subscribe();
```

### Storage Integration

For file uploads (documents, images):

```typescript
// Upload file to Supabase Storage
const { data, error } = await supabase.storage
  .from('debate-attachments')
  .upload(`${debateId}/${filename}`, file);
```

## References

- [Supabase Documentation](https://supabase.com/docs)
- [MCP Documentation](https://modelcontextprotocol.io)
- [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Memory Fabric Architecture](./06-memory-fabric-architecture-2026.md)

---

**Status**: Framework prepared for future MCP integration  
**Runtime Access**: Direct database access maintained for performance  
**Last Updated**: 2026-02-05
