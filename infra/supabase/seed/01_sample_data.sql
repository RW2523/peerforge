-- Seed Data: 01_sample_data.sql
-- Description: Sample data for local development and testing
-- Includes: one tenant, workspace, debate, participants, and events

-- ============================================================================
-- TENANT AND WORKSPACE SEED DATA
-- ============================================================================

-- Insert demo tenant
INSERT INTO tenants (tenant_id, name, slug, status, settings, created_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Demo Organization',
    'demo-org',
    'active',
    '{"plan": "developer", "max_workspaces": 10}',
    NOW()
) ON CONFLICT (tenant_id) DO NOTHING;

-- Insert demo workspace
INSERT INTO workspaces (workspace_id, tenant_id, name, slug, description, settings, created_at)
VALUES (
    '00000000-0000-0000-0000-000000000101',
    '00000000-0000-0000-0000-000000000001',
    'Product Strategy',
    'product-strategy',
    'Workspace for product planning and strategy discussions',
    '{"visibility": "private"}',
    NOW()
) ON CONFLICT (workspace_id) DO NOTHING;

-- ============================================================================
-- AGENT SEED DATA
-- ============================================================================

-- Product Manager agent
INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt, model_config, created_at)
VALUES (
    '00000000-0000-0000-0000-000000001001',
    '00000000-0000-0000-0000-000000000101',
    'Product Manager',
    'Strategic product leader focused on user needs and business value',
    'You are an experienced product manager. Focus on user value, business impact, and feasibility. Ask clarifying questions and push for measurable outcomes.',
    '{"model": "anthropic/claude-3.5-sonnet", "temperature": 0.7, "max_tokens": 2000}',
    NOW()
) ON CONFLICT (agent_id) DO NOTHING;

-- Engineer agent
INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt, model_config, created_at)
VALUES (
    '00000000-0000-0000-0000-000000001002',
    '00000000-0000-0000-0000-000000000101',
    'Senior Engineer',
    'Technical lead with focus on system design and implementation',
    'You are a senior software engineer. Evaluate technical feasibility, identify risks, and propose robust solutions. Consider scalability and maintainability.',
    '{"model": "anthropic/claude-3.5-sonnet", "temperature": 0.7, "max_tokens": 2000}',
    NOW()
) ON CONFLICT (agent_id) DO NOTHING;

-- Designer agent
INSERT INTO agents (agent_id, workspace_id, name, role_description, system_prompt, model_config, created_at)
VALUES (
    '00000000-0000-0000-0000-000000001003',
    '00000000-0000-0000-0000-000000000101',
    'UX Designer',
    'User experience designer focused on usability and accessibility',
    'You are a UX designer. Advocate for user needs, identify usability issues, and propose user-friendly solutions. Consider accessibility and inclusive design.',
    '{"model": "openai/gpt-4-turbo", "temperature": 0.7, "max_tokens": 2000}',
    NOW()
) ON CONFLICT (agent_id) DO NOTHING;

-- ============================================================================
-- DEBATE SEED DATA
-- ============================================================================

-- Sample debate session
INSERT INTO debates (debate_id, workspace_id, title, description, state, timebox_minutes, policy_config, created_at, started_at)
VALUES (
    '00000000-0000-0000-0000-000000002001',
    '00000000-0000-0000-0000-000000000101',
    'Feature Prioritization Q1 2026',
    'Discuss and prioritize features for Q1 2026 product roadmap',
    'running',
    60,
    '{"internet_research_enabled": false, "tool_calling_enabled": false, "strict_citation_mode": true, "max_tokens_per_response": 1500}',
    NOW() - INTERVAL '10 minutes',
    NOW() - INTERVAL '8 minutes'
) ON CONFLICT (debate_id) DO NOTHING;

-- ============================================================================
-- PARTICIPANT SEED DATA
-- ============================================================================

