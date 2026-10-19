CREATE TABLE IF NOT EXISTS license_groups (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

ALTER TABLE licenses ADD COLUMN group_id TEXT;
CREATE INDEX IF NOT EXISTS idx_licenses_group_id ON licenses(group_id);
