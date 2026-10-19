CREATE TABLE IF NOT EXISTS support_tickets (
  id TEXT PRIMARY KEY,
  reference TEXT NOT NULL UNIQUE,
  customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  created_by_account_id TEXT REFERENCES customer_portal_accounts(id) ON DELETE SET NULL,
  category TEXT NOT NULL CHECK (category IN ('eventhub', 'license', 'account', 'other')),
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'in_progress', 'waiting_customer', 'closed')),
  assigned_to TEXT REFERENCES staff_access_tokens(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status_updated
  ON support_tickets(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_customer_created
  ON support_tickets(customer_id, created_at DESC);
