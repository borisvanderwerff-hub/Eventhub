CREATE TABLE IF NOT EXISTS support_ticket_messages (
  id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  author_name TEXT NOT NULL,
  author_email TEXT NOT NULL,
  message TEXT NOT NULL,
  delivery_status TEXT NOT NULL CHECK (delivery_status IN ('pending', 'sent', 'failed')),
  created_at TEXT NOT NULL,
  sent_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_support_ticket_messages_ticket_created
  ON support_ticket_messages(ticket_id, created_at ASC);
