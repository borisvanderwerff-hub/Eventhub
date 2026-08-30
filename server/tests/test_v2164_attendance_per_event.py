"""Aanwezigheid wordt per evenement bewaard (bestandsversie 11)."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import (
    attendance_map,
    detach_event_from_records,
    is_present,
    is_present_in_scope,
    rename_attendance_event,
    set_present,
)


VOORLICHTING = "Voorlichting maart 2026"
MEELOOPDAG = "Meeloopdag april 2026"


def visitor(**overrides):
    record = {"Evenement": f"{VOORLICHTING}; {MEELOOPDAG}", "Aanwezig": {}}
    record.update(overrides)
    return record


class AttendanceMigrationTests(unittest.TestCase):
    def test_old_boolean_applies_to_every_linked_event(self):
        record = visitor(Aanwezig=True)
        self.assertEqual(
            attendance_map(record),
            {VOORLICHTING: True, MEELOOPDAG: True},
        )

    def test_old_false_boolean_never_invents_attendance(self):
        record = visitor(Aanwezig=False)
        self.assertEqual(attendance_map(record), {VOORLICHTING: False, MEELOOPDAG: False})
        self.assertFalse(is_present(record))

    def test_dict_format_is_returned_unchanged(self):
        record = visitor(Aanwezig={VOORLICHTING: True, MEELOOPDAG: False})
        self.assertEqual(attendance_map(record), {VOORLICHTING: True, MEELOOPDAG: False})


class AttendancePerEventTests(unittest.TestCase):
    def test_second_event_does_not_overwrite_the_first(self):
        """De kern van de fix: was aanwezig in maart, no-show in april."""
        record = visitor()
        set_present(record, VOORLICHTING, True)
        set_present(record, MEELOOPDAG, False)

        self.assertTrue(is_present(record, VOORLICHTING))
        self.assertFalse(is_present(record, MEELOOPDAG))

    def test_event_name_matching_ignores_case_and_spacing(self):
        record = visitor()
        set_present(record, VOORLICHTING, True)
        self.assertTrue(is_present(record, f"  {VOORLICHTING.upper()}  "))

    def test_set_present_reports_only_real_changes(self):
        record = visitor()
        self.assertTrue(set_present(record, VOORLICHTING, True))
        self.assertFalse(set_present(record, VOORLICHTING, True))
        self.assertTrue(set_present(record, VOORLICHTING, False))

    def test_scope_covers_the_events_currently_in_view(self):
        record = visitor()
        set_present(record, MEELOOPDAG, True)

        self.assertTrue(is_present_in_scope(record, {MEELOOPDAG}))
        self.assertFalse(is_present_in_scope(record, {VOORLICHTING}))
        # Zonder selectie telt aanwezigheid bij welk evenement dan ook.
        self.assertTrue(is_present_in_scope(record, set()))

    def test_unknown_event_is_never_reported_as_present(self):
        record = visitor()
        set_present(record, VOORLICHTING, True)
        self.assertFalse(is_present(record, "Open dag die niet bestaat"))


class AttendanceFollowsTheEventTests(unittest.TestCase):
    def test_renaming_an_event_keeps_its_attendance(self):
        record = visitor()
        set_present(record, VOORLICHTING, True)
        rename_attendance_event(record, VOORLICHTING, "Voorlichting Den Helder")

        self.assertTrue(is_present(record, "Voorlichting Den Helder"))
        self.assertFalse(is_present(record, VOORLICHTING))

    def test_detaching_an_event_drops_only_its_own_attendance(self):
        record = visitor()
        set_present(record, VOORLICHTING, True)
        set_present(record, MEELOOPDAG, True)

        retained = detach_event_from_records([record], VOORLICHTING)

        self.assertEqual(len(retained), 1)
        self.assertEqual(attendance_map(retained[0]), {MEELOOPDAG: True})


class LiveSessionWriteBackTests(unittest.TestCase):
    """apply_live_attendance mag alleen het evenement van de sessie raken."""

    def _apply(self, records, participants, event_name):
        # bezoekerslijst_app importeert PySide6; die is in deze testruntime niet
        # nodig, dus de functie wordt los uit de bron uitgevoerd.
        import ast

        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "apply_live_attendance"
        )
        namespace = {
            "normalize": __import__("bezoekerslijst_core").normalize,
            "record_events": __import__("bezoekerslijst_core").record_events,
            "set_present": set_present,
        }
        exec(compile(ast.Module([function], []), "<apply_live_attendance>", "exec"), namespace)
        return namespace["apply_live_attendance"](records, participants, event_name)

    def test_checkin_writes_only_to_the_session_event(self):
        record = visitor(_id="abc")
        set_present(record, VOORLICHTING, True)

        changed = self._apply(
            [record],
            [{"id": "abc", "attendance_status": "not_checked_in", "checkin_time": None}],
            MEELOOPDAG,
        )

        self.assertEqual(changed, 0, "afwezig blijft afwezig; er verandert niets")
        self.assertTrue(is_present(record, VOORLICHTING), "maart mag niet gewist worden")
        self.assertFalse(is_present(record, MEELOOPDAG))

    def test_checkin_marks_the_session_event_present(self):
        record = visitor(_id="abc")

        changed = self._apply(
            [record],
            [{"id": "abc", "attendance_status": "present", "checkin_time": "2026-04-02T09:14:00"}],
            MEELOOPDAG,
        )

        self.assertEqual(changed, 1)
        self.assertTrue(is_present(record, MEELOOPDAG))
        self.assertFalse(is_present(record, VOORLICHTING))


if __name__ == "__main__":
    unittest.main()
