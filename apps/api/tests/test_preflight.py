"""
Tests for Preflight Orchestrator
"""

import psycopg2
import pytest
from src.config import settings
from src.tasks.preflight import orchestrate_preflight, prepare_participant_preflight


def test_start_preflight_creates_run_and_participant_runs():
    """
    Test that starting preflight creates run and participant run entries
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        workspace_id = "00000000-0000-0000-0000-000000000101"
        
        # Create persistent agent
        cursor.execute("""
            INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt)
            VALUES (gen_random_uuid(), %s, 'Product Manager', 'Senior PM', 'You are a PM.')
            RETURNING agent_id
        """, (workspace_id,))
        agent_id = cursor.fetchone()[0]
        
        # Create debate
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state, policy_config)
            VALUES (gen_random_uuid(), %s, 'Test Debate', 'pending', %s::jsonb)
            RETURNING debate_id
        """, (workspace_id, '{"problem_statement": "Should we launch product X?"}'))
        debate_id = cursor.fetchone()[0]
        
        # Create participant
        cursor.execute("""
            INSERT INTO participants (
                participant_id, debate_id, participant_type, role_name, agent_config
            ) VALUES (
                gen_random_uuid(), %s, 'agent', 'Product Manager',
                %s::jsonb
            )
            RETURNING participant_id
        """, (debate_id, f'{{"agent_id": "{agent_id}", "model_id": "anthropic/claude-3.5-sonnet"}}'))
        participant_id = cursor.fetchone()[0]
        
        # Create some material chunks
        cursor.execute("""
            INSERT INTO memory_chunks (chunk_id, source_debate_id, chunk_text, chunk_metadata)
            VALUES (gen_random_uuid(), %s, 'Product X market analysis shows strong demand', '{"source_type": "material"}'::jsonb)
        """, (debate_id,))
        
        conn.commit()
        
        # Start preflight run
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status)
            VALUES (gen_random_uuid(), %s, 'queued')
            RETURNING run_id
        """, (debate_id,))
        run_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO preflight_participant_runs (
                participant_run_id, run_id, participant_id, agent_id, status
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'queued'
            )
            RETURNING participant_run_id
        """, (run_id, participant_id, agent_id))
        participant_run_id = cursor.fetchone()[0]
        
        conn.commit()
        
        # Execute orchestrator synchronously (like materials test)
        orchestrate_preflight(run_id, debate_id)
        
        # Verify run status
        cursor.execute("""
            SELECT status, started_at, completed_at
            FROM preflight_runs
            WHERE run_id = %s
        """, (run_id,))
        
        run_result = cursor.fetchone()
        assert run_result is not None
        assert run_result[0] in ('completed', 'failed')  # Should have completed
        assert run_result[1] is not None  # started_at set
        assert run_result[2] is not None  # completed_at set
        
        # Verify participant run status
        cursor.execute("""
            SELECT status, prep_pack_knowledge_id, completed_at
            FROM preflight_participant_runs
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        
        part_result = cursor.fetchone()
        assert part_result is not None
        assert part_result[0] == 'success'  # Should succeed
        assert part_result[1] is not None  # prep_pack_knowledge_id set
        assert part_result[2] is not None  # completed_at set
        
        # Verify prep pack was created
        prep_pack_id = part_result[1]
        cursor.execute("""
            SELECT agent_id, knowledge_type, content, metadata
            FROM agent_knowledge_units
            WHERE knowledge_id = %s
        """, (prep_pack_id,))
        
        knowledge = cursor.fetchone()
        assert knowledge is not None
        assert knowledge[0] == agent_id
        assert knowledge[1] == 'prep_pack'
        assert len(knowledge[2]) > 0  # content not empty
        assert 'created_by' in knowledge[3]
        assert knowledge[3]['created_by'] == 'preflight'
    
    finally:
        cursor.close()
        conn.close()


def test_preflight_with_imported_memory():
    """
    Test that preflight retrieves imported memory chunks when grants exist
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        workspace_id = "00000000-0000-0000-0000-000000000101"
        
        # Create agent
        cursor.execute("""
            INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt)
            VALUES (gen_random_uuid(), %s, 'Legal Counsel', 'Senior Legal', 'You are a lawyer.')
            RETURNING agent_id
        """, (workspace_id,))
        agent_id = cursor.fetchone()[0]
        
        # Create source debate with chunk
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state)
            VALUES (gen_random_uuid(), %s, 'Prior Legal Review', 'ended')
            RETURNING debate_id
        """, (workspace_id,))
        source_debate_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO memory_chunks (chunk_id, source_debate_id, chunk_text)
            VALUES (gen_random_uuid(), %s, 'Contract terms from prior negotiation')
        """, (source_debate_id,))
        
        # Create target debate
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state, policy_config)
            VALUES (gen_random_uuid(), %s, 'Current Contract Review', 'pending', '{"problem_statement": "Review new contract"}'::jsonb)
            RETURNING debate_id
        """, (workspace_id,))
        target_debate_id = cursor.fetchone()[0]
        
        # Create participant
        cursor.execute("""
            INSERT INTO participants (
                participant_id, debate_id, participant_type, role_name, agent_config
            ) VALUES (
                gen_random_uuid(), %s, 'agent', 'Legal Counsel',
                %s::jsonb
            )
            RETURNING participant_id
        """, (target_debate_id, f'{{"agent_id": "{agent_id}", "model_id": "anthropic/claude-3.5-sonnet"}}'))
        participant_id = cursor.fetchone()[0]
        
        # Create memory grant
        cursor.execute("""
            INSERT INTO debate_memory_grants (
                grant_id, debate_id, source_debate_id, source_type, scope, granted_by
            ) VALUES (gen_random_uuid(), %s, %s, 'debate_full', 'all_agents', %s)
        """, (target_debate_id, source_debate_id, workspace_id))
        
        conn.commit()
        
        # Start preflight
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status)
            VALUES (gen_random_uuid(), %s, 'queued')
            RETURNING run_id
        """, (target_debate_id,))
        run_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO preflight_participant_runs (
                participant_run_id, run_id, participant_id, agent_id, status
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'queued'
            )
            RETURNING participant_run_id
        """, (run_id, participant_id, agent_id))
        participant_run_id = cursor.fetchone()[0]
        
        conn.commit()
        
        # Execute preflight
        orchestrate_preflight(run_id, target_debate_id)
        
        # Verify prep pack includes imported context
        cursor.execute("""
            SELECT prep_pack_knowledge_id
            FROM preflight_participant_runs
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        
        prep_pack_id = cursor.fetchone()[0]
        assert prep_pack_id is not None
        
        cursor.execute("""
            SELECT metadata
            FROM agent_knowledge_units
            WHERE knowledge_id = %s
        """, (prep_pack_id,))
        
        metadata = cursor.fetchone()[0]
        assert 'imported_chunks_count' in metadata
        assert metadata['imported_chunks_count'] > 0  # Should have retrieved imported chunks
        assert 'grant_ids_used' in metadata
    
    finally:
        cursor.close()
        conn.close()