-- Add agents as participants
INSERT INTO participants (participant_id, debate_id, participant_type, role_name, agent_config, created_at)
VALUES
    (
        '00000000-0000-0000-0000-000000003001',
        '00000000-0000-0000-0000-000000002001',
        'agent',
        'Product Manager',
        '{"agent_id": "00000000-0000-0000-0000-000000001001", "model": "anthropic/claude-3.5-sonnet"}',
        NOW() - INTERVAL '8 minutes'
    ),
    (
        '00000000-0000-0000-0000-000000003002',
        '00000000-0000-0000-0000-000000002001',
        'agent',
        'Senior Engineer',
        '{"agent_id": "00000000-0000-0000-0000-000000001002", "model": "anthropic/claude-3.5-sonnet"}',
        NOW() - INTERVAL '8 minutes'
    ),
    (
        '00000000-0000-0000-0000-000000003003',
        '00000000-0000-0000-0000-000000002001',
        'agent',
        'UX Designer',
        '{"agent_id": "00000000-0000-0000-0000-000000001003", "model": "openai/gpt-4-turbo"}',
        NOW() - INTERVAL '8 minutes'
    )
ON CONFLICT (participant_id) DO NOTHING;

-- ============================================================================
-- EVENT SEED DATA
-- ============================================================================

-- Debate start event
INSERT INTO events (event_id, debate_id, event_type, sender_type, sender_id, content, priority, created_at)
VALUES
    (
        '00000000-0000-0000-0000-000000004001',
        '00000000-0000-0000-0000-000000002001',
        'system_message',
        'system',
        NULL,
        '{"message": "Debate session started", "participants": 3}',
        0,
        NOW() - INTERVAL '8 minutes'
    ),
    -- Product Manager opening statement
    (
        '00000000-0000-0000-0000-000000004002',
        '00000000-0000-0000-0000-000000002001',
        'agent_message',
        'agent',
        '00000000-0000-0000-0000-000000003001',
        '{"message": "Thanks everyone for joining. For Q1 2026, I propose we focus on three key areas: improving onboarding flow, adding collaboration features, and enhancing mobile experience. These align with our user feedback showing 60% drop-off in onboarding and 40% of users accessing on mobile.", "model_id": "anthropic/claude-3.5-sonnet", "tokens_used": 85}',
        2,
        NOW() - INTERVAL '7 minutes'
    ),
    -- Engineer response
    (
        '00000000-0000-0000-0000-000000004003',
        '00000000-0000-0000-0000-000000002001',
        'agent_message',
        'agent',
        '00000000-0000-0000-0000-000000003002',
        '{"message": "From a technical perspective, the onboarding flow improvements are the most straightforward - estimated 2-3 weeks. Collaboration features will require significant backend work including real-time sync and conflict resolution, probably 6-8 weeks. Mobile optimization needs responsive design work and potentially a PWA upgrade, around 4 weeks.", "model_id": "anthropic/claude-3.5-sonnet", "tokens_used": 92}',
        2,
        NOW() - INTERVAL '6 minutes'
    ),
    -- Designer input
    (
        '00000000-0000-0000-0000-000000004004',
        '00000000-0000-0000-0000-000000002001',
        'agent_message',
        'agent',
        '00000000-0000-0000-0000-000000003003',
        '{"message": "The onboarding improvements should address accessibility from the start. Our current flow has several WCAG violations. For mobile, we need to ensure touch targets are properly sized and navigation is thumb-friendly. I recommend we do mobile-first design for the collaboration features to avoid retrofitting later.", "model_id": "openai/gpt-4-turbo", "tokens_used": 78}',
        2,
        NOW() - INTERVAL '5 minutes'
    ),
    -- Product Manager follow-up
    (
        '00000000-0000-0000-0000-000000004005',
        '00000000-0000-0000-0000-000000002001',
        'agent_message',
        'agent',
        '00000000-0000-0000-0000-000000003001',
        '{"message": "Good points. Given the timeline and impact, I suggest we prioritize: 1) Onboarding flow (high impact, quick win), 2) Mobile optimization (large user base), 3) Collaboration features (defer to Q2 for proper design). This gives us early wins while setting up Q2 for success.", "model_id": "anthropic/claude-3.5-sonnet", "tokens_used": 88}',
        2,
        NOW() - INTERVAL '4 minutes'
    )
