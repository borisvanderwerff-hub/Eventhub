"""Het evenementkeuzevenster toont per evenement het aantal aanmeldingen."""
import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QDialog

import bezoekerslijst_app as app_module


class PickerRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        window = app_module.BezoekerslijstWindow()
        events = []
        # Toekomstige datums: het keuzevenster toont zonder zoekopdracht de eerstvolgende evenementen.
        dagen = [(date.today() + timedelta(days=n)).strftime("%d-%m-%Y") for n in (10, 20)]
        for naam, datum in (("Open Dag", dagen[0]), ("Meeloopdag", dagen[1])):
            source = app_module.empty_event(naam, window.task_templates, "Meeloopdag")
            source["date"] = datum
            source["name"] = app_module.event_name_with_date(naam, datum)
            events.append(app_module.prepare_event(source, window.task_templates))
        window.events.extend(events)
        for voornaam, gast in (("Sam", ""), ("Noor", ""), ("Daan", "123")):
            record = app_module.empty_record()
            record.update({"Voornaam": voornaam, "Achternaam": "Fictief", "Evenement": events[0]["name"],
                           "GastVan": gast})
            window.records.append(record)
        window._render_all()
        cls.window, cls.events = window, events

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def test_lines_count_registrations_and_introducees(self):
        regels = self.window._registration_lines(self.events)
        self.assertEqual(regels[self.events[0]["id"]], "<b>3</b> aanmeldingen · waarvan 1 introducé")
        self.assertEqual(regels[self.events[1]["id"]], "<b>0</b> aanmeldingen")

    def _cards_from(self, button):
        captured = {}
        original = QDialog.exec

        def fake(dialog):
            captured["cards"] = dialog.findChildren(app_module.EventCard)
            return 0

        QDialog.exec = fake
        try:
            button.click()
        finally:
            QDialog.exec = original
        return captured["cards"]

    def test_after_sales_and_event_control_pickers_show_the_count(self):
        for name in ("after_sales_event_combo", "event_control_event_combo"):
            with self.subTest(picker=name):
                button = getattr(self.window, name)
                button.set_events(self.events, self.events[0]["id"])
                cards = {card.event_id: card for card in self._cards_from(button)}
                card = cards[self.events[0]["id"]]
                self.assertIsNotNone(card.registrations_label)
                self.assertIn("<b>3</b> aanmeldingen", card.registrations_label.text())

    def test_card_without_count_stays_as_before(self):
        card = app_module.EventCard(self.events[1])
        self.assertIsNone(card.registrations_label)


if __name__ == "__main__":
    unittest.main()
