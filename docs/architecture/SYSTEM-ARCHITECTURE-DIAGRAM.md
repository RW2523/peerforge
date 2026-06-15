# System Architecture Diagram (Current Implementation)

Last updated: 2026-02-17

## 1) High-Level Component Architecture

```mermaid
flowchart LR
    U["Operator/User"] --> W["Web App (Next.js)"]

    subgraph Frontend["apps/web"]
      W --> SPA["Room Page + Hooks\nroom/page.tsx + useDebateRoom.ts"]
      SPA --> APIClient["REST Client\nlib/api.ts"]
      SPA --> WSClient["WebSocket Client\nlib/wsClient.ts"]
      SPA --> SupabaseClient["Supabase Auth\nlib/supabase.ts"]
    end

    SupabaseClient --> Supabase["Supabase Auth Service"]
    Supabase -->|"JWT"| APIClient
    Supabase -->|"JWT"| WSClient

    APIClient -->|"HTTPS REST"| FastAPI["FastAPI Domain Service\napps/api/src/main.py"]
    WSClient -->|"WSS /ws/debates/{id}"| WSRoute["WebSocket Route\nroutes/websocket.py"]

    subgraph API["apps/api"]
      FastAPI --> DebateRoutes["Debates + Turns + Preflight + Materials + Autonomous Routes"]
      DebateRoutes --> DebateService["DebateService / State Machine"]
      DebateRoutes --> TurnOrchestrator["TurnOrchestrator"]
      DebateRoutes --> PreflightTask["Preflight Orchestrator\n(tasks/preflight.py)"]
      DebateRoutes --> MaterialRoutes["Materials Upload API\n(routes/materials.py)"]

      WSRoute --> WSService["WebSocketService + Handlers"]
      WSService --> TurnOrchestrator
      PreflightTask --> WSService

      MaterialRoutes --> MinIOClient["MinIO Storage Client"]
      MaterialRoutes --> CeleryTask["Celery Tasks\n(tasks/material_processing.py)"]
      CeleryTask --> ExtractChunk["Text Extraction + Chunking"]
    end

    TurnOrchestrator -->|"LLM Completion"| OpenRouter["OpenRouter API"]
    PreflightTask -->|"Prep Pack Generation"| OpenRouter
    PreflightTask -->|"Optional Web Research"| DuckDuckGo["DuckDuckGo Search"]

    FastAPI -->|"SQL"| PG["PostgreSQL (Supabase Local DB)"]
    WSService -->|"Read/Write Events"| PG
    PreflightTask -->|"Read/Write Preflight + Knowledge"| PG
    ExtractChunk -->|"Write memory_chunks"| PG

    CeleryTask -->|"Broker / Backend"| Redis["Redis"]
    CeleryTask --> MinIO["MinIO Object Storage"]
    MinIOClient --> MinIO
```

## 2) Runtime Flow (Room + Preflight)

```mermaid
sequenceDiagram
    participant User as Operator
    participant Web as Next.js Room UI
    participant API as FastAPI
    participant WS as WebSocketService
    participant DB as PostgreSQL
    participant OR as OpenRouter

    User->>Web: Open /room?debate_id=...
    Web->>API: GET /debates/{id}
    API->>DB: Read debate + participants
    DB-->>API: Debate payload
    API-->>Web: Debate payload

    Web->>WS: Connect /ws/debates/{id}?token=...
    WS->>DB: Replay events since sequence
    DB-->>WS: Historical events
    WS-->>Web: Event envelopes

    User->>Web: Start preflight
    Web->>API: POST /debates/{id}/preflight/start
    API->>DB: Create preflight_runs + participant_runs
    API-->>Web: Accepted (run_id)
    API->>API: Background thread orchestrate_preflight_impl
    API->>OR: Generate prep pack(s)
    API->>DB: Persist agent_knowledge_units + statuses
    API->>WS: Broadcast preflight_progress
    WS-->>Web: Progress updates

    User->>Web: Trigger next turn
    Web->>WS: command control.next_turn
    WS->>API: TurnOrchestrator.trigger_next_turn
    API->>DB: Load history + participants + prep pack
    API->>OR: Generate agent response
    OR-->>API: Agent message
    API->>DB: Persist event + update turn counters
    API->>WS: Broadcast agent_message
    WS-->>Web: Real-time room update
```

## Source Pointers

- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/main.py`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/routes/websocket.py`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/routes/preflight.py`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/tasks/preflight.py`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/routes/materials.py`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/tasks/material_processing.py`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/api/src/turn_orchestrator.py`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/app/room/page.tsx`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/hooks/useDebateRoom.ts`
- `/Users/pv/Downloads/arinar-6-IPSS-V5/arinar-v2/apps/web/src/lib/api.ts`
