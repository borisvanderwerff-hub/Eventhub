"""Gereed-status kijkt alleen naar werk tot en met de evenementdag."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow
from emt_models import DEFAULT_TASK_TEMPLATES, task_notifications


TODAY = date.today()
IN_TWO_WEEKS = (TODAY + timedelta(days=14)).strftime("%d-%m-%Y")


def task(title, offset, relative, done=False):
    return {
        "id": title,
        "title": title,
        "offset_days": offset,
        "relative": relative,
        "reminder_days": 30,
        "done": done,
    }


def event(tasks, datum=IN_TWO_WEEKS, status="In voorbereiding"):
    return {"id": "e1", "name": "Meeloopdag", "date": datum, "status": status, "tasks": tasks}


def sync(item):
    window = BezoekerslijstWindow.__new__(BezoekerslijstWindow)
    BezoekerslijstWindow._sync_event_status_from_tasks(window, item)
    return item["status"]


def blocks(item, one_task):
    return BezoekerslijstWindow._task_blocks_readiness(item, one_task)


class ReadinessScopeTests(unittest.TestCase):
    """Nazorgtaken hoorden de voorbereiding niet tegen te houden."""

    def setUp(self):
        self.event = event([])

    def test_work_before_the_event_counts(self):
        self.assertTrue(blocks(self.event, task("Bus regelen", 7, "before")))

    def test_work_on_the_event_day_counts(self):
        self.assertTrue(blocks(self.event, task("Briefing", 0, "before")))
        self.assertTrue(blocks(self.event, task("Debriefing", 0, "after")))

    def test_work_after_the_event_does_not_count(self):
        self.assertFalse(blocks(self.event, task("Registreren in Rudder", 2, "after")))

    def test_without_an_event_date_the_task_label_decides(self):
        undated = event([], datum="")
        self.assertTrue(blocks(undated, task("Voorbereiden", 3, "before")))
        self.assertFalse(blocks(undated, task("Nazorg", 3, "after")))


class StatusTests(unittest.TestCase):
    def test_open_aftercare_no_longer_blocks_gereed(self):
        """De gemelde fout: alleen nazorg open, en toch In voorbereiding."""
        item = event([
            task("Bus regelen", 7, "before", done=True),
            task("Registreren in Rudder", 2, "after", done=False),
        ])
        self.assertEqual(sync(item), "Gereed")

    def test_open_preparation_still_blocks_gereed(self):
        item = event([
            task("Bus regelen", 7, "before", done=False),
            task("Registreren in Rudder", 2, "after", done=False),
        ])
        self.assertEqual(sync(item), "In voorbereiding")

    def test_everything_done_is_gereed(self):
        item = event([
            task("Bus regelen", 7, "before", done=True),
            task("Registreren in Rudder", 2, "after", done=True),
        ])
        self.assertEqual(sync(item), "Gereed")

    def test_gereed_falls_back_when_preparation_reopens(self):
        item = event([task("Bus regelen", 7, "before", done=False)], status="Gereed")
        self.assertEqual(sync(item), "In voorbereiding")

    def test_gereed_survives_when_only_aftercare_reopens(self):
        item = event([
            task("Bus regelen", 7, "before", done=True),
            task("Nazorg", 5, "after", done=False),
        ], status="Gereed")
        self.assertEqual(sync(item), "Gereed")


class DefaultTemplateTests(unittest.TestCase):
    """Het standaardtemplate bevat twee taken na afloop."""

    def _tasks(self, preparation_done, aftercare_done):
        tasks = []
        for template in DEFAULT_TASK_TEMPLATES:
            item = dict(template)
            item["id"] = template["title"]
            after = template.get("relative") == "after"
            item["done"] = aftercare_done if after else preparation_done
            tasks.append(item)
        return tasks

    def test_template_really_contains_after_event_tasks(self):
        after = [t for t in DEFAULT_TASK_TEMPLATES if t.get("relative") == "after"]
        self.assertTrue(after, "zonder die taken toont deze test niets aan")

    def test_a_standard_event_can_reach_gereed_before_the_day(self):
        item = event(self._tasks(preparation_done=True, aftercare_done=False))
        self.assertEqual(sync(item), "Gereed")

    def test_a_standard_event_with_open_preparation_stays_in_voorbereiding(self):
        item = event(self._tasks(preparation_done=False, aftercare_done=False))
        self.assertEqual(sync(item), "In voorbereiding")


class VisibilityTests(unittest.TestCase):
    def test_aftercare_tasks_remain_visible_as_notifications(self):
        """Niet meetellen voor Gereed mag ze niet uit het takenoverzicht halen."""
        tomorrow = (TODAY + timedelta(days=1)).strftime("%d-%m-%Y")
        item = event([task("Nazorg", 2, "after")], datum=tomorrow, status="Gereed")
        self.assertTrue(task_notifications([item]))


if __name__ == "__main__":
    unittest.main()
