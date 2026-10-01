"""Per evenement kan er maar een livesessie zijn.

Voor de vaardag van 2 september stonden er zeven op de server, met nul tot
vierenvijftig inchecks. Elke sessie vertelde een ander verhaal over dezelfde
dag, en welke daarvan werd gesynchroniseerd hing af van de volgorde waarin ze
in de sessielijst stonden. Een van die zeven had het inchecken gestopt zonder
dat er ooit was gescand, en die zette in een keer 57 aanwezigen en 19
afmeldingen om in no-shows.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

APP_SOURCE = desktop_source(ROOT)


def start_block():
    """Het blok waarin een nieuwe livesessie wordt aangemaakt."""
    einde = APP_SOURCE.index("session_result = live_session_service.create_session(")
    start = APP_SOURCE.rindex("\n    def ", 0, einde)
    return APP_SOURCE[start:einde]


class OnlyOneSessionTests(unittest.TestCase):
    def test_er_wordt_eerst_gekeken_of_er_al_een_is(self):
        self.assertIn("bestaande = self._previous_live_session_for_event(active_event)", start_block())

    def test_bestaat_er_al_een_dan_wordt_die_geopend(self):
        block = start_block()
        controle = block.index("bestaande = self._previous_live_session_for_event")

        self.assertIn("self.reopen_previous_live_session()", block[controle:])
        self.assertIn("return", block[controle:])

    def test_de_controle_gaat_vooraf_aan_het_instelvenster(self):
        """Anders vul je eerst een venster in en blijkt het daarna voor niets."""
        block = start_block()

        self.assertLess(
            block.index("bestaande = self._previous_live_session_for_event"),
            block.index("LiveSessionSetupDialog("),
        )

    def test_de_gebruiker_hoort_waarom(self):
        block = start_block()

        self.assertIn("Er is al een livesessie", block)
        self.assertIn("elkaar tegenspreken", block)

    def test_een_sessie_wordt_gekoppeld_aan_het_evenement(self):
        """Zonder source_event_id is achteraf niet te zien welke sessie erbij hoort."""
        einde = APP_SOURCE.index("session_result = live_session_service.create_session(")
        self.assertIn("source_event_id", APP_SOURCE[einde:einde + 400])


class TheLookupFindsTheSessionTests(unittest.TestCase):
    def _lookup(self):
        start = APP_SOURCE.index("def _previous_live_session_for_event")
        return APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

    def test_er_wordt_op_de_koppeling_gezocht(self):
        self.assertIn("source_event_id", self._lookup())

    def test_oudere_sessies_worden_op_naam_en_datum_herkend(self):
        """Sessies van voor de expliciete koppeling hebben geen source_event_id."""
        lookup = self._lookup()

        self.assertIn("event_name", lookup)
        self.assertIn("event_date", lookup)


if __name__ == "__main__":
    unittest.main()
