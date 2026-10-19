ALTER TABLE staff_access_tokens
  ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1));

ALTER TABLE staff_sessions
  ADD COLUMN password_change_only INTEGER NOT NULL DEFAULT 0 CHECK (password_change_only IN (0, 1));
