"""Evenementen kunnen expliciet of door ontbrekende deelnemers buiten analyses blijven."""
import os
from pathlib import Path
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from bezoekerslijst_app import BezoekerslijstWindow, NewProjectDialog
from emt_models import empty_event, prepare_event
from emt_trends import collect_summaries, event_summary


def measured_event(**extra):
    return {
        "id": "e1", "name": "Test", "date": "01-09-2026", "status": "Afgerond",
        "statistiek": {"aangemeld": 10, "aanwezig": 8, "noshows": 2, "verdeling": {}},
        **extra,
    }


class ModelTests(unittest.TestCase):
    def test_existing_events_still_count_by_default(self):
        self.assertFalse(empty_event()["exclude_from_analysis"])
        self.assertFalse(prepare_event({"name": "Bestaand"})["exclude_from_analysis"])

    def test_choice_survives_loading(self):
        self.assertTrue(prepare_event({"name": "Test", "exclude_from_analysis": True})["exclude_from_analysis"])


class TrendTests(unittest.TestCase):
    def test_explicitly_excluded_event_is_skipped(self):
        self.assertIsNone(event_summary(measured_event(exclude_from_analysis=True)))

    def test_event_without_participants_is_skipped(self):
        event = measured_event()
        event["statistiek"]["aangemeld"] = 0
        self.assertIsNone(event_summary(event))

    def test_only_real_measurements_are_collected(self):
        empty = measured_event(id="empty")
        empty["statistiek"]["aangemeld"] = 0
        self.assertEqual(len(collect_summaries([measured_event(), empty, measured_event(id="off", exclude_from_analysis=True)])), 1)

    def test_open_aftercare_tasks_do_not_block_a_complete_measurement(self):
        self.assertIsNotNone(event_summary(measured_event(status="In voorbereiding")))

    def test_unknown_attendance_blocks_the_measurement(self):
        event = measured_event(status="Afgerond")
        event["statistiek"]["onbekend"] = 1
        self.assertIsNone(event_summary(event))


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_event_form_exposes_the_choice(self):
        dialog = NewProjectDialog(event=prepare_event({"name": "Test", "date": "01-09-2026"}))
        self.assertFalse(dialog.exclude_from_analysis.isChecked())
        dialog.exclude_from_analysis.setChecked(True)
        self.assertTrue(dialog.value()["exclude_from_analysis"])

    def test_snapshot_capture_stops_for_excluded_event(self):
        class Stub:
            _capture_event_statistics = BezoekerslijstWindow._capture_event_statistics
        window = Stub()
        event = measured_event(exclude_from_analysis=True)
        self.assertFalse(BezoekerslijstWindow._capture_event_statistics(window, event))


if __name__ == "__main__":
    unittest.main()
