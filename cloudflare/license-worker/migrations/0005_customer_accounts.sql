CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  contact_name TEXT NOT NULL DEFAULT '',
  contact_email TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

INSERT OR IGNORE INTO products (id, name, active) VALUES ('eventhub', 'EventHub', 1);

CREATE TABLE IF NOT EXISTS customer_products (
  customer_id TEXT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  product_id TEXT NOT NULL REFERENCES products(id),
  max_licenses INTEGER NOT NULL DEFAULT 0 CHECK (max_licenses >= 0),
  allowed_license_types TEXT NOT NULL DEFAULT '["beta"]',
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  PRIMARY KEY (customer_id, product_id)
);

ALTER TABLE licenses ADD COLUMN customer_id TEXT REFERENCES customers(id);
ALTER TABLE licenses ADD COLUMN product_id TEXT NOT NULL DEFAULT 'eventhub';

CREATE INDEX IF NOT EXISTS idx_licenses_customer_product ON licenses(customer_id, product_id, revoked_at, valid_until);

CREATE TABLE IF NOT EXISTS staff_access_tokens (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL DEFAULT 'support' CHECK (role IN ('support')),
  created_at TEXT NOT NULL,
  revoked_at TEXT,
  last_seen_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_staff_access_tokens_active ON staff_access_tokens(token_hash, revoked_at);
