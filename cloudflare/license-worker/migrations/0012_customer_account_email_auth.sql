CREATE TABLE IF NOT EXISTS customer_auth_tokens (
  token_hash TEXT PRIMARY KEY,
  customer_account_id TEXT NOT NULL REFERENCES customer_portal_accounts(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL CHECK (purpose IN ('invite', 'password_reset')),
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER,
  created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customer_auth_tokens_account_purpose
  ON customer_auth_tokens(customer_account_id, purpose);

CREATE TABLE IF NOT EXISTS customer_auth_rate_limits (
  bucket_key TEXT PRIMARY KEY,
  window_started_at INTEGER NOT NULL,
  attempts INTEGER NOT NULL
);
