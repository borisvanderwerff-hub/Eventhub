CREATE TABLE IF NOT EXISTS support_mail_sync_issues (
  id TEXT PRIMARY KEY,
  mailbox TEXT NOT NULL,
  uid_validity TEXT NOT NULL,
  uid INTEGER NOT NULL,
  subject TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  UNIQUE(mailbox, uid_validity, uid)
);
CREATE INDEX IF NOT EXISTS idx_support_mail_sync_issues_unresolved
  ON support_mail_sync_issues(mailbox, resolved_at, created_at);
