-- 013: Multi-student advisor console (Phase 3 / M7)
-- Tag each review session with a student identifier so an advisor can group a
-- shared department workspace's sessions by student, track readiness per
-- student, and flag who needs support — without a full RBAC/user overhaul.
ALTER TABLE debates ADD COLUMN IF NOT EXISTS student_label TEXT;
CREATE INDEX IF NOT EXISTS idx_debates_student_label ON debates (workspace_id, student_label);
