# RLM (Recursive Language Models) Application Notes for Arinar

Date: 2026-02-10  
Owner: Product/Architecture  
Status: Guidance (non-binding)  

## Why This Doc Exists

Arinar’s core UX involves **very long context**:
- problem statement + agenda/outcome
- many materials (PDF/DOCX/TXT/MD + URLs)
- prior meeting memory imports (selective, auditable)
- multi-agent preparation + debate + artifact generation

Even if we pick long-context models, long inputs can degrade performance (“context rot” / “lost in the middle”). RLMs are a practical inference-time strategy to keep quality high by *not* forcing the model to “read everything in one pass”.

This document explains:
1) what RLMs are (conceptually)  
2) where they fit in Arinar  
3) how to implement an “RLM-style” approach using our existing primitives (materials chunks + memory grants + event ledger), without adopting a research repo as production code

## What RLMs Are (Conceptually)

Recursive Language Models (RLMs) are an **inference strategy**:
- treat the long prompt as an external environment (not fully injected into the model context)
- have the model **programmatically inspect slices**, search, and decompose tasks
- recursively call itself (or a smaller model) on subproblems/snippets, then synthesize

Practical takeaway for Arinar:
- do not pass “all materials” to any single model call
- instead run a structured loop: plan -> retrieve snippets -> draft sections -> validate/merge

### References

- Paper: “Recursive Language Models” (arXiv:2512.24601) + overview pages:
  - https://arxiv.org/abs/2512.24601
  - https://huggingface.co/papers/2512.24601
- Author blogpost: https://alexzhang13.github.io/blog/2025/rlm/
- Official repo: https://github.com/alexzhang13/rlm
- “Context rot” background:
  - ChromaDB report index: https://research.trychroma.com/context-rot
  - Redis explainer: https://redis.io/blog/context-rot/

## Where RLM-Style Helps Most in Arinar

### 1) Preflight (Agent Preparation)

Goal: each agent produces a **Prep Pack** (memo) based only on:
- current debate materials
- selectively granted memory imports
- (optional later) allowed internet research

RLM-style approach:
1) **Scan pass**: build a table of contents of relevant material topics (fast, cheap model).
2) **Deep dives**: for each topic, retrieve small sets of chunks and write evidence-grounded notes.
3) **Synthesis**: merge notes into a prep memo with citations + “open questions”.
4) **Consistency pass**: check for contradictions and missing coverage against agenda/outcome.

Why it’s valuable:
- stable quality with many materials
- easy to enforce memory grants: retrieval is explicit and logged
- easy to timebox (max iterations, max chunks per step, max tokens)

Implementation anchor:
- store final prep pack as `agent_knowledge_units` with `knowledge_type='prep_pack'`

### 2) Live Artifact Generation (Figma-like Board)

Arinar’s “artifact board” is naturally recursive:
- each agent owns sections (e.g., Legal, Technical, Product)
- each section can be drafted independently with its own retrieved snippets
- host runs a coherence pass and generates a “polished version”

RLM-style approach:
1) section plan (outline + responsibilities)
2) per-section worker calls (agent-owned) to produce blocks
3) cross-section coherence merge (host)
4) post-merge QA: citations, conflict checks, missing constraints

This maps to our artifact block types:
- `rich_text`
- `diagram_mermaid`
- `chart` (JSON spec)
- `table`

### 3) Materials “Map” and Chunk Provenance

During ingestion we already produce `memory_chunks` with provenance metadata.
RLM-style approach builds on this by producing:
- a *material index* (topics, key claims, definitions) without reading everything at once
- per-topic “evidence packs” (top chunks, citations)

This becomes a fast reference for agents during debate.

### 4) Debate Summaries / Minutes / Action Items

End-of-meeting outputs are also long-context:
- hundreds/thousands of events
- multiple threads + interventions
- plus materials/memory references

RLM-style approach:
- summarize by phases (setup -> debate -> decisions -> actions)
- per-agent “what I believe we decided” statements
- host merges + resolves disagreements with citations to events

## How to Implement RLM-Style in Arinar (Without a REPL Sandbox)

The RLM paper often uses a Python REPL environment. We can implement the same idea using our existing “environment”:

### Our “Environment” (Source of Truth)

