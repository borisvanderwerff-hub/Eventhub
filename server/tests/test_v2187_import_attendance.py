"""Aanwezigheid uit een Rudder-lijst moet bij het juiste evenement landen."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import infer_presence_from_text, is_present, set_present

APP_SOURCE = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")


class RudderValueTests(unittest.TestCase):
    """Rudder schrijft Yes en No; die moeten herkend worden."""

    def test_yes_and_no_in_any_casing(self):
        for value in ("Yes", "yes", "YES"):
            self.assertIs(infer_presence_from_text(value), True, value)
        for value in ("No", "no", "NO"):
            self.assertIs(infer_presence_from_text(value), False, value)

    def test_dutch_wording_keeps_working(self):
        self.assertIs(infer_presence_from_text("Ja"), True)
        self.assertIs(infer_presence_from_text("Nee"), False)

    def test_rudder_placeholders_stay_undecided(self):
        """Canceled en Unknown zijn geen uitspraak over aanwezigheid."""
        self.assertIsNone(infer_presence_from_text("Canceled"))
        self.assertIsNone(infer_presence_from_text("Unknown"))
        self.assertIsNone(infer_presence_from_text(""))


class AttendanceFollowsTheEventNameTests(unittest.TestCase):
    """De bronkolom noemt het evenement anders dan EventHub.

    EventHub zet de datum in de naam, de aanmeldlijst niet. De import
    overschreef het veld Evenement maar liet de aanwezigheid onder de oude
    naam staan, waardoor de statistieken iedereen als afwezig zagen.
    """

    def _imported_record(self, present):
        record = {"Evenement": "Meeloopdag Marine", "Voornaam": "Jan", "Aanwezig": {}}
        set_present(record, "Meeloopdag Marine", present)
        return record

    def _reassign(self, record, target):
        """Zoals de import het doet."""
        aanwezig = is_present(record)
        record["Evenement"] = target
        record["Aanwezig"] = {}
        set_present(record, target, aanwezig)
        return record

    def test_attendance_survives_the_rename(self):
        doel = "Meeloopdag Marine (02-09-'26)"
        record = self._reassign(self._imported_record(True), doel)
        self.assertTrue(is_present(record, doel))

    def test_absence_survives_the_rename(self):
        doel = "Meeloopdag Marine (02-09-'26)"
        record = self._reassign(self._imported_record(False), doel)
        self.assertFalse(is_present(record, doel))
        self.assertIn(doel, record["Aanwezig"])

    def test_the_old_name_is_not_left_behind(self):
        doel = "Meeloopdag Marine (02-09-'26)"
        record = self._reassign(self._imported_record(True), doel)
        self.assertEqual(list(record["Aanwezig"]), [doel])

    def test_the_import_does_this(self):
        start = APP_SOURCE.index("linked_to_active = active_event")
        block = APP_SOURCE[start:start + 800]
        self.assertIn("aanwezig_in_bestand = is_present(record)", block)
        self.assertIn('set_present(record, active_event["name"], aanwezig_in_bestand)', block)


if __name__ == "__main__":
    unittest.main()
