-- Shop, Stripe-betalingen, abonnementen en centrale rechten (entitlements).
-- Breidt de bestaande klantadministratie uit; er komt geen tweede klant- of accountsysteem.
PRAGMA defer_foreign_keys = true;

-- Klanttype: 'business' = organisatieaccount (meerdere gebruikers mogelijk), 'individual' = particulier of zelfstandig kopend (eenmanszaak/zzp).
-- Bestaande klanten zijn door medewerkers als bedrijf aangemaakt en worden dus 'business'.
ALTER TABLE customers ADD COLUMN customer_type TEXT NOT NULL DEFAULT 'business' CHECK (customer_type IN ('business', 'individual'));
-- Bedrijfsnaam op de factuur voor een zelfstandig kopende klant; bij een organisatie is dat customers.name.
ALTER TABLE customers ADD COLUMN billing_company TEXT NOT NULL DEFAULT '';
ALTER TABLE customers ADD COLUMN stripe_customer_id TEXT;
ALTER TABLE customers ADD COLUMN source TEXT NOT NULL DEFAULT 'staff' CHECK (source IN ('staff', 'shop'));
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_stripe ON customers(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- Rol binnen de klant: 'admin' beheert facturatie, abonnementen, gebruikers en licentiesleutels; 'member' gebruikt alleen.
-- Bestaande portaalgebruikers konden alles en blijven daarom 'admin'.
ALTER TABLE customer_portal_accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin', 'member'));
ALTER TABLE customer_portal_accounts ADD COLUMN email_verified_at TEXT;
-- Wie een wachtwoord via de e-maillink heeft ingesteld, heeft het e-mailadres bevestigd.
UPDATE customer_portal_accounts SET email_verified_at = updated_at WHERE active = 1;

-- Zelfregistratie: pas na bevestiging van het e-mailadres ontstaat een klantrecord.
CREATE TABLE IF NOT EXISTS customer_registrations (
  token_hash TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE,
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  consumed_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_customer_registrations_email ON customer_registrations(email, consumed_at);

-- Shopgegevens op de bestaande productentabel. 'active' blijft de licentieschakelaar; 'published' bepaalt zichtbaarheid in de shop.
ALTER TABLE products ADD COLUMN slug TEXT;
ALTER TABLE products ADD COLUMN tagline TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN published INTEGER NOT NULL DEFAULT 0 CHECK (published IN (0, 1));
ALTER TABLE products ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;
ALTER TABLE products ADD COLUMN stripe_product_id TEXT;
ALTER TABLE products ADD COLUMN created_at TEXT;
ALTER TABLE products ADD COLUMN updated_at TEXT;
-- Maatwerkproducten (zoals EventHub) worden via Cohentra geleverd en nooit in de shop aangeboden of verkocht.
ALTER TABLE products ADD COLUMN shop_allowed INTEGER NOT NULL DEFAULT 1 CHECK (shop_allowed IN (0, 1));
UPDATE products SET shop_allowed = 0 WHERE id = 'eventhub';
UPDATE products SET slug = id WHERE slug IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_slug ON products(slug) WHERE slug IS NOT NULL;

CREATE TABLE IF NOT EXISTS product_images (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  r2_key TEXT NOT NULL UNIQUE,
  content_type TEXT NOT NULL,
  alt TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_product_images_product ON product_images(product_id, sort_order);

-- Functies en limieten die een product kent; abonnementen vullen deze per sleutel in.
CREATE TABLE IF NOT EXISTS product_features (
  product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  feature_key TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'flag' CHECK (kind IN ('flag', 'limit')),
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (product_id, feature_key)
);

-- Abonnementsvormen (en eenmalige aankopen). features_json: {"feature_key": true | getal}.
CREATE TABLE IF NOT EXISTS product_plans (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  billing_type TEXT NOT NULL CHECK (billing_type IN ('one_time', 'recurring')),
  features_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(features_json)),
  max_users INTEGER CHECK (max_users IS NULL OR max_users >= 1),
  max_activations INTEGER CHECK (max_activations IS NULL OR max_activations >= 0),
  trial_days INTEGER NOT NULL DEFAULT 0 CHECK (trial_days >= 0 AND trial_days <= 730),
  rank INTEGER NOT NULL DEFAULT 0,
  published INTEGER NOT NULL DEFAULT 0 CHECK (published IN (0, 1)),
  archived_at TEXT,
  stripe_product_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (product_id, code)
);

-- Prijzen zijn onveranderlijk (net als in Stripe). Een prijswijziging is een nieuwe prijs; de oude wordt gearchiveerd.
CREATE TABLE IF NOT EXISTS plan_prices (
  id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL REFERENCES product_plans(id),
  currency TEXT NOT NULL CHECK (length(currency) = 3),
  unit_amount INTEGER NOT NULL CHECK (unit_amount >= 0),
  billing_interval TEXT CHECK (billing_interval IS NULL OR billing_interval IN ('day', 'week', 'month', 'year')),
  interval_count INTEGER NOT NULL DEFAULT 1 CHECK (interval_count >= 1),
  tax_behavior TEXT NOT NULL CHECK (tax_behavior IN ('inclusive', 'exclusive', 'unspecified')),
  stripe_price_id TEXT UNIQUE,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  archived_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_plan_prices_plan ON plan_prices(plan_id, active);

-- Versies en downloadbestanden. Bestanden staan in een privé R2-bucket en zijn alleen via tijdelijke links te halen.
CREATE TABLE IF NOT EXISTS product_releases (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  version TEXT NOT NULL,
  platform TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  r2_key TEXT UNIQUE,
  file_name TEXT,
  file_size INTEGER,
  sha256 TEXT,
  published INTEGER NOT NULL DEFAULT 0 CHECK (published IN (0, 1)),
  published_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (product_id, version, platform)
);

-- Bestellingen. Plan-, prijs- en factuurgegevens worden bij de aankoop vastgelegd, zodat latere wijzigingen de historie niet raken.
CREATE TABLE IF NOT EXISTS shop_orders (
  id TEXT PRIMARY KEY,
  order_number TEXT NOT NULL UNIQUE,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  account_id TEXT REFERENCES customer_portal_accounts(id) ON DELETE SET NULL,
  product_id TEXT NOT NULL REFERENCES products(id),
  plan_id TEXT NOT NULL REFERENCES product_plans(id),
  price_id TEXT NOT NULL REFERENCES plan_prices(id),
  purchase_context TEXT NOT NULL CHECK (purchase_context IN ('private', 'business')),
  billing_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(billing_json)),
  plan_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(plan_snapshot_json)),
  currency TEXT NOT NULL,
  amount_total INTEGER,
  amount_refunded INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'paid', 'failed', 'expired', 'canceled', 'refunded', 'partially_refunded')),
  stripe_checkout_session_id TEXT UNIQUE,
  stripe_payment_intent_id TEXT,
  stripe_subscription_id TEXT,
  stripe_invoice_id TEXT,
  livemode INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  paid_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_shop_orders_customer ON shop_orders(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shop_orders_payment_intent ON shop_orders(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_shop_orders_subscription ON shop_orders(stripe_subscription_id);

-- Abonnementen zoals Stripe ze bevestigt, vertaald naar een interne status.
CREATE TABLE IF NOT EXISTS shop_subscriptions (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  product_id TEXT NOT NULL REFERENCES products(id),
  plan_id TEXT NOT NULL REFERENCES product_plans(id),
  price_id TEXT REFERENCES plan_prices(id),
  order_id TEXT REFERENCES shop_orders(id),
  stripe_subscription_id TEXT NOT NULL UNIQUE,
  stripe_status TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'trialing', 'active', 'past_due', 'suspended', 'paused', 'canceled', 'expired')),
  current_period_start TEXT,
  current_period_end TEXT,
  cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
  cancel_at TEXT,
  canceled_at TEXT,
  ended_at TEXT,
  trial_end TEXT,
  past_due_since TEXT,
  pending_plan_id TEXT REFERENCES product_plans(id),
  pending_price_id TEXT REFERENCES plan_prices(id),
  pending_change_at TEXT,
  stripe_schedule_id TEXT,
  plan_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(plan_snapshot_json)),
  livemode INTEGER NOT NULL DEFAULT 0,
  synced_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shop_subscriptions_customer ON shop_subscriptions(customer_id, product_id);

