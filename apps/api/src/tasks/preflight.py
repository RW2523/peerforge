"""
Preflight Orchestrator Tasks
Prepares agents before debate starts by generating prep packs
"""

import psycopg2
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from psycopg2.extras import Json

from src.config import settings
from src.database import get_cursor
from src.services.memory_retrieval import retrieve_allowed_chunks

# Web search via Tavily (uses the key from settings.tavily_api_key)
try:
    from tavily import TavilyClient as _TavilyClient
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    _TavilyClient = None

# Try to import Celery, but make it optional
try:
    from src.celery_app import celery_app
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    celery_app = None

# Try to import OpenRouterClient
try:
    from src.openrouter_client import OpenRouterClient
except ImportError:
    OpenRouterClient = None


def orchestrate_preflight_impl(run_id: str, debate_id: str):
    """
    Main orchestrator task for preflight preparation
    
    Fans out to prepare_participant_preflight for each participant
    """
    print(f"🚀 Starting preflight orchestration: run_id={run_id}, debate_id={debate_id}")
    
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        # Update run status to running
        cursor.execute("""
            UPDATE preflight_runs
            SET status = 'running', started_at = NOW()
            WHERE run_id = %s
        """, (run_id,))
        conn.commit()
        print(f"✅ Updated preflight run status to 'running'")
        
        # Get all participants for this run
        cursor.execute("""
            SELECT participant_run_id, participant_id
            FROM preflight_participant_runs
            WHERE run_id = %s AND status = 'queued'
        """, (run_id,))
        
        participant_runs = cursor.fetchall()
        
        if not participant_runs:
            # No participants to process
            cursor.execute("""
                UPDATE preflight_runs
                SET status = 'completed', completed_at = NOW()
                WHERE run_id = %s
            """, (run_id,))
            conn.commit()
            return
        
        # Prepare participants in parallel — each prep is I/O-bound (DB +
        # OpenRouter HTTP) and self-contained (own connection), so threads cut
        # wall-clock from sum-of-agents to ~slowest-agent (BUG-019).
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _prep(run):
            participant_id = run['participant_id']
            try:
                print(f"  → Processing participant {participant_id}...")
                prepare_participant_preflight(
                    participant_run_id=run['participant_run_id'],
                    participant_id=participant_id,
                    debate_id=debate_id,
                )
                print(f"  ✅ Participant {participant_id} prepared successfully")
            except Exception as e:
                print(f"  ❌ Error preparing participant {participant_id}: {e}")
                import traceback
                traceback.print_exc()
                # Continue with other participants

        print(f"📋 Processing {len(participant_runs)} participants (parallel)...")
        max_workers = min(len(participant_runs), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_prep, run) for run in participant_runs]
            for _ in as_completed(futures):
                pass
        
        # Check if all participants completed
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM preflight_participant_runs
            WHERE run_id = %s
            GROUP BY status
        """, (run_id,))
        
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        print(f"📊 Participant status summary: {status_counts}")
        
        # Determine overall run status
        if status_counts.get('failed', 0) > 0 or status_counts.get('running', 0) > 0:
            final_status = 'failed' if status_counts.get('failed', 0) > 0 else 'running'
        else:
            final_status = 'completed'
        
        print(f"🏁 Preflight orchestration complete: status={final_status}")
        
        cursor.execute("""
            UPDATE preflight_runs
            SET status = %s, completed_at = NOW()
            WHERE run_id = %s
        """, (final_status, run_id))
        conn.commit()
        
    except Exception as e:
        cursor.execute("""
            UPDATE preflight_runs
            SET status = 'failed', error = %s, completed_at = NOW()
            WHERE run_id = %s
        """, (str(e), run_id))
        conn.commit()
        raise
    finally:
        cursor.close()
        conn.close()


def prepare_participant_preflight(participant_run_id: str, participant_id: str, debate_id: str):
    """
    Prepare a single participant for the debate
    
    Steps:
    1. Resolve participant -> agent identity
    2. Gather context (materials + imported memory)
    3. Generate prep pack via OpenRouter
    4. Persist as agent_knowledge_units
    """
    print(f"    🔄 Preparing participant: run_id={participant_run_id}, participant={participant_id}")
    
    conn = psycopg2.connect(settings.database_url)
    cursor = get_cursor(conn)
    
    try:
        # Update participant run status
        cursor.execute("""
            UPDATE preflight_participant_runs
            SET status = 'running', started_at = NOW()
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        conn.commit()
        print(f"    ✓ Status updated to 'running'")
        
        # Broadcast progress event via WebSocket
        _broadcast_preflight_progress(debate_id, participant_id, 'running', 'Reading materials and context')
        
        # 1. Get participant details and resolve agent
        cursor.execute("""
            SELECT p.agent_config, d.title, d.policy_config
            FROM participants p
            JOIN debates d ON p.debate_id = d.debate_id
            WHERE p.participant_id = %s
        """, (participant_id,))
        
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Participant {participant_id} not found")
        
        # agent_config is nullable in the schema — default to {} so a NULL
        # config can't crash preflight with AttributeError.
        agent_config = result['agent_config'] or {}
        debate_title = result['title']
        policy_config = result['policy_config']

        # Extract agent details
        # agent_id can be None for inline agents (created from templates)
        agent_id = agent_config.get('agent_id')
        model_id = agent_config.get('model_id', 'openai/gpt-4o-mini')  # Cost-optimized: $0.15/$0.60 (was $3/$15!)
        system_prompt = agent_config.get('system_prompt', '')
        model_config = agent_config.get('model_config', {})
        agent_name = agent_config.get('name', 'Participant')
        role_description = agent_config.get('role_description') or agent_config.get('role') or agent_name
        
        # For inline agents (no agent_id), create a temporary agent record
        # This is needed because agent_knowledge_units has a NOT NULL FK to agents table
        if not agent_id:
            # Check if agent already exists for this participant
            cursor.execute("""
                SELECT agent_id FROM agents WHERE agent_id = %s
            """, (participant_id,))
            
            existing_agent = cursor.fetchone()
            
            if not existing_agent:
                # Create agent record using participant_id
                # Get workspace_id from debate
                cursor.execute("""
                    SELECT workspace_id FROM debates WHERE debate_id = %s
                """, (debate_id,))
                workspace_id = cursor.fetchone()['workspace_id']
                
                cursor.execute("""
                    INSERT INTO agents (agent_id, workspace_id, name, system_prompt, model_id, model_config, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (
                    participant_id,
                    workspace_id,
                    f"{agent_name} (Inline)",
                    system_prompt,
                    model_id,
                    Json(model_config) if model_config else None
                ))
                conn.commit()
                print(f"    ✓ Created temporary agent record for inline participant")
            
            agent_id = participant_id
        
        effective_agent_id = agent_id
        print(f"    ✓ Agent identity: id={effective_agent_id}")
        
        # Update participant run with agent_id
        cursor.execute("""
            UPDATE preflight_participant_runs
            SET agent_id = %s
            WHERE participant_run_id = %s
        """, (agent_id, participant_run_id))
        conn.commit()
        
        # 2. Gather context using semantic retrieval (TICKET-13C, TICKET-13C.1)
        print(f"    🔍 Gathering context...")
        problem_statement = policy_config.get('problem_statement', '') if policy_config else ''
        
        # Get pre-computed query embedding from participant_run metadata (BYOK-safe)
        cursor.execute("""
            SELECT metadata FROM preflight_participant_runs WHERE participant_run_id = %s
        """, (participant_run_id,))
        
        run_metadata = cursor.fetchone()
        stored_query_embedding = None
        if run_metadata and run_metadata['metadata']:
            stored_query_embedding = run_metadata['metadata'].get('query_embedding')
        
        # Build semantic query for logging/audit (even if embedding pre-computed)
        semantic_query = f"{problem_statement[:300] if problem_statement else 'context summary'}\n\nRole: {system_prompt[:200]}"
        
        # Retrieve chunks using pre-computed embedding (BYOK-safe: no key needed)
        try:
            memory_retrieval_result = retrieve_allowed_chunks(
                debate_id=debate_id,
                participant_id=participant_id,
                query=semantic_query,
                top_k=15,
                openrouter_key=None,  # Not needed with pre-computed embedding
                use_semantic=True,
                query_embedding=stored_query_embedding  # Use stored embedding
            )
            
            all_chunks = memory_retrieval_result.chunks
            grant_ids_used = memory_retrieval_result.grant_ids_used
            retrieval_method = memory_retrieval_result.retrieval_method
            print(f"    ✓ Retrieved {len(all_chunks)} chunks via {retrieval_method}")
        except Exception as e:
            print(f"    ⚠️  Memory retrieval failed: {e}")
            all_chunks = []
            grant_ids_used = []
            retrieval_method = 'error'
        
        # Separate material chunks from imported chunks for better context presentation
        material_chunks = [c for c in all_chunks if c.source_debate_id == debate_id]
        imported_chunks = [c for c in all_chunks if c.source_debate_id != debate_id]
        
        materials_context = "\n\n".join([
            f"[Material Chunk {i+1}]: {chunk.chunk_text[:500]}"
            for i, chunk in enumerate(material_chunks)
        ])
        
        imported_context = "\n\n".join([
            f"[Imported Context {i+1}]: {chunk.chunk_text[:500]}"
            for i, chunk in enumerate(imported_chunks)
        ])
        
        # 3. Perform web research (if available and debate is recent/current topic)
        web_research_results = ""
        web_search_urls = []  # Store URLs separately for metadata
        web_search_data = []  # Store full structured results
        
        tavily_key = settings.tavily_api_key or ""
        if WEB_SEARCH_AVAILABLE and problem_statement and tavily_key:
            try:
                _broadcast_preflight_progress(debate_id, participant_id, 'running', 'Researching topic online')

                # Build a concise, search-friendly query from the problem statement
                search_query = problem_statement[:300].strip()
                print(f"    🔍 Tavily web search for preflight")
                print(f"    📝 Query: {search_query[:150]}")

                tavily = _TavilyClient(api_key=tavily_key)
                response = tavily.search(
                    query=search_query,
                    search_depth="basic",
                    max_results=5,
                    include_answer=False,
                    include_raw_content=False,
                )

                results = response.get("results", [])
                if results:
                    web_research_results = "\n**Web Research Results**:\n"
                    for i, item in enumerate(results, 1):
                        title   = item.get("title", "")
                        url     = item.get("url", "")
                        content = item.get("content", "")[:800]
                        web_research_results += (
                            f"{i}. **{title}**\n"
                            f"   URL: {url}\n\n"
                            f"{content}\n\n---\n\n"
                        )
                        web_search_urls.append(url)
                        web_search_data.append({
                            "title":   title,
                            "snippet": content,
                            "url":     url,
                        })
                    print(f"    ✅ Tavily returned {len(results)} results")
                    print(f"    🔗 First 3 URLs: {', '.join(web_search_urls[:3])}")
                else:
                    print(f"    ℹ️ Tavily returned no results")

            except Exception as e:
                import traceback
                print(f"    ⚠️ Web search failed: {e}")
                traceback.print_exc()
                web_research_results = ""
        elif not tavily_key:
            print(f"    ⚠️ TAVILY_API_KEY not set — skipping web research")
        
        # 3b. Build role-specific prep prompt using the persona_prompts module
        from src.services.persona_prompts import get_preflight_prep_prompt, resolve_role

        current_datetime = datetime.utcnow()
        current_date_str = current_datetime.strftime("%A, %B %d, %Y")
        current_time_str = current_datetime.strftime("%I:%M %p UTC")

        # Resolve the reviewer role from their config
        role_for_prep = agent_config.get('role', '') or agent_config.get('role_description', '') or role_description
        prep_prompt = get_preflight_prep_prompt(
            role_label         = role_for_prep,
            persona_name       = agent_name,
            debate_title       = debate_title,
            problem_statement  = problem_statement,
            materials_context  = materials_context,
            imported_context   = imported_context,
            web_research_results = web_research_results,
            current_date_str   = current_date_str,
            current_time_str   = current_time_str,
        )
        
        # 4. Call OpenRouter to generate prep pack
        # For V1, use a simple synchronous call (no streaming)
        # In production, you'd get the OpenRouter key from debate policy or user
        # For now, we'll simulate or use a test key
        
        # Get OpenRouter key from policy_config (if exists) or use test mode
        openrouter_key = policy_config.get('openrouter_key') if policy_config else None
        
        # Broadcast progress: Generating review prep
        _broadcast_preflight_progress(debate_id, participant_id, 'running', 'Generating reviewer preparation memo')
        
        if not openrouter_key:
            # For V1, create a placeholder prep pack (no real OpenRouter call)
            print(f"    📝 Generating placeholder prep pack (no OpenRouter key)")
            prep_pack_content = f"""**Preparation Memo**

**Role**: {system_prompt[:100] if system_prompt else 'Strategic advisor'}

**Key Context**:
- Problem: {problem_statement[:200] if problem_statement else 'N/A'}
- Materials reviewed: {len(material_chunks)} chunks
- Prior context: {len(imported_chunks)} imported chunks

**Initial Assessment**:
This is a placeholder prep pack generated without OpenRouter key. In production, this would contain:
- Synthesized insights from materials
- Risk analysis
- Open questions
- Initial recommendations

**Status**: Generated successfully with {len(material_chunks)} material chunks and {len(imported_chunks)} imported memory chunks."""
        else:
            print(f"    🤖 Calling OpenRouter for prep pack generation...")
            # Real OpenRouter call
            try:
                client = OpenRouterClient(api_key=openrouter_key)
                
                # Use the full deep system_prompt if the agent has one (built by persona_suggester);
                # otherwise fall back to the canonical base prompt for this role.
                from src.services.persona_prompts import get_base_prompt, resolve_role as _resolve_role, ROLE_DISPLAY as _ROLE_DISPLAY
                if system_prompt and len(system_prompt.strip()) > 150:
                    # Agent already has a rich deep system prompt
                    persona_specific_prompt = system_prompt
                else:
                    # Build from canonical base + persona identity
                    _canonical = _resolve_role(role_description or role_for_prep)
                    persona_specific_prompt = (
                        f"You are {agent_name}, serving as {_ROLE_DISPLAY.get(_canonical, _canonical.replace('_',' ').title())} "
                        f"on an academic review panel.\n\n"
                        + get_base_prompt(_canonical)
                    )
                
                # Adjust model config for longer, more detailed output
                enhanced_config = model_config.copy()
                enhanced_config['max_tokens'] = 2000  # Allow longer prep packs
                enhanced_config['temperature'] = 0.8  # Higher for more personality in prep
                
                print(f"    🎭 Using persona: {role_description[:50]}...")
                
                response = client.chat_completion(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": persona_specific_prompt},
                        {"role": "user", "content": prep_prompt}
                    ],
                    _debate_id=debate_id,
                    _stage="preflight",
                    _participant=role_description[:80] if role_description else None,
                    **enhanced_config
                )
                prep_pack_content = response.get('content', '')
                
                if not prep_pack_content or len(prep_pack_content.strip()) == 0:
                    print(f"    ⚠️ OpenRouter returned empty content! Creating fallback prep pack...")
                    prep_pack_content = f"""**Preparation Memo** (Fallback - OpenRouter returned empty response)

**Current Date**: {current_date_str}

**Role**: {role_description}

**Problem Statement**: {problem_statement[:300]}

**Web Research Summary** ({len(web_search_urls)} sources found):
{"" if not web_search_urls else chr(10).join([f"- {url}" for url in web_search_urls[:5]])}

**Status**: OpenRouter returned an empty response. Web research data was collected but LLM failed to generate prep pack."""
                else:
                    print(f"    ✅ Generated prep pack: {len(prep_pack_content)} chars")
                    
                    # Log if web research was included
                    if web_search_urls:
                        print(f"    📊 Web research was available ({len(web_search_urls)} URLs)")
                        # Check if URLs are actually cited in content
                        citations_found = sum(1 for url in web_search_urls[:3] if url in prep_pack_content)
                        if citations_found == 0:
                            print(f"    ⚠️ WARNING: No web sources were cited in the prep pack content!")
                        else:
                            print(f"    ✓ {citations_found} sources cited in prep pack")
            except Exception as e:
                print(f"    ❌ OpenRouter error: {str(e)}")
                prep_pack_content = f"Error calling OpenRouter: {str(e)}\n\nFallback prep pack with {len(material_chunks)} materials and {len(imported_chunks)} imported chunks."
        
        # 5. Persist prep pack as agent_knowledge_units (TICKET-13C: include retrieval metadata)
        # Extract chunk IDs for provenance
        material_chunk_ids = [str(chunk.chunk_id) for chunk in material_chunks]
        imported_chunk_ids = [str(chunk.chunk_id) for chunk in imported_chunks]
        
        # Use effective_agent_id for knowledge persistence
        # Track whether web research was performed
        web_research_performed = bool(web_research_results and WEB_SEARCH_AVAILABLE)
        
        cursor.execute("""
            INSERT INTO agent_knowledge_units (
                knowledge_id, agent_id, source_debate_id, knowledge_type, content, metadata, created_at
            ) VALUES (
                gen_random_uuid(), %s, %s, 'prep_pack', %s, %s, NOW()
            )
            RETURNING knowledge_id
        """, (
            effective_agent_id,
            debate_id,
            prep_pack_content,
            Json({
                'created_by': 'preflight',
                'participant_id': participant_id,
                'participant_name': agent_name,
                'is_inline_agent': agent_id is None,
                'material_chunks_count': len(material_chunks),
                'imported_chunks_count': len(imported_chunks),
                'grant_ids_used': grant_ids_used,
                'model_used': model_id,
                'retrieval_method': retrieval_method,
                'material_chunk_ids': material_chunk_ids,
                'imported_chunk_ids': imported_chunk_ids,
                'semantic_query_used': semantic_query[:200],
                'web_research_performed': web_research_performed,
                'web_research_query': problem_statement[:100] if web_research_performed else None,
                'web_search_urls': web_search_urls,  # List of URLs searched
                'web_search_results': web_search_data,  # Full structured results
                'generated_at': datetime.utcnow().isoformat()
            })
        ))
        
        prep_pack_knowledge_id = cursor.fetchone()['knowledge_id']
        print(f"    ✓ Prep pack persisted: knowledge_id={prep_pack_knowledge_id}")

        # ── Eval log: record preflight prep pack ──────────────────────
        try:
            from src.services.eval_logger import get_logger
            get_logger(debate_id).log_preflight_participant(
                participant_id=participant_id,
                agent_name=agent_name or role_description[:60],
                model=model_id,
                prep_pack=prep_pack_content,
            )
        except Exception as _log_exc:
            print(f"[eval_logger] log_preflight_participant failed: {_log_exc}")
        # ─────────────────────────────────────────────────────────────
        
        # 6. Update participant run to success (TICKET-13C: include retrieval metadata)
        cursor.execute("""
            UPDATE preflight_participant_runs
            SET status = 'success', 
                completed_at = NOW(),
                prep_pack_knowledge_id = %s,
                metadata = %s
            WHERE participant_run_id = %s
        """, (
            prep_pack_knowledge_id,
            Json({
                'chunks_processed': len(material_chunks) + len(imported_chunks),
                'grants_used': len(grant_ids_used),
                'retrieval_mode': retrieval_method,
                'embeddings_used': retrieval_method == 'semantic',
                'material_chunk_ids': material_chunk_ids,
                'imported_chunk_ids': imported_chunk_ids
            }),
            participant_run_id
        ))
        conn.commit()
        print(f"    ✅ Participant preparation complete!")
        
        # Broadcast completion event
        _broadcast_preflight_progress(debate_id, participant_id, 'success', 'Preparation complete')
        
    except Exception as e:
        # Rollback any failed transaction first
        conn.rollback()
        # Update participant run to failed
        try:
            cursor.execute("""
                UPDATE preflight_participant_runs
                SET status = 'failed', error = %s, completed_at = NOW()
                WHERE participant_run_id = %s
            """, (str(e), participant_run_id))
            conn.commit()
            
            # Broadcast failure event
            _broadcast_preflight_progress(debate_id, participant_id, 'failed', f'Error: {str(e)[:100]}')
        except Exception as update_error:
            print(f"    ⚠️  Failed to update participant status: {update_error}")
        raise
    finally:
        cursor.close()
        conn.close()


def _broadcast_preflight_progress(debate_id: str, participant_id: str, status: str, message: str):
    """Helper to broadcast preflight progress events via WebSocket"""
    try:
        from src.websocket_service import websocket_manager
        
        # Create progress event envelope
        event = {
            'type': 'preflight_progress',
            'debate_id': debate_id,
            'participant_id': participant_id,
            'status': status,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Broadcast asynchronously
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(websocket_manager.broadcast_to_debate(debate_id, event))
        else:
            loop.run_until_complete(websocket_manager.broadcast_to_debate(debate_id, event))
    except Exception as e:
        print(f"    ⚠️  Failed to broadcast progress: {e}")


# Create Celery task wrapper if Celery is available
if CELERY_AVAILABLE and celery_app:
    orchestrate_preflight = celery_app.task(name='tasks.preflight.orchestrate_preflight')(orchestrate_preflight_impl)
else:
    # No Celery - use implementation directly
    orchestrate_preflight = orchestrate_preflight_impl
