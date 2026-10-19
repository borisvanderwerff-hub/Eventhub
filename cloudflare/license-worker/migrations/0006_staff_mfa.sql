ALTER TABLE staff_access_tokens ADD COLUMN totp_secret_enc TEXT;
ALTER TABLE staff_access_tokens ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1));
ALTER TABLE staff_access_tokens ADD COLUMN last_totp_counter INTEGER NOT NULL DEFAULT -1;
ALTER TABLE staff_access_tokens ADD COLUMN username TEXT COLLATE NOCASE;
ALTER TABLE staff_access_tokens ADD COLUMN password_salt TEXT;
ALTER TABLE staff_access_tokens ADD COLUMN password_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_access_username ON staff_access_tokens(username COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS owner_mfa (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  totp_secret_enc TEXT NOT NULL,
  mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
  last_totp_counter INTEGER NOT NULL DEFAULT -1,
  enrolled_at TEXT,
  username TEXT COLLATE NOCASE UNIQUE,
  password_salt TEXT,
  password_hash TEXT
);

CREATE TABLE IF NOT EXISTS staff_sessions (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  staff_id TEXT REFERENCES staff_access_tokens(id) ON DELETE CASCADE,
  actor_role TEXT NOT NULL CHECK (actor_role IN ('owner', 'support')),
  created_at TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  last_seen_at TEXT,
  revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_staff_sessions_active ON staff_sessions(token_hash, expires_at, revoked_at);

CREATE TABLE IF NOT EXISTS auth_login_attempts (
  login_key TEXT PRIMARY KEY,
  failures INTEGER NOT NULL DEFAULT 0,
  window_started_at INTEGER NOT NULL,
  locked_until INTEGER
);

CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
  id TEXT PRIMARY KEY,
  owner_id INTEGER CHECK (owner_id = 1),
  staff_id TEXT REFERENCES staff_access_tokens(id) ON DELETE CASCADE,
  code_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  used_at TEXT,
  CHECK ((owner_id = 1 AND staff_id IS NULL) OR (owner_id IS NULL AND staff_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_mfa_recovery_owner ON mfa_recovery_codes(owner_id, used_at);
CREATE INDEX IF NOT EXISTS idx_mfa_recovery_staff ON mfa_recovery_codes(staff_id, used_at);
