ALTER TABLE support_tickets ADD COLUMN source TEXT NOT NULL DEFAULT 'customer_portal'
  CHECK (source IN ('customer_portal', 'website'));
ALTER TABLE support_tickets ADD COLUMN contact_name TEXT NOT NULL DEFAULT '';
ALTER TABLE support_tickets ADD COLUMN contact_email TEXT NOT NULL DEFAULT '';
ALTER TABLE support_tickets ADD COLUMN organization TEXT NOT NULL DEFAULT '';
ALTER TABLE support_tickets ADD COLUMN request_type TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS website_contact_rate_limits (
  ip_hash TEXT NOT NULL,
  window_started_at INTEGER NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (ip_hash, window_started_at)
);
