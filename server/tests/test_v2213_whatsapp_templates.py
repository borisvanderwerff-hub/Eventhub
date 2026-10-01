"""WhatsApp-sjablonen, enkele datum in berichten en gekleurde contactstatussen."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

import bezoekerslijst_app as app_module
from bezoekerslijst_app import (
    CALLBACK_STATUSES,
    WhatsAppQueueDialog,
    WhatsAppTemplatesDialog,
    callback_status_colour,
    load_whatsapp_templates,
    normalize_whatsapp_templates,
    save_whatsapp_templates,
    whatsapp_event_name,
)

GREEN, ORANGE, RED, GREY = "#2f9e5b", "#e08a1e", "#d64545", "#8c919a"


def _record(**extra):
    record = {"Voornaam": "Sam", "Achternaam": "Fictief", "Telefoonnummer": "0612345678",
              "WhatsAppStatus": "Nog te sturen"}
    record.update(extra)
    return record


class EventNameTests(unittest.TestCase):
    def test_date_suffix_is_removed(self):
        self.assertEqual(whatsapp_event_name("Open Dag (24-08-'26)"), "Open Dag")

    def test_sequence_after_date_is_removed(self):
        self.assertEqual(whatsapp_event_name("Open Dag (24-08-'26) (2)"), "Open Dag")

    def test_name_without_date_is_untouched(self):
        self.assertEqual(whatsapp_event_name("Meeloopdag (2)"), "Meeloopdag (2)")
        self.assertEqual(whatsapp_event_name("Meeloopdag"), "Meeloopdag")


class TemplateStorageTests(unittest.TestCase):
    def setUp(self):
        self.settings = QSettings(str(Path(os.environ.get("TMPDIR", "/tmp")) / "eh_wa_test.ini"),
                                  QSettings.Format.IniFormat)
        self.settings.clear()

    def test_default_template_until_first_save(self):
        templates = load_whatsapp_templates(self.settings)
        self.assertEqual(len(templates), 1)

    def test_empty_list_stays_empty(self):
        save_whatsapp_templates(self.settings, [])
        self.assertEqual(load_whatsapp_templates(self.settings), [])

    def test_round_trip_keeps_order(self):
        save_whatsapp_templates(self.settings, [
            {"id": "b", "name": "Tweede", "text": "B"},
            {"id": "a", "name": "Eerste", "text": "A"},
        ])
        self.assertEqual([t["name"] for t in load_whatsapp_templates(self.settings)], ["Tweede", "Eerste"])

    def test_invalid_entries_are_dropped(self):
        cleaned = normalize_whatsapp_templates([{"name": "", "text": "x"}, {"name": "x", "text": " "}, "rommel",
                                                {"id": "d", "name": "Goed", "text": "Tekst"},
                                                {"id": "d", "name": "Ook goed", "text": "Tekst"}])
        self.assertEqual([t["name"] for t in cleaned], ["Goed", "Ook goed"])
        self.assertNotEqual(cleaned[0]["id"], cleaned[1]["id"])
        self.assertEqual(normalize_whatsapp_templates("geen json"), [])


class QueueDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, templates, template_text=None):
        event = {"name": "Open Dag (24-08-'26)", "date": "24-08-2026", "place": "Den Helder"}
        if template_text is not None:
            event["whatsapp_template"] = template_text
        return WhatsAppQueueDialog([_record()], event, {"name": "Recruiter"}, None, templates=templates)

    def test_date_appears_once(self):
        dialog = self._dialog([], "Welkom bij [evenement] op [datum].")
        dialog.add_signature.setChecked(False)
        message = dialog._message_for(dialog.records[0])
        self.assertEqual(message, "Welkom bij Open Dag op 24-08-2026.")

    def test_picker_sits_on_the_candidate_row(self):
        dialog = self._dialog([{"id": "a", "name": "A", "text": "Tekst A"}])
        row = None
        layout = dialog.layout()
        for index in range(layout.count()):
            child = layout.itemAt(index).layout()
            if child and child.indexOf(dialog.person_label) >= 0:
                row = child
        self.assertIsNotNone(row)
        self.assertGreaterEqual(row.indexOf(dialog.template_picker), 0)

    def test_picking_fills_the_message(self):
        dialog = self._dialog([{"id": "a", "name": "A", "text": "Hoi [voornaam]"}])
        index = dialog.template_picker.findData("a")
        dialog.template_picker.setCurrentIndex(index)
        dialog._apply_picked_template(index)
        self.assertEqual(dialog.template_edit.toPlainText(), "Hoi [voornaam]")
        dialog.add_signature.setChecked(False)
        self.assertEqual(dialog.preview.toPlainText(), "Hoi Sam")

    def test_matching_template_is_preselected(self):
        dialog = self._dialog([{"id": "a", "name": "A", "text": "X"}, {"id": "b", "name": "B", "text": "Y"}], "Y")
        self.assertEqual(dialog.template_picker.currentData(), "b")

    def test_long_list_scrolls_and_picker_stays_narrow(self):
        templates = [{"id": str(i), "name": f"Sjabloon met een behoorlijk lange naam {i}", "text": f"T{i}"}
                     for i in range(30)]
        dialog = self._dialog(templates)
        picker = dialog.template_picker
        self.assertLessEqual(picker.maxVisibleItems(), 10)
        self.assertLessEqual(picker.maximumWidth(), 280)
        dialog.show()
        picker.showPopup()
        view = picker.view()
        self.assertLess(view.height(), view.sizeHintForRow(0) * 12)
        self.assertTrue(view.verticalScrollBar().maximum() > 0)
        picker.hidePopup()
        dialog.close()

    def test_without_templates_picker_is_disabled(self):
        dialog = self._dialog([])
        self.assertFalse(dialog.template_picker.isEnabled())


class ManagerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_add_move_remove(self):
        dialog = WhatsAppTemplatesDialog([{"id": "a", "name": "A", "text": "Tekst"}])
        dialog._add_template()
        dialog.name_edit.setText("B")
        dialog.text_edit.setPlainText("Andere tekst")
        dialog._move_template(-1)
        self.assertEqual([t["name"] for t in dialog.value()], ["B", "A"])
        original = app_module.QMessageBox.question
        app_module.QMessageBox.question = staticmethod(lambda *a, **k: app_module.QMessageBox.StandardButton.Yes)
        try:
            dialog._remove_template()
        finally:
            app_module.QMessageBox.question = original
        self.assertEqual([t["name"] for t in dialog.value()], ["A"])

    def test_duplicate_names_are_refused(self):
        dialog = WhatsAppTemplatesDialog([{"id": "a", "name": "A", "text": "x"}, {"id": "b", "name": "a", "text": "y"}])
        warnings = []
        original = app_module.QMessageBox.warning
        app_module.QMessageBox.warning = staticmethod(lambda *a, **k: warnings.append(a))
        try:
            dialog._accept_if_valid()
        finally:
            app_module.QMessageBox.warning = original
        self.assertTrue(warnings)
        self.assertNotEqual(dialog.result(), 1)


class StatusColourTests(unittest.TestCase):
    def test_colour_groups(self):
        expected = {
            "Gesproken": GREEN, "Afgerond": GREEN, "WhatsApp verzonden": GREEN,
            "Terugbellen op verzoek": ORANGE, "Voicemail": ORANGE, "Geen gehoor": ORANGE,
            "Niet meer benaderen": RED, "Nog bellen": GREY,
        }
        self.assertEqual(set(expected), set(CALLBACK_STATUSES))
        for status, colour in expected.items():
            self.assertEqual(callback_status_colour(status), colour, status)



class SettingsMenuTests(unittest.TestCase):
    def test_both_settings_menus_offer_whatsapp_templates(self):
        QApplication.instance() or QApplication([])
        window = app_module.BezoekerslijstWindow()
        menubar = [action.text() for menu_action in window.menuBar().actions()
                   if menu_action.text() == "Instellingen" for action in menu_action.menu().actions()]
        gear = [action.text() for action in window.settings_button.menu().actions()]
        self.assertIn("WhatsApp-sjablonen", menubar)
        self.assertIn("WhatsApp-sjablonen", gear)
        window.close()

    def test_status_dot_follows_a_status_change(self):
        QApplication.instance() or QApplication([])
        window = app_module.BezoekerslijstWindow()
        source = app_module.empty_event("Open Dag", window.task_templates, "Meeloopdag")
        source["date"] = "24-08-2026"
        source["name"] = app_module.event_name_with_date("Open Dag", "24-08-2026")
        event = app_module.prepare_event(source, window.task_templates)
        window.events.append(event)
        record = app_module.empty_record()
        record.update({"Voornaam": "Sam", "Achternaam": "Fictief", "Evenement": event["name"]})
        window.records.append(record)
        window.active_event_id = event["id"]
        window.selected_events = {event["name"]}
        window.after_sales_event_combo.set_events(window.events, event["id"])
        window._render_all()
        self.assertEqual(window.callback_table.rowCount(), 1)
        item = window.callback_table.item(0, 0)
        self.assertEqual(item.toolTip(), "Contactstatus: Nog bellen")
        window._callback_status_changed(record["_id"], "Niet meer benaderen")
        item = window.callback_table.item(0, 0)
        self.assertEqual(item.toolTip(), "Contactstatus: Niet meer benaderen")
        colour = item.icon().pixmap(12, 12).toImage().pixelColor(6, 6).name()
        self.assertEqual(colour, RED)
        window.close()


if __name__ == "__main__":
    unittest.main()