def test_preflight_retry():
    """
    Test that retry works for failed participant runs
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        workspace_id = "00000000-0000-0000-0000-000000000101"
        
        # Create agent
        cursor.execute("""
            INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt)
            VALUES (gen_random_uuid(), %s, 'Designer', 'Senior Designer', 'You are a designer.')
            RETURNING agent_id
        """, (workspace_id,))
        agent_id = cursor.fetchone()[0]
        
        # Create debate
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state, policy_config)
            VALUES (gen_random_uuid(), %s, 'Design Review', 'pending', '{"problem_statement": "Review UI mockups"}'::jsonb)
            RETURNING debate_id
        """, (workspace_id,))
        debate_id = cursor.fetchone()[0]
        
        # Create participant
        cursor.execute("""
            INSERT INTO participants (
                participant_id, debate_id, participant_type, role_name, agent_config
            ) VALUES (
                gen_random_uuid(), %s, 'agent', 'Designer',
                %s::jsonb
            )
            RETURNING participant_id
        """, (debate_id, f'{{"agent_id": "{agent_id}", "model_id": "anthropic/claude-3.5-sonnet"}}'))
        participant_id = cursor.fetchone()[0]
        
        # Create run
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status)
            VALUES (gen_random_uuid(), %s, 'running')
            RETURNING run_id
        """, (debate_id,))
        run_id = cursor.fetchone()[0]
        
        # Create failed participant run
        cursor.execute("""
            INSERT INTO preflight_participant_runs (
                participant_run_id, run_id, participant_id, agent_id, status, error
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'failed', 'Network timeout'
            )
            RETURNING participant_run_id
        """, (run_id, participant_id, agent_id))
        participant_run_id = cursor.fetchone()[0]
        
        conn.commit()
        
        # Retry: reset to queued
        cursor.execute("""
            UPDATE preflight_participant_runs
            SET status = 'queued', error = NULL, started_at = NULL, completed_at = NULL
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        conn.commit()
        
        # Re-run
        prepare_participant_preflight(participant_run_id, participant_id, debate_id)
        
        # Verify now success
        cursor.execute("""
            SELECT status, prep_pack_knowledge_id
            FROM preflight_participant_runs
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        
        result = cursor.fetchone()
        assert result[0] == 'success'
        assert result[1] is not None  # prep_pack created
    
    finally:
        cursor.close()
        conn.close()


def test_preflight_skip():
    """
    Test that skip marks participant run as skipped with reason
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        workspace_id = "00000000-0000-0000-0000-000000000101"
        
        # Create agent
        cursor.execute("""
            INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt)
            VALUES (gen_random_uuid(), %s, 'Engineer', 'Senior Engineer', 'You are an engineer.')
            RETURNING agent_id
        """, (workspace_id,))
        agent_id = cursor.fetchone()[0]
        
        # Create debate
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state)
            VALUES (gen_random_uuid(), %s, 'Engineering Review', 'pending')
            RETURNING debate_id
        """, (workspace_id,))
        debate_id = cursor.fetchone()[0]
        
        # Create participant
        cursor.execute("""
            INSERT INTO participants (
                participant_id, debate_id, participant_type, role_name, agent_config
            ) VALUES (
                gen_random_uuid(), %s, 'agent', 'Engineer',
                %s::jsonb
            )
            RETURNING participant_id
        """, (debate_id, f'{{"agent_id": "{agent_id}", "model_id": "anthropic/claude-3.5-sonnet"}}'))
        participant_id = cursor.fetchone()[0]
        
        # Create run
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status)
            VALUES (gen_random_uuid(), %s, 'running')
            RETURNING run_id
        """, (debate_id,))
        run_id = cursor.fetchone()[0]
        
        # Create queued participant run
        cursor.execute("""
            INSERT INTO preflight_participant_runs (
                participant_run_id, run_id, participant_id, agent_id, status
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'queued'
            )
            RETURNING participant_run_id
        """, (run_id, participant_id, agent_id))
        participant_run_id = cursor.fetchone()[0]
        
        conn.commit()
        
        # Skip
        skip_reason = "Agent not available for preflight"
        cursor.execute("""
            UPDATE preflight_participant_runs
            SET status = 'skipped', skip_reason = %s, completed_at = NOW()
            WHERE participant_run_id = %s
        """, (skip_reason, participant_run_id))
        conn.commit()
        
        # Verify
        cursor.execute("""
            SELECT status, skip_reason, completed_at
            FROM preflight_participant_runs
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        
        result = cursor.fetchone()
        assert result[0] == 'skipped'
        assert result[1] == skip_reason
        assert result[2] is not None  # completed_at set
    
    finally:
        cursor.close()
        conn.close()


def test_preflight_creates_prep_pack_with_correct_metadata():
    """
    Test that prep pack is created with knowledge_type='prep_pack' and correct metadata
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        workspace_id = "00000000-0000-0000-0000-000000000101"
        
        # Create agent
        cursor.execute("""
            INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt)
            VALUES (gen_random_uuid(), %s, 'Finance Lead', 'CFO', 'You are a CFO.')
            RETURNING agent_id
        """, (workspace_id,))
        agent_id = cursor.fetchone()[0]
        
        # Create debate with problem statement
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state, policy_config)
            VALUES (gen_random_uuid(), %s, 'Budget Review', 'pending', %s::jsonb)
            RETURNING debate_id
        """, (workspace_id, '{"problem_statement": "Should we increase R&D budget by 20%?"}'))
        debate_id = cursor.fetchone()[0]
        
        # Create participant
        cursor.execute("""
            INSERT INTO participants (
                participant_id, debate_id, participant_type, role_name, agent_config
            ) VALUES (
                gen_random_uuid(), %s, 'agent', 'Finance Lead',
                %s::jsonb
            )
            RETURNING participant_id
        """, (debate_id, f'{{"agent_id": "{agent_id}", "model_id": "anthropic/claude-3.5-sonnet"}}'))
        participant_id = cursor.fetchone()[0]
        
        # Add materials
        cursor.execute("""
            INSERT INTO memory_chunks (chunk_id, source_debate_id, chunk_text, chunk_metadata)
            VALUES 
                (gen_random_uuid(), %s, 'Q4 budget report shows 15%% underspend', '{"source_type": "material"}'::jsonb),
                (gen_random_uuid(), %s, 'Competitor analysis suggests increased R&D investment', '{"source_type": "material"}'::jsonb)
        """, (debate_id, debate_id))
        
        conn.commit()
        
        # Start preflight
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status)
            VALUES (gen_random_uuid(), %s, 'queued')
            RETURNING run_id
        """, (debate_id,))
        run_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO preflight_participant_runs (
                participant_run_id, run_id, participant_id, agent_id, status
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'queued'
            )
            RETURNING participant_run_id
        """, (run_id, participant_id, agent_id))
        participant_run_id = cursor.fetchone()[0]
        
        conn.commit()
        
        # Execute
        orchestrate_preflight(run_id, debate_id)
        
        # Verify prep pack metadata
        cursor.execute("""
            SELECT aku.knowledge_type, aku.content, aku.metadata
            FROM preflight_participant_runs ppr
            JOIN agent_knowledge_units aku ON ppr.prep_pack_knowledge_id = aku.knowledge_id
            WHERE ppr.participant_run_id = %s
        """, (participant_run_id,))
        
        result = cursor.fetchone()
        assert result is not None
        
        knowledge_type, content, metadata = result
        assert knowledge_type == 'prep_pack'
        assert len(content) > 50  # Should have substantial content
        assert metadata['created_by'] == 'preflight'
        assert metadata['participant_id'] == participant_id
        assert 'material_chunks_count' in metadata
        assert metadata['material_chunks_count'] >= 2  # We created 2 chunks
    
    finally:
        cursor.close()
        conn.close()


def test_preflight_multiple_participants():
    """
    Test that preflight processes all participants in a debate
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        workspace_id = "00000000-0000-0000-0000-000000000101"
        
        # Create 3 agents
        agent_ids = []
        for name in ['PM', 'Engineer', 'Designer']:
            cursor.execute("""
                INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt)
                VALUES (gen_random_uuid(), %s, %s, %s, %s)
                RETURNING agent_id
            """, (workspace_id, name, f'Senior {name}', f'You are a {name}.'))
            agent_ids.append(cursor.fetchone()[0])
        
        # Create debate
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state, policy_config)
            VALUES (gen_random_uuid(), %s, 'Product Launch Review', 'pending', '{"problem_statement": "Should we launch now?"}'::jsonb)
            RETURNING debate_id
        """, (workspace_id,))
        debate_id = cursor.fetchone()[0]
        
        # Create 3 participants
        participant_ids = []
        for i, agent_id in enumerate(agent_ids):
            cursor.execute("""
                INSERT INTO participants (
                    participant_id, debate_id, participant_type, role_name, agent_config
                ) VALUES (
                    gen_random_uuid(), %s, 'agent', %s,
                    %s::jsonb
                )
                RETURNING participant_id
            """, (debate_id, ['PM', 'Engineer', 'Designer'][i], f'{{"agent_id": "{agent_id}", "model_id": "anthropic/claude-3.5-sonnet"}}'))
            participant_ids.append(cursor.fetchone()[0])
        
        conn.commit()
        
        # Start preflight
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status)
            VALUES (gen_random_uuid(), %s, 'queued')
            RETURNING run_id
        """, (debate_id,))
        run_id = cursor.fetchone()[0]
        
        # Create participant runs
        for participant_id, agent_id in zip(participant_ids, agent_ids):
            cursor.execute("""
                INSERT INTO preflight_participant_runs (
                    participant_run_id, run_id, participant_id, agent_id, status
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s, 'queued'
                )
            """, (run_id, participant_id, agent_id))
        
        conn.commit()
        
        # Execute
        orchestrate_preflight(run_id, debate_id)
        
        # Verify all 3 participants have prep packs
        cursor.execute("""
            SELECT COUNT(*), COUNT(prep_pack_knowledge_id)
            FROM preflight_participant_runs
            WHERE run_id = %s AND status = 'success'
        """, (run_id,))
        
        result = cursor.fetchone()
        assert result[0] == 3  # All 3 participants
        assert result[1] == 3  # All 3 have prep_pack_knowledge_id
        
        # Verify 3 prep_pack knowledge units exist
        cursor.execute("""
            SELECT COUNT(*)
            FROM agent_knowledge_units
            WHERE source_debate_id = %s AND knowledge_type = 'prep_pack'
        """, (debate_id,))
        
        count = cursor.fetchone()[0]
        assert count == 3
    
    finally:
        cursor.close()
        conn.close()


