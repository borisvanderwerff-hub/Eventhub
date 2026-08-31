"""Waarschuwing bij het exporteren van persoonsgegevens, en de vraag om de map te openen."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SOURCE = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

# Exports die deelnemersgegevens meenemen en dus gewaarschuwd horen te worden.
WITH_PERSONAL_DATA = [
    "export_participant_list",
    "export_participant_pdf",
    "export_excel",
    "export_rudder_attendance",
    "export_fivewh_document",
    "export_selected_attachment",
]
# Exports die uitsluitend aantallen of eigen profielgegevens bevatten.
WITHOUT_PERSONAL_DATA = [
    "export_statistics",
    "export_trend_data",
    "export_evaluation_document",
]


def block(name):
    start = SOURCE.index(f"def {name}(self")
    return SOURCE[start:SOURCE.index("\n    def ", start + 1)]


class WarningTests(unittest.TestCase):
    def test_every_export_with_personal_data_warns_first(self):
        for name in WITH_PERSONAL_DATA:
            self.assertIn("_confirm_personal_data_export", block(name), f"{name} waarschuwt niet")

    def test_anonymous_exports_do_not_nag(self):
        for name in WITHOUT_PERSONAL_DATA:
            self.assertNotIn(
                "_confirm_personal_data_export", block(name),
                f"{name} bevat geen bezoekersgegevens en hoort niet te waarschuwen",
            )

    def test_the_warning_precedes_the_file_dialog(self):
        """Annuleren moet kunnen voordat er een locatie is gekozen."""
        for name in WITH_PERSONAL_DATA:
            body = block(name)
            self.assertLess(
                body.index("_confirm_personal_data_export"),
                body.index("getSaveFileName"),
                f"{name} vraagt te laat",
            )

    def test_declining_stops_the_export(self):
        for name in WITH_PERSONAL_DATA:
            body = block(name)
            index = body.index("_confirm_personal_data_export")
            self.assertIn("return", body[index:index + 120], f"{name} gaat door na annuleren")

    def test_warning_names_the_retention_period_and_the_responsibility(self):
        body = block("_confirm_personal_data_export")
        self.assertIn("self._retention_days()", body)
        self.assertIn("verlaten die gegevens EventHub", body)
        self.assertIn("zelf verantwoordelijk", body)

    def test_warning_can_be_cancelled(self):
        body = block("_confirm_personal_data_export")
        self.assertIn("Annuleren", body)
        self.assertIn("Toch exporteren", body)


class FolderPromptTests(unittest.TestCase):
    def test_every_export_offers_to_open_the_folder(self):
        for name in WITH_PERSONAL_DATA + WITHOUT_PERSONAL_DATA:
            self.assertIn("_offer_open_export_folder", block(name), f"{name} biedt de map niet aan")

    def test_prompt_opens_the_containing_folder_not_the_file(self):
        body = block("_offer_open_export_folder")
        self.assertIn("folder = path.parent", body)
        self.assertIn("QUrl.fromLocalFile(str(folder.resolve()))", body)

    def test_prompt_can_be_declined(self):
        body = block("_offer_open_export_folder")
        self.assertIn("StandardButton.No", body)
        self.assertIn("if answer != QMessageBox.StandardButton.Yes:", body)

    def test_failure_to_open_is_reported(self):
        self.assertIn("Map openen mislukt", block("_offer_open_export_folder"))


if __name__ == "__main__":
    unittest.main()
