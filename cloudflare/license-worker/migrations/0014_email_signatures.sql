ALTER TABLE staff_access_tokens ADD COLUMN first_name TEXT;
ALTER TABLE owner_mfa ADD COLUMN first_name TEXT;
ALTER TABLE owner_mfa ADD COLUMN name TEXT;
UPDATE staff_access_tokens SET first_name = trim(substr(name, 1, instr(name || ' ', ' ') - 1)) WHERE first_name IS NULL AND trim(name) <> '';
