CREATE TABLE IF NOT EXISTS email_template_settings (
  template_key TEXT PRIMARY KEY,
  settings_json TEXT NOT NULL CHECK (json_valid(settings_json)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL
);

INSERT OR IGNORE INTO email_template_settings (template_key, settings_json, updated_at, updated_by) VALUES
  ('support', '{"reply_heading":"Een reactie van Cohentra Support","reply_closing":"Ik kijk graag met je mee als je nog vragen hebt.","status_heading":"We nemen je aanvraag in behandeling","status_body":"We hebben je supportaanvraag {{reference}} in behandeling genomen.","status_closing":"Ik help je graag verder.","new_heading":"{{subject}}","new_button":"Open de supportinbox"}', datetime('now'), 'system'),
  ('auth', '{"invite_subject":"Je Cohentra klantenportaal instellen","invite_intro":"Er is een account voor je aangemaakt in het Cohentra klantenportaal. Stel via de beveiligde link je wachtwoord in.","invite_button":"Account instellen","reset_subject":"Wachtwoord herstellen voor Cohentra","reset_intro":"We hebben een verzoek ontvangen om het wachtwoord van je Cohentra klantenportaal te herstellen. Gebruik de beveiligde link om een nieuw wachtwoord te kiezen.","reset_button":"Wachtwoord herstellen","expiry_note":"De link is één uur geldig en kan één keer worden gebruikt. Heb je dit niet aangevraagd? Dan kun je deze e-mail negeren."}', datetime('now'), 'system'),
  ('branding', '{"accent":"#7152ff"}', datetime('now'), 'system');

UPDATE staff_functions
SET permissions_json = json_insert(permissions_json, '$[#]', 'email.templates.manage'),
    updated_at = datetime('now')
WHERE function_key = 'beheer'
  AND NOT EXISTS (
    SELECT 1 FROM json_each(staff_functions.permissions_json)
    WHERE json_each.value = 'email.templates.manage'
  );
