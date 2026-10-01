"""De deelnemerslijsttaak volgt de inschrijvingssluiting uit Rudder."""
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from emt_models import DEFAULT_TASK_TEMPLATES, EVENT_TYPES, prepare_task, task_due_date, task_timing_text


def template():
    return next(item for item in DEFAULT_TASK_TEMPLATES if item["title"] == "Deelnemerslijst toevoegen")


class ParticipantListTaskTests(unittest.TestCase):
    def test_task_is_available_for_every_event_type(self):
        self.assertEqual(template()["event_types"], EVENT_TYPES)

    def test_without_rudder_it_is_due_seven_days_before(self):
        task = prepare_task(template())
        self.assertEqual(task_due_date({"date": "19-08-2026"}, task), date(2026, 8, 12))

    def test_rudder_closing_days_override_the_default(self):
        task = prepare_task(template())
        event = {"date": "19-08-2026", "rudder_data": {"prior_closing_days": "3"}}
        self.assertEqual(task_due_date(event, task), date(2026, 8, 16))

    def test_explicit_rudder_expiration_is_the_fallback(self):
        task = prepare_task(template())
        event = {"date": "19-08-2026", "rudder_data": {"expiration_date": "10-08-2026"}}
        self.assertEqual(task_due_date(event, task), date(2026, 8, 10))

    def test_special_planning_is_visible_to_the_user(self):
        self.assertIn("Rudder-sluitingsdatum", task_timing_text(prepare_task(template())))

    def test_completed_state_is_preserved_by_the_model(self):
        task = prepare_task({**template(), "done": True, "completed_on": "01-08-2026"})
        self.assertTrue(task["done"])
        self.assertEqual(task["completed_on"], "01-08-2026")


if __name__ == "__main__":
    unittest.main()
