"""Central EventHub 2 visual system for the PySide6 application."""


def build_stylesheet(dark_mode: bool = False) -> str:
    """Return the shared EventHub stylesheet without changing widget behavior."""
    if dark_mode:
        background, surface, surface_alt = "#090d15", "#111827", "#151e2e"
        hover, text, muted = "#1b2940", "#f5f7fb", "#93a4ba"
        border, selected, input_background = "#26334a", "#243c69", "#0d1420"
        danger_bg, danger_hover = "#24151b", "#3a1823"
    else:
        background, surface, surface_alt = "#f3f6fb", "#ffffff", "#eef3f9"
        hover, text, muted = "#e7eef9", "#172235", "#637187"
        border, selected, input_background = "#d8e0eb", "#dce9ff", "#ffffff"
        danger_bg, danger_hover = "#fff7f8", "#ffedf0"

    return f"""
        QMainWindow, QWidget {{ background: {background}; color: {text}; font-family: 'Plus Jakarta Sans', 'Avenir Next', 'Segoe UI', sans-serif; font-size: 10pt; }}
        QLabel {{ background: transparent; color: {text}; }}
        QWidget#mainShell, QWidget#bodyCanvas, QWidget#bodyContent {{ background: {background}; }}
        QWidget#neonEdgeOverlay {{ background: transparent; border: none; }}

        QFrame#sidebar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #080d17, stop:1 #0c1220); border: none; border-right: 1px solid #253047; }}
        QWidget#sidebarBrand, QWidget#sidebarBrandText {{ background: transparent; }}
        QLabel#sidebarLogo {{ background: #101827; border: 1px solid #2b3952; border-radius: 14px; }}
        QLabel#sidebarBrandTitle {{ background: transparent; color: #f6f8ff; border: none; font-size: 13pt; font-weight: 800; letter-spacing: 1px; }}
        QLabel#sidebarBrandSubtitle {{ background: transparent; color: #7186a6; border: none; font-size: 8pt; }}
        QLabel#sidebarSectionLabel {{ color: #586b89; font-size: 7.2pt; font-weight: 800; letter-spacing: 1px; padding: 7px 8px 2px 8px; }}
        QPushButton#sidebarButton, QPushButton#sidebarButtonActive {{ text-align: left; padding: 5px 10px; border-radius: 9px; border: 1px solid transparent; color: #9aabc1; background: transparent; font-size: 9.4pt; }}
        QPushButton#sidebarButton:hover {{ color: #ffffff; background: #131e31; border-color: #263957; }}
        QPushButton#sidebarButtonActive {{ color: #ffffff; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #25205a, stop:1 #17234f); border-color: #5b55ff; }}
        QPushButton#sidebarButtonActive:hover {{ background: #2b326d; }}
        QPushButton#sidebarButton[collapsed="true"], QPushButton#sidebarButtonActive[collapsed="true"] {{ text-align: center; padding: 6px; }}
        QPushButton#sidebarButton::menu-indicator, QPushButton#sidebarButtonActive::menu-indicator {{ image: none; width: 0px; }}
        QPushButton#sidebarCollapseButton {{ min-height: 0px; padding: 0; color: #7d90aa; background: #101827; border: 1px solid #253047; text-align: center; border-radius: 9px; font-size: 14pt; }}
        QPushButton#sidebarCollapseButton:hover {{ color: #ffffff; border-color: #6c5cff; }}

        QFrame#masthead {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0e1624, stop:0.58 #111827, stop:1 #15132d); border: none; border-bottom: 1px solid #26334a; }}
        QLabel#appTitle {{ color: #ffffff; font-size: 17pt; font-weight: 800; }}
        QLabel#appSubtitle {{ color: #8799b2; font-size: 9pt; }}
        QLabel#workspaceStatus {{ color: #79e9b4; background: #10251f; border: 1px solid #1f5c49; border-radius: 13px; padding: 5px 10px; font-size: 8.5pt; font-weight: 700; }}
        QLabel#privacyLabel {{ color: #6f819b; font-size: 8.5pt; }}
        QLabel#poweredByLabel {{ color: {muted}; font-size: 8pt; font-style: italic; padding: 2px 4px; }}

        QFrame#dashboardHero {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #131b2d, stop:0.62 #171c38, stop:1 #221847); border: 1px solid #343b62; border-radius: 16px; }}
        QLabel#heroTitle {{ color: #ffffff; font-size: 17pt; font-weight: 800; }}
        QLabel#heroSubtitle {{ color: #a8b6cb; font-size: 8.5pt; }}
        QLabel#eyebrowLabel {{ color: #687d9d; font-size: 8pt; font-weight: 800; letter-spacing: 1.4px; padding: 2px 2px 0 2px; }}

        QPushButton {{ min-height: 20px; padding: 8px 14px; border-radius: 8px; border: 1px solid {border}; font-weight: 700; }}
        /* Compacte knoppen met alleen een teken: de gewone zijmarge van 14px
           laat op een vaste breedte van 34px niets over voor het teken zelf. */
        QPushButton[picker="true"] {{ padding: 4px 2px; font-size: 12pt; }}
        QPushButton#primaryButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6c2cff, stop:1 #8f3cff); color: #ffffff; border-color: #8a52ff; }}
        QPushButton#primaryButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #7f3cff, stop:1 #b44cff); border-color: #b486ff; }}
        QPushButton#primaryButton:pressed {{ background: #5520d6; }}
        QPushButton#secondaryButton, QPushButton#notificationButton, QPushButton#iconButton {{ background: {surface}; color: {text}; border-color: {border}; }}
        QPushButton#secondaryButton:hover, QPushButton#notificationButton:hover, QPushButton#iconButton:hover {{ background: {hover}; border-color: #486fff; }}
        QPushButton#iconButton {{ padding: 0; }}
        QPushButton#iconButton::menu-indicator {{ image: none; width: 0px; height: 0px; subcontrol-position: center; }}
        QPushButton#activeNavigationButton {{ background: #263b67; color: #ffffff; border: 1px solid #5274ff; }}
        QPushButton#dangerButton {{ background: {danger_bg}; color: #ff6f8e; border-color: #6d3042; }}
        QPushButton#dangerButton:hover {{ background: {danger_hover}; border-color: #e94d70; }}
        QPushButton:disabled {{ background: {surface_alt}; color: #5f6d80; border-color: {border}; }}
        QPushButton#notificationButton {{ border-radius: 18px; padding: 7px 13px; }}
        QPushButton#notificationButton[hasNotifications="true"] {{ background: #33250d; color: #ffc867; border-color: #7e5e21; }}

        QFrame#toolbar, QFrame#summaryCard, QFrame#compactSummaryCard, QFrame#statisticsCard, QFrame#eventBar, QGroupBox {{ background: {surface}; border: 1px solid {border}; border-radius: 12px; }}

        QFrame#eventWorkspaceHeader {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #111827, stop:0.65 #161b34, stop:1 #211847); border: 1px solid #343b62; border-left: 3px solid #765dff; border-radius: 14px; }}
        QLabel#eventWorkspaceTitle {{ color: #ffffff; font-size: 17pt; font-weight: 800; }}
        QLabel#eventStatusBadge {{ color: #d7ccff; background: #211b45; border: 1px solid #6259d6; border-radius: 12px; padding: 5px 10px; font-size: 8.5pt; font-weight: 800; }}
        QLabel#eventStatusBadge[statusKind="afgerond"] {{ color: #88e9bd; background: #10251f; border-color: #1f6d50; }}
        QLabel#eventStatusBadge[statusKind="geannuleerd"] {{ color: #ff8aa3; background: #2b151d; border-color: #7b3044; }}
        QFrame#eventWorkspaceCard, QFrame#eventWorkspaceCardPrimary, QFrame#eventDetailsCard {{ background: {surface}; border: 1px solid {border}; border-radius: 14px; }}
        QFrame#eventWorkspaceCard:hover {{ border-color: #4e5f7c; }}
        QFrame#eventWorkspaceCardPrimary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #17162f, stop:1 #211745); border: 1px solid #6655d9; }}
        QFrame#eventDetailsCard {{ border-left: 3px solid #486fff; }}
        QLabel#workspaceCardTitle {{ color: {text}; font-size: 13pt; font-weight: 800; }}
        QLabel#workspaceCardMetric {{ color: #9b8cff; font-size: 9pt; font-weight: 800; }}
        QLabel#eventDetailsText {{ color: {text}; font-size: 9.3pt; }}
        QFrame#liveChoiceCard, QFrame#liveChoiceCardPrimary {{ background: {surface}; border: 1px solid {border}; border-radius: 16px; }}
        QFrame#liveChoiceCardPrimary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #17162f, stop:1 #211745); border: 1px solid #6655d9; }}
        QFrame#liveChoiceCard {{ border: 1px solid #33415a; }}
        QLabel#choiceEyebrow {{ color: #7f8fab; font-size: 7.5pt; font-weight: 800; letter-spacing: 1.4px; }}
        QLabel#choiceTitle {{ color: {text}; font-size: 14pt; font-weight: 800; }}
        QLabel#choiceText {{ color: {muted}; font-size: 9pt; }}
        QFrame#toolbar {{ border-left: 3px solid #486fff; }}
        QFrame#summaryCard {{ border-top: 2px solid #643dff; }}
        QFrame#summaryCard[dashboardCard="true"] {{ min-height: 62px; max-height: 74px; }}
        QFrame#compactSummaryCard {{ border-top: 2px solid #16c8e7; }}
        QFrame#statisticsCard {{ border-top: 2px solid #486fff; }}
        QLabel#cardHeading {{ color: {muted}; font-size: 8pt; font-weight: 800; letter-spacing: .5px; }}
        QLabel#cardNumber, QLabel#compactCardNumber {{ color: #9b72ff; font-weight: 800; }}
        QLabel#cardNumber {{ font-size: 17pt; }}
        QLabel#compactCardNumber {{ font-size: 14pt; }}
        QLabel#cardCaption, QLabel#hintLabel, QLabel#statusLabel {{ color: {muted}; font-size: 9pt; }}
        QLabel#statisticsTitle, QLabel#sectionTitle {{ color: #b08cff; font-weight: 800; }}
        QLabel#statisticsTitle {{ font-size: 13pt; }}
        QLabel#sectionTitle {{ font-size: 18pt; }}
        QLabel#statisticsCaption {{ color: {muted}; font-size: 9pt; }}
        QGroupBox {{ margin-top: 12px; padding-top: 8px; font-weight: 700; }}
        QGroupBox#dashboardPanel {{ margin-top: 13px; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #a98aff; }}

        QScrollArea {{ background: {background}; border: none; }}
        QTabWidget::pane {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; }}
        QTabBar::tab {{ background: {surface_alt}; color: {muted}; border: 1px solid {border}; border-radius: 8px; padding: 10px 16px; margin-right: 4px; font-weight: 700; }}
        QTabBar::tab:selected {{ background: {surface}; color: #ad8cff; border-color: #6259d6; }}
        QTabBar::tab:hover {{ background: {hover}; color: #7fa1ff; }}
        QComboBox QAbstractItemView {{ background: {surface}; color: {text}; border: 1px solid {border}; selection-background-color: {selected}; }}
        QTableWidget {{ background: {surface}; alternate-background-color: {surface_alt}; color: {text}; border: 1px solid {border}; border-radius: 9px; gridline-color: {border}; selection-background-color: {selected}; selection-color: {text}; }}
        QTableWidget#dashboardTable {{ border-radius: 10px; }}
        QWidget#appFooter {{ background: {background}; border: none; }}
        QTableWidget::item {{ padding: 6px 9px; border-bottom: 1px solid {border}; }}
        QTableWidget::item:selected {{ background: #202f4f; color: {text}; border-left: 2px solid #765dff; }}
        QHeaderView::section {{ background: #182233; color: #b7c4d6; border: none; border-right: 1px solid {border}; padding: 8px 9px; font-weight: 800; }}
        QLineEdit, QComboBox, QPlainTextEdit, QSpinBox {{ background: {input_background}; color: {text}; border: 1px solid {border}; border-radius: 8px; padding: 8px 10px; }}
        QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus {{ border: 2px solid #5274ff; }}
        QComboBox#callbackStatusCombo {{ padding: 2px 28px 2px 9px; min-height: 24px; }}
        QComboBox#callbackStatusCombo::drop-down {{ width: 24px; border: none; }}
        QCheckBox {{ spacing: 8px; padding: 4px; }}
        QMenu {{ background: {surface}; color: {text}; border: 1px solid {border}; padding: 6px; }}
        QMenu::item {{ padding: 8px 24px 8px 12px; border-radius: 6px; }}
        QMenu::item:selected {{ background: {selected}; color: {text}; }}

        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: #2d3a52; min-height: 30px; border-radius: 4px; }}
        QScrollBar::handle:vertical:hover {{ background: #53658a; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: #2d3a52; min-width: 30px; border-radius: 4px; }}
        QScrollBar::handle:horizontal:hover {{ background: #53658a; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
        QToolTip {{ background: #0d1117; color: #ffffff; border: 1px solid #5274ff; padding: 5px; }}
        QStatusBar {{ background: #080d15; color: #71839d; padding: 4px 10px; }}
        QDialog {{ background: {background}; }}
        QMessageBox {{ background: {surface}; }}
        QProgressBar {{ background: {surface_alt}; color: {text}; border: 1px solid {border}; border-radius: 6px; text-align: center; height: 12px; }}
        QProgressBar::chunk {{ background: #16c8e7; border-radius: 5px; }}
    """
