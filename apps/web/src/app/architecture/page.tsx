'use client';

import { useEffect, useRef } from 'react';
import mermaid from 'mermaid';
import AppNav from '@/components/layout/AppNav';
import styles from './architecture.module.css';

export default function ArchitecturePage() {
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current) {
      mermaid.initialize({
        startOnLoad: true,
        theme: 'dark',
        themeVariables: {
          darkMode: true,
          background: '#000000',
          primaryColor: '#0070F3',
          primaryTextColor: '#fff',
          primaryBorderColor: '#333',
          lineColor: '#666',
          secondaryColor: '#10b981',
          tertiaryColor: '#f59e0b',
          fontSize: '14px',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        },
        flowchart: {
          htmlLabels: true,
          curve: 'basis',
        },
        sequence: {
          diagramMarginX: 50,
          diagramMarginY: 10,
          actorMargin: 50,
          width: 150,
          height: 65,
          boxMargin: 10,
          boxTextMargin: 5,
          noteMargin: 10,
          messageMargin: 35,
        },
      });
      initialized.current = true;
    }

    // Re-render all mermaid diagrams
    mermaid.run({
      querySelector: '.mermaid',
    });
  }, []);

  return (
    <>
      <AppNav />
      <div className={styles.container}>
        <div className={styles.header}>
          <h1>System Architecture</h1>
          <p className={styles.subtitle}>
            PeerForge — Multi-Agent Academic Review Platform
          </p>
        </div>

        <div className={styles.content}>
          {/* High-Level System Overview */}
          <section className={styles.section}>
            <h2>High-Level System Overview</h2>
            <div className={styles.diagramWrapper}>
              <pre className="mermaid">
{`graph TB
    subgraph Frontend["Frontend - Next.js 15"]
        UI[React UI Components]
        WSClient[WebSocket Client]
        APIClient[API Client]
        Hooks[Custom Hooks]
        
        UI --> WSClient
        UI --> APIClient
        UI --> Hooks
    end
    
    subgraph Backend["Backend - FastAPI Python"]
        APIGateway[API Gateway Main]
        DebateRoutes[Debate Routes]
        AutonomousRoutes[Autonomous Routes]
        EventRoutes[Event Routes]
        WSRoutes[WebSocket Routes]
        
        DebateService[Debate Service]
        TurnOrch[Turn Orchestrator]
        AutonomousService[Autonomous Service]
        WSService[WebSocket Service]
        OpenRouterClient[OpenRouter Client]
        PrepPackService[Prep Pack Service]
        StateMachine[State Machine]
        
        APIGateway --> DebateRoutes
        APIGateway --> AutonomousRoutes
        APIGateway --> EventRoutes
        APIGateway --> WSRoutes
        
        DebateRoutes --> DebateService
        DebateRoutes --> TurnOrch
        AutonomousRoutes --> AutonomousService
        WSRoutes --> WSService
        
        TurnOrch --> OpenRouterClient
        TurnOrch --> PrepPackService
        AutonomousService --> TurnOrch
        WSService --> DebateService
    end
    
    subgraph DataLayer["Data Layer - PostgreSQL"]
        DB[(PostgreSQL Database)]
        Debates[debates table]
        Participants[participants table]
        Events[events table]
        Artifacts[artifacts table]
        PrepPacks[prep_packs table]
        
        DB --> Debates
        DB --> Participants
        DB --> Events
        DB --> Artifacts
        DB --> PrepPacks
    end
    
    subgraph External["External Services"]
        OpenRouter[OpenRouter API<br/>Multiple LLM Models]
        Tavily[Tavily Search API<br/>Web Research]
        MinIO[MinIO<br/>File Storage]
    end
    
    WSClient -.WebSocket.-> WSRoutes
    APIClient -->|HTTP REST| APIGateway
    
    DebateService --> DB
    TurnOrch --> DB
    AutonomousService --> DB
    WSService --> DB
    
    OpenRouterClient -->|LLM Calls| OpenRouter
    PrepPackService -->|Web Search| Tavily
    PrepPackService --> MinIO
    
    style UI fill:#0070F3,color:#fff
    style WSClient fill:#0070F3,color:#fff
    style APIClient fill:#0070F3,color:#fff
    
    style APIGateway fill:#10b981,color:#fff
    style DebateService fill:#10b981,color:#fff
    style TurnOrch fill:#10b981,color:#fff
    style AutonomousService fill:#10b981,color:#fff
    
    style DB fill:#666,color:#fff
    
    style OpenRouter fill:#f59e0b,color:#fff
    style Tavily fill:#f59e0b,color:#fff
    style MinIO fill:#f59e0b,color:#fff`}
              </pre>
            </div>
          </section>

          {/* Detailed Component Architecture */}
          <section className={styles.section}>
            <h2>Detailed Component Architecture</h2>
            <div className={styles.diagramWrapper}>
              <pre className="mermaid">
{`graph LR
    subgraph FrontendComponents["Frontend Components"]
        SetupPage[Setup Page<br/>Wizard Flow]
        RoomPage[Room Page<br/>Live Debate]
        HistoryPage[History Page<br/>Past Debates]
        
        SetupPage --> BasicInfoStep
        SetupPage --> ParticipantsStep
        SetupPage --> MaterialsStep
        SetupPage --> PreflightStep
        SetupPage --> ReviewStep
        
        RoomPage --> EventFeed
        RoomPage --> DebateControls
        RoomPage --> InterventionBox
        
        ParticipantsStep --> AgentTemplates[80 Plus Agent Templates]
    end
    
    subgraph BackendServices["Backend Services"]
        DebateSvc[Debate Service<br/>CRUD Operations]
        TurnOrc[Turn Orchestrator<br/>Agent Execution]
        AutoSvc[Autonomous Service<br/>YOLO Mode Loop]
        WSSvc[WebSocket Service<br/>Real-time Events]
        PrepSvc[Prep Pack Service<br/>Research and Context]
        
        TurnOrc --> AgentPrompts[Prompt Engineering]
        TurnOrc --> LLMCalls[OpenRouter Integration]
        AutoSvc --> BackgroundTasks[Asyncio Tasks]
        PrepSvc --> WebSearch[Tavily API]
        PrepSvc --> FileStorage[MinIO Storage]
    end
    
    subgraph DatabaseSchema["Database Schema"]
        DebatesTable[debates<br/>state policy_config autonomous]
        ParticipantsTable[participants<br/>agents and host config]
        EventsTable[events<br/>messages actions system]
        ArtifactsTable[artifacts<br/>documents sections]
        PrepPacksTable[prep_packs<br/>research bundles]
    end
    
    style SetupPage fill:#0070F3,color:#fff
    style RoomPage fill:#0070F3,color:#fff
    style TurnOrc fill:#10b981,color:#fff
    style AutoSvc fill:#10b981,color:#fff
    style DebatesTable fill:#666,color:#fff`}
              </pre>
            </div>
          </section>

          {/* Autonomous YOLO Mode Flow */}
          <section className={styles.section}>
            <h2>Autonomous (YOLO) Mode Flow</h2>
            <div className={styles.diagramWrapper}>
              <pre className="mermaid">
{`sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant AutoService
    participant TurnOrch
    participant OpenRouter
    participant DB
    participant WebSocket

    User->>Frontend: Enable YOLO Mode + Launch
    Frontend->>API: POST /api/debates/id/start-autonomous
    Note over Frontend,API: Includes X-OpenRouter-Key header BYOK
    
    API->>DB: UPDATE debates SET autonomous_mode true
    API->>AutoService: start_autonomous_debate
    AutoService->>AutoService: Create background task run_autonomous_loop
    API-->>Frontend: status started
    
    loop Every N seconds auto_turn_delay
        AutoService->>DB: Check debate status and limits
        alt Status running AND within limits
            AutoService->>TurnOrch: trigger_next_turn
            TurnOrch->>DB: Get next agent and history
            TurnOrch->>TurnOrch: Build agent prompt with context
            TurnOrch->>OpenRouter: POST chat completion
            OpenRouter-->>TurnOrch: Agent response
            TurnOrch->>DB: INSERT event agent_message
            TurnOrch->>WebSocket: Broadcast event to clients
            WebSocket-->>Frontend: Real-time message update
            Frontend->>Frontend: Display in EventFeed
        else Status paused
            AutoService->>AutoService: Sleep and continue loop
        else Limits reached
            AutoService->>AutoService: conclude_debate
            AutoService->>DB: UPDATE debates SET state ended
            AutoService->>AutoService: Exit loop
        end
    end
    
    User->>Frontend: Click Pause
    Frontend->>API: POST /api/debates/id/pause-autonomous
    API->>DB: UPDATE autonomous_status paused
    Note over AutoService: Loop continues but skips turns
    
    User->>Frontend: Click Resume
    Frontend->>API: POST /api/debates/id/resume-autonomous
    Note over Frontend,API: Includes X-OpenRouter-Key header
    API->>DB: UPDATE autonomous_status running
    API->>AutoService: Restart background task if needed`}
              </pre>
            </div>
          </section>

          {/* Turn Orchestration Flow */}
          <section className={styles.section}>
            <h2>Turn Orchestration Flow</h2>
            <div className={styles.diagramWrapper}>
              <pre className="mermaid">
{`flowchart TD
    Start[trigger_next_turn called] --> CheckState{Debate state<br/>equals running?}
    CheckState -->|No| Error1[Throw StateTransitionError]
    CheckState -->|Yes| GetParticipants[Get participants list]
    
    GetParticipants --> CalcNext[Calculate next participant<br/>current_turn_index mod participant_count]
    CalcNext --> CheckLimits{Max rounds<br/>or timebox<br/>exceeded?}
    CheckLimits -->|Yes| Error2[Throw All rounds complete]
    CheckLimits -->|No| GetHistory[Fetch debate history<br/>and prep packs]
    
    GetHistory --> BuildPrompt[Build agent prompt]
    BuildPrompt --> AddContext[Add conversation history]
    AddContext --> AddMentions[Add mention context]
    AddMentions --> AddInterventions[Add moderator interventions]
    AddInterventions --> AddInstructions[Add turn round awareness]
    
    AddInstructions --> CallLLM[Call OpenRouter API]
    CallLLM --> ParseResponse[Parse LLM response]
    ParseResponse --> CalcRound[Calculate round number<br/>turn_index div participant_count plus 1]
    CalcRound --> PersistEvent[INSERT event to DB<br/>with round number]
    
    PersistEvent --> UpdatePolicy[Update policy_config<br/>increment turn_index and total_turns]
    UpdatePolicy --> BroadcastWS[Broadcast via WebSocket]
    BroadcastWS --> Return[Return event details]
    
    style Start fill:#0070F3,color:#fff
    style CallLLM fill:#f59e0b,color:#fff
    style PersistEvent fill:#666,color:#fff
    style Return fill:#10b981,color:#fff`}
              </pre>
            </div>
          </section>

          {/* Database Schema */}
          <section className={styles.section}>
            <h2>Database Schema</h2>
            <div className={styles.diagramWrapper}>
              <pre className="mermaid">
{`erDiagram
    DEBATES ||--o{ PARTICIPANTS : has
    DEBATES ||--o{ EVENTS : contains
    DEBATES ||--o{ ARTIFACTS : produces
    PARTICIPANTS ||--o{ PREP_PACKS : has
    
    DEBATES {
        uuid debate_id PK
        uuid workspace_id
        string title
        string state
        jsonb policy_config
        boolean autonomous_mode
        string autonomous_status
        int auto_turn_delay_seconds
        timestamp created_at
        timestamp started_at
        timestamp ended_at
    }
    
    PARTICIPANTS {
        uuid participant_id PK
        uuid debate_id FK
        string participant_type
        string role_name
        jsonb agent_config
        timestamp created_at
    }
    
    EVENTS {
        uuid event_id PK
        uuid debate_id FK
        string event_type
        string sender_type
        uuid sender_id FK
        bigint sequence_number
        jsonb content
        timestamp created_at
    }
    
    ARTIFACTS {
        uuid artifact_id PK
        uuid debate_id FK
        string artifact_type
        jsonb metadata
        timestamp created_at
    }
    
    PREP_PACKS {
        uuid prep_pack_id PK
        uuid participant_id FK
        uuid debate_id FK
        jsonb search_results
        string status
        timestamp created_at
    }`}
              </pre>
            </div>
          </section>

          {/* State Machines */}
          <section className={styles.section}>
            <h2>Debate State Machine</h2>
            <div className={styles.diagramWrapper}>
              <pre className="mermaid">
{`stateDiagram-v2
    [*] --> pending: Create Debate
    pending --> running: Start Debate
    running --> paused: Pause
    paused --> running: Resume
    running --> ended: End or Conclude
    paused --> ended: End
    ended --> [*]
    
    note right of running: Autonomous mode can be independently paused or resumed without affecting debate state`}
              </pre>
            </div>
          </section>

          <section className={styles.section}>
            <h2>Autonomous Service State Machine</h2>
            <div className={styles.diagramWrapper}>
              <pre className="mermaid">
{`stateDiagram-v2
    [*] --> idle: Service Initialized
    idle --> running: start_autonomous_debate
    running --> paused: pause_autonomous_debate
    paused --> running: resume_autonomous_debate
    running --> completed: Debate limits reached
    running --> crashed: Exception in loop
    crashed --> running: resume_autonomous_debate
    completed --> [*]
    
    note right of running: Background asyncio task checks status every loop iteration and triggers turns automatically`}
              </pre>
            </div>
          </section>

          {/* Key Features */}
          <section className={styles.section}>
            <h2>Key Features</h2>
            <div className={styles.features}>
              <div className={styles.feature}>
                <h3>🧙 Debate Setup Wizard</h3>
                <ul>
                  <li>6-step guided setup flow</li>
                  <li>80+ pre-configured agent personas across 15+ categories</li>
                  <li>Iconic voices (Elon Musk, Steve Jobs, Jeff Bezos, etc.)</li>
                  <li>Medical specialists, legal professionals, tech experts</li>
                  <li>Custom agent creation with inline editing</li>
                  <li>Prep pack generation with web research (Tavily)</li>
                  <li>Host configuration (Ultimate Host as neutral moderator)</li>
                  <li>Policy configuration (max rounds, timebox, YOLO mode)</li>
                </ul>
              </div>

              <div className={styles.feature}>
                <h3>💬 Live Debate Room</h3>
                <ul>
                  <li>Real-time event feed with WebSocket</li>
                  <li>Turn-based orchestration (round-robin)</li>
                  <li>Progress tracking (per-agent turn counts, round numbers)</li>
                  <li>Intervention system (moderator can inject guidance)</li>
                  <li>Autonomous (YOLO) mode with background loop</li>
                  <li>Unified pause/resume controls</li>
                  <li>Turn separators showing round progression</li>
                  <li>@mention support for agent tagging</li>
                </ul>
              </div>

              <div className={styles.feature}>
                <h3>🤖 Agent Intelligence</h3>
                <ul>
                  <li>Multi-model support via OpenRouter</li>
                  <li>Persona-specific system prompts</li>
                  <li>Context-aware prompts with full debate history</li>
                  <li>Web research integration (prep packs)</li>
                  <li>Temperature and token customization per agent</li>
                  <li>First principles thinking, strategic analysis, domain expertise</li>
                </ul>
              </div>

              <div className={styles.feature}>
                <h3>🚀 Autonomous Debates (YOLO Mode)</h3>
                <ul>
                  <li>Background asyncio task loop</li>
                  <li>Auto-triggers agents every N seconds (configurable)</li>
                  <li>Respects max_rounds and timebox limits</li>
                  <li>Pause/resume capability</li>
                  <li>Crash recovery and status tracking</li>
                  <li>BYOK model (Bring Your Own OpenRouter Key)</li>
                </ul>
              </div>

              <div className={styles.feature}>
                <h3>📡 Event System</h3>
                <ul>
                  <li>Sequential event numbering</li>
                  <li>Event types: agent_message, system_message, human_message, intervention, state_update, presence_update</li>
                  <li>WebSocket broadcasting to all connected clients</li>
                  <li>Historical event replay (since sequence number)</li>
                  <li>Persistent storage in PostgreSQL</li>
                </ul>
              </div>

              <div className={styles.feature}>
                <h3>🔐 Security & Authentication</h3>
                <ul>
                  <li>JWT-based authentication for all API endpoints</li>
                  <li>Workspace-based access control (multi-tenancy ready)</li>
                  <li>CORS configured for cross-origin frontend-backend communication</li>
                  <li>Bring Your Own Key (BYOK) model for OpenRouter API</li>
                  <li>API key sent via X-OpenRouter-Key header</li>
                  <li>Never stored server-side (privacy & security)</li>
                  <li>WebSocket authentication via query parameter token</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Tech Stack */}
          <section className={styles.section}>
            <h2>Technology Stack</h2>
            <div className={styles.techStack}>
              <div className={styles.techCategory}>
                <h3>Frontend</h3>
                <ul>
                  <li><strong>Next.js 15 (React)</strong> - Server-side rendering, routing, UI components</li>
                  <li><strong>React Hooks</strong> - Client-side state, WebSocket management</li>
                  <li><strong>CSS Modules</strong> - Scoped styles, Vercel OLED dark theme</li>
                  <li><strong>WebSocket (native)</strong> - Live event streaming</li>
                </ul>
              </div>

              <div className={styles.techCategory}>
                <h3>Backend</h3>
                <ul>
                  <li><strong>FastAPI (Python)</strong> - REST API, WebSocket server, async operations</li>
                  <li><strong>OpenRouter API</strong> - Multi-model LLM support (GPT-4, Claude, etc.)</li>
                  <li><strong>Tavily API</strong> - Real-time web search for agent context</li>
                  <li><strong>Python asyncio</strong> - Autonomous debate loops, async operations</li>
                </ul>
              </div>

              <div className={styles.techCategory}>
                <h3>Data & Storage</h3>
                <ul>
                  <li><strong>PostgreSQL 15+</strong> - Relational data, JSONB for flexible schemas</li>
                  <li><strong>MinIO (S3-compatible)</strong> - Artifact and document storage</li>
                  <li><strong>JWT tokens</strong> - Workspace-based access control</li>
                </ul>
              </div>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
