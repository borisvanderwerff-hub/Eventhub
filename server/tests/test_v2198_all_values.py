"""Overig met zijn aantal, alles kunnen tonen, en twee kolommen bij veel waarden.

De grafieken toonden de acht grootste waarden en telden de rest op onder
'Overig', zonder aantal en zonder uitweg. Bij een vaardag van 102 deelnemers
verdween daarmee 43 procent van de bezoekers in een grijze balk: Economie,
Mobiliteit en Transport, VeVa Beveiliging en nog twintig andere profielen.

De kruistabel eronder deed het al wel goed - met het aantal erbij en een
schakelaar om alles te tonen. Nu geldt die schakelaar voor het hele tabblad,
inclusief de export.
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

APP_SOURCE = desktop_source(ROOT)


class Vinkje:
    def __init__(self, aan): self.aan = aan
    def isChecked(self): return self.aan


class Venster:
    """Genoeg van het hoofdvenster om _field_counts los te kunnen draaien."""

    def __init__(self, records, alles=False):
        import bezoekerslijst_app

        self.records = records
        self.statistics_show_all = Vinkje(alles)
        for naam in ("_show_all_values", "_grouped_value", "_field_counts"):
            setattr(self, naam, getattr(bezoekerslijst_app.BezoekerslijstWindow, naam).__get__(self))


def deelnemers(verdeling):
    records = []
    for waarde, aantal in verdeling.items():
        records += [{"Profiel": waarde} for _ in range(aantal)]
    return records


VAARDAG = {
    "Media, Vormgeving en ICT": 14, "Economie en Maatschappij": 12, "Natuur en Gezondheid": 10,
    "Zorg en Welzijn": 9, "Techniek": 8, "Cultuur en Maatschappij": 7,
    "Dienstverlening en Producten": 6, "Onbekend": 5,
    "Economie": 4, "Mobiliteit en Transport": 4, "VeVa Beveiliging": 3, "Groen": 2,
}


class FieldCountsTests(unittest.TestCase):
    def test_overig_vertelt_om_hoeveel_waarden_het_gaat(self):
        counts = Venster(deelnemers(VAARDAG))._field_counts("Profiel")

        self.assertEqual(counts[-1][0], "Overig (4)")
        self.assertEqual(counts[-1][1], 4 + 4 + 3 + 2)

    def test_de_acht_grootste_blijven_apart(self):
        counts = Venster(deelnemers(VAARDAG))._field_counts("Profiel")

        self.assertEqual(len(counts), 9)
        self.assertEqual(counts[0], ("Media, Vormgeving en ICT", 14))

    def test_er_gaat_geen_deelnemer_verloren(self):
        records = deelnemers(VAARDAG)

        counts = Venster(records)._field_counts("Profiel")

        self.assertEqual(sum(value for _, value in counts), len(records))

    def test_met_alles_tonen_krijgt_elke_waarde_een_eigen_balk(self):
        counts = Venster(deelnemers(VAARDAG), alles=True)._field_counts("Profiel")

        self.assertEqual(len(counts), len(VAARDAG))
        self.assertNotIn("Overig", [label for label, _ in counts])

    def test_zonder_staart_verschijnt_overig_niet(self):
        counts = Venster(deelnemers({"Techniek": 5, "Zorg": 3}))._field_counts("Profiel")

        self.assertEqual(counts, [("Techniek", 5), ("Zorg", 3)])

    def test_een_limiet_van_nul_toont_alles(self):
        counts = Venster(deelnemers(VAARDAG))._field_counts("Profiel", limit=0)

        self.assertEqual(len(counts), len(VAARDAG))

    def test_lege_waarden_heten_onbekend(self):
        counts = Venster([{"Profiel": ""}, {"Profiel": "  "}])._field_counts("Profiel")

        self.assertEqual(counts, [("Onbekend", 2)])


class SameDenominatorAsTheCrosstabTests(unittest.TestCase):
    """De grafiek telde de ruwe waarde, de kruistabel de herkende noemer.

    Daardoor kon dezelfde opleiding als twee balken naast elkaar staan en samen
    een echte categorie uit de top acht verdringen, terwijl de tabel eronder
    zei dat het er een was.
    """

    def test_schrijfwijzen_van_een_niveau_worden_een_balk(self):
        records = [{"Opleiding": waarde} for waarde in ("MBO 4", "mbo-4", "MBO niveau 4")]

        counts = Venster(records)._field_counts("Opleiding")

        self.assertEqual(counts, [("MBO 4", 3)])

    def test_het_label_is_hetzelfde_als_in_de_kruistabel(self):
        from emt_education import education_level

        counts = Venster([{"Opleiding": "VMBO Theoretisch"}])._field_counts("Opleiding")

        self.assertEqual(counts[0][0], education_level("VMBO Theoretisch"))
        self.assertEqual(counts[0][0], "VMBO TL")

    def test_profielen_groeperen_op_schrijfwijze(self):
        records = [{"Profiel": waarde} for waarde in ("Techniek", "techniek", "TECHNIEK")]

        counts = Venster(records)._field_counts("Profiel")

        self.assertEqual(counts, [("Techniek", 3)])

    def test_andere_velden_blijven_ongemoeid(self):
        """Geslacht kent geen noemer om naartoe te herleiden."""
        records = [{"Geslacht": "Man"}, {"Geslacht": "man"}]

        counts = Venster(records)._field_counts("Geslacht", limit=10)

        self.assertEqual(sorted(label for label, _ in counts), ["Man", "man"])

    def test_een_lege_opleiding_heet_onbekend(self):
        self.assertEqual(Venster([{"Opleiding": ""}])._field_counts("Opleiding"), [("Onbekend", 1)])


class ChartLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import bezoekerslijst_app

        cls.app = QApplication.instance() or QApplication([])
        cls.chart = bezoekerslijst_app.StatisticsChart()
        cls.chart.resize(900, 400)

    def setUp(self):
        """De kaart is gedeeld; elke test begint op dezelfde breedte."""
        self.chart.resize(900, 400)

    def _kolommen(self, aantal):
        self.chart.set_data([(f"Waarde {index}", index + 1) for index in range(aantal)])
        return self.chart._row_columns()

    def test_een_korte_lijst_blijft_een_kolom(self):
        self.assertEqual(self._kolommen(6), 1)

    def test_een_lange_lijst_gaat_naast_elkaar(self):
        """Anders wordt de kaart bij zevenentwintig profielen eindeloos lang."""
        self.assertEqual(self._kolommen(27), 2)

    def test_de_kaart_wordt_daardoor_half_zo_hoog(self):
        self.chart.set_data([(f"Waarde {index}", index + 1) for index in range(28)])
        twee = self.chart.minimumHeight()
        self.chart.resize(400, 400)
        self.chart.set_data([(f"Waarde {index}", index + 1) for index in range(28)])
        een = self.chart.minimumHeight()

        self.assertLess(twee, een)

    def test_een_smalle_kaart_blijft_een_kolom(self):
        self.chart.resize(400, 400)
        self.assertEqual(self._kolommen(27), 1)

    def test_tekenen_lukt_in_beide_vormen(self):
        from PySide6.QtGui import QPixmap

        for breedte, aantal in ((900, 27), (400, 6)):
            self.chart.resize(breedte, 400)
            self.chart.set_data([(f"Waarde {index}", index + 1) for index in range(aantal)])
            pixmap = QPixmap(self.chart.size())
            self.chart.render(pixmap)
            self.assertFalse(pixmap.isNull())


class TheSwitchCoversTheWholeTabTests(unittest.TestCase):
    def test_de_schakelaar_staat_bij_de_andere_keuzes(self):
        self.assertIn('self.statistics_show_all = QCheckBox("Alle waarden tonen")', APP_SOURCE)
        self.assertIn("statistics_top.addWidget(self.statistics_show_all)", APP_SOURCE)

    def test_hij_geldt_ook_voor_de_kruistabel(self):
        start = APP_SOURCE.index("def _crosstab_data")
        block = APP_SOURCE[start:start + 500]

        self.assertIn("if self._show_all_values():", block)

    def test_hij_geldt_ook_voor_de_export(self):
        """De export bouwt zijn tabellen met dezelfde bundeling, dus hij volgt vanzelf."""
        start = APP_SOURCE.index("def export_statistics(self)")
        block = APP_SOURCE[start:APP_SOURCE.index(chr(10) + "    def ", start + 1)]

        self.assertIn("self._dimension_rows(", block)
        self.assertIn("crosstab=self._crosstab_data(crosstab_records)", block)

    def test_de_tabelopbouw_kent_de_schakelaar(self):
        start = APP_SOURCE.index("def _dimension_rows")
        block = APP_SOURCE[start:APP_SOURCE.index(chr(10) + "    def ", start + 1)]

        self.assertIn("not self._show_all_values()", block)

    def test_de_keuze_wordt_onthouden(self):
        self.assertIn('self.settings.setValue("statistics_show_all"', APP_SOURCE)
        self.assertIn('self.settings.value("statistics_show_all", False, type=bool)', APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
