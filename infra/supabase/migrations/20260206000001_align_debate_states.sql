-- Migration: Align debate states with M2 state machine
-- Date: 2026-02-06
-- Ticket: DEMO-01 blocker fix
--
-- Changes database constraint to match DebateState enum in apps/api/src/state_machine.py
-- Old states: draft, preflight, live, paused, synthesis, closed, archived
-- New states: pending, running, paused, ended

-- Step 1: Drop old constraint
ALTER TABLE debates DROP CONSTRAINT IF EXISTS debates_state_check;

-- Step 2: Migrate existing data to new states
UPDATE debates SET state = 'pending' WHERE state IN ('draft', 'preflight');
UPDATE debates SET state = 'running' WHERE state = 'live';
-- paused stays paused
UPDATE debates SET state = 'ended' WHERE state IN ('synthesis', 'closed', 'archived');

-- Step 3: Add new constraint matching DebateState enum
ALTER TABLE debates 
  ADD CONSTRAINT debates_state_check 
  CHECK (state IN ('pending', 'running', 'paused', 'ended'));

-- Step 4: Update column comment
COMMENT ON COLUMN debates.state IS 'Debate lifecycle state (M2): pending (created), running (active), paused (operator intervention), ended (completed)';