- `meeting_materials` metadata + processing status
- `memory_chunks` text + provenance (material_id, offsets, sha256, etc.)
- `debate_memory_grants` allowlists what prior debates are accessible
- `events` ledger for everything that happens (including preflight/artifact progress)
- `memory_access_log` audit trail for retrieval (chunk_ids + grant_ids)

### Environment APIs (Tools) We Can Provide Internally

Instead of a REPL, we provide a small tool surface the orchestrator can call:

1) `search_allowed_chunks(debate_id, participant_id, query, top_k)`
   - implemented by `retrieve_allowed_chunks(...)`
   - logs `chunk_ids` + `grant_ids` for audit

2) `get_materials_status(debate_id)`
3) `get_chunks_by_material(material_id, offset/limit or range)`
4) `get_recent_events(debate_id, cursor, limit)`

Later (optional tools):
5) `research(query)` (policy-controlled; citations required; logged)
6) `render_artifact(blocks)` (HTML export pipeline)

### RLM Driver Pattern (Recommended)

Implement as a deterministic orchestration loop (Celery-friendly):

1) **Planner call** (cheap model):
   - inputs: problem statement, agenda/outcome, list of available sources (materials + grants)
   - output: structured plan (topics, retrieval queries, per-topic budgets)

2) **Worker calls** (agent model or cheaper sub-model):
   - for each topic:
     - call retrieval tool with query
     - ask model to write “evidence notes” with citations to returned chunk_ids

3) **Synthesizer call** (agent model):
   - merge topic notes into a single prep pack / section
   - include: assumptions, risks, questions, recommended decisions

4) **Verifier pass** (optional):
   - check for missing agenda items
   - ensure citations exist for key claims

#### Budget/Guardrail Controls (Enterprise)

Every recursive pipeline must have:
- max iterations (per agent and per debate)
- max retrieved chunks per topic
- hard timeouts per task
- cost visibility (estimated token budgets)
- explicit policy checks (internet research off by default)

## Recommended Model Routing (OpenRouter-Friendly)

RLM-style recursion benefits from using different models for different stages:

- Planner: small/cheap model (fast scanning)
- Worker: medium model (extract + write notes)
- Synthesizer: best model (final narrative, structure, tone)

Arinar should allow:
- per-agent `model_id`
- optional “subcall model” override for planner/worker stages
- “extended thinking” toggle per stage (where supported by chosen model/provider)

Important:
- We should not hardcode model lists. Use `/openrouter/models` to populate choices dynamically.

## What To Ship First (Pragmatic Sequence)

### Phase 1: Preflight Core (RLM-style, no research)

Implement RLM-style preflight as:
- plan -> retrieve -> topic notes -> prep pack
- store prep pack in `agent_knowledge_units(knowledge_type='prep_pack')`
- log retrieval in `memory_access_log`

### Phase 2: Preflight UI

- progress view (per agent)
- retry/skip controls
- show “evidence packs” (citations + sources)

### Phase 3: Internet Research (Policy Controlled)

- provider abstraction
- citations required
- per-debate budgets and audit logging

### Phase 4: Live Artifacts Engine (RLM-style section drafting)

- section ownership
- streaming deltas
- coherence/merge pass
- export PDF/DOCX

## Evaluation: How We Know It Works

Minimum evaluation harness for RLM-style pipelines:
- Citation accuracy:
  - % of claims with valid citations to chunk_ids/events
- Coverage:
  - agenda items covered (yes/no + confidence)
- Consistency:
  - contradictions detected across sections (count)
- Latency:
  - per-agent preflight completion time
- Cost:
  - tokens per debate, per stage

## Risks / Caveats

- “Recursive” can become “unbounded” without strict budgets; we must implement hard caps.
- Tool surfaces must be minimal and auditable; do not allow arbitrary code execution in production.
- Avoid vendor lock-in:
  - keep RLM driver generic; OpenRouter model_id decides provider/model.
- Do not rely on “we’ll fix citations later”:
  - citations/audit are the enterprise moat; bake them in from day 1.

## Relationship to Other “Recursive” Retrieval Approaches

RLMs are one approach. Another related concept is hierarchical/recursive summarization trees for retrieval (e.g., RAPTOR). In Arinar:
- RAPTOR-like trees could be a future optimization for fast retrieval over huge corpora,
- but the immediate path is simpler: chunk + keyword/vector + recursive synthesis.

