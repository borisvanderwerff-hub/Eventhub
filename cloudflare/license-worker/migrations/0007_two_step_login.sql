ALTER TABLE staff_sessions ADD COLUMN mfa_verified INTEGER NOT NULL DEFAULT 1 CHECK (mfa_verified IN (0, 1));

CREATE INDEX IF NOT EXISTS idx_staff_sessions_mfa_challenge
  ON staff_sessions(token_hash, mfa_verified, expires_at, revoked_at);
