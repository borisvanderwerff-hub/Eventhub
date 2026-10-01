"""Installatiehulp is bereikbaar via instellingen, niet via het Rudder-tabblad."""
import inspect
import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget
from bezoekerslijst_app import ApplicationSettingsDialog, BezoekerslijstWindow, RETENTION_DEFAULT_DAYS
from theme.styles import build_stylesheet


class BrowserExtensionSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_installation_help_keeps_settings_open_and_preserves_choices(self):
        preferences = dict(mode="relevant", upcoming_days=30,
                           autosave_enabled=True, autosave_delay_seconds=3,
                           backups_enabled=True, backup_count=5,
                           retention_days=RETENTION_DEFAULT_DAYS, dark_mode=False)
        for dark in (False, True):
            with self.subTest(dark=dark):
                owner = QWidget()
                for name in ("show_storage_locations", "manage_recovery_files",
                             "review_retention_cleanup", "open_rudder_extension_folder"):
                    setattr(owner, name, Mock())
                dialog = ApplicationSettingsDialog(owner, preferences)
                dialog.setStyleSheet(build_stylesheet(dark))
                dialog.show()
                self.app.processEvents()
                before = dialog.value()
                dialog.extension_install_button.click()
                owner.open_rudder_extension_folder.assert_called_once_with(dialog_parent=dialog)
                self.assertTrue(dialog.isVisible())
                self.assertEqual(dialog.value(), before)
                self.assertFalse(dialog.grab().isNull())
                dialog.close()
                owner.close()

    def test_no_old_installation_button_or_navigation_hint(self):
        source = inspect.getsource(BezoekerslijstWindow)
        self.assertNotIn("Browserassistent installeren / openen", source)
        self.assertNotIn("rudder_layout.addWidget(extension_button)", source)
        helper = inspect.getsource(BezoekerslijstWindow.open_rudder_extension_folder)
        self.assertIn("Algemene instellingen → Browserextensie", helper)
        self.assertIn("QDialog(owner)", helper)


if __name__ == "__main__":
    unittest.main()
