"""Twee gescheiden werkgebieden in Trends: eigen evenementen en losse analyse."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow, TrendPanel


TODAY = date.today()


def snapshot(aangemeld, aanwezig):
    return {
        "schema": 2,
        "aangemeld": aangemeld,
        "aanwezig": aanwezig,
        "noshows": aangemeld - aanwezig,
        "opkomst_percentage": round(aanwezig / aangemeld * 100, 1),
        "verdeling": {},
    }


def own_event(name="Eigen evenement"):
    return {
        "id": name,
        "name": name,
        "date": (TODAY - timedelta(days=40)).strftime("%d-%m-%Y"),
        "event_type": "Meeloopdag",
        "place": "Ermelo",
        "statistiek": snapshot(80, 60),
    }


def imported(name="Ingeladen evenement"):
    return {
        "id": f"import:{name}",
        "name": name,
        "date": (TODAY - timedelta(days=20)).strftime("%d-%m-%Y"),
        "event_type": "Onbekend",
        "place": "Onbekend",
        "location": "Onbekend",
        "source": "Bezoekerslijst",
        "statistiek": snapshot(50, 20),
    }


class FakeCombo:
    def __init__(self, value=""):
        self._value = value

    def currentData(self):
        return self._value


class WorkspaceWindow:
    """Draait de scheidingslogica zonder de Qt-vensterconstructie."""

    _loose_trend_summaries = BezoekerslijstWindow._loose_trend_summaries

    def __init__(self, sources, selected=""):
        self.trend_sources = sources
        self.trend_source = FakeCombo(selected)


class SeparationTests(unittest.TestCase):
    """De kern: een losse analyse mag de eigen cijfers niet vertroebelen."""

    def setUp(self):
        self.sources = [
            {"label": "Regio Noord", "summaries": [imported("Noord A"), imported("Noord B")]},
            {"label": "Regio Zuid", "summaries": [imported("Zuid A")]},
        ]

    def test_loose_workspace_holds_only_imported_data(self):
        window = WorkspaceWindow(self.sources)
        names = [item["name"] for item in window._loose_trend_summaries()]
        self.assertEqual(names, ["Noord A", "Noord B", "Zuid A"])
        self.assertNotIn("Eigen evenement", names)

    def test_own_events_are_never_pulled_in(self):
        """Ook als het dossier vol staat, blijft de losse analyse los."""
        window = WorkspaceWindow(self.sources)
        window.events = [own_event()]
        self.assertNotIn("Eigen evenement", repr(window._loose_trend_summaries()))

    def test_source_filter_narrows_to_one_set(self):
        window = WorkspaceWindow(self.sources, selected="Regio Zuid")
        self.assertEqual([item["name"] for item in window._loose_trend_summaries()], ["Zuid A"])

    def test_empty_selection_means_all_sets(self):
        window = WorkspaceWindow(self.sources, selected="")
        self.assertEqual(len(window._loose_trend_summaries()), 3)

    def test_without_imports_the_loose_workspace_is_empty(self):
        self.assertEqual(WorkspaceWindow([])._loose_trend_summaries(), [])

    def test_unknown_selection_yields_nothing_rather_than_everything(self):
        window = WorkspaceWindow(self.sources, selected="Verwijderde set")
        self.assertEqual(window._loose_trend_summaries(), [])


class PanelTests(unittest.TestCase):
    """Het paneel bestaat één keer en wordt door beide werkgebieden gebruikt."""

    def setUp(self):
        self.source = desktop_source(ROOT)

    def _block(self, name):
        start = self.source.index(f"def {name}(self")
        return self.source[start:self.source.index(chr(10) + "    def ", start + 1)]

    def test_panel_is_a_reusable_widget(self):
        self.assertIn("class TrendPanel(QWidget):", self.source)
        self.assertTrue(hasattr(TrendPanel, "refresh"))
        self.assertTrue(hasattr(TrendPanel, "current_series"))
        self.assertTrue(hasattr(TrendPanel, "value_text"))

    def test_both_workspaces_instantiate_the_same_panel(self):
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("self.own_trend_panel = TrendPanel(", block)
        self.assertIn("self.loose_trend_panel = TrendPanel(", block)
        self.assertIn('self.trend_tabs.addTab(own_tab, "Eigen evenementen")', block)
        self.assertIn('self.trend_tabs.addTab(loose_tab, "Losse analyse")', block)

    def test_own_panel_reads_from_the_dossier(self):
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("self._own_trend_summaries", block)
        start = self.source.index("def _own_trend_summaries(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("collect_trend_summaries(self.events", block)

    def test_loose_panel_reads_from_the_imported_sets(self):
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("TrendPanel(self._loose_trend_summaries)", block)

    def test_the_export_follows_the_open_workspace(self):
        """Eén knop rechtsboven, die exporteert wat er openstaat.

        De knop stond eerst in de filterrij van elk paneel afzonderlijk. Nu
        hangt hij aan de tabbladen, dus mag hij niet aan een vast paneel
        gekoppeld zijn maar moet hij het actieve werkgebied opzoeken.
        """
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn(
            "self.trend_export_button.clicked.connect(lambda: self.export_trend_data())",
            block,
        )

        handler = self._block("export_trend_data")
        self.assertIn("panel = panel or self._active_trend_panel()", handler)

    def test_the_active_workspace_is_the_open_tab(self):
        self.assertIn("self.trend_tabs.currentIndex()", self._block("_active_trend_panel"))


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.source = desktop_source(ROOT)

    def _block(self, name):
        start = self.source.index(f"def {name}(self")
        return self.source[start:self.source.index("\n    def ", start + 1)]

    def test_loaded_sets_can_be_removed_one_by_one(self):
        block = self._block("remove_trend_source")
        self.assertIn("self.trend_sources = [", block)
        self.assertIn("self._sync_trend_sources()", block)

    def test_clearing_everything_asks_first(self):
        block = self._block("clear_trend_sources")
        self.assertIn("QMessageBox.question", block)
        self.assertIn("Uw eigen evenementen blijven ongemoeid", block)

    def test_import_jumps_to_the_loose_workspace(self):
        self.assertIn("self.trend_tabs.setCurrentIndex(1)", self._block("import_trend_data"))

    def test_overview_counts_events_and_participants_per_set(self):
        block = self._block("_sync_trend_sources")
        self.assertIn('"aangemeld"', block)
        self.assertIn("len(source[\"summaries\"])", block)

    def test_the_report_names_the_workspace_it_came_from(self):
        """Een rapport zonder herkomst is niet na te lopen."""
        block = self._block("export_trend_data")
        self.assertIn("self.trend_source.currentText()", block)
        self.assertIn('"Eigen dossier"', block)
        self.assertIn("bron=bron", block)

        opmaak = (ROOT / "emt_report_layout.py").read_text(encoding="utf-8")
        self.assertIn('f"Bron: {self.model[', opmaak)


if __name__ == "__main__":
    unittest.main()
