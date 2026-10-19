CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  contact_name TEXT NOT NULL DEFAULT '',
  contact_email TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  customer_number TEXT,
  kvk_number TEXT NOT NULL DEFAULT '',
  vat_number TEXT NOT NULL DEFAULT '',
  website TEXT NOT NULL DEFAULT '',
  contact_role TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '',
  invoice_email TEXT NOT NULL DEFAULT '',
  street TEXT NOT NULL DEFAULT '',
  postal_code TEXT NOT NULL DEFAULT '',
  city TEXT NOT NULL DEFAULT '',
  country TEXT NOT NULL DEFAULT 'Nederland'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_number ON customers(customer_number) WHERE customer_number IS NOT NULL;

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

CREATE TABLE IF NOT EXISTS license_groups (
  id TEXT PRIMARY KEY,
  customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_license_groups_owner_name ON license_groups(COALESCE(customer_id, ''), name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS licenses (
  id TEXT PRIMARY KEY,
  key_hash TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  valid_from TEXT NOT NULL,
  valid_until TEXT NOT NULL,
  revoked_at TEXT,
  license_type TEXT NOT NULL DEFAULT 'Gesloten beta',
  activated_device_hash TEXT,
  activated_at TEXT,
  last_seen_at TEXT,
  customer_id TEXT REFERENCES customers(id),
  product_id TEXT NOT NULL DEFAULT 'eventhub' REFERENCES products(id),
  group_id TEXT REFERENCES license_groups(id),
  expiry_notice_sent_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_licenses_valid_until ON licenses(valid_until);
CREATE INDEX IF NOT EXISTS idx_licenses_customer_product ON licenses(customer_id, product_id, revoked_at, valid_until);

CREATE INDEX IF NOT EXISTS idx_licenses_group_id ON licenses(group_id);

CREATE TABLE IF NOT EXISTS staff_access_tokens (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  first_name TEXT,
  token_hash TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL DEFAULT 'support' CHECK (role IN ('support')),
  created_at TEXT NOT NULL,
  revoked_at TEXT,
  last_seen_at TEXT,
  totp_secret_enc TEXT,
  mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
  last_totp_counter INTEGER NOT NULL DEFAULT -1,
  username TEXT COLLATE NOCASE,
  password_salt TEXT,
  password_hash TEXT,
  must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_staff_access_tokens_active ON staff_access_tokens(token_hash, revoked_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_staff_access_username ON staff_access_tokens(username COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS owner_mfa (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT,
  first_name TEXT,
  totp_secret_enc TEXT NOT NULL,
  mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK (mfa_enabled IN (0, 1)),
  last_totp_counter INTEGER NOT NULL DEFAULT -1,
  enrolled_at TEXT,
  username TEXT COLLATE NOCASE UNIQUE,
  password_salt TEXT,
  password_hash TEXT
);

CREATE TABLE IF NOT EXISTS staff_sessions (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  staff_id TEXT REFERENCES staff_access_tokens(id) ON DELETE CASCADE,
  actor_role TEXT NOT NULL CHECK (actor_role IN ('owner', 'support')),
  created_at TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  last_seen_at TEXT,
  revoked_at TEXT,
  mfa_verified INTEGER NOT NULL DEFAULT 1 CHECK (mfa_verified IN (0, 1)),
  password_change_only INTEGER NOT NULL DEFAULT 0 CHECK (password_change_only IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_staff_sessions_active ON staff_sessions(token_hash, expires_at, revoked_at);
CREATE INDEX IF NOT EXISTS idx_staff_sessions_mfa_challenge ON staff_sessions(token_hash, mfa_verified, expires_at, revoked_at);

CREATE TABLE IF NOT EXISTS auth_login_attempts (
  login_key TEXT PRIMARY KEY,
  failures INTEGER NOT NULL DEFAULT 0,
  window_started_at INTEGER NOT NULL,
  locked_until INTEGER
);

CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
  id TEXT PRIMARY KEY,
  owner_id INTEGER CHECK (owner_id = 1),
  staff_id TEXT REFERENCES staff_access_tokens(id) ON DELETE CASCADE,
  code_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  used_at TEXT,
  CHECK ((owner_id = 1 AND staff_id IS NULL) OR (owner_id IS NULL AND staff_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_mfa_recovery_owner ON mfa_recovery_codes(owner_id, used_at);
CREATE INDEX IF NOT EXISTS idx_mfa_recovery_staff ON mfa_recovery_codes(staff_id, used_at);

CREATE TABLE IF NOT EXISTS customer_portal_accounts (
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
CREATE INDEX IF NOT EXISTS idx_customer_portal_accounts_active
  ON customer_portal_accounts(username COLLATE NOCASE, active);
CREATE INDEX IF NOT EXISTS idx_customer_portal_accounts_customer
  ON customer_portal_accounts(customer_id);

CREATE TABLE IF NOT EXISTS customer_sessions (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  customer_account_id TEXT NOT NULL REFERENCES customer_portal_accounts(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  last_seen_at TEXT,
  revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_customer_sessions_active
  ON customer_sessions(token_hash, expires_at, revoked_at);

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
  updated_at TEXT NOT NULL,
  created_by_staff_name TEXT
);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status_updated
  ON support_tickets(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_tickets_customer_created
  ON support_tickets(customer_id, created_at DESC);

CREATE TABLE IF NOT EXISTS support_ticket_messages (
  id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  author_name TEXT NOT NULL,
  author_email TEXT NOT NULL,
  message TEXT NOT NULL,
  delivery_status TEXT NOT NULL CHECK (delivery_status IN ('pending', 'sent', 'failed')),
  created_at TEXT NOT NULL,
  sent_at TEXT,
  external_message_id TEXT,
  is_internal INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_support_ticket_messages_external_id
  ON support_ticket_messages(external_message_id)
  WHERE external_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_support_ticket_messages_ticket_created
  ON support_ticket_messages(ticket_id, created_at ASC);

CREATE TABLE IF NOT EXISTS support_mail_sync_state (
  mailbox TEXT PRIMARY KEY,
  uid_validity TEXT NOT NULL,
  last_uid INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_template_settings (
  template_key TEXT PRIMARY KEY,
  settings_json TEXT NOT NULL CHECK (json_valid(settings_json)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
);
