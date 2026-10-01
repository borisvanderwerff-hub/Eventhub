"""Datum- en tijdkeuze openen als eigen venster dat altijd op het scherm past."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication, QCalendarWidget, QDialog, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from bezoekerslijst_app import with_date_picker, with_time_picker


class _Catcher:
    def __enter__(self):
        self.original = QDialog.exec
        self.popup = None

        def fake(dialog):
            self.popup = dialog
            return 0

        QDialog.exec = fake
        return self

    def __exit__(self, *_):
        QDialog.exec = self.original


class PickerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window_at_bottom_right(self, factory):
        area = self.app.primaryScreen().availableGeometry()
        host = QWidget()
        layout = QVBoxLayout(host)
        field = QLineEdit()
        holder = factory(field)
        layout.addWidget(holder)
        host.resize(260, 60)
        host.move(area.right() - 250, area.bottom() - 50)  # knop tegen de rechteronderhoek
        host.show()
        self.app.processEvents()
        self.addCleanup(host.close)
        with _Catcher() as catcher:
            holder.layout().itemAt(1).widget().click()
        return host, field, catcher.popup

    def _assert_on_screen(self, popup):
        area = self.app.primaryScreen().availableGeometry()
        geometry = popup.geometry()
        geometry.setSize(popup.sizeHint().expandedTo(popup.size()))
        self.assertTrue(area.contains(geometry), f"{geometry} valt buiten {area}")

    def test_date_picker_is_a_titled_window_on_screen(self):
        _host, _field, popup = self._window_at_bottom_right(with_date_picker)
        self.assertFalse(popup.windowFlags() & Qt.WindowType.Popup == Qt.WindowType.Popup)
        self.assertEqual(popup.windowTitle(), "Datum kiezen")
        self.assertTrue(popup.isModal())
        self._assert_on_screen(popup)

    def test_time_picker_is_a_titled_window_on_screen(self):
        _host, _field, popup = self._window_at_bottom_right(with_time_picker)
        self.assertEqual(popup.windowTitle(), "Tijd kiezen")
        self._assert_on_screen(popup)

    def _button(self, popup, text):
        return next(b for b in popup.findChildren(QPushButton) if b.text() == text)

    def test_today_and_clear_buttons(self):
        _host, field, popup = self._window_at_bottom_right(with_date_picker)
        saved = []
        field.editingFinished.connect(lambda: saved.append(field.text()))
        self._button(popup, "Vandaag").click()
        self.assertEqual(field.text(), QDate.currentDate().toString("dd-MM-yyyy"))
        with _Catcher() as catcher:
            field.parentWidget().layout().itemAt(1).widget().click()
        self._button(catcher.popup, "Leegmaken").click()
        self.assertEqual(field.text(), "")
        self.assertEqual(saved, [QDate.currentDate().toString("dd-MM-yyyy"), ""])

    def test_cancel_leaves_the_field_alone(self):
        _host, field, popup = self._window_at_bottom_right(with_date_picker)
        field.setText("01-02-2026")
        self._button(popup, "Annuleren").click()
        self.assertEqual(field.text(), "01-02-2026")
        self.assertIsNotNone(popup.findChild(QCalendarWidget))


if __name__ == "__main__":
    unittest.main()
