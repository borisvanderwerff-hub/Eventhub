import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
APP_SOURCE = desktop_source(ROOT)


def method_block(name: str) -> str:
    start = APP_SOURCE.index(f"    def {name}")
    end = APP_SOURCE.find("\n    def ", start + 1)
    return APP_SOURCE[start:end if end >= 0 else None]


class SharedEventContextTests(unittest.TestCase):
    def test_operationele_kiezers_staan_een_lege_keuze_toe(self):
        self.assertIn("self.after_sales_event_combo = EventPickerButton(allow_none=True)", APP_SOURCE)
        self.assertIn("self.event_control_event_combo = EventPickerButton(allow_none=True)", APP_SOURCE)
        self.assertIn('"×  Selectie wissen"', APP_SOURCE)

    def test_een_wijziging_synchroniseert_beide_menu_kiezers(self):
        after_sales = method_block("_after_sales_event_changed")
        event_control = method_block("_event_control_event_changed")
        self.assertIn("self._sync_event_context_pickers()", after_sales)
        self.assertIn("self._sync_event_context_pickers()", event_control)
        self.assertIn('self.active_event_id = ""', after_sales)
        self.assertIn('self.active_event_id = ""', event_control)

    def test_synchronisatie_neemt_de_gedeelde_context_en_niet_de_oude_knop(self):
        block = method_block("_sync_event_combo")
        self.assertIn("gekozen = self._active_event()", block)
        self.assertNotIn("combo.current_id()", block)

    def test_geen_event_betekent_geen_aanwezigheids_of_nazorgregels(self):
        presence = method_block("_render_presence_table")
        render_all = method_block("_render_all")
        self.assertIn("if event else []", presence)
        self.assertIn("callback_source = self._event_visitors(after_sales_event) if after_sales_event else []", render_all)
        self.assertIn("presence_rows = self._sorted_records(self._event_visitors(presence_event)) if presence_event else []", render_all)

    def test_eventcontrol_en_after_sales_worden_zichtbaar_geblokkeerd(self):
        presence = method_block("_update_presence_registration_availability")
        after_sales = method_block("_update_after_sales_availability")
        self.assertIn("self.event_control_tabs.setEnabled(has_event)", presence)
        self.assertIn("self.event_control_context_hint.setVisible(not has_event)", presence)
        self.assertIn("self.after_sales_context_hint.setVisible(not has_event)", after_sales)
        self.assertIn("widget.setEnabled(has_event)", after_sales)


if __name__ == "__main__":
    unittest.main()
