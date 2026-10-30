ALTER TABLE staff_access_tokens ADD COLUMN avatar_key TEXT;
ALTER TABLE owner_mfa ADD COLUMN avatar_key TEXT;
ALTER TABLE support_ticket_messages ADD COLUMN author_staff_id TEXT;
