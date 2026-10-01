"""Per soort evenement instellen welke standaardtaken meekomen.

Tot nu toe zat die keuze vast in de code: bij een online voorlichting vielen
beveiliging, vervoer en catering weg. Dat is nu een instelling per taak, en
bestaande standaardtaken worden omgezet naar precies dezelfde keuze.
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QCheckBox

from bezoekerslijst_app import TaskDialog
from emt_models import (
    DEFAULT_TASK_TEMPLATES,
    EVENT_TYPES,
    prepare_task,
    prepare_template,
    task_allowed_for_event_type,
    tasks_from_templates,
    template_event_types,
    template_scope_text,
)

APP_SOURCE = desktop_source(ROOT)


class DefaultTemplateTests(unittest.TestCase):
    """De standaardtaken zeggen nu zelf waar ze bij horen."""

    def _template(self, titel):
        return next(item for item in DEFAULT_TASK_TEMPLATES if item["title"] == titel)

    def test_poort_bus_en_broodjes_horen_niet_bij_online(self):
        for titel in ("Bezoekers aanmelden bij de beveiliging", "Vervoer regelen",
                      "Catering regelen"):
            with self.subTest(titel=titel):
                self.assertNotIn("Online voorlichting", template_event_types(self._template(titel)))

    def test_de_rest_geldt_overal(self):
        for titel in ("Laatste informatie versturen", "Deelnemers registreren in Rudder"):
            with self.subTest(titel=titel):
                self.assertEqual(template_event_types(self._template(titel)), EVENT_TYPES)


class ChoiceTests(unittest.TestCase):
    def test_een_vastgelegde_keuze_telt(self):
        template = {"title": "Zaal reserveren", "event_types": ["Inloopdag", "Meeloopdag"]}

        # In de volgorde van EVENT_TYPES, zodat de lijst er altijd hetzelfde uitziet.
        self.assertEqual(template_event_types(template), ["Meeloopdag", "Inloopdag"])

    def test_een_lege_lijst_is_ook_een_keuze(self):
        self.assertEqual(template_event_types({"title": "Uit", "event_types": []}), [])

    def test_zonder_keuze_geldt_de_oude_regel(self):
        """Bestaande installaties mogen niet ineens anders gaan doen."""
        oud = {"title": "Catering regelen", "category": "catering"}

        self.assertEqual(template_event_types(oud),
                         ["Meeloopdag", "Inloopdag", "Voorlichting"])

    def test_zonder_keuze_geldt_een_eigen_taak_overal(self):
        self.assertEqual(template_event_types({"title": "Eigen taak"}), EVENT_TYPES)

    def test_onzin_in_de_lijst_wordt_genegeerd(self):
        template = {"title": "Zaal", "event_types": ["Meeloopdag", "Braderie", 7]}

        self.assertEqual(template_event_types(template), ["Meeloopdag"])

    def test_een_onbekend_soort_krijgt_alles(self):
        """Liever een taak te veel dan een evenement zonder planning."""
        template = {"title": "Catering regelen", "category": "catering"}

        self.assertTrue(task_allowed_for_event_type(template, "Open dag"))


class ScopeTextTests(unittest.TestCase):
    def test_alles_aangevinkt_leest_als_alle_soorten(self):
        self.assertEqual(template_scope_text({"event_types": list(EVENT_TYPES)}), "Alle soorten")

    def test_een_deel_wordt_opgesomd(self):
        self.assertEqual(
            template_scope_text({"event_types": ["Meeloopdag", "Inloopdag"]}),
            "Meeloopdag, Inloopdag",
        )

    def test_niets_aangevinkt_is_zichtbaar(self):
        self.assertEqual(template_scope_text({"event_types": []}), "Geen enkel soort")


class NewEventTests(unittest.TestCase):
    """Wat een nieuw evenement aan taken meekrijgt."""

    def setUp(self):
        self.templates = [
            {"title": "Alleen inloop", "event_types": ["Inloopdag"]},
            {"title": "Altijd", "event_types": list(EVENT_TYPES)},
            {"title": "Nooit", "event_types": []},
        ]

    def test_alleen_de_taken_van_dat_soort(self):
        self.assertEqual([taak["title"] for taak in tasks_from_templates(self.templates, "Inloopdag")],
                         ["Alleen inloop", "Altijd"])
        self.assertEqual([taak["title"] for taak in tasks_from_templates(self.templates, "Meeloopdag")],
                         ["Altijd"])

    def test_de_taak_zelf_draagt_de_keuze_niet_mee(self):
        """De soortkeuze hoort bij de standaardtaak, niet bij het evenement."""
        taken = tasks_from_templates(self.templates, "Inloopdag")

        for taak in taken:
            with self.subTest(taak=taak["title"]):
                self.assertNotIn("event_types", taak)

    def test_prepare_template_bewaart_de_keuze_wel(self):
        bewaard = prepare_template({"title": "Alleen inloop", "event_types": ["Inloopdag"]})

        self.assertEqual(bewaard["event_types"], ["Inloopdag"])
        self.assertNotIn("event_types", prepare_task(bewaard))


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_een_standaardtaak_krijgt_een_vinkje_per_soort(self):
        dialog = TaskDialog({"title": "Zaal", "event_types": ["Meeloopdag"]}, standaard=True)

        self.assertEqual(list(dialog.type_boxes), EVENT_TYPES)
        self.assertTrue(dialog.type_boxes["Meeloopdag"].isChecked())
        self.assertFalse(dialog.type_boxes["Voorlichting"].isChecked())

    def test_de_keuze_komt_terug_uit_het_venster(self):
        dialog = TaskDialog({"title": "Zaal", "event_types": list(EVENT_TYPES)}, standaard=True)
        dialog.type_boxes["Online voorlichting"].setChecked(False)

        self.assertEqual(dialog.value()["event_types"],
                         ["Meeloopdag", "Inloopdag", "Voorlichting"])

    def test_een_taak_van_een_evenement_kiest_geen_soorten(self):
        dialog = TaskDialog({"title": "Zaal reserveren"})

        self.assertEqual(dialog.type_boxes, {})
        self.assertFalse(dialog.findChildren(QCheckBox))
        self.assertNotIn("event_types", dialog.value())


class ScreenTests(unittest.TestCase):
    """Waar je de keuze ziet staan."""

    def test_de_kolom_staat_op_de_pagina_standaardtaken(self):
        self.assertIn(
            'self.standard_tasks_table = self._new_table(["Taak", "Geldt voor", "Planning", "Melding"])',
            APP_SOURCE,
        )

    def test_de_kolom_staat_ook_in_het_venster_vanuit_een_evenement(self):
        self.assertIn('table = self._new_table(["Taak", "Geldt voor", "Planning", "Melding"])', APP_SOURCE)

    def test_beide_plekken_openen_het_venster_met_soorten(self):
        self.assertEqual(APP_SOURCE.count("standaard=True"), 4)

    def test_de_keuze_overleeft_het_opslaan(self):
        for regel in (
            "self.task_templates = [prepare_template(template) for template in templates]",
            "return [prepare_template(template) for template in stored if isinstance(template, dict)]",
        ):
            with self.subTest(regel=regel):
                self.assertIn(regel, APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
