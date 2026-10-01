"""Kalender- en tijdknop naast de datum- en tijdvelden."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import (
    QApplication, QCalendarWidget, QDialog, QLineEdit, QPushButton, QTimeEdit,
)

import bezoekerslijst_app
from bezoekerslijst_app import with_date_picker, with_time_picker

SOURCE = desktop_source(ROOT)


class _PopupCatcher:
    """Vangt de popup op zodat hij zonder scherm te bedienen is."""

    def __enter__(self):
        self.original = QDialog.exec
        self.popup = None

        def fake(dialog):
            self.popup = dialog
            return 0

        QDialog.exec = fake
        return self

    def __exit__(self, *_args):
        QDialog.exec = self.original


class DatePickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _open(self, start_text):
        field = QLineEdit(start_text)
        holder = with_date_picker(field)
        with _PopupCatcher() as catcher:
            holder.layout().itemAt(1).widget().click()
            return field, catcher.popup.findChild(QCalendarWidget), catcher.popup

    def test_the_field_stays_editable_next_to_the_button(self):
        field = QLineEdit()
        holder = with_date_picker(field)
        self.assertEqual(holder.layout().count(), 2)
        self.assertIs(holder.layout().itemAt(0).widget(), field)
        self.assertFalse(field.isReadOnly(), "typen moet mogelijk blijven")

    def test_picking_a_day_fills_the_field(self):
        field, calendar, popup = self._open("")
        calendar.clicked.emit(QDate(2026, 9, 2))
        self.assertEqual(field.text(), "02-09-2026")

    def test_the_calendar_opens_on_the_date_already_entered(self):
        _field, calendar, _popup = self._open("15-04-2026")
        self.assertEqual(calendar.selectedDate(), QDate(2026, 4, 15))

    def test_an_empty_field_opens_on_today(self):
        _field, calendar, _popup = self._open("")
        self.assertEqual(calendar.selectedDate(), QDate.currentDate())

    def test_nonsense_in_the_field_does_not_break_the_calendar(self):
        _field, calendar, _popup = self._open("geen datum")
        self.assertEqual(calendar.selectedDate(), QDate.currentDate())

    def test_the_field_may_stay_empty(self):
        """Daarom geen QDateEdit: die heeft altijd een waarde."""
        field = QLineEdit()
        with_date_picker(field)
        self.assertEqual(field.text(), "")

    def test_choosing_a_date_triggers_saving(self):
        """Nazorg slaat op via editingFinished; dat moet ook na kiezen."""
        field, calendar, _popup = self._open("")
        opgeslagen = []
        field.editingFinished.connect(lambda: opgeslagen.append(field.text()))
        calendar.clicked.emit(QDate(2026, 1, 8))
        self.assertEqual(opgeslagen, ["08-01-2026"])


class TimePickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _open(self, start_text):
        field = QLineEdit(start_text)
        holder = with_time_picker(field)
        with _PopupCatcher() as catcher:
            holder.layout().itemAt(1).widget().click()
            popup = catcher.popup
            confirm = next(b for b in popup.findChildren(QPushButton) if b.text() == "Kiezen")
            return field, popup.findChild(QTimeEdit), confirm

    def test_picking_a_time_fills_the_field(self):
        field, editor, confirm = self._open("")
        editor.setTime(QTime(13, 30))
        confirm.click()
        self.assertEqual(field.text(), "13:30")

    def test_the_picker_opens_on_the_time_already_entered(self):
        _field, editor, _confirm = self._open("07:45")
        self.assertEqual(editor.time(), QTime(7, 45))

    def test_an_empty_field_opens_on_a_sensible_default(self):
        _field, editor, _confirm = self._open("")
        self.assertEqual(editor.time(), QTime(9, 0))

    def test_the_field_may_stay_empty(self):
        field = QLineEdit()
        with_time_picker(field)
        self.assertEqual(field.text(), "")

    def test_the_stored_format_matches_what_the_app_validates(self):
        field, editor, confirm = self._open("")
        editor.setTime(QTime(8, 5))
        confirm.click()
        self.assertEqual(field.text(), "08:05")
        self.assertTrue(bezoekerslijst_app.valid_time_text(field.text()))


class ButtonFitTests(unittest.TestCase):
    """Een vaste breedte moet ruimte laten voor het teken zelf.

    De gewone knopstijl heeft 14px zijmarge; op een knop van 34px bleef daar
    4px over en werd het kalendericoon half afgesneden.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.window = bezoekerslijst_app.BezoekerslijstWindow()
        cls.window.resize(1400, 900)
        cls.window.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def _fits(self, button):
        button.ensurePolished()
        return button.sizeHint().width() <= button.width()

    def test_every_compact_button_shows_its_glyph(self):
        knoppen = [
            ("hulpknop live sessie", self.window.live_session_help_button),
            ("maximaliseren", self.window.own_trend_panel.expand_button),
        ]
        for naam, knop in knoppen:
            with self.subTest(button=naam):
                self.assertTrue(self._fits(knop), f"{naam} snijdt zijn teken af")

    def test_the_pickers_in_the_event_form_fit(self):
        dialog = bezoekerslijst_app.NewProjectDialog(self.window)
        kiezers = [b for b in dialog.findChildren(QPushButton) if b.property("picker") == "true"]
        self.assertEqual(len(kiezers), 3, "datum, begintijd en eindtijd")
        for knop in kiezers:
            with self.subTest(button=knop.toolTip()):
                self.assertTrue(self._fits(knop))

    def test_compact_buttons_are_marked_so_the_stylesheet_can_reach_them(self):
        for knop in (self.window.live_session_help_button,
                     self.window.own_trend_panel.expand_button):
            self.assertEqual(knop.property("picker"), "true")

    def test_the_stylesheet_trims_the_padding_for_them(self):
        css = (ROOT / "theme" / "styles.py").read_text(encoding="utf-8")
        self.assertIn('QPushButton[picker="true"]', css)


class WiringTests(unittest.TestCase):
    def test_all_four_date_fields_have_a_picker(self):
        for snippet in (
            'form.addRow("Datum*:", with_date_picker(self.project_date))',
            '("Opnieuw contact", with_date_picker(self.callback_detail_followup))',
            'form.addRow(f"{name}:", with_date_picker(field))',
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, SOURCE)

    def test_both_time_fields_have_a_picker(self):
        self.assertIn("with_time_picker(self.start_time)", SOURCE)
        self.assertIn("with_time_picker(self.end_time)", SOURCE)

    def test_the_5wh_time_fields_are_left_alone(self):
        """Daar staat vrije tekst als 'vanaf 06:30'; een kiezer zou dat wissen."""
        start = SOURCE.index("short_fields = {")
        block = SOURCE[start:start + 400]
        self.assertIn("build_time", block)
        self.assertNotIn("with_time_picker", block)

    def test_no_date_field_was_replaced_by_a_qdateedit(self):
        """QDateEdit kan niet leeg zijn; drie van de vier velden mogen dat wel."""
        self.assertNotIn("QDateEdit(", SOURCE)


if __name__ == "__main__":
    unittest.main()
