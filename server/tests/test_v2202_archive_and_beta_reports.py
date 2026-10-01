"""Archiveren blijft een weergavekeuze en beta-foutrapporten zijn deelbaar."""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

import bezoekerslijst_app as app


APP_SOURCE = desktop_source(ROOT)


class EventArchiveTests(unittest.TestCase):
    def test_een_voorbij_evenement_wordt_automatisch_gearchiveerd(self):
        verleden = {
            "id": "oud",
            "name": "Oud evenement",
            "date": (date.today() - timedelta(days=1)).strftime("%d-%m-%Y"),
        }
        toekomst = {
            "id": "nieuw",
            "name": "Nieuw evenement",
            "date": (date.today() + timedelta(days=1)).strftime("%d-%m-%Y"),
        }
        window = SimpleNamespace(events=[verleden, toekomst])

        changed = app.BezoekerslijstWindow._archive_passed_events(window)

        self.assertTrue(changed)
        self.assertTrue(verleden["archived"])
        self.assertNotIn("archived", toekomst)

    def test_een_bewust_teruggezet_evenement_wordt_niet_opnieuw_gearchiveerd(self):
        verleden = {
            "date": (date.today() - timedelta(days=30)).strftime("%d-%m-%Y"),
            "archive_exempt": True,
        }
        window = SimpleNamespace(events=[verleden])

        changed = app.BezoekerslijstWindow._archive_passed_events(window)

        self.assertFalse(changed)
        self.assertNotIn("archived", verleden)

    def test_archiveren_filtert_trends_niet(self):
        self.assertIn("collect_trend_summaries(self.events, source=\"Eigen dossier\")", APP_SOURCE)
        self.assertNotIn("collect_trend_summaries([event for event in self.events", APP_SOURCE)

    def test_overzicht_heeft_een_archiefschakelaar_en_geen_datumgroepen(self):
        self.assertIn('QCheckBox("Gearchiveerd")', APP_SOURCE)
        board_start = APP_SOURCE.index("def _refresh_event_board")
        board_block = APP_SOURCE[board_start:APP_SOURCE.index("def _board_section", board_start)]
        self.assertNotIn('groepen = {"vandaag": [], "komend": [], "geweest": []}', board_block)


class BetaErrorReportTests(unittest.TestCase):
    def test_foutrapport_verbergt_contactgegevens(self):
        details = f"Fout in {Path.home()} voor tester@example.nl en 0612345678"

        report = app.BezoekerslijstWindow._sanitized_error_report("Test", details)

        self.assertIn("<gebruikersmap>", report)
        self.assertIn("<e-mailadres>", report)
        self.assertIn("<telefoonnummer>", report)
        self.assertNotIn("tester@example.nl", report)
        self.assertNotIn("0612345678", report)

    def test_foutvenster_biedt_mailactie(self):
        self.assertIn('"Log per e-mail versturen"', APP_SOURCE)
        self.assertIn("self._prepare_error_email(context, details)", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
