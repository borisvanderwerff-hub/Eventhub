from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PySide6.QtWidgets import QApplication

from server.logging_setup import configure_logging
from server.manager.manager_window import ManagerWindow
from server.manager.new_session_dialog import NewSessionDialog


def main():
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("EventHub Server")

    dialog = NewSessionDialog()
    if dialog.exec() != NewSessionDialog.DialogCode.Accepted or dialog.result_session is None:
        return 0

    window = ManagerWindow(dialog.result_session)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
