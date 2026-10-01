"""Vier aanwezigheidsstanden in plaats van een ja/nee.

Rudder levert Yes, No, Canceled en Unknown. EventHub kende alleen aanwezig of
niet, waarin 'niet' zowel 'was er niet' als 'we weten het niet' betekende. Van
alles wat Rudder aanlevert is het overgrote deel Unknown of Canceled: die
landden allemaal als no-show. Een evenement dat nog moest plaatsvinden stond
daardoor op nul procent opkomst, en wie zich netjes had afgemeld telde als
gemiste opkomst.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import (
    AANWEZIG,
    AFGEMELD,
    AFWEZIG,
    ONBEKEND,
    apply_attendance_conflicts,
    attendance_counts,
    clear_absence_for_events,
    attendance_map,
    attendance_status,
    attendance_value,
    has_status_in_scope,
    import_registration_files,
    infer_attendance_from_text,
    is_cancelled,
    is_no_show,
    is_present,
    set_attendance,
    set_present,
    turnout_percentage,
)

APP_SOURCE = desktop_source(ROOT)
MANAGER_SOURCE = (ROOT / "server" / "manager" / "manager_window.py").read_text(encoding="utf-8")

EVENEMENT = "Meeloopdag Marine (Varend) (02-09-'26)"


def bezoeker(status=None, evenement=EVENEMENT):
    record = {"Voornaam": "Jan", "Achternaam": "Jansen", "Evenement": evenement, "Aanwezig": {}}
    if status:
        set_attendance(record, evenement, status)
    return record


def sync_block():
    """De hele functie, ongeacht hoe lang de toelichting erboven wordt."""
    start = APP_SOURCE.index("def apply_live_attendance")
    einde = APP_SOURCE.index(chr(10) + "class ", start)
    return APP_SOURCE[start:einde]


class RudderValuesTests(unittest.TestCase):
    def test_de_vier_standen_worden_herkend(self):
        self.assertEqual(infer_attendance_from_text("Yes"), AANWEZIG)
        self.assertEqual(infer_attendance_from_text("No"), AFWEZIG)
        self.assertEqual(infer_attendance_from_text("Canceled"), AFGEMELD)
        self.assertEqual(infer_attendance_from_text("Unknown"), ONBEKEND)

    def test_de_schrijfwijze_maakt_niet_uit(self):
        for waarde in ("CANCELLED", "cancelled", "Afgemeld", "geannuleerd"):
            self.assertEqual(infer_attendance_from_text(waarde), AFGEMELD, waarde)

    def test_nederlands_blijft_werken(self):
        self.assertEqual(infer_attendance_from_text("Ja"), AANWEZIG)
        self.assertEqual(infer_attendance_from_text("Nee"), AFWEZIG)

    def test_een_lege_waarde_zegt_niets(self):
        self.assertIsNone(infer_attendance_from_text(""))
        self.assertIsNone(infer_attendance_from_text("iets onbegrijpelijks"))


class MigrationTests(unittest.TestCase):
    def test_het_oude_ja_nee_migreert(self):
        self.assertEqual(attendance_value(True), AANWEZIG)
        self.assertEqual(attendance_value(False), AFWEZIG)

    def test_een_onbekende_waarde_wordt_onbekend(self):
        self.assertEqual(attendance_value("iets anders"), ONBEKEND)
        self.assertEqual(attendance_value(None), ONBEKEND)

    def test_de_nieuwe_standen_blijven_staan(self):
        for status in (AANWEZIG, AFWEZIG, AFGEMELD, ONBEKEND):
            self.assertEqual(attendance_value(status), status)

    def test_een_dossier_van_versie_11_migreert_per_evenement(self):
        record = {"Evenement": EVENEMENT, "Aanwezig": {EVENEMENT: True}}
        self.assertEqual(attendance_map(record), {EVENEMENT: AANWEZIG})


class MeaningTests(unittest.TestCase):
    def test_alleen_aanwezig_telt_als_aanwezig(self):
        self.assertTrue(is_present(bezoeker(AANWEZIG), EVENEMENT))
        for status in (AFWEZIG, AFGEMELD, ONBEKEND):
            self.assertFalse(is_present(bezoeker(status), EVENEMENT), status)

    def test_alleen_niet_gekomen_telt_als_no_show(self):
        """De kern: afgemeld en onbekend zijn geen no-show."""
        self.assertTrue(is_no_show(bezoeker(AFWEZIG), EVENEMENT))
        self.assertFalse(is_no_show(bezoeker(AFGEMELD), EVENEMENT))
        self.assertFalse(is_no_show(bezoeker(ONBEKEND), EVENEMENT))

    def test_afgemeld_is_apart_te_vinden(self):
        self.assertTrue(is_cancelled(bezoeker(AFGEMELD), EVENEMENT))

    def test_zonder_registratie_is_de_stand_onbekend(self):
        self.assertEqual(attendance_status(bezoeker(), EVENEMENT), ONBEKEND)

    def test_set_present_blijft_werken(self):
        record = bezoeker()
        set_present(record, EVENEMENT, True)
        self.assertEqual(attendance_status(record, EVENEMENT), AANWEZIG)
        set_present(record, EVENEMENT, False)
        self.assertEqual(attendance_status(record, EVENEMENT), AFWEZIG)


class TurnoutTests(unittest.TestCase):
    def test_alle_aanmeldingen_tellen_mee_in_de_noemer(self):
        counts = {AANWEZIG: 27, AFWEZIG: 3, AFGEMELD: 10, ONBEKEND: 62}

        self.assertEqual(turnout_percentage(counts), 26.5)

    def test_een_evenement_dat_nog_moet_plaatsvinden_heeft_geen_no_shows(self):
        """92 keer Unknown en 10 keer Canceled: nul no-shows, geen opkomstcijfer."""
        records = [bezoeker(ONBEKEND) for _ in range(92)] + [bezoeker(AFGEMELD) for _ in range(10)]

        counts = attendance_counts(records, EVENEMENT)

        self.assertEqual(counts[AFWEZIG], 0)
        self.assertEqual(counts[AFGEMELD], 10)
        self.assertEqual(counts[ONBEKEND], 92)
        self.assertEqual(turnout_percentage(counts), 0.0)

    def test_de_telling_dekt_iedereen(self):
        records = [bezoeker(AANWEZIG), bezoeker(AFWEZIG), bezoeker(AFGEMELD), bezoeker()]

        self.assertEqual(sum(attendance_counts(records, EVENEMENT).values()), 4)


class ScopeTests(unittest.TestCase):
    def test_de_stand_wordt_binnen_de_selectie_gezocht(self):
        record = bezoeker(AFGEMELD)

        self.assertTrue(has_status_in_scope(record, {EVENEMENT}, AFGEMELD))
        self.assertFalse(has_status_in_scope(record, {EVENEMENT}, AFWEZIG))

    def test_zonder_selectie_gelden_alle_evenementen_van_de_bezoeker(self):
        record = bezoeker(AANWEZIG)

        self.assertTrue(has_status_in_scope(record, set(), AANWEZIG))


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def _lijst(self, rijen):
        path = self.folder / "rudder.xlsx"
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Voornaam", "Achternaam", "Email", "Evenement", "Aanwezigheid"])
        for rij in rijen:
            sheet.append(rij)
        workbook.save(path)
        return [str(path)]

    def test_canceled_en_unknown_overleven_de_import(self):
        paden = self._lijst([
            ["Jan", "Jansen", "jan@x.nl", "Meeloopdag", "Canceled"],
            ["Sanne", "Bakker", "sanne@x.nl", "Meeloopdag", "Unknown"],
            ["Peter", "Smit", "peter@x.nl", "Meeloopdag", "Yes"],
        ])

        resultaat = import_registration_files(paden, [], target_event=EVENEMENT)

        standen = [attendance_status(record, EVENEMENT) for record in resultaat["records"]]
        self.assertEqual(standen, [AFGEMELD, ONBEKEND, AANWEZIG])

    def test_onbekend_telt_niet_als_herkende_aanwezigheid(self):
        """De melding na afloop hoort niet te beweren dat er iets is overgenomen."""
        paden = self._lijst([["Sanne", "Bakker", "sanne@x.nl", "Meeloopdag", "Unknown"]])

        resultaat = import_registration_files(paden, [], target_event=EVENEMENT)

        self.assertEqual(resultaat["reports"][0]["presence_detected"], 0)

    def test_het_bestand_vult_aan_waar_eventhub_niets_weet(self):
        bekend = {"Voornaam": "Jan", "Achternaam": "Jansen", "Email": "jan@x.nl",
                  "Evenement": EVENEMENT, "Aanwezig": {}}
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", "Meeloopdag", "Yes"]])

        resultaat = import_registration_files(paden, [bekend], target_event=EVENEMENT)

        self.assertEqual(attendance_status(bekend, EVENEMENT), AANWEZIG)
        self.assertEqual(resultaat["attendance_conflicts"], [])

    def test_een_botsing_wordt_gemeld_en_niet_stilzwijgend_doorgevoerd(self):
        bekend = {"Voornaam": "Jan", "Achternaam": "Jansen", "Email": "jan@x.nl",
                  "Evenement": EVENEMENT, "Aanwezig": {}}
        set_attendance(bekend, EVENEMENT, AANWEZIG)
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", "Meeloopdag", "No"]])

        resultaat = import_registration_files(paden, [bekend], target_event=EVENEMENT)

        self.assertEqual(len(resultaat["attendance_conflicts"]), 1)
        self.assertEqual(attendance_status(bekend, EVENEMENT), AANWEZIG)

    def test_na_de_vraag_kan_het_bestand_alsnog_voorgaan(self):
        bekend = {"Voornaam": "Jan", "Achternaam": "Jansen", "Email": "jan@x.nl",
                  "Evenement": EVENEMENT, "Aanwezig": {}}
        set_attendance(bekend, EVENEMENT, AANWEZIG)
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", "Meeloopdag", "No"]])
        resultaat = import_registration_files(paden, [bekend], target_event=EVENEMENT)

        gewijzigd = apply_attendance_conflicts(resultaat["attendance_conflicts"])

        self.assertEqual(gewijzigd, 1)
        self.assertEqual(attendance_status(bekend, EVENEMENT), AFWEZIG)

    def test_meteen_overschrijven_kan_ook(self):
        bekend = {"Voornaam": "Jan", "Achternaam": "Jansen", "Email": "jan@x.nl",
                  "Evenement": EVENEMENT, "Aanwezig": {}}
        set_attendance(bekend, EVENEMENT, AANWEZIG)
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", "Meeloopdag", "No"]])

        resultaat = import_registration_files(
            paden, [bekend], target_event=EVENEMENT, overwrite_attendance=True
        )

        self.assertEqual(resultaat["attendance_conflicts"], [])
        self.assertEqual(attendance_status(bekend, EVENEMENT), AFWEZIG)

    def test_onbekend_uit_het_bestand_overschrijft_nooit(self):
        """Anders wist een lijst van voor het evenement de registratie erna."""
        bekend = {"Voornaam": "Jan", "Achternaam": "Jansen", "Email": "jan@x.nl",
                  "Evenement": EVENEMENT, "Aanwezig": {}}
        set_attendance(bekend, EVENEMENT, AANWEZIG)
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", "Meeloopdag", "Unknown"]])

        resultaat = import_registration_files(paden, [bekend], target_event=EVENEMENT)

        self.assertEqual(attendance_status(bekend, EVENEMENT), AANWEZIG)
        self.assertEqual(resultaat["attendance_conflicts"], [])


class FutureEventsHaveNoNoShowsTests(unittest.TestCase):
    """Een evenement dat nog moet plaatsvinden kan niemand hebben gemist.

    Dossiers van voor versie 12 hebben daar toch no-shows staan: alles wat
    geen aanwezigheid was werd een nee.
    """

    def test_de_no_shows_worden_onbekend(self):
        records = [bezoeker(AFWEZIG) for _ in range(3)]

        self.assertEqual(clear_absence_for_events(records, [EVENEMENT]), 3)
        for record in records:
            self.assertEqual(attendance_status(record, EVENEMENT), ONBEKEND)

    def test_een_geregistreerde_aanwezigheid_blijft_staan(self):
        """Aanwezigheid is een uitspraak; die gooien we nooit weg."""
        record = bezoeker(AANWEZIG)

        clear_absence_for_events([record], [EVENEMENT])

        self.assertEqual(attendance_status(record, EVENEMENT), AANWEZIG)

    def test_afgemeld_blijft_afgemeld(self):
        record = bezoeker(AFGEMELD)

        clear_absence_for_events([record], [EVENEMENT])

        self.assertEqual(attendance_status(record, EVENEMENT), AFGEMELD)

    def test_andere_evenementen_blijven_ongemoeid(self):
        record = bezoeker(AFWEZIG, "Meeloopdag Defensie (26-08-'26)")

        self.assertEqual(clear_absence_for_events([record], [EVENEMENT]), 0)
        self.assertEqual(attendance_status(record, "Meeloopdag Defensie (26-08-'26)"), AFWEZIG)

    def test_zonder_evenementen_gebeurt_er_niets(self):
        record = bezoeker(AFWEZIG)

        self.assertEqual(clear_absence_for_events([record], []), 0)


class TheApplicationUsesTheStatusesTests(unittest.TestCase):
    def test_het_bestandsformaat_is_opgehoogd(self):
        self.assertIn('"version": 12,', APP_SOURCE)

    def test_er_kan_op_afgemeld_en_onbekend_gefilterd_worden(self):
        self.assertIn('("Alleen afgemeld", AFGEMELD)', APP_SOURCE)
        self.assertIn('("Alleen onbekend", ONBEKEND)', APP_SOURCE)

    def test_de_momentopname_houdt_ze_apart(self):
        start = APP_SOURCE.index("def _event_statistics_snapshot")
        block = APP_SOURCE[start:start + 2500]

        self.assertIn('"schema": 5,', block)
        self.assertIn('"afgemeld": counts[AFGEMELD],', block)
        self.assertIn('"onbekend": counts[ONBEKEND],', block)
        self.assertIn('"opkomst_percentage": turnout_percentage(counts),', block)

    def test_de_aanwezigheid_is_per_deelnemer_te_kiezen(self):
        self.assertIn("def _set_presence_status", APP_SOURCE)
        self.assertIn("Aanwezigheid: {ATTENDANCE_LABELS[status]}", APP_SOURCE)

    def test_presentieregistratie_heeft_een_snel_aanwezig_vinkje(self):
        self.assertIn("self.access_table.itemChanged.connect(self._presence_changed)", APP_SOURCE)
        self.assertIn("def _presence_changed", APP_SOURCE)
        self.assertIn("Qt.ItemFlag.ItemIsUserCheckable", APP_SOURCE)
        self.assertIn("if item.checkState() == Qt.CheckState.Checked", APP_SOURCE)
        self.assertIn("else ONBEKEND", APP_SOURCE)

    def test_presentieregistratie_is_muisloos_te_bedienen_en_meldt_wanneer_deze_klaar_is(self):
        self.assertIn("self.access_table.installEventFilter(self)", APP_SOURCE)
        self.assertIn("event.key() == Qt.Key.Key_Space", APP_SOURCE)
        self.assertIn("self.access_table.currentRow()", APP_SOURCE)
        self.assertIn('self.presence_save_button = QPushButton("Registratie afronden")', APP_SOURCE)
        self.assertIn("self.presence_save_button.setVisible(False)", APP_SOURCE)
        self.assertIn("self._set_presence_save_pending(True)", APP_SOURCE)
        self.assertIn("def _finish_presence_registration", APP_SOURCE)
        self.assertIn("Aanwezigheidsregistratie afgerond.", APP_SOURCE)

    def test_opslaan_rondt_alleen_onbekende_deelnemers_af_als_afwezig(self):
        start = APP_SOURCE.index("def _finish_presence_registration")
        block = APP_SOURCE[start:start + 1800]
        self.assertNotIn("_sync_latest_live_attendance_for_event", block)
        self.assertIn("attendance_status(record, event_name) == ONBEKEND", block)
        self.assertIn("set_attendance(record, event_name, AFWEZIG)", block)

    def test_een_actieve_livesessie_vergrendelt_handmatige_presentie(self):
        self.assertIn("def _presence_registration_locked", APP_SOURCE)
        self.assertIn('getattr(window, "server_thread", None) is not None', APP_SOURCE)
        self.assertIn("self.access_table.setEnabled(has_event and not locked)", APP_SOURCE)
        self.assertIn("Live registratie is actief voor dit evenement", APP_SOURCE)
        self.assertIn("server_state_changed = Signal(bool)", MANAGER_SOURCE)
        self.assertIn("self.server_state_changed.emit(True)", MANAGER_SOURCE)
        self.assertIn("self.server_state_changed.emit(False)", MANAGER_SOURCE)

    def test_een_presentievinkje_ververst_niet_de_hele_applicatie(self):
        start = APP_SOURCE.index("def _presence_changed")
        block = APP_SOURCE[start:APP_SOURCE.index("def _set_presence_save_pending", start)]
        self.assertIn("self._refresh_presence_status_item(item, status)", block)
        self.assertNotIn("self._render_all()", block)
        show_start = APP_SOURCE.index("def show_event_control_page")
        show_block = APP_SOURCE[show_start:APP_SOURCE.index("def _after_sales_event_changed", show_start)]
        self.assertIn("self._render_presence_table()", show_block)
        self.assertNotIn("self._render_all()", show_block)

    def test_event_control_heeft_een_eigen_beperkte_verversingsroute(self):
        start = APP_SOURCE.index("def _render_event_control_scope")
        block = APP_SOURCE[start:APP_SOURCE.index("def _render_all", start)]
        self.assertIn("self._render_presence_table()", block)
        self.assertIn("self._update_statistics()", block)
        self.assertNotIn("self._render_attachments()", block)
        self.assertNotIn("self._render_management()", block)
        change_start = APP_SOURCE.index("def _event_control_event_changed")
        change_block = APP_SOURCE[change_start:APP_SOURCE.index("def _previous_live_session_for_event", change_start)]
        self.assertIn("self._render_event_control_scope()", change_block)
        self.assertNotIn("self._render_all()", change_block)
        live_start = APP_SOURCE.index("def _render_live_attendance_scope")
        live_block = APP_SOURCE[live_start:APP_SOURCE.index("def _render_all", live_start)]
        self.assertIn("self._render_presence_table()", live_block)
        self.assertNotIn("self._update_statistics()", live_block)

    def test_zichtbare_presentielijst_en_opslaan_gebruiken_hetzelfde_evenement(self):
        start = APP_SOURCE.index("def show_event_control_page")
        block = APP_SOURCE[start:APP_SOURCE.index("def _after_sales_event_changed", start)]
        self.assertIn("event = self._combo_event(self.event_control_event_combo)", block)
        self.assertIn('self.active_event_id = event.get("id", "")', block)
        self.assertIn('self.selected_events = {event.get("name", "")}', block)
        finish_start = APP_SOURCE.index("def _finish_presence_registration")
        finish_block = APP_SOURCE[finish_start:APP_SOURCE.index("def _callback_status_changed", finish_start)]
        self.assertIn("event = event or self._presence_registration_event()", finish_block)

    def test_event_control_bouwt_een_ongewijzigde_presentielijst_niet_opnieuw(self):
        start = APP_SOURCE.index("def _render_presence_table")
        block = APP_SOURCE[start:APP_SOURCE.index("def _render_event_control_scope", start)]
        self.assertIn("signature = self._presence_table_signature(rows, presence_fields)", block)
        self.assertIn("if signature == self._presence_render_signature", block)
        self.assertIn("return", block)
        self.assertIn("self._presence_render_signature = signature", block)
        self.assertIn("def _presence_table_signature", block)

    def test_bij_het_importeren_wordt_om_een_keuze_gevraagd(self):
        self.assertIn("def _ask_about_attendance_conflicts", APP_SOURCE)
        self.assertIn("_ask_about_attendance_conflicts(result.get(\"attendance_conflicts\")", APP_SOURCE)

    def test_de_migratie_draait_alleen_op_oudere_dossiers(self):
        start = APP_SOURCE.index("def _migrate_future_absence")
        block = APP_SOURCE[start:start + 1500]

        self.assertIn("if version >= 12:", block)
        self.assertIn("event_date > today", block)

    def test_een_teruggedraaide_incheck_maakt_de_stand_onbekend(self):
        """Niet 'afwezig': dat een scan is teruggedraaid zegt niet dat iemand wegbleef."""
        self.assertIn("status = ONBEKEND", sync_block())

    def test_de_stopactie_van_de_server_telt_wel_als_niet_gekomen(self):
        """Serverbeheer zet 'absent' bij Inchecken stoppen; dat is een uitspraak."""
        block = sync_block()

        self.assertIn('afgesloten = server_status == "absent"', block)
        self.assertIn("status = AFWEZIG", block)

    def test_de_stopactie_overschrijft_niets_wat_al_bekend_is(self):
        """Een balie waar niet is gescand zet iedereen op absent; dat mag niet wissen."""
        self.assertIn(
            "if afgesloten and attendance_status(record, target) != ONBEKEND:",
            sync_block(),
        )


if __name__ == "__main__":
    unittest.main()
