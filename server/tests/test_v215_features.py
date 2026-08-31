from pathlib import Path
import os
import tempfile
import unittest


_TEST_ROOT = tempfile.mkdtemp(prefix="eventhub_v215_tests_")
os.environ["XDG_DATA_HOME"] = _TEST_ROOT

from server import network
from server.database import connect
from server.services import session_service


ROOT = Path(__file__).resolve().parents[2]


class HotspotSelectionTests(unittest.TestCase):
    def test_windows_hotspot_wins_over_regular_and_virtual_adapters(self):
        hotspot = network._candidate_score("192.168.137.1", "Draadloze LAN-adapter LAN-verbinding* 10")
        regular = network._candidate_score("192.168.1.42", "Draadloze LAN-adapter Wi-Fi")
        virtual = network._candidate_score("192.168.56.1", "VirtualBox Host-Only Network")
        self.assertGreater(hotspot, regular)
        self.assertGreater(regular, virtual)

    def test_unusable_addresses_are_rejected(self):
        self.assertFalse(network._usable_ipv4("127.0.0.1"))
        self.assertFalse(network._usable_ipv4("169.254.10.2"))
        self.assertTrue(network._usable_ipv4("192.168.137.1"))


class SessionActivityTests(unittest.TestCase):
    def test_freeze_stop_and_resume_appear_in_dashboard_activity(self):
        session = session_service.create_session("Meldingentest", "25-08-2026", "Utrecht")
        connection = connect(session.db_path)
        session_service.set_frozen(connection, True, "Druk bij de ingang", "Balie 1")
        session_service.set_frozen(connection, False, by="Balie 1")
        session_service.stop_checkin(connection, "Programma begonnen", "Beheerder")
        session_service.resume_checkin(connection, "Beheerder")
        activity = session_service.recent_session_activity(connection)
        self.assertEqual([item["action"] for item in activity[:4]], [
            "checkin_resumed", "checkin_stopped", "session_unfrozen", "session_frozen",
        ])
        self.assertEqual(activity[1]["detail"], "Programma begonnen")
        self.assertEqual(activity[3]["by"], "Balie 1")


class UserInterfaceStaticTests(unittest.TestCase):
    def test_dashboard_and_resume_warning_are_present(self):
        dashboard = (ROOT / "server/web/templates/dashboard.html").read_text(encoding="utf-8")
        connect_js = (ROOT / "server/web/static/js/connect.js").read_text(encoding="utf-8")
        manager = (ROOT / "server/manager/manager_window.py").read_text(encoding="utf-8")
        self.assertIn('id="sessionStatusWindow"', dashboard)
        self.assertIn("worden teruggezet naar Nog niet ingecheckt", connect_js)
        # De knop heet nu Apparaten en het logboek zit in een menu in plaats
        # van in het knoppenraster; beide moeten wel bereikbaar blijven.
        self.assertIn("def show_connections(self)", manager)
        self.assertIn('QPushButton("Apparaten")', manager)
        self.assertIn("def open_logs_folder(self)", manager)
        self.assertIn('addAction("Logmap openen")', manager)


if __name__ == "__main__":
    unittest.main()
