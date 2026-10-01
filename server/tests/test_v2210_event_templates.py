"""Templates retain reusable defaults and never the identity of an edition."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from bezoekerslijst_app import NewProjectDialog, TaskDialog
from emt_models import empty_event, prepare_event, prepare_task, task_due_date
from emt_event_templates import template_event_data, event_from_template
from emt_event_templates_ui import TemplateEditor, TemplateManager, TemplateCard


def example():
    event = empty_event("Meeloopdag (09-09-'26)")
    event.update(date="09-09-2026", start_time="09:00", location="Den Helder",
                 rudder_event_id="123", rudder_data={"prior_closing_days": "7"},
                 template_id="old", status="Gereed", listings=[{"label": "old"}],
                 evaluation={"notes": "oud"}, attachments=[{"name": "lijst"}])
    event["tasks"] = [prepare_task({"title": "Lijst sturen", "done": True,
        "completed_on": "01-09-2026", "use_rudder_closing_date": True})]
    return event


class TemplateDataTests(unittest.TestCase):
    def test_saved_event_remains_unchanged_and_excludes_edition_data(self):
        event = example()
        before = deepcopy(event)
        data = template_event_data(event)
        self.assertEqual(event, before)
        self.assertEqual(data["name"], "Meeloopdag")
        for field in ("date", "start_time", "rudder_event_id", "rudder_data", "listings",
                      "evaluation", "attachments", "template_id", "status"):
            self.assertNotIn(field, data)
        self.assertFalse(data["tasks"][0]["done"])
        self.assertEqual(data["tasks"][0]["completed_on"], "")

    def test_closing_date_becomes_relative_deadline(self):
        data = template_event_data(example())
        task = data["tasks"][0]
        self.assertFalse(task["use_rudder_closing_date"])
        self.assertEqual(task["offset_days"], 7)
        self.assertEqual(str(task_due_date({"date": "20-10-2026"}, task)), "2026-10-13")

    def test_empty_task_choice_does_not_reintroduce_defaults(self):
        template = {"id": "t", "name": "Leeg", "event": template_event_data(example(), False)}
        self.assertEqual(event_from_template(template)["tasks"], [])

    def test_new_events_have_independent_ids_tasks_and_stable_link(self):
        template = {"id": "t", "name": "Marine", "event": template_event_data(example())}
        first, second = event_from_template(template), event_from_template(template)
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["tasks"][0]["id"], second["tasks"][0]["id"])
        first["tasks"][0]["done"] = True
        template["event"]["location"] = "Andere locatie"
        self.assertFalse(second["tasks"][0]["done"])
        self.assertEqual(first["location"], "Den Helder")
        loaded = prepare_event(json.loads(json.dumps(first)))
        self.assertEqual(loaded["template_id"], "t")
        self.assertEqual(loaded["template_name"], "Marine")
        self.assertEqual(loaded["rudder_event_id"], "")


class TemplateUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_save_dialog_task_choice_and_link_default(self):
        dialog = TemplateEditor(None, TaskDialog, [], event=example())
        self.assertTrue(dialog.link.isChecked())
        self.assertEqual(dialog.name.text(), "Meeloopdag")
        self.assertIn("7 dagen", dialog.task_list.item(0).text())
        dialog.include_tasks.setChecked(False)
        self.assertEqual(dialog.value()["event"]["tasks"], [])
        dialog.close()

    def test_order_and_task_instructions_are_saved(self):
        data = template_event_data(example())
        data["tasks"].append(prepare_task({"title": "Tweede", "notes": "Instructie"}))
        dialog = TemplateEditor(None, TaskDialog, [], template={"id": "t", "name": "Test", "event": data})
        item = dialog.task_list.takeItem(1)
        dialog.task_list.insertItem(0, item)
        saved = dialog.value()
        self.assertEqual(saved["event"]["tasks"][0]["title"], "Tweede")
        self.assertEqual(event_from_template(saved)["tasks"][0]["notes"], "Instructie")
        dialog.close()

    def test_linking_existing_event_changes_only_link_in_dialog(self):
        event = example()
        template = {"id": "new", "name": "Nieuw", "event": {"location": "Anders"}}
        dialog = NewProjectDialog(None, event, [template])
        dialog.template_link.setCurrentIndex(dialog.template_link.findData("new"))
        values = dialog.value()
        self.assertEqual(values["template_id"], "new")
        self.assertEqual(values["location"], "Den Helder")
        self.assertNotIn("tasks", values)
        self.assertEqual(event["template_id"], "old")
        dialog.close()

    def test_manager_edit_duplicate_delete_and_cards(self):
        template = {"id": "t", "name": "Marine", "event": template_event_data(example())}
        templates, saves = [template], []
        manager = TemplateManager(None, templates, TaskDialog, [], lambda: saves.append(deepcopy(templates)))
        edited = deepcopy(template)
        edited["name"] = "Marine nieuw"
        with patch.object(TemplateEditor, "exec", new=lambda self: QDialog.DialogCode.Accepted), patch.object(TemplateEditor, "value", new=lambda self: edited):
            manager.edit(template)
        self.assertEqual(templates[0]["id"], "t")
        self.assertEqual(templates[0]["name"], "Marine nieuw")
        with patch.object(TemplateEditor, "exec", new=lambda self: QDialog.DialogCode.Accepted):
            manager.edit(template, True)
        self.assertEqual(len(templates), 2)
        self.assertNotEqual(templates[0]["id"], templates[1]["id"])
        self.assertEqual(len(manager.scroll.widget().findChildren(TemplateCard)), 2)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            manager.remove(templates[1])
        self.assertEqual(len(templates), 1)
        self.assertEqual(len(saves), 3)
        manager.close()


if __name__ == "__main__":
    unittest.main()
