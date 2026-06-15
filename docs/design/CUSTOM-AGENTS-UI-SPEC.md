# Custom Agents UI - Design Specification

**Date:** 2026-02-09  
**Status:** Design Proposal  
**Related:** AGENT-PREPARATION-ARCHITECTURE.md  
**Priority:** HIGH (Can be built in parallel with materials pipeline)

---

## Goal

Enable users to create, edit, and manage custom AI agents from the Settings page.

**User Value**: Not limited to 10 preset templates - users can create agents tailored to their specific needs.

---

## User Stories

### **Story 1: Create Custom Agent**
```
As a user,
I want to create a custom agent with my own prompt and character,
So that I can have domain-specific experts in my debates.

Acceptance Criteria:
- Settings page has "Custom Agents" section
- Form to create agent: name, role, character, system prompt, model
- Prompt preview before saving
- Agent saved to my workspace
- Agent appears in setup wizard participant selection
```

### **Story 2: Edit Existing Agent**
```
As a user,
I want to edit agents I created,
So that I can refine prompts based on debate quality.

Acceptance Criteria:
- List shows all custom agents in workspace
- Click "Edit" opens form with current values
- Can update any field
- Can delete agent (with confirmation)
```

### **Story 3: Prompt Preview**
```
As a user,
I want to preview the exact prompt that will be used,
So that I understand what the agent will do.

Acceptance Criteria:
- "Preview Prompt" button shows compiled system prompt
- Includes: base prompt + character + role context
- Can copy to clipboard
```

---

## UI Wireframe

### Settings Page - Custom Agents Section

```
┌──────────────────────────────────────────────────────────────┐
│  Settings                                                     │
│  [OpenRouter Key Section - Already Built]                    │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│  Custom Agents                                                │
│  Create domain-specific experts for your debates              │
│                                                                │
│  [+ Create New Agent]                                         │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Senior Legal Counsel (Tech M&A)          [Edit] [Delete]│  │
│  │ Role: Legal Counsel                                     │  │
│  │ Character: Risk-aware but pragmatic                     │  │
│  │ Model: anthropic/claude-3.5-sonnet                      │  │
│  │ Created: 2026-02-05                                     │  │
│  │ [Preview Prompt]                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Growth PM (B2B SaaS)                     [Edit] [Delete]│  │
│  │ Role: Product Manager                                   │  │
│  │ Character: Data-driven growth hacker                    │  │
│  │ Model: anthropic/claude-3.5-sonnet                      │  │
│  │ Created: 2026-02-03                                     │  │
│  │ [Preview Prompt]                                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

### Create/Edit Agent Modal

```
┌──────────────────────────────────────────────────────────────┐
│  Create Custom Agent                                    [✕]   │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Agent Name *                                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Senior Legal Counsel (Tech M&A)                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  Role Title *                                                  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Legal Counsel                                          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  Character Style (optional)                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Risk-aware but pragmatic                               │  │
│  └────────────────────────────────────────────────────────┘  │
│  Examples: "Visionary - Jobs-style", "Data-driven"            │
│                                                                │
│  System Prompt *                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ You are a Senior Legal Counsel specializing in tech   │  │
│  │ M&A transactions. Your focus: identify legal risks,   │  │
│  │ ensure compliance, protect IP, negotiate favorable    │  │
│  │ terms. You balance legal protection with business     │  │
│  │ velocity. You're direct, practical, and solution-     │  │
│  │ oriented.                                              │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│  [AI Generate Draft] [Load Template]                          │
│                                                                │
│  Model *                                                       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ anthropic/claude-3.5-sonnet                 [Browse ▼]│  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  Advanced: Model Config (optional)                            │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ {                                                      │  │
│  │   "temperature": 0.7,                                  │  │
│  │   "max_tokens": 2000                                   │  │
│  │ }                                                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    [Preview Prompt]                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  [Cancel]                              [Save Agent]           │
└──────────────────────────────────────────────────────────────┘
```

---

## Backend Integration

### Existing Endpoints (Already Built)

```yaml
POST /agents
  Input: { workspace_id, name, role_description, system_prompt, model_id, model_config }
  Output: { agent_id, ... }
  
GET /agents?workspace_id=...
  Output: [{ agent_id, name, role_description, ... }]
