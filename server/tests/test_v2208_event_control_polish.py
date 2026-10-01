"""Regressietests voor de veilige EventControl-route in 0.2.0 Beta."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow


APP_SOURCE = desktop_source(ROOT)
MANAGER_SOURCE = (ROOT / "server" / "manager" / "manager_window.py").read_text(encoding="utf-8")


def method_block(name: str) -> str:
    start = APP_SOURCE.index(f"    def {name}")
    end = APP_SOURCE.find("\n    def ", start + 5)
    return APP_SOURCE[start:end if end >= 0 else None]


class EventSpecificLiveWindowTests(unittest.TestCase):
    def test_live_window_lookup_stays_with_selected_event(self):
        event_a = {"id": "event-a"}
        event_b = {"id": "event-b"}
        stopped_a = SimpleNamespace(linked_event_id="event-a", server_thread=None)
        running_b = SimpleNamespace(linked_event_id="event-b", server_thread=object())
        host = SimpleNamespace(_live_server_windows=[stopped_a, running_b])

        result = BezoekerslijstWindow._active_live_server_window(host, event_a)

        self.assertIs(result, stopped_a)

    def test_dashboard_uses_the_event_control_selection(self):
        block = method_block("open_live_dashboard")
        self.assertIn("event = self._event_control_selected_event()", block)
        self.assertIn("self._active_live_server_window(event)", block)

    def test_connecting_filters_discovered_sessions(self):
        block = method_block("open_live_webclient")
        self.assertIn("belongs_to_selected_event", block)
        self.assertIn('hub.get("source_event_id"', block)
        self.assertIn("hubs = [hub for hub in hubs if belongs_to_selected_event(hub)]", block)


class EventControlLayoutTests(unittest.TestCase):
    def test_dashboard_is_an_action_not_a_tab(self):
        build = method_block("_build_event_control_page")
        self.assertNotIn('addTab(live_dashboard_tab, "Live dashboard")', build)
        self.assertIn('self.live_dashboard_button = QPushButton("Dashboard openen")', build)

    def test_requested_names_are_visible(self):
        self.assertIn('insertTab(0, access_widget, "Aanwezigheid")', APP_SOURCE)
        self.assertIn('QLabel("＋  Livesessie hosten")', APP_SOURCE)
        self.assertIn('QPushButton("Verbinden als incheckpunt  →")', APP_SOURCE)

    def test_active_session_has_compact_controls(self):
        build = method_block("_build_event_control_page")
        self.assertIn('QPushButton("Beheer openen")', build)
        self.assertIn('QPushButton("Dashboard openen")', build)
        self.assertNotIn('QPushButton("Pauzeren")', build)


class SafeCompletionTests(unittest.TestCase):
    def test_manual_completion_warns_before_unknown_becomes_absent(self):
        block = method_block("_finish_presence_registration")
        warning = block.index('"Registratie afronden?"')
        mutation = block.index("set_attendance(record, event_name, AFWEZIG)")
        self.assertLess(warning, mutation)
        self.assertIn("QMessageBox.StandardButton.Cancel", block)

    def test_closing_a_live_window_offers_review_or_completion(self):
        block = method_block("_offer_live_session_completion")
        self.assertIn('"Aanwezigheid controleren"', block)
        self.assertIn('"Registratie afronden"', block)
        self.assertIn('"Aanwezigheid naar Rudder"', block)
        self.assertIn("self.export_directly_to_rudder(event=event)", block)
        self.assertIn("confirm=False", block)

    def test_event_picker_uses_its_own_selection_api(self):
        review = method_block("_show_event_control_presence")
        home = method_block("_open_home_today_live_session")
        self.assertIn("event_control_event_combo.set_current_id", review)
        self.assertIn("event_control_event_combo.set_current_id", home)
        self.assertNotIn("event_control_event_combo.findData", APP_SOURCE)
        self.assertNotIn("event_control_event_combo.setCurrentIndex", APP_SOURCE)

    def test_rudder_export_accepts_the_completed_event_explicitly(self):
        block = method_block("export_directly_to_rudder")
        self.assertIn("*, event=None", block)
        self.assertIn("event = event or self._selected_rudder_event()", block)

    def test_manager_keeps_existing_pause_and_stop_controls(self):
        self.assertIn('self.freeze_button = QPushButton("Pauzeren")', MANAGER_SOURCE)
        self.assertIn('self.stop_checkin_button = QPushButton("Stoppen")', MANAGER_SOURCE)


class VersionTests(unittest.TestCase):
    def test_beta_version_is_020(self):
        self.assertIn('APP_VERSION = "0.2.1 Beta"', APP_SOURCE)
        self.assertIn('EventHub • 0.2.1 Beta', MANAGER_SOURCE)


if __name__ == "__main__":
    unittest.main()