def test_preflight_without_materials():
    """
    Test that preflight works even without materials (only problem statement)
    """
    conn = psycopg2.connect(settings.database_url)
    cursor = conn.cursor()
    
    try:
        workspace_id = "00000000-0000-0000-0000-000000000101"
        
        # Create agent
        cursor.execute("""
            INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt)
            VALUES (gen_random_uuid(), %s, 'Strategist', 'Strategy Lead', 'You are a strategist.')
            RETURNING agent_id
        """, (workspace_id,))
        agent_id = cursor.fetchone()[0]
        
        # Create debate (NO materials)
        cursor.execute("""
            INSERT INTO debates (debate_id, workspace_id, title, state, policy_config)
            VALUES (gen_random_uuid(), %s, 'Strategic Discussion', 'pending', '{"problem_statement": "What is our 5-year vision?"}'::jsonb)
            RETURNING debate_id
        """, (workspace_id,))
        debate_id = cursor.fetchone()[0]
        
        # Create participant
        cursor.execute("""
            INSERT INTO participants (
                participant_id, debate_id, participant_type, role_name, agent_config
            ) VALUES (
                gen_random_uuid(), %s, 'agent', 'Strategist',
                %s::jsonb
            )
            RETURNING participant_id
        """, (debate_id, f'{{"agent_id": "{agent_id}", "model_id": "anthropic/claude-3.5-sonnet"}}'))
        participant_id = cursor.fetchone()[0]
        
        conn.commit()
        
        # Start preflight
        cursor.execute("""
            INSERT INTO preflight_runs (run_id, debate_id, status)
            VALUES (gen_random_uuid(), %s, 'queued')
            RETURNING run_id
        """, (debate_id,))
        run_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO preflight_participant_runs (
                participant_run_id, run_id, participant_id, agent_id, status
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, 'queued'
            )
            RETURNING participant_run_id
        """, (run_id, participant_id, agent_id))
        participant_run_id = cursor.fetchone()[0]
        
        conn.commit()
        
        # Execute
        orchestrate_preflight(run_id, debate_id)
        
        # Verify prep pack created even without materials
        cursor.execute("""
            SELECT status, prep_pack_knowledge_id
            FROM preflight_participant_runs
            WHERE participant_run_id = %s
        """, (participant_run_id,))
        
        result = cursor.fetchone()
        assert result[0] == 'success'
        assert result[1] is not None  # prep_pack still created
        
        # Verify content mentions no materials
        cursor.execute("""
            SELECT content, metadata
            FROM agent_knowledge_units
            WHERE knowledge_id = %s
        """, (result[1],))
        
        knowledge = cursor.fetchone()
        assert knowledge[0] is not None
        assert knowledge[1]['material_chunks_count'] == 0
    
    finally:
        cursor.close()
        conn.close()