-- Centrale rechten: per klant(organisatie) en product. Bron is een abonnement, een eenmalige bestelling of handmatige toekenning.
CREATE TABLE IF NOT EXISTS entitlements (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  product_id TEXT NOT NULL REFERENCES products(id),
  plan_id TEXT REFERENCES product_plans(id),
  source TEXT NOT NULL CHECK (source IN ('subscription', 'order', 'manual')),
  source_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'active', 'grace', 'suspended', 'expired', 'revoked')),
  status_reason TEXT NOT NULL DEFAULT '',
  plan_name TEXT NOT NULL DEFAULT '',
  features_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(features_json)),
  max_users INTEGER,
  max_activations INTEGER,
  valid_from TEXT NOT NULL,
  valid_until TEXT,
  created_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_entitlements_customer ON entitlements(customer_id, product_id, status);

-- Handmatige uitzonderingen door medewerkers. Ze liggen bovenop de rechten uit Stripe en worden nooit door webhooks overschreven.
CREATE TABLE IF NOT EXISTS entitlement_overrides (
  id TEXT PRIMARY KEY,
  entitlement_id TEXT NOT NULL REFERENCES entitlements(id),
  kind TEXT NOT NULL CHECK (kind IN ('extend', 'suspend', 'features', 'limits')),
  value_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(value_json)),
  reason TEXT NOT NULL CHECK (length(reason) >= 3),
  created_by_staff_id TEXT,
  created_by_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,
  revoked_at TEXT,
  revoked_by_name TEXT,
  revoke_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_entitlement_overrides_entitlement ON entitlement_overrides(entitlement_id, revoked_at);