ON CONFLICT (event_id) DO NOTHING;

-- ============================================================================
-- MEMORY SEED DATA
-- ============================================================================

-- Sample memory chunks for agents
INSERT INTO memory_chunks (chunk_id, agent_id, source_debate_id, chunk_text, chunk_metadata, created_at)
VALUES
    (
        '00000000-0000-0000-0000-000000005001',
        '00000000-0000-0000-0000-000000001001',
        '00000000-0000-0000-0000-000000002001',
        'User onboarding has 60% drop-off rate. This is a critical metric affecting user retention.',
        '{"source": "debate", "confidence": 0.9, "tags": ["onboarding", "metrics"]}',
        NOW() - INTERVAL '4 minutes'
    ),
    (
        '00000000-0000-0000-0000-000000005002',
        '00000000-0000-0000-0000-000000001001',
        '00000000-0000-0000-0000-000000002001',
        '40% of users access the platform on mobile devices. Mobile experience is a key priority.',
        '{"source": "debate", "confidence": 0.9, "tags": ["mobile", "metrics"]}',
        NOW() - INTERVAL '4 minutes'
    )
ON CONFLICT (chunk_id) DO NOTHING;

-- Sample agent knowledge units
INSERT INTO agent_knowledge_units (knowledge_id, agent_id, source_debate_id, content, metadata, confidence_score, created_at)
VALUES
    (
        '00000000-0000-0000-0000-000000006001',
        '00000000-0000-0000-0000-000000001002',
        '00000000-0000-0000-0000-000000002001',
        'Collaboration features require real-time sync infrastructure with conflict resolution. Estimated 6-8 weeks development time.',
        '{"topic": "technical_estimate", "feature": "collaboration"}',
        0.85,
        NOW() - INTERVAL '3 minutes'
    ),
    (
        '00000000-0000-0000-0000-000000006002',
        '00000000-0000-0000-0000-000000001003',
        '00000000-0000-0000-0000-000000002001',
        'Current onboarding flow has WCAG accessibility violations that need to be addressed in the redesign.',
        '{"topic": "accessibility", "feature": "onboarding"}',
        0.9,
        NOW() - INTERVAL '2 minutes'
    )
ON CONFLICT (knowledge_id) DO NOTHING;

-- ============================================================================
-- USER WORKSPACE MAPPINGS (for Supabase Auth)
-- ============================================================================

-- Map test user to Product Strategy workspace
-- Test user ID: 00000000-0000-0000-0000-000000000999 (for local testing)
INSERT INTO user_workspaces (user_id, workspace_id, role, created_at)
VALUES
    (
        '00000000-0000-0000-0000-000000000999',
        '00000000-0000-0000-0000-000000000101',
        'owner',
        NOW()
    )
ON CONFLICT (user_id, workspace_id) DO NOTHING;

-- ============================================================================
-- SUMMARY
-- ============================================================================

-- Output seed data summary
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Seed data loaded successfully!';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Tenants: 1 (Demo Organization)';
    RAISE NOTICE 'Workspaces: 1 (Product Strategy)';
    RAISE NOTICE 'Agents: 3 (PM, Engineer, Designer)';
    RAISE NOTICE 'Debates: 1 (Feature Prioritization Q1 2026)';
    RAISE NOTICE 'Participants: 3';
    RAISE NOTICE 'Events: 5';
    RAISE NOTICE 'Memory Chunks: 2';
    RAISE NOTICE 'Knowledge Units: 2';
    RAISE NOTICE 'User Workspaces: 1 (test user)';
    RAISE NOTICE '========================================';
END $$;
