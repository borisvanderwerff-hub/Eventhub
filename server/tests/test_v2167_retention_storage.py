"""Bewaartermijn op alle opslaglocaties: kopieën en livesessiedatabase."""
from datetime import date, timedelta
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow
from emt_retention import scrub_payload


TODAY = date.today()
LONG_AGO = (TODAY - timedelta(days=90)).strftime("%d-%m-%Y")


def payload_with_personal_data():
    return {
        "format": "DCPL Event Management Tool",
        "version": 11,
        "events": [{"id": "e1", "name": "Voorlichting", "date": LONG_AGO,
                    "statistiek": {"aangemeld": 1, "aanwezig": 1}}],
        "records": [{
            "_id": "r1",
            "Evenement": "Voorlichting",
            "Voornaam": "Jan",
            "Achternaam": "Jansen",
            "Geboortedatum": "01-06-2008",
            "Telefoonnummer": "0612345678",
            "Email": "jan@example.com",
        }],
    }


class StoredCopyScrubTests(unittest.TestCase):
    """Reservekopieën bevatten dezelfde gegevens als het hoofddossier."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def _window(self, backups, recovery):
        window = BezoekerslijstWindow.__new__(BezoekerslijstWindow)
        window._backup_files = lambda *a, **k: backups
        window._recovery_path = lambda: recovery
        window._write_payload_atomic = lambda path, data: Path(path).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        window._write_error_log = lambda *a, **k: None
        return window

    def test_backups_and_recovery_copy_are_cleaned(self):
        backup = self.directory / "dossier - 20260401.bvp"
        recovery = self.directory / "autosave.bvp"
        for path in (backup, recovery):
            path.write_text(json.dumps(payload_with_personal_data()), encoding="utf-8")

        window = self._window([backup], recovery)
        cleaned = BezoekerslijstWindow._scrub_stored_copies(window, 21)

        self.assertEqual(cleaned, 2)
        for path in (backup, recovery):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("Jansen", text)
            self.assertNotIn("0612345678", text)
            self.assertNotIn("01-06-2008", text)
            # De cijfers moeten juist wel bewaard blijven.
            self.assertIn("statistiek", text)

    def test_unreadable_copy_is_skipped_without_crashing(self):
        broken = self.directory / "kapot.bvp"
        broken.write_text("dit is geen json", encoding="utf-8")
        window = self._window([broken], self.directory / "bestaat-niet.bvp")

        self.assertEqual(BezoekerslijstWindow._scrub_stored_copies(window, 21), 0)
        self.assertTrue(broken.is_file())

    def test_copy_without_expired_events_is_left_alone(self):
        payload = payload_with_personal_data()
        payload["events"][0]["date"] = TODAY.strftime("%d-%m-%Y")
        recent = self.directory / "recent.bvp"
        recent.write_text(json.dumps(payload), encoding="utf-8")

        window = self._window([recent], self.directory / "bestaat-niet.bvp")

        self.assertEqual(BezoekerslijstWindow._scrub_stored_copies(window, 21), 0)
        self.assertIn("Jansen", recent.read_text(encoding="utf-8"))


class SessionDatabaseScrubTests(unittest.TestCase):
    """De livesessiedatabase bevat namen in meer tabellen dan alleen participant."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "event.db"
        self.addCleanup(self.temporary.cleanup)

        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE participant (id TEXT, voornaam TEXT, achternaam TEXT, geboortedatum TEXT);
            CREATE TABLE audit_log (id INTEGER, actor TEXT, details TEXT);
            CREATE TABLE emergency_status (id INTEGER, participant_naam TEXT);
            CREATE TABLE event_session (id TEXT, name TEXT);
            """
        )
        connection.execute("INSERT INTO participant VALUES ('p1','Jan','Jansen','01-06-2008')")
        connection.execute("INSERT INTO audit_log VALUES (1,'Boris','Jan Jansen ingecheckt')")
        connection.execute("INSERT INTO emergency_status VALUES (1,'Jan Jansen')")
        connection.execute("INSERT INTO event_session VALUES ('s1','Voorlichting')")
        connection.commit()
        connection.close()

    def _scrub(self):
        window = BezoekerslijstWindow.__new__(BezoekerslijstWindow)
        window._write_error_log = lambda *a, **k: None
        return BezoekerslijstWindow._scrub_session_database(window, self.database)

    def test_every_table_holding_names_is_emptied(self):
        self.assertTrue(self._scrub())

        connection = sqlite3.connect(self.database)
        try:
            for table in ("participant", "audit_log", "emergency_status"):
                count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(count, 0, f"{table} bevat nog rijen")
            # De sessie zelf blijft bestaan; alleen de personen verdwijnen.
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM event_session").fetchone()[0], 1)
        finally:
            connection.close()

    def test_names_are_not_recoverable_from_the_raw_file(self):
        """Zonder VACUUM blijven verwijderde rijen leesbaar in het bestand."""
        self._scrub()
        raw = self.database.read_bytes()
        for personal in (b"Jansen", b"01-06-2008", b"Jan Jansen"):
            self.assertNotIn(personal, raw)

    def test_missing_database_is_harmless(self):
        window = BezoekerslijstWindow.__new__(BezoekerslijstWindow)
        window._write_error_log = lambda *a, **k: None
        self.assertFalse(
            BezoekerslijstWindow._scrub_session_database(window, self.database.with_name("weg.db"))
        )

    def test_database_without_those_tables_is_handled(self):
        other = self.database.with_name("ander.db")
        connection = sqlite3.connect(other)
        connection.execute("CREATE TABLE iets (id INTEGER)")
        connection.commit()
        connection.close()

        window = BezoekerslijstWindow.__new__(BezoekerslijstWindow)
        window._write_error_log = lambda *a, **k: None
        self.assertTrue(BezoekerslijstWindow._scrub_session_database(window, other))


class PayloadRoundTripTests(unittest.TestCase):
    def test_scrubbed_payload_stays_loadable(self):
        payload = payload_with_personal_data()
        scrub_payload(payload, 21)
        restored = json.loads(json.dumps(payload))

        self.assertEqual(restored["records"], [])
        self.assertEqual(restored["events"][0]["statistiek"]["aanwezig"], 1)
        self.assertTrue(restored["events"][0]["persoonsgegevens_gewist"])


if __name__ == "__main__":
    unittest.main()
