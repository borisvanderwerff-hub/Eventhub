CREATE TABLE IF NOT EXISTS staff_functions (
  function_key TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  permissions_json TEXT NOT NULL CHECK (json_valid(permissions_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS staff_function_assignments (
  staff_id TEXT NOT NULL REFERENCES staff_access_tokens(id) ON DELETE CASCADE,
  function_key TEXT NOT NULL REFERENCES staff_functions(function_key) ON DELETE CASCADE,
  assigned_at TEXT NOT NULL,
  PRIMARY KEY (staff_id, function_key)
);

CREATE INDEX IF NOT EXISTS idx_staff_function_assignments_function
  ON staff_function_assignments(function_key, staff_id);

INSERT OR IGNORE INTO staff_functions (function_key, name, permissions_json, created_at, updated_at) VALUES
  ('beheer', 'Beheer', '["customers.view","customers.manage","licenses.view","licenses.issue","licenses.manage","support.view","support.reply","support.status"]', datetime('now'), datetime('now')),
  ('support', 'Support', '["support.view","support.reply","support.status","customers.view","licenses.view","licenses.issue"]', datetime('now'), datetime('now')),
  ('sales', 'Sales', '["sales.view","sales.manage","customers.view"]', datetime('now'), datetime('now'));

INSERT OR IGNORE INTO staff_function_assignments (staff_id, function_key, assigned_at)
SELECT id, 'support', datetime('now') FROM staff_access_tokens WHERE revoked_at IS NULL;
