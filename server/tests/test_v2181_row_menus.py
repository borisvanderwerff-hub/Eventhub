"""Rij-acties zitten in het rechtermuismenu, niet in knoppenrijen."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import bezoekerslijst_app

SOURCE = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

TABLES_WITH_MENU = [
    "home_event_table",
    "task_table",
    "standard_tasks_table",
    "open_tasks_table",
    "attachments_table",
]

# Deze acties werkten op de geselecteerde rij en hoeven geen knop meer.
# De knopvorm heeft een derde element met de stijlnaam; het contextmenu niet.
# Daarop matchen houdt deze test los van de menudefinities eronder.
REMOVED_BUTTONS = [
    '("Openen", self.activate_selected_event, "primaryButton")',
    '("Aanpassen", self.edit_selected_event, "secondaryButton")',
    '("Verwijderen", self.remove_selected_event, "dangerButton")',
    'QPushButton("Taak aanpassen")',
    'QPushButton("Taak bewerken")',
    'QPushButton("Taak verwijderen")',
    'QPushButton("Afronden")',
    'QPushButton("Taak openen")',
    '("Opslaan als", self.export_selected_attachment, "secondaryButton")',
    '("Verwijderen", self.remove_selected_attachment, "dangerButton")',
]

# Aanmaken blijft een knop: bij een lege tabel valt er niets aan te wijzen.
KEPT_BUTTONS = [
    'QPushButton("Taak toevoegen")',
    '("Document toevoegen", self.add_attachment, "primaryButton")',
    'self.new_event_button = QPushButton(',
]


class MenuWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.window = bezoekerslijst_app.BezoekerslijstWindow()

    def test_every_row_table_has_a_context_menu(self):
        for name in TABLES_WITH_MENU:
            with self.subTest(table=name):
                table = getattr(self.window, name)
                self.assertEqual(
                    table.contextMenuPolicy(), Qt.ContextMenuPolicy.CustomContextMenu
                )

    def test_row_menu_ignores_clicks_outside_a_row(self):
        """Rechtsklikken op leegte mag geen menu op een willekeurige rij openen."""
        block = SOURCE[SOURCE.index("def _show_row_menu(self"):]
        block = block[:block.index("\n    def ", 1)]
        self.assertIn("if row < 0 or table.isRowHidden(row):", block)
        self.assertIn("return", block)

    def test_menus_are_built_from_one_shared_helper(self):
        self.assertIn("def _attach_row_menu(self, table, actions):", SOURCE)
        self.assertGreaterEqual(SOURCE.count("self._attach_row_menu("), 4)


class ButtonRemovalTests(unittest.TestCase):
    def test_row_action_buttons_are_gone(self):
        for snippet in REMOVED_BUTTONS:
            with self.subTest(button=snippet):
                self.assertNotIn(snippet, SOURCE, "deze actie hoort in het contextmenu")

    def test_creating_still_has_a_visible_button(self):
        """Zonder rij om aan te wijzen moet aanmaken bereikbaar blijven."""
        for snippet in KEPT_BUTTONS:
            with self.subTest(button=snippet):
                self.assertIn(snippet, SOURCE)

    def test_the_handlers_themselves_still_exist(self):
        for handler in (
            "edit_selected_task", "remove_selected_task",
            "edit_standard_task", "remove_standard_task",
            "complete_selected_open_task", "open_selected_open_task",
            "export_selected_attachment", "remove_selected_attachment",
            "activate_selected_event", "edit_selected_event", "remove_selected_event",
        ):
            with self.subTest(handler=handler):
                self.assertTrue(hasattr(bezoekerslijst_app.BezoekerslijstWindow, handler))


class DiscoverabilityTests(unittest.TestCase):
    def test_the_event_list_explains_both_gestures(self):
        """Zonder knoppen moet de hint vertellen hoe je er dan wel komt."""
        block = SOURCE[SOURCE.index("def _build_events_page"):]
        block = block[:block.index("\n    def ", 1)]
        self.assertIn("Dubbelklik", block)
        self.assertIn("rechtermuisknop", block)


if __name__ == "__main__":
    unittest.main()
