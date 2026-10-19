CREATE TABLE IF NOT EXISTS customer_portal_accounts (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
  username TEXT NOT NULL COLLATE NOCASE UNIQUE,
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_seen_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_customer_portal_accounts_active
  ON customer_portal_accounts(username COLLATE NOCASE, active);

CREATE TABLE IF NOT EXISTS customer_sessions (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  customer_account_id TEXT NOT NULL REFERENCES customer_portal_accounts(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  last_seen_at TEXT,
  revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_customer_sessions_active
  ON customer_sessions(token_hash, expires_at, revoked_at);
