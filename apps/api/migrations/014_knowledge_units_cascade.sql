-- Prep packs outlived their sessions and became readable by everyone.
--
-- agent_knowledge_units.source_debate_id was ON DELETE SET NULL, so deleting a
-- debate detached its knowledge units rather than removing them. The read 
-- authorization in routes/knowledge.py resolves a unit's workspace THROUGH
-- that link, so a detached unit had no workspace to check and matched every
-- caller. On the live database all 16 units were in that state.
--
-- A knowledge unit is meaningless without the session that produced it, so it
-- should go with it.

DELETE FROM agent_knowledge_units WHERE source_debate_id IS NULL;

ALTER TABLE agent_knowledge_units
    DROP CONSTRAINT IF EXISTS agent_knowledge_units_source_debate_id_fkey;

ALTER TABLE agent_knowledge_units
    ADD CONSTRAINT agent_knowledge_units_source_debate_id_fkey
    FOREIGN KEY (source_debate_id) REFERENCES debates(debate_id) ON DELETE CASCADE;
