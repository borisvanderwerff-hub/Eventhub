"""Event Control aan de bureaubladkant: inchecken als losse incheckclient, het
aanmaken van een livesessie en de tijdelijke lokale koppeling met de
Rudder-browserassistent.

De koppelingen luisteren alleen op deze computer en geven niets af zonder dat de
gebruiker het in EventHub bevestigt.
"""
from __future__ import annotations

from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PySide6.QtCore import QObject, QSettings, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from bezoekerslijst_core import (
    AANWEZIG, AFWEZIG, ONBEKEND, attendance_status, normalize, record_events,
    set_attendance,
)
from emt_rudder import RUDDER_EVENT_FORMAT
from emt_widgets import _fit_dialog_to_screen


class _AttendanceRequest:
    """Een vraag van de Browserassistent die op een antwoord uit het scherm wacht."""

    def __init__(self, rudder_event_id: str):
        self.rudder_event_id = str(rudder_event_id or "").strip()
        self.payload = None
        self.status = 504
        self.error = "EventHub heeft de aanvraag niet beantwoord."
        self.done = threading.Event()


class RudderAttendanceService(QObject):
    """Vaste loopback-ingang waarmee de Browserassistent presentie kan opvragen.

    De bestaande brug is eenmalig en wordt door EventHub zelf geopend, met een
    willekeurige poort in de URL. Wie in Rudder begint kan die niet vinden en
    belandde daarom bij een bestandskiezer.

    Deze luisteraar staat open zolang EventHub draait, maar geeft nooit uit
    zichzelf iets af: elke aanvraag wordt eerst als vraag aan de gebruiker
    voorgelegd. Er gaat bewust geen Access-Control-Allow-Origin mee, zodat een
    gewone webpagina er niet bij kan; alleen de extensie, die localhost in zijn
    machtigingen heeft, bereikt hem. De bevestiging in EventHub is het slot.
    """

    PORT = 47615

    requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = None
        self.thread = None
        service = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                """Geen serverlogregels in de console van een bureaubladapp."""

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/attendance":
                    self.send_error(404)
                    return
                wanted = (urllib.parse.parse_qs(parsed.query).get("event") or [""])[0].strip()
                if not wanted.isdigit():
                    self.send_error(404)
                    return
                request = _AttendanceRequest(wanted)
                service.requested.emit(request)
                # De gebruiker moet de vraag nog beantwoorden; zo lang blijft
                # deze verbinding open, en daarna niet langer.
                request.done.wait(180)
                if request.payload is None:
                    body = json.dumps({"error": request.error}, ensure_ascii=False).encode("utf-8")
                    self.send_response(request.status)
                else:
                    body = json.dumps(request.payload, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

        self._handler = Handler

    def start(self) -> bool:
        """Draait al een EventHub op deze poort, dan laat deze het erbij zitten."""
        if self.server is not None:
            return True
        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", self.PORT), self._handler)
        except OSError:
            self.server = None
            return False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        server, self.server = self.server, None
        if server is None:
            return
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
        self.thread = None


class RudderLocalBridge:
    """One-use loopback bridge between EventHub and the browser extension."""

    def __init__(self, payload: dict | None = None, lifetime_seconds: int = 300,
                 receive_event=False, batch: bool = False):
        self.payload = payload
        self.receive_event = bool(receive_event)
        # In batchmodus blijft de brug open tot de assistent klaar is of de
        # levensduur verstrijkt; anders sluit hij na het eerste evenement.
        self.batch = bool(batch)
        self._received_payload = None
        self._received_batch: list[dict] = []
        self._lock = threading.Lock()
        self.token = uuid.uuid4().hex + uuid.uuid4().hex
        self.lifetime_seconds = max(30, int(lifetime_seconds))
        self.server = None
        self.thread = None
        self.timer = None
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                supplied_token = (query.get("token") or [""])[0]
                expected_path = "/event" if bridge.payload and bridge.payload.get("format") == RUDDER_EVENT_FORMAT else "/attendance"
                if bridge.receive_event or parsed.path != expected_path or supplied_token != bridge.token:
                    self.send_error(404)
                    return
                body = json.dumps(bridge.payload, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                threading.Thread(target=bridge.stop, daemon=True).start()

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                supplied_token = (query.get("token") or [""])[0]
                if not bridge.receive_event or parsed.path != "/event" or supplied_token != bridge.token:
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > 512 * 1024:
                    self.send_error(413)
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError("not an object")
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    self.send_error(400)
                    return
                with bridge._lock:
                    bridge._received_payload = payload
                    if bridge.batch:
                        bridge._received_batch.append(payload)
                    received = len(bridge._received_batch) if bridge.batch else 1
                body = json.dumps({"ok": True, "received": received}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
                # In batchmodus blijft de brug open voor het volgende evenement.
                if not bridge.batch:
                    threading.Thread(target=bridge.stop, daemon=True).start()

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()

            def log_message(self, _format, *_args):
                return

        self._handler_class = Handler

    def start(self):
        self.stop()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_class)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, name="EventHub-Rudder-Bridge", daemon=True)
        self.thread.start()
        self.timer = threading.Timer(self.lifetime_seconds, self.stop)
        self.timer.daemon = True
        self.timer.start()
        return self.server.server_address[1], self.token

    def take_received_batch(self):
        """Haal de tot nu toe ontvangen evenementen op en maak de lijst leeg."""
        with self._lock:
            received, self._received_batch = list(self._received_batch), []
        return received

    def take_received_payload(self):
        with self._lock:
            payload, self._received_payload = self._received_payload, None
        return payload

    def stop(self):
        timer, self.timer = self.timer, None
        if timer is not None and timer is not threading.current_thread():
            timer.cancel()
        server, self.server = self.server, None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            server.server_close()


def apply_live_attendance(records: list[dict], participants: list[dict], event_name: str = "",
                          reverted_ids=None, unmatched: list | None = None) -> int:
    """Apply server attendance to linked EventHub records without guessing duplicates.

    De server kent vier standen. present en checked_out zijn aanwezigheid.
    not_checked_in is de beginstand van iedereen die wordt ingelezen en
    betekent 'nog niet gescand', niet 'was er niet'; hem overnemen als afwezig
    wiste de aanwezigheid uit de aanmeldlijst - bij een sessie met twee scans
    bleven van zevenentachtig aanwezigen er twee over.

    absent is wel een uitspraak: die zet de server wanneer in Serverbeheer het
    inchecken wordt gestopt, bedoeld als 'we zijn klaar, wie er nu niet is komt
    niet meer'. Maar die uitspraak gaat alleen over wat de balie weet. Is er
    aan die balie niet gescand, dan staat iedereen daar op absent terwijl
    EventHub allang aanwezigheid uit de aanmeldlijst had - en dan wist het
    overnemen ervan precies wat je wilde bewaren. Zo verdwenen 57 aanwezigen
    en 19 afmeldingen in een keer.

    Daarom vult absent alleen aan waar EventHub niets weet. Een vastgelegde
    aanwezigheid of afmelding blijft staan; die corrigeer je zo nodig met de
    hand, per persoon.

    Een bewust teruggedraaide incheck (checkin_undone) maakt de stand onbekend:
    dat een scan is teruggedraaid zegt niet dat iemand wegbleef.

    Staat iemand twee keer in de deelnemerslijst - zelfde naam en zelfde
    geboortedatum, bijvoorbeeld na twee aanmeldingen - dan weigert de koppeling
    op naam te raden welke van de twee bedoeld is. Dat is juist, maar het mocht
    niet stilzwijgend gebeuren: zo verdween de incheck van drie bezoekers
    zonder een spoor. Wie niet gekoppeld kan worden komt daarom in ``unmatched``
    terecht, zodat de gebruiker het te zien krijgt.
    """
    reverted = {str(value) for value in (reverted_ids or ())}
    by_id = {str(record.get("_id", "")): record for record in records if record.get("_id")}
    fallback = {}
    for record in records:
        key = (normalize(record.get("Voornaam", "")), normalize(record.get("Achternaam", "")),
               str(record.get("Geboortedatum", "") or "").strip())
        fallback.setdefault(key, []).append(record)
    changed = 0
    for participant in participants:
        record = by_id.get(str(participant.get("id", "")))
        if record is None:
            key = (normalize(participant.get("voornaam", "")), normalize(participant.get("achternaam", "")),
                   str(participant.get("geboortedatum", "") or "").strip())
            matches = fallback.get(key, [])
            record = matches[0] if len(matches) == 1 else None
        if record is None:
            if unmatched is not None and (
                bool(participant.get("checkin_time"))
                or str(participant.get("attendance_status", "") or "") in {"present", "checked_out"}
            ):
                naam = " ".join(filter(None, [
                    str(participant.get("voornaam", "") or "").strip(),
                    str(participant.get("achternaam", "") or "").strip(),
                ])) or "Onbekende deelnemer"
                unmatched.append(naam)
            continue
        server_status = str(participant.get("attendance_status", "") or "")
        present = bool(participant.get("checkin_time")) or server_status in {"present", "checked_out"}
        # De server zet 'absent' bij Inchecken stoppen in Serverbeheer. Dat vult
        # hieronder alleen aan wat EventHub nog niet weet; het overschrijft geen
        # vastgelegde aanwezigheid of afmelding.
        afgesloten = server_status == "absent"
        if not present and not afgesloten and str(participant.get("id", "")) not in reverted:
            # Niet gescand is geen uitspraak; laat staan wat er lokaal bekend is.
            continue
        if present:
            status = AANWEZIG
        elif afgesloten:
            status = AFWEZIG
        else:
            status = ONBEKEND
        # Schrijf alleen naar het evenement van deze sessie. Voorheen werd hier
        # één gedeelde boolean gezet, waardoor het inchecken bij een tweede
        # evenement de registratie van het eerste wiste.
        targets = [event_name] if event_name else record_events(record)
        for target in targets:
            if afgesloten and attendance_status(record, target) != ONBEKEND:
                continue
            if set_attendance(record, target, status):
                changed += 1
    return changed


class LiveSessionSetupDialog(QDialog):
    """Run-specific settings before an EventHub event is put live."""

    def __init__(self, event: dict, location_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nieuwe livesessie instellen")
        self.setMinimumWidth(520)
        self.checkout_required = False

        layout = QVBoxLayout(self)
        title = QLabel("Nieuwe livesessie")
        title.setObjectName("sectionTitle")
        hint = QLabel(
            "De evenementgegevens en deelnemers worden automatisch uit het dossier overgenomen. "
            "Kies hieronder alleen de instellingen voor deze livesessie."
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(8)

        summary = QFrame()
        summary.setObjectName("summaryCard")
        form = QFormLayout(summary)
        form.addRow("Evenement", QLabel(str(event.get("name", "") or "Onbenoemd evenement")))
        form.addRow("Datum", QLabel(str(event.get("date", "") or "Niet opgegeven")))
        location_label = QLabel(location_text or "Niet opgegeven")
        location_label.setWordWrap(True)
        form.addRow("Locatie", location_label)
        layout.addWidget(summary)

        self.checkout_checkbox = QCheckBox("Uitchecken registreren (toon wie nog in het pand is)")
        self.checkout_checkbox.setToolTip(
            "Schakel dit in wanneer vertrek tijdens deze livesessie ook geregistreerd moet worden."
        )
        layout.addWidget(self.checkout_checkbox)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        start_button = buttons.addButton("Livesessie starten", QDialogButtonBox.ButtonRole.AcceptRole)
        start_button.setObjectName("primaryButton")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._accept_setup)
        layout.addWidget(buttons)

    def _accept_setup(self):
        self.checkout_required = self.checkout_checkbox.isChecked()
        self.accept()


class LiveCheckinDialog(QDialog):
    """Native EventHub-client voor een bestaande Event Control-sessie."""

    def __init__(self, parent=None, default_url: str = ""):
        super().__init__(parent)
        self.base_url = ""
        self.client_id = ""
        self.participants = []
        self.live_settings = QSettings("Cohentra Digital", "EventHub Live Client")
        self.offline_queue = json.loads(self.live_settings.value("offline_queue", "[]") or "[]")
        self.session_frozen = False
        self.checkout_required = False
        self.checkin_stopped = False
        self._stop_notice_shown = False
        self.setWindowTitle("Event Control — verbinden")
        _fit_dialog_to_screen(self, 980, 680, 700, 480)
        layout = QVBoxLayout(self)

        connection_box = QGroupBox("Verbinden met live sessie")
        connection_layout = QGridLayout(connection_box)
        self.live_url_input = QLineEdit(default_url)
        self.live_url_input.setPlaceholderText("http://192.168.1.25:8080")
        self.live_client_name_input = QLineEdit()
        self.live_client_name_input.setPlaceholderText("Bijvoorbeeld: Balie ingang")
        self.live_event_code_input = QLineEdit()
        self.live_event_code_input.setPlaceholderText("4 cijfers")
        self.live_event_code_input.setMaxLength(4)
        self.live_event_code_input.setInputMask("0000")
        self.live_connect_button = QPushButton("Verbinden")
        self.live_connect_button.setObjectName("primaryButton")
        self.live_connect_button.clicked.connect(self.connect_to_session)
        self.live_discover_button = QPushButton("Hubs zoeken")
        self.live_discover_button.setObjectName("secondaryButton")
        self.live_discover_button.clicked.connect(self.discover_hubs)
        connection_layout.addWidget(QLabel("Serveradres:"), 0, 0)
        connection_layout.addWidget(self.live_url_input, 0, 1)
        connection_layout.addWidget(QLabel("Naam apparaat/balie:"), 1, 0)
        connection_layout.addWidget(self.live_client_name_input, 1, 1)
        connection_layout.addWidget(QLabel("Sessiecode:"), 2, 0)
        connection_layout.addWidget(self.live_event_code_input, 2, 1)
        connection_layout.addWidget(self.live_connect_button, 0, 2, 3, 1)
        connection_layout.addWidget(self.live_discover_button, 3, 1)
        layout.addWidget(connection_box)

        status_row = QHBoxLayout()
        self.live_connection_status = QLabel("Niet verbonden")
        self.live_connection_status.setObjectName("statusLabel")
        self.live_search_input = QLineEdit()
        self.live_search_input.setPlaceholderText("Zoek op naam, geboortedatum of geboorteplaats…")
        self.live_search_input.setClearButtonEnabled(True)
        self.live_search_input.setEnabled(False)
        self.live_search_timer = QTimer(self)
        self.live_search_timer.setSingleShot(True)
        self.live_search_timer.setInterval(250)
        self.live_search_timer.timeout.connect(self.refresh_participants)
        self.live_search_input.textChanged.connect(lambda *_: self.live_search_timer.start())
        refresh_button = QPushButton("Vernieuwen")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_participants)
        status_row.addWidget(self.live_connection_status)
        status_row.addWidget(self.live_search_input, 1)
        status_row.addWidget(refresh_button)
        layout.addLayout(status_row)

        self.live_table = QTableWidget()
        headers = ["Naam", "Geboortedatum", "Geboorteplaats", "Status"]
        self.live_table.setColumnCount(len(headers))
        self.live_table.setHorizontalHeaderLabels(headers)
        self.live_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.live_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.live_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.live_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.live_table.cellDoubleClicked.connect(lambda *_: self.toggle_selected_participant())
        layout.addWidget(self.live_table, 1)

        actions = QHBoxLayout()
        self.live_checkin_button = QPushButton("Inchecken")
        self.live_checkin_button.setObjectName("primaryButton")
        self.live_checkin_button.clicked.connect(lambda: self.set_selected_presence(True))
        self.live_checkout_button = QPushButton("Ongedaan maken")
        self.live_checkout_button.setObjectName("secondaryButton")
        self.live_checkout_button.clicked.connect(lambda: self.set_selected_presence(False))
        close_button = QPushButton("Sluiten")
        close_button.clicked.connect(self.close)
        self.live_checkin_button.setEnabled(False)
        self.live_checkout_button.setEnabled(False)
        actions.addWidget(self.live_checkin_button)
        actions.addWidget(self.live_checkout_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)

        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.setInterval(20000)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(5000)
        self.sync_timer.timeout.connect(self.sync_offline_queue)

    def discover_hubs(self):
        self.live_connection_status.setText("Hubs zoeken op het lokale netwerk…")
        QApplication.processEvents()
        try:
            from server.network import discover_hubs
            hubs = discover_hubs()
        except Exception as exc:
            QMessageBox.warning(self, "Hubdetectie mislukt", str(exc)); return
        if not hubs:
            QMessageBox.information(self, "Geen hubs gevonden", "Geen actieve EventHub-hub gevonden op dit netwerk.")
            self.live_connection_status.setText("Niet verbonden"); return
        labels = [f"{hub.get('name', 'EventHub-sessie')} — {hub['url']}" for hub in hubs]
        selected, ok = QInputDialog.getItem(self, "Hub kiezen", "Actieve hubs:", labels, 0, False)
        if ok:
            self.live_url_input.setText(hubs[labels.index(selected)]["url"])
        self.live_connection_status.setText("Hub gevonden — vul de sessiecode in.")

    def _json_request(self, path: str, method: str = "GET", payload=None, operation_id: str = "",
                      operation_created_at: str = ""):
        url = self.base_url.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.client_id:
            headers["X-Client-Id"] = self.client_id
        if operation_id:
            headers["X-Operation-Id"] = operation_id
        if operation_created_at:
            headers["X-Operation-Created-At"] = operation_created_at
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=4) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            try:
                message = json.loads(exc.read().decode("utf-8")).get("error", str(exc))
            except Exception:
                message = str(exc)
            raise RuntimeError(message) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("De server is niet bereikbaar. Controleer adres, netwerk en firewall.") from exc

    def connect_to_session(self):
        base_url = self.live_url_input.text().strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            base_url = "http://" + base_url
        parsed = urllib.parse.urlparse(base_url)
        if not parsed.hostname:
            QMessageBox.information(self, "Serveradres ontbreekt", "Vul het netwerkadres uit EventHub Server in.")
            return
        code = self.live_event_code_input.text().replace(" ", "").strip()
        if not re.fullmatch(r"\d{4}", code):
            QMessageBox.information(self, "Sessiecode controleren", "Vul de viercijferige sessiecode in.")
            return
        self.base_url = base_url
        try:
            client = self._json_request(
                "/api/clients/register",
                "POST",
                {
                    "client_name": self.live_client_name_input.text().strip() or "EventHub Desktop",
                    "client_type": "EventHub Desktop",
                    "role": "checkin",
                    "event_code": code,
                },
            )
        except RuntimeError as exc:
            QMessageBox.warning(self, "Verbinden mislukt", str(exc))
            return
        self.client_id = str(client.get("id", ""))
        self.live_connection_status.setText(f"● Verbonden als {client.get('client_name', 'EventHub Desktop')}")
        for widget in (self.live_url_input, self.live_client_name_input, self.live_event_code_input, self.live_connect_button):
            widget.setEnabled(False)
        self.live_search_input.setEnabled(True)
        self.live_checkin_button.setEnabled(True)
        self.live_checkout_button.setEnabled(True)
        self.heartbeat_timer.start()
        self.sync_timer.start()
        self.refresh_participants()

    def refresh_participants(self):
        if not self.client_id:
            return
        query = urllib.parse.quote(self.live_search_input.text().strip())
        try:
            self.participants = self._json_request(f"/api/participants/search?q={query}&limit=1000")
        except RuntimeError as exc:
            self.live_connection_status.setText(f"Verbinding onderbroken: {exc}")
            cached = self.live_settings.value("participant_cache", "")
            if cached:
                try: self.participants = json.loads(cached)
                except ValueError: pass
                self._render_participants()
            return
        self.live_settings.setValue("participant_cache", json.dumps(self.participants))
        self._render_participants()

    def _render_participants(self):
        query = self.live_search_input.text().strip().lower()
        if query:
            self.participants = [p for p in self.participants if query in " ".join(str(p.get(k, "")) for k in
                                 ("voornaam", "tussenvoegsel", "achternaam", "geboortedatum", "geboorteplaats")).lower()]
        def sort_key(participant):
            return tuple(normalize(participant.get(field, "")) for field in
                         ("achternaam", "tussenvoegsel", "voornaam"))
        self.participants = sorted(self.participants, key=sort_key)
        self.live_table.setRowCount(len(self.participants))
        for row_index, participant in enumerate(self.participants):
            surname = str(participant.get("achternaam", "") or "").strip()
            given = " ".join(filter(None, [str(participant.get("voornaam", "") or "").strip(),
                                            str(participant.get("tussenvoegsel", "") or "").strip()]))
            display_name = f"{surname}, {given}" if surname and given else surname or given
            values = [
                display_name, participant.get("geboortedatum", ""), participant.get("geboorteplaats", ""),
                {"present": "Binnen", "checked_out": "Uitgecheckt", "absent": "Afwezig"}.get(
                    participant.get("attendance_status"), "Nog niet ingecheckt"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.ItemDataRole.UserRole, participant.get("id", ""))
                self.live_table.setItem(row_index, column, item)

    def _selected_participant(self):
        row = self.live_table.currentRow()
        if row < 0 or row >= len(self.participants):
            return None
        return self.participants[row]

    def set_selected_presence(self, present: bool):
        participant = self._selected_participant()
        if not participant:
            QMessageBox.information(self, "Geen bezoeker gekozen", "Selecteer eerst een bezoeker.")
            return
        status = participant.get("attendance_status", "not_checked_in")
        if present and status in {"checked_out", "absent"}:
            QMessageBox.information(self, "Niet beschikbaar", "Deze bezoeker kan in deze fase niet opnieuw worden ingecheckt.")
            return
        action = "checkin" if present else ("checkout" if self.checkout_required else "undo")
        if present and self.checkin_stopped:
            QMessageBox.information(self, "Inchecken beëindigd", "Het inchecken is beëindigd door de beheerder.")
            return
        if self.session_frozen:
            QMessageBox.information(self, "Inchecken gepauzeerd", "De beheerder heeft de sessie tijdelijk bevroren.")
            return
        operation_id = str(uuid.uuid4())
        try:
            self._json_request(f"/api/participants/{participant['id']}/{action}", "POST", {}, operation_id)
        except RuntimeError as exc:
            if "gepauzeerd" in str(exc).lower():
                self.session_frozen = True
                QMessageBox.information(self, "Inchecken gepauzeerd", str(exc)); return
            if "beëindigd" in str(exc).lower():
                self.checkin_stopped = True
                if not self._stop_notice_shown:
                    self._stop_notice_shown = True
                    QMessageBox.information(self, "Inchecken beëindigd", str(exc))
                self.live_connection_status.setText("● Verbonden · inchecken beëindigd")
                return
            self.offline_queue.append({"id": operation_id, "participant_id": participant["id"],
                                       "action": action, "created_at": datetime.now().isoformat()})
            self.live_settings.setValue("offline_queue", json.dumps(self.offline_queue))
            participant["attendance_status"] = "present" if present else ("checked_out" if self.checkout_required else "not_checked_in")
            self.live_connection_status.setText(f"● Offline · {len(self.offline_queue)} actie(s) wachten")
            self._render_participants()
            return
        self.refresh_participants()

    def sync_offline_queue(self):
        if not self.client_id:
            return
        try:
            state = self._json_request("/api/session/state")
            self.session_frozen = bool(state.get("frozen"))
            self.checkout_required = bool(state.get("checkout_required"))
            self.checkin_stopped = bool(state.get("checkin_stopped"))
            if not self.checkin_stopped:
                self._stop_notice_shown = False
            self.live_checkout_button.setText("Uitchecken" if self.checkout_required else "Ongedaan maken")
            if self.checkin_stopped and not self._stop_notice_shown:
                self._stop_notice_shown = True
                QMessageBox.information(self, "Inchecken beëindigd",
                    "Het inchecken is beëindigd door de beheerder." +
                    (f"\n\nReden: {state.get('checkin_stopped_reason')}" if state.get("checkin_stopped_reason") else ""))
            if self.session_frozen:
                self.live_connection_status.setText("⏸ Inchecken gepauzeerd" + (f" — {state.get('reason')}" if state.get("reason") else "")); return
            while self.offline_queue:
                item = self.offline_queue[0]
                if item.get("conflict"):
                    self.live_connection_status.setText("● Conflict · controle door beheerder vereist")
                    return
                self._json_request(f"/api/participants/{item['participant_id']}/{item['action']}",
                                   "POST", {}, item["id"], item.get("created_at", ""))
                self.offline_queue.pop(0)
                self.live_settings.setValue("offline_queue", json.dumps(self.offline_queue))
            self.live_connection_status.setText("● Verbonden · alles bijgewerkt")
        except RuntimeError as exc:
            if ("conflict" in str(exc).lower() or "beëindigd" in str(exc).lower()) and self.offline_queue:
                self.offline_queue[0]["conflict"] = True
                self.live_settings.setValue("offline_queue", json.dumps(self.offline_queue))
                self.live_connection_status.setText("● Conflict · controle door beheerder vereist")
                return
            if self.offline_queue:
                self.live_connection_status.setText(f"● Offline · {len(self.offline_queue)} actie(s) wachten")

    def toggle_selected_participant(self):
        participant = self._selected_participant()
        if participant:
            self.set_selected_presence(participant.get("attendance_status") != "present")

    def send_heartbeat(self):
        if not self.client_id:
            return
        try:
            self._json_request(f"/api/clients/{self.client_id}/heartbeat", "POST", {})
        except RuntimeError:
            self.live_connection_status.setText("Verbinding met de live sessie is onderbroken of door de beheerder beëindigd.")

    def closeEvent(self, event: QCloseEvent):
        self.heartbeat_timer.stop()
        self.sync_timer.stop()
        if self.client_id:
            try:
                self._json_request(f"/api/clients/{self.client_id}", "DELETE")
            except RuntimeError:
                pass
        super().closeEvent(event)
