ALTER TABLE staff_access_tokens ADD COLUMN email TEXT;
ALTER TABLE owner_mfa ADD COLUMN email TEXT;
UPDATE staff_access_tokens SET email = lower(username) WHERE email IS NULL AND instr(username, '@') > 0;
UPDATE owner_mfa SET email = lower(username) WHERE email IS NULL AND instr(username, '@') > 0;

-- A challenge session in which a staff member links their own authenticator
ALTER TABLE staff_sessions ADD COLUMN mfa_enrollment INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS staff_password_resets (
  token_hash TEXT PRIMARY KEY,
  staff_id TEXT REFERENCES staff_access_tokens(id) ON DELETE CASCADE,
  is_owner INTEGER NOT NULL DEFAULT 0 CHECK (is_owner IN (0, 1)),
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_staff_password_resets_account ON staff_password_resets(staff_id, is_owner);
