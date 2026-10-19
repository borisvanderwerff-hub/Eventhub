ALTER TABLE licenses ADD COLUMN license_type TEXT NOT NULL DEFAULT 'Gesloten beta';
ALTER TABLE licenses ADD COLUMN activated_device_hash TEXT;
ALTER TABLE licenses ADD COLUMN activated_at TEXT;

UPDATE licenses
SET license_type = 'Beheerder'
WHERE valid_until = '9999-12-31';
