ALTER TABLE support_ticket_messages ADD COLUMN external_message_id TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_support_ticket_messages_external_id
  ON support_ticket_messages(external_message_id)
  WHERE external_message_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS support_mail_sync_state (
  mailbox TEXT PRIMARY KEY,
  uid_validity TEXT NOT NULL,
  last_uid INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
