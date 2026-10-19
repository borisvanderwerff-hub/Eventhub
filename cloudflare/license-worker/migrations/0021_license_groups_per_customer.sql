-- License groups now belong to one customer; customer_id NULL means Cohentra (internal).
-- Group names only have to be unique per customer, so the table is rebuilt without UNIQUE(name).
-- Nothing has a foreign key to license_groups (licenses.group_id is a plain column), so the rebuild is safe.
CREATE TABLE license_groups_new (
  id TEXT PRIMARY KEY,
  customer_id TEXT REFERENCES customers(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
INSERT INTO license_groups_new (id, customer_id, name, created_at)
SELECT g.id,
       (SELECT CASE WHEN COUNT(DISTINCT l.customer_id) = 1 AND SUM(l.customer_id IS NULL) = 0 THEN MAX(l.customer_id) END FROM licenses l WHERE l.group_id = g.id AND l.revoked_at IS NULL),
       g.name, g.created_at
FROM license_groups g;
DROP TABLE license_groups;
ALTER TABLE license_groups_new RENAME TO license_groups;
CREATE UNIQUE INDEX IF NOT EXISTS idx_license_groups_owner_name ON license_groups(COALESCE(customer_id, ''), name COLLATE NOCASE);

-- Licenses in a group that belongs to another owner lose that group.
UPDATE licenses SET group_id = NULL
WHERE group_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM license_groups g WHERE g.id = licenses.group_id AND g.customer_id IS licenses.customer_id);

-- When the customer received the "your license expires soon" e-mail
ALTER TABLE licenses ADD COLUMN expiry_notice_sent_at TEXT;
