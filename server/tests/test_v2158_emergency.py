from pathlib import Path
from tempfile import TemporaryDirectory
import os
import tempfile
import unittest

from openpyxl import load_workbook

os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="eventhub_v2158_tests_")

from server.database import connect, now_iso, transaction
from server.services import emergency_service


ROOT = Path(__file__).resolve().parents[2]


class Version2158EmergencyServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.connection = connect(Path(self.temp.name) / "event.db")
        stamp = now_iso()
        with transaction(self.connection) as tx:
            tx.execute(
                "INSERT INTO event_session (id,name,date,location,status,created_at,updated_at) VALUES ('event-1','Testevent','01-01-2027','Utrecht','active',?,?)",
                (stamp, stamp),
            )
            for pid, first, last, status in [
                ("p1", "Boris", "Werff", "present"),
                ("p2", "Safa", "Bekour", "present"),
                ("p3", "Frank", "Burg", "absent"),
            ]:
                tx.execute(
                    "INSERT INTO participant (id,event_id,voornaam,achternaam,attendance_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (pid, "event-1", first, last, status, stamp, stamp),
                )

    def tearDown(self):
        self.temp.cleanup()

    def test_emergency_tracks_only_people_inside_without_changing_attendance(self):
        state = emergency_service.start(self.connection, "Ga naar verzamelplaats Noord.", "Manager")
        self.assertTrue(state["active"])
        overview = emergency_service.overview(self.connection)
        self.assertEqual(overview["total"], 2)
        self.assertEqual(overview["unaccounted"], 2)
        emergency_service.mark_safe(self.connection, "p1", True, "Balie 1", "Noord", "Team A")
        overview = emergency_service.overview(self.connection)
        self.assertEqual(overview["safe"], 1)
        attendance = self.connection.execute("SELECT attendance_status FROM participant WHERE id='p1'").fetchone()[0]
        self.assertEqual(attendance, "present")
        emergency_service.end(self.connection, "Manager")
        self.assertFalse(emergency_service.state(self.connection)["active"])

    def test_excel_export_contains_incident_columns(self):
        emergency_service.start(self.connection, "Volg instructies.", "Manager")
        emergency_service.mark_safe(self.connection, "p1", True, "Balie 1", "Noord", "Team A")
        output = emergency_service.export_workbook(self.connection)
        workbook = load_workbook(output, read_only=True)
        sheet = workbook["Calamiteitenregistratie"]
        values = list(sheet.values)
        self.assertIn("Veilig gemeld", values[5])
        self.assertTrue(any("Werff" in row for row in values if row))

    def test_browser_and_manager_expose_emergency_controls(self):
        app = (ROOT / "server/web/app.py").read_text(encoding="utf-8")
        html = (ROOT / "server/web/templates/connect.html").read_text(encoding="utf-8")
        js = (ROOT / "server/web/static/js/connect.js").read_text(encoding="utf-8")
        manager = (ROOT / "server/manager/manager_window.py").read_text(encoding="utf-8")
        self.assertIn('@app.post("/api/emergency/start")', app)
        self.assertIn("Calamiteitenmodus actief", html)
        self.assertIn("Volg de instructies van de eventmanager of beheerder.", html)
        self.assertIn("De normale functies zijn hervat.", html)
        self.assertIn("refreshEmergency", js)
        self.assertIn('QPushButton("Calamiteitenmodus starten")', manager)


if __name__ == "__main__":
    unittest.main()
