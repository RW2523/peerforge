-- Add 'web' to the meeting_materials kind check constraint
-- so Tavily web search results can be saved alongside literature papers.

ALTER TABLE meeting_materials
  DROP CONSTRAINT IF EXISTS meeting_materials_kind_check;

ALTER TABLE meeting_materials
  ADD CONSTRAINT meeting_materials_kind_check CHECK (
    kind IN ('text', 'link', 'file_placeholder', 'file', 'literature', 'web')
  );