```

**Status**: ✅ Backend complete, just needs UI wrapper

---

### Avoid Duplicates (Reuse Existing Capabilities)
This repo already contains OpenRouter + persona + key-management foundations. The Custom Agents UI must reuse them rather than re-implementing parallel flows.

Already available:
- OpenRouter model catalog: `GET /openrouter/models` (BYOK)
- Persona draft generation: `POST /personas/generate-draft` (BYOK)
- Persona validation: `POST /personas/validate` (no LLM call)
- Centralized web key store: `useOpenRouterKey` + `openrouterKeyStore`

Implications:
- Model picker should default to a searchable dropdown fed by `GET /openrouter/models` (free-text entry can be an advanced escape hatch).
- “AI-assisted prompt generation” should call `POST /personas/generate-draft` and show the compiled prompt preview before saving.
- Do not create any new "OpenRouter key" input inside Custom Agents. It must use Settings key store only.

---

### Frontend API Client

```typescript
// apps/web/src/lib/api.ts (extend existing)

export async function createCustomAgent(
  workspaceId: string,
  agent: {
    name: string;
    role_description: string;
    character?: string;
    system_prompt: string;
    model_id: string;
    model_config?: Record<string, any>;
  }
): Promise<Agent> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}/agents`, {
    method: 'POST',
    headers: {
      ...headers,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      workspace_id: workspaceId,
      name: agent.name,
      role_description: agent.role_description,
      system_prompt: agent.system_prompt,
      model_id: agent.model_id,
      agent_model_config: agent.model_config || {}
    })
  });
  
  if (!response.ok) {
    throw new Error('Failed to create agent');
  }
  
  return response.json();
}

export async function updateCustomAgent(
  agentId: string,
  updates: Partial<Agent>
): Promise<Agent> {
  // NOTE: Requires PUT /agents/{agent_id} backend endpoint
}

export async function deleteCustomAgent(agentId: string): Promise<void> {
  // NOTE: Requires DELETE /agents/{agent_id} backend endpoint
}
```

---

## Agent Fields (Single Source Of Truth)
Custom agents should store only the minimal data needed to reproduce behavior consistently:
- `name` (display name)
- `role_description`
- `character` (optional; displayed and injected into compiled prompt)
- `system_prompt` (editable)
- `model_id` (OpenRouter model string)
- `model_config` (JSON)
- `policy_defaults` (recommended, per agent):
  - `internet_mode`: off | limited | on
  - `citation_mode`: relaxed | strict
  - `tool_calling_enabled`: boolean (future MCP)

Avoid storing:
- OpenRouter API keys (BYOK stays client-side only)
- duplicated derived fields if they can be computed at runtime (keep prompt preview UX, but don't persist a second "compiled prompt" source of truth)

## Implementation Complexity

### **Effort Estimate**: 3-5 days

**Day 1**: UI components
- Custom agent list
- Create/edit modal
- Form validation

**Day 2**: Integration
- Wire up POST /agents
- Add PUT/DELETE endpoints if needed
- Error handling

**Day 3**: Polish
- Prompt preview modal
- AI-assisted persona draft generation (optional, but high value)
  - Uses `POST /personas/generate-draft` (requires BYOK in Settings)
  - Runs `POST /personas/validate` on edited content before save
- Load from template helper

**Day 4-5**: Testing + edge cases
- Form validation
- Character limit enforcement
- Model selection from catalog

---

## Open Questions

1. **Should custom agents have categories?**
   - Pro: Organizes large agent libraries
   - Con: Extra complexity
   - **Recommendation**: Yes, but allow "Custom" category

2. **Should we support agent import/export?**
   - Pro: Users can share agent configs
   - Con: Security concern (malicious prompts)
   - **Recommendation**: Phase 2 feature with validation

3. **Should we allow AI-generated agent drafts?**
   - Pro: Lower barrier to entry
   - Con: Costs $0.05 per generation
   - **Recommendation**: Yes, make it optional

---

## Success Criteria

| Metric | Target |
|--------|--------|
| Custom agents created per user | >2 in first week |
| Custom agents used in debates | >50% of users |
| Prompt quality (user survey) | >4/5 stars |
| Time to create agent | <3 minutes |

---

**Document Status**: Design Complete  
**Ready for**: Implementation ticket creation
