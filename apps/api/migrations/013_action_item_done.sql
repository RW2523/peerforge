-- An action item could be extracted, debated and decided — but never finished.
-- The status CHECK had no terminal value, so "mark as done" was impossible and
-- any attempt returned a 500 from the constraint violation.
ALTER TABLE transcript_action_items DROP CONSTRAINT IF EXISTS transcript_action_items_status_check;
ALTER TABLE transcript_action_items ADD CONSTRAINT transcript_action_items_status_check
    CHECK (status IN ('extracted', 'debating', 'decided', 'done', 'dismissed'));
