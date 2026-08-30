"""EventHub visual system for Server Manager (PySide6).

Deliberate, self-contained copy of ``theme/styles.py`` from EventHub
Desktop, kept in sync by hand. Vendored here so EventHub Server has no
import dependency on the EventHub Desktop repository and can be copied
to a machine that never had EventHub Desktop installed.
"""


def build_stylesheet(dark_mode: bool = False) -> str:
    """Return the shared EventHub stylesheet without changing widget behavior."""
    if dark_mode:
        background, surface, surface_alt = "#081120", "#0f1b31", "#13243f"
        hover, text, muted = "#193153", "#f6f8ff", "#9fb0cc"
        border, selected, input_background = "#253a5e", "#1c3155", "#0b1628"
    else:
        background, surface, surface_alt = "#f3f6fb", "#ffffff", "#eef3f9"
        hover, text, muted = "#e5edf8", "#172235", "#637187"
        border, selected, input_background = "#d8e0eb", "#dce9ff", "#ffffff"

    return f"""
        QMainWindow, QWidget {{ background: {background}; color: {text}; font-family: 'Plus Jakarta Sans', 'Avenir Next', 'Segoe UI', sans-serif; font-size: 10pt; }}
        QLabel {{ background: transparent; color: {text}; }}
        QFrame#masthead {{ background: #0b1730; border: 1px solid #263c62; border-radius: 14px; }}
        QLabel#appLogo {{ background: #151c26; border: 1px solid #2d3a4b; border-radius: 14px; }}
        QLabel#appTitle {{ color: #ffffff; font-size: 22pt; font-weight: 800; }}
        QLabel#appSubtitle {{ color: #9fb0cc; font-size: 9pt; }}
        QLabel#privacyLabel {{ color: #00d4ff; font-weight: 600; }}
        QPushButton {{ min-height: 28px; padding: 9px 16px; border-radius: 9px; border: 1px solid {border}; font-weight: 650; }}
        QPushButton#primaryButton {{ background: #6c2cff; color: #ffffff; border-color: #824cff; }}
        QPushButton#primaryButton:hover {{ background: #a83dff; border-color: #a83dff; }}
        QPushButton#primaryButton:pressed {{ background: #5520d6; }}
        QPushButton#secondaryButton, QPushButton#notificationButton, QPushButton#iconButton {{ background: {surface}; color: {text}; border-color: {border}; }}
        QPushButton#secondaryButton:hover, QPushButton#notificationButton:hover, QPushButton#iconButton:hover {{ background: {hover}; border-color: #386bff; }}
        QPushButton#activeNavigationButton {{ background: #263b67; color: #ffffff; border: 1px solid #386bff; }}
        QPushButton#dangerButton {{ background: #c9234f; color: #ffffff; border-color: #c9234f; }}
        QPushButton#dangerButton:hover {{ background: #a9173e; color: #ffffff; border-color: #a9173e; }}
        QPushButton#dangerButton:pressed {{ background: #851130; color: #ffffff; border-color: #851130; }}
        QPushButton:disabled {{ background: {surface_alt}; color: {muted}; border-color: {border}; }}
        QPushButton#notificationButton {{ border-radius: 18px; padding: 7px 13px; }}
        QPushButton#notificationButton[hasNotifications="true"] {{ background: #fff2d6; color: #8a5600; border-color: #e8b84c; }}
        QFrame#toolbar, QFrame#summaryCard, QFrame#compactSummaryCard, QFrame#statisticsCard, QFrame#eventBar, QGroupBox {{ background: {surface}; border: 1px solid {border}; border-radius: 9px; }}
        QFrame#actionSection {{ background: {surface}; border: 1px solid {border}; border-radius: 14px; min-height: 112px; }}
        QFrame#actionSection[tone="server"] {{ border-left: 4px solid #2d8cff; }}
        QFrame#actionSection[tone="participants"] {{ border-left: 4px solid #00b8ff; }}
        QFrame#actionSection[tone="checkin"] {{ border-left: 4px solid #7b3cff; }}
        QFrame#actionSection[tone="emergency"] {{ border-left: 4px solid #d62857; }}
        QLabel#actionSectionTitle {{ color: #c4d4ef; font-size: 9pt; font-weight: 800; letter-spacing: 0.6px; }}
        QLabel#actionStatus {{ color: {text}; font-size: 10pt; font-weight: 700; }}
        QLabel#actionMeta {{ color: {muted}; font-size: 9pt; }}
        QPushButton#tertiaryButton {{ background: transparent; color: {muted}; border: none; padding: 6px 4px; }}
        QPushButton#tertiaryButton:hover {{ color: #6c2cff; background: {hover}; }}
        QFrame#toolbar {{ border-left: 3px solid #2d8cff; }}
        QFrame#summaryCard {{ border-top: 3px solid #7b3cff; }}
        QFrame#compactSummaryCard {{ border-top: 3px solid #00d4ff; }}
        QFrame#statisticsCard {{ border-top: 3px solid #386bff; }}
        QLabel#cardHeading {{ color: {muted}; font-size: 8pt; font-weight: 700; }}
        QLabel#cardNumber, QLabel#compactCardNumber {{ color: #9f6cff; font-weight: 800; }}
        QLabel#cardNumber {{ font-size: 20pt; }}
        QLabel#compactCardNumber {{ font-size: 14pt; }}
        QLabel#cardCaption, QLabel#hintLabel, QLabel#statusLabel {{ color: {muted}; font-size: 9pt; }}
        QLabel#statisticsTitle, QLabel#sectionTitle {{ color: #6c2cff; font-weight: 700; }}
        QLabel#statisticsTitle {{ font-size: 13pt; }}
        QLabel#sectionTitle {{ font-size: 18pt; }}
        QLabel#statisticsCaption {{ color: {muted}; font-size: 9pt; }}
        QGroupBox {{ margin-top: 12px; padding-top: 8px; font-weight: 700; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #6c2cff; }}
        QScrollArea {{ background: {background}; border: none; }}
        QTabWidget::pane {{ background: {surface}; border: 1px solid {border}; border-radius: 8px; }}
        QTabBar::tab {{ background: {surface_alt}; color: {muted}; border: 1px solid {border}; border-radius: 7px; padding: 10px 16px; margin-right: 3px; font-weight: 600; }}
        QTabBar::tab:selected {{ background: {surface}; color: #6c2cff; border-bottom-color: #6c2cff; }}
        QTabBar::tab:hover {{ background: {hover}; color: #386bff; }}
        QComboBox QAbstractItemView {{ background: {surface}; color: {text}; border: 1px solid {border}; selection-background-color: {selected}; }}
        QTableWidget {{ background: {surface}; alternate-background-color: {surface_alt}; color: {text}; border: 1px solid {border}; gridline-color: {border}; selection-background-color: {selected}; selection-color: {text}; }}
        QTableWidget::item {{ padding: 7px 9px; border-bottom: 1px solid {border}; }}
        QTableWidget::item:selected {{ border-left: 2px solid #00d4ff; }}
        QHeaderView::section {{ background: {surface_alt}; color: {text}; border: none; border-right: 1px solid {border}; padding: 9px; font-weight: 700; }}
        QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {{ background: {input_background}; color: {text}; border: 1px solid {border}; border-radius: 7px; padding: 8px 10px; }}
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border: 2px solid #386bff; }}
        QCheckBox {{ spacing: 8px; padding: 4px; }}
        QMenu {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 6px; }}
        QMenu::item {{ padding: 8px 24px 8px 12px; border-radius: 5px; }}
        QMenu::item:selected {{ background: {selected}; color: {text}; }}
        QToolTip {{ background: #091426; color: #ffffff; border: 1px solid #386bff; padding: 5px; }}
        QLabel#footerLabel {{ color: #7083a4; font-size: 8pt; }}
        QStatusBar {{ background: #0d1117; color: #a8b5c7; padding: 4px 10px; }}
        QDialog {{ background: {background}; }}
        QMessageBox {{ background: {surface}; }}
        QProgressBar {{ background: {surface_alt}; color: {text}; border: 1px solid {border}; border-radius: 6px; text-align: center; height: 12px; }}
        QProgressBar::chunk {{ background: #00d4ff; border-radius: 5px; }}
    """
