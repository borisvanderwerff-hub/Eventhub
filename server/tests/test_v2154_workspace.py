from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2154WorkspaceTests(unittest.TestCase):
    def test_server_actions_are_compact_and_fit_three_rows(self):
        source = (ROOT / "server/manager/manager_window.py").read_text(encoding="utf-8")
        self.assertIn('self.start_stop_button = _compact(QPushButton("Server starten"))', source)
        self.assertIn('self.stop_checkin_button = _compact(QPushButton("Inchecken stoppen"))', source)
        self.assertIn("action_grid.addWidget(logs_button, 2, 1)", source)
        self.assertNotIn("utility_grid.setColumnStretch", source)
        self.assertIn("layout.addSpacing(36)", source)

    def test_event_workspace_defaults_to_maximum_without_corner_button(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("self.event_focus_mode = True", source)
        self.assertNotIn("self.event_focus_button =", source)
        self.assertNotIn("self.event_action_bar =", source)
        self.assertNotIn('("Deelnemerslijst exporteren", self.export_participant_list', source)

    def test_summary_cards_wrap_in_three_plus_two_grid(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("cards = QGridLayout(self.event_summary_bar)", source)
        self.assertIn("cards.addWidget(card, 0, index)", source)
        self.assertIn("caption.setWordWrap(True)", source)

    def test_splash_uses_neon_wave_asset(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("if NEON_WAVES_PATH.exists():", source)
        self.assertIn("painter.drawPixmap(canvas.rect(), waves)", source)
        self.assertTrue((ROOT / "assets/backgrounds/neon_waves.png").is_file())

    def test_dashboard_uses_one_live_session_status_window(self):
        template = (ROOT / "server/web/templates/dashboard.html").read_text(encoding="utf-8")
        script = (ROOT / "server/web/static/js/dashboard.js").read_text(encoding="utf-8")
        css = (ROOT / "server/web/static/css/style.css").read_text(encoding="utf-8")
        self.assertIn('id="sessionStatusWindow"', template)
        self.assertIn('id="sessionStatusText"', template)
        self.assertNotIn('id="sessionActivityList"', template)
        self.assertIn('textElement.textContent = "Inchecken actief"', script)
        self.assertIn('textElement.textContent = "Inchecken gepauzeerd"', script)
        self.assertIn('textElement.textContent = "Inchecken gestopt"', script)
        self.assertIn(".session-status-window", css)


if __name__ == "__main__":
    unittest.main()
