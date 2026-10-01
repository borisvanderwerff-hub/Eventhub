"""Het detailpaneel van After sales blijft leesbaar op kleine of geschaalde schermen."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

import bezoekerslijst_app as app_module


class DetailPanelLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        window = app_module.BezoekerslijstWindow()
        window.settings.remove("after_sales_workspace_splitter")
        source = app_module.empty_event("Open Dag", window.task_templates, "Meeloopdag")
        source["date"] = "24-08-2026"
        source["name"] = app_module.event_name_with_date("Open Dag", "24-08-2026")
        event = app_module.prepare_event(source, window.task_templates)
        window.events.append(event)
        record = app_module.empty_record()
        record.update({"Voornaam": "Fenna", "Tussenvoegsel": "van", "Achternaam": "Breda Vriesman",
                       "Telefoonnummer": "06 42013424", "Evenement": event["name"]})
        window.records.append(record)
        window.active_event_id = event["id"]
        window.selected_events = {event["name"]}
        window.after_sales_event_combo.set_events(window.events, event["id"])
        window._render_all()
        window.show_nazorg_page()
        window.resize(1000, 480)  # bewust te laag voor het hele paneel
        window.show()
        cls.app.processEvents()
        window.callback_table.selectRow(0)
        cls.app.processEvents()
        cls.window = window

    @classmethod
    def tearDownClass(cls):
        cls.window.close()

    def test_panel_scrolls_instead_of_squeezing_fields(self):
        window = self.window
        self.assertTrue(window.callback_detail_card.isVisible())
        scroll = window.callback_detail_scroll
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        for widget in (window.callback_detail_status, window.callback_detail_followup,
                       window.callback_detail_notes):
            with self.subTest(widget=widget.objectName() or type(widget).__name__):
                self.assertGreaterEqual(widget.height(), widget.minimumSizeHint().height())

    def test_date_button_stays_inside_the_card(self):
        window = self.window
        holder = window.callback_detail_followup.parentWidget()
        button = next(child for child in holder.findChildren(QPushButton))
        card = window.callback_detail_card
        right_edge = button.mapTo(card, QPoint(button.width(), 0)).x()
        self.assertLessEqual(right_edge, card.width())
        self.assertGreaterEqual(window.callback_detail_followup.width(), 120)

    def test_card_is_never_narrower_than_its_content(self):
        window = self.window
        body = window.callback_detail_scroll.widget()
        self.assertGreaterEqual(window.callback_detail_card.minimumSizeHint().width(),
                                body.minimumSizeHint().width())

    def test_no_fixed_small_input_heights(self):
        source = desktop_source(ROOT)
        block = source[source.index("self.callback_detail_card = QFrame()"):]
        block = block[:block.index("self.callback_workspace_splitter.addWidget(self.callback_detail_card)")]
        self.assertNotIn("setMaximumHeight(32)", block)


if __name__ == "__main__":
    unittest.main()
