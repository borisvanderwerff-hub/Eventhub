PRAGMA defer_foreign_keys = true;

-- Customer details
ALTER TABLE customers ADD COLUMN customer_number TEXT;
ALTER TABLE customers ADD COLUMN kvk_number TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN vat_number TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN website TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN contact_role TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN phone TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN invoice_email TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN street TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN postal_code TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN city TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN country TEXT NOT NULL DEFAULT 'Nederland';

UPDATE customers SET customer_number = 'CUS-' || printf('%04d', (
  SELECT COUNT(*) FROM customers c2
  WHERE c2.id <> 'cohentra-website-intake'
    AND (c2.created_at < customers.created_at OR (c2.created_at = customers.created_at AND c2.id <= customers.id))
)) WHERE id <> 'cohentra-website-intake';

CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_number ON customers(customer_number) WHERE customer_number IS NOT NULL;

-- Tickets that staff log on behalf of a customer
ALTER TABLE support_tickets ADD COLUMN created_by_staff_name TEXT;

-- Several portal users per customer: rebuild the table without UNIQUE(customer_id).
-- Dropping the old table cascades to sessions and auth tokens and clears support_tickets.created_by_account_id,
-- so keep a copy of all three and put them back.
CREATE TABLE customer_sessions_backup_0019 AS SELECT * FROM customer_sessions;
CREATE TABLE customer_auth_tokens_backup_0019 AS SELECT * FROM customer_auth_tokens;
CREATE TABLE support_ticket_accounts_backup_0019 AS SELECT id, created_by_account_id FROM support_tickets WHERE created_by_account_id IS NOT NULL;

CREATE TABLE customer_portal_accounts_new (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  username TEXT NOT NULL COLLATE NOCASE UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  password_salt TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  disabled_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_seen_at TEXT
);

INSERT INTO customer_portal_accounts_new (id, customer_id, username, name, email, password_salt, password_hash, active, disabled_at, created_at, updated_at, last_seen_at)
SELECT a.id, a.customer_id, a.username, COALESCE(c.contact_name, ''),
       lower(CASE WHEN instr(a.username, '@') > 0 THEN a.username ELSE COALESCE(c.contact_email, '') END),
       a.password_salt, a.password_hash, a.active, NULL, a.created_at, a.updated_at, a.last_seen_at
FROM customer_portal_accounts a JOIN customers c ON c.id = a.customer_id;

DROP TABLE customer_portal_accounts;
ALTER TABLE customer_portal_accounts_new RENAME TO customer_portal_accounts;

INSERT OR IGNORE INTO customer_sessions SELECT * FROM customer_sessions_backup_0019;
INSERT OR IGNORE INTO customer_auth_tokens SELECT * FROM customer_auth_tokens_backup_0019;
UPDATE support_tickets SET created_by_account_id = (SELECT b.created_by_account_id FROM support_ticket_accounts_backup_0019 b WHERE b.id = support_tickets.id) WHERE id IN (SELECT id FROM support_ticket_accounts_backup_0019);
DROP TABLE customer_sessions_backup_0019;
DROP TABLE support_ticket_accounts_backup_0019;
DROP TABLE customer_auth_tokens_backup_0019;

CREATE INDEX IF NOT EXISTS idx_customer_portal_accounts_active ON customer_portal_accounts(username COLLATE NOCASE, active);
CREATE INDEX IF NOT EXISTS idx_customer_portal_accounts_customer ON customer_portal_accounts(customer_id);