-- Licentiesleutels die bij een recht horen; het recht bepaalt dan geldigheid en functies.
ALTER TABLE licenses ADD COLUMN entitlement_id TEXT REFERENCES entitlements(id);
CREATE INDEX IF NOT EXISTS idx_licenses_entitlement ON licenses(entitlement_id, revoked_at);

-- Facturen komen uitsluitend uit Stripe; hier staat alleen een verwijzing, zodat er nooit twee facturen voor één betaling ontstaan.
CREATE TABLE IF NOT EXISTS billing_invoices (
  id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  stripe_invoice_id TEXT NOT NULL UNIQUE,
  stripe_subscription_id TEXT,
  order_id TEXT REFERENCES shop_orders(id),
  number TEXT,
  status TEXT NOT NULL,
  currency TEXT NOT NULL,
  amount_due INTEGER NOT NULL DEFAULT 0,
  amount_paid INTEGER NOT NULL DEFAULT 0,
  hosted_invoice_url TEXT,
  invoice_pdf TEXT,
  period_start TEXT,
  period_end TEXT,
  stripe_created INTEGER NOT NULL,
  livemode INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_customer ON billing_invoices(customer_id, stripe_created DESC);

-- Ontvangen Stripe-meldingen: voorkomt dubbele verwerking.
CREATE TABLE IF NOT EXISTS stripe_events (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  stripe_created INTEGER NOT NULL,
  object_id TEXT,
  livemode INTEGER NOT NULL DEFAULT 0,
  received_at TEXT NOT NULL,
  processed_at TEXT,
  status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processed', 'ignored', 'failed')),
  error TEXT
);

-- Tijdelijke downloadlinks (alleen hash opgeslagen).
CREATE TABLE IF NOT EXISTS download_tokens (
  token_hash TEXT PRIMARY KEY,
  release_id TEXT NOT NULL REFERENCES product_releases(id),
  customer_id TEXT NOT NULL REFERENCES customers(id),
  account_id TEXT REFERENCES customer_portal_accounts(id) ON DELETE SET NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  uses INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_download_tokens_expiry ON download_tokens(expires_at);

-- Historie van commerciële en rechtenwijzigingen, zichtbaar voor medewerkers.
CREATE TABLE IF NOT EXISTS commerce_audit_log (
  id TEXT PRIMARY KEY,
  customer_id TEXT,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  action TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('staff', 'customer', 'stripe', 'system')),
  actor_name TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  details_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(details_json)),
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_commerce_audit_customer ON commerce_audit_log(customer_id, created_at DESC);
