from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source


class Version2163HomeTodayTests(unittest.TestCase):
    """Home 'Vandaag'-blok en dag-afhankelijke verversing."""

    def setUp(self):
        self.source = desktop_source(ROOT)

    def _render_block(self):
        start = self.source.index("def _render_management")
        end = self.source.index("def ", start + 1)
        return self.source[start:end]

    def test_today_actions_are_hidden_when_no_event_today(self):
        block = self._render_block()
        # Geen doelloze grijze knoppen: bij een lege dag worden ze verborgen.
        self.assertIn("self.home_today_button.setVisible(False)", block)
        self.assertIn("self.home_today_live_button.setVisible(False)", block)
        # En weer getoond zodra er wel een evenement vandaag is.
        self.assertIn("self.home_today_button.setVisible(True)", block)
        self.assertIn("self.home_today_live_button.setVisible(True)", block)

    def test_empty_today_block_points_to_next_upcoming_event(self):
        block = self._render_block()
        self.assertIn("next_events = self._upcoming_events()", block)
        self.assertIn('self.home_today_button.setText("Volgende evenement openen →")', block)
        self.assertIn('self.home_today_button.setText("Evenement openen →")', block)

    def test_continue_button_is_hidden_without_work_context(self):
        block = self._render_block()
        self.assertIn("self.home_continue_button.setVisible(False)", block)
        self.assertIn("self.home_continue_button.setVisible(True)", block)

    def test_daily_refresh_timer_rerenders_when_the_date_rolls_over(self):
        self.assertIn("self._schedule_daily_refresh()", self.source)
        self.assertIn("def _schedule_daily_refresh(self):", self.source)
        self.assertIn("def _daily_refresh_tick(self):", self.source)

        start = self.source.index("def _daily_refresh_tick(self):")
        end = self.source.index("def ", start + 1)
        tick = self.source[start:end]
        self.assertIn("current_date = date.today()", tick)
        self.assertIn('getattr(self, "_daily_refresh_date"', tick)
        self.assertIn("self._render_management()", tick)


if __name__ == "__main__":
    unittest.main()
