"""Flask application for EventHub Server.

Chosen over FastAPI for this v1: FastAPI/uvicorn/websockets could not be
installed or verified in the development sandbox used to build this
(no network access), while Flask + Jinja2 were already available and
could be fully exercised by the automated tests in server/tests. The
service layer (server/services/*.py) has no Flask-specific code in it,
so swapping the web framework later does not require touching business
logic — only this file and events_hub.py's transport.
"""
from __future__ import annotations

import mimetypes
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask, Response, g, jsonify, request, render_template, send_file, stream_with_context
from werkzeug.utils import secure_filename

from .. import importer
from ..database import connect
from ..events_hub import hub
from ..logging_setup import get_logger
from ..paths import events_directory
from ..services import client_service, emergency_service, participant_service, session_service, statistics_service

logger = get_logger("web")

SERVER_VERSION = "1.6.0"
PROTOCOL_VERSION = "5"
ALLOWED_IMPORT_EXTENSIONS = {".xlsx", ".xlsm", ".xls"}
MAX_IMPORT_SIZE = 20 * 1024 * 1024  # 20 MB is generous for a visitor list
MUTATING_ROLES = {"admin", "event_manager"}
CHECKIN_ROLES = {"admin", "event_manager", "checkin"}
READ_ROLES = {"admin", "event_manager", "checkin"}
SESSION_STATE_ROLES = {"admin", "event_manager", "checkin", "viewer"}


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def create_app(db_path: Path, event_id: str) -> Flask:
    app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"),
                template_folder=str(Path(__file__).parent / "templates"))
    app.config["MAX_CONTENT_LENGTH"] = MAX_IMPORT_SIZE
    app.config["EVENT_ID"] = event_id
    app.config["DB_PATH"] = db_path

    def get_connection() -> sqlite3.Connection:
        if "connection" not in g:
            g.connection = connect(db_path)
        return g.connection

    def current_client_role(connection: sqlite3.Connection) -> Optional[str]:
        client_id = request.headers.get("X-Client-Id")
        if not client_id:
            return None
        row = connection.execute("SELECT role FROM client_session WHERE id = ?", (client_id,)).fetchone()
        return row["role"] if row else None

    def require_role(connection: sqlite3.Connection, allowed_roles: set) -> str:
        client_id = request.headers.get("X-Client-Id")
        if not client_id:
            raise ApiError("Registreer eerst een client (X-Client-Id header ontbreekt).", 401)
        role = current_client_role(connection)
        if role is None:
            raise ApiError("Onbekende client-id; registreer opnieuw.", 401)
        if role not in allowed_roles:
            raise ApiError(f"Rol '{role}' heeft geen rechten voor deze actie.", 403)
        return client_id

    def require_not_frozen(connection: sqlite3.Connection) -> None:
        if emergency_service.state(connection)["active"]:
            raise ApiError("De calamiteitenmodus is actief. Volg de instructies van de eventmanager of beheerder.", 423)
        state = session_service.freeze_state(connection)
        if state["frozen"]:
            reason = f" Reden: {state['reason']}" if state["reason"] else ""
            raise ApiError(f"Inchecken is tijdelijk gepauzeerd.{reason}", 423)
        if session_service.action_conflicts_with_freeze(connection, request.headers.get("X-Operation-Created-At", "")):
            raise ApiError("Conflict: deze offline handeling vond plaats tijdens een freeze en vereist controle.", 409)

    def require_checkin_open(connection: sqlite3.Connection) -> None:
        state = session_service.freeze_state(connection)
        if state["checkin_stopped"]:
            raise ApiError("Het inchecken is beëindigd door de beheerder.", 423)

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(participant_service.NotFoundError)
    def handle_not_found(error: participant_service.NotFoundError):
        return jsonify({"error": str(error)}), 404

    @app.errorhandler(session_service.SessionValidationError)
    def handle_validation(error: session_service.SessionValidationError):
        return jsonify({"error": str(error)}), 400

    # ---- Server / session info -------------------------------------------------
    def _public_session(session: Optional[dict]) -> Optional[dict]:
        """Session info safe to expose over the API: never include the
        event_code, since that would let anyone with the URL read the
        check-in gate code without actually knowing it."""
        if not session:
            return session
        return {key: value for key, value in session.items() if key != "event_code"}

    @app.get("/api/server")
    def api_server():
        connection = get_connection()
        session = session_service.get_session(connection)
        return jsonify({
            "product": "EventHub Server",
            "server_version": SERVER_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "event": _public_session(session),
        })

    @app.get("/api/session")
    def api_session():
        connection = get_connection()
        session = session_service.get_session(connection)
        if not session:
            raise ApiError("Geen actieve sessie.", 404)
        return jsonify(_public_session(session))

    @app.get("/api/session/state")
    def api_session_state():
        connection = get_connection()
        require_role(connection, SESSION_STATE_ROLES)
        return jsonify({**session_service.freeze_state(connection), "emergency": emergency_service.state(connection)})

    @app.get("/api/session/activity")
    def api_session_activity():
        connection = get_connection()
        emergency = emergency_service.overview(connection)
        return jsonify({
            "items": session_service.recent_session_activity(connection, request.args.get("limit", 12, type=int)),
            "state": session_service.freeze_state(connection),
            "server_started_at": app.config.get("SERVER_STARTED_AT"),
            "emergency": {key: emergency.get(key) for key in (
                "active", "incident_id", "instruction", "total", "safe", "unaccounted"
            )},
        })

    @app.post("/api/session/freeze")
    def api_session_freeze():
        connection = get_connection()
        client_id = require_role(connection, MUTATING_ROLES)
        payload = request.get_json(silent=True) or {}
        row = connection.execute("SELECT client_name FROM client_session WHERE id=?", (client_id,)).fetchone()
        return jsonify(session_service.set_frozen(connection, bool(payload.get("frozen", True)),
                                                  payload.get("reason", ""), row["client_name"] if row else client_id))

    @app.post("/api/session/stop-checkin")
    def api_stop_checkin():
        connection = get_connection(); client_id = require_role(connection, MUTATING_ROLES)
        payload = request.get_json(silent=True) or {}
        row = connection.execute("SELECT client_name FROM client_session WHERE id=?", (client_id,)).fetchone()
        return jsonify(session_service.stop_checkin(connection, payload.get("reason", ""), row["client_name"] if row else client_id))

    @app.post("/api/session/resume-checkin")
    def api_resume_checkin():
        connection = get_connection(); client_id = require_role(connection, MUTATING_ROLES)
        row = connection.execute("SELECT client_name FROM client_session WHERE id=?", (client_id,)).fetchone()
        return jsonify(session_service.resume_checkin(connection, row["client_name"] if row else client_id))

    # ---- Calamiteitenmodus ----------------------------------------------------
    def _actor_name(connection: sqlite3.Connection, client_id: str) -> str:
        row = connection.execute("SELECT client_name FROM client_session WHERE id=?", (client_id,)).fetchone()
        return row["client_name"] if row else client_id

    @app.get("/api/emergency")
    def api_emergency_overview():
        connection = get_connection()
        require_role(connection, READ_ROLES)
        return jsonify(emergency_service.overview(connection))

    @app.post("/api/emergency/start")
    def api_emergency_start():
        connection = get_connection(); client_id = require_role(connection, MUTATING_ROLES)
        payload = request.get_json(silent=True) or {}
        return jsonify(emergency_service.start(
            connection, payload.get("instruction", ""), _actor_name(connection, client_id)
        ))

    @app.patch("/api/emergency/instruction")
    def api_emergency_instruction():
        connection = get_connection(); client_id = require_role(connection, MUTATING_ROLES)
        payload = request.get_json(silent=True) or {}
        return jsonify(emergency_service.update_instruction(
            connection, payload.get("instruction", ""), _actor_name(connection, client_id)
        ))

    @app.post("/api/emergency/end")
    def api_emergency_end():
        connection = get_connection(); client_id = require_role(connection, MUTATING_ROLES)
        return jsonify(emergency_service.end(connection, _actor_name(connection, client_id)))

    @app.patch("/api/emergency/participants/<participant_id>")
    def api_emergency_mark_participant(participant_id: str):
        connection = get_connection(); client_id = require_role(connection, CHECKIN_ROLES)
        payload = request.get_json(silent=True) or {}
        return jsonify(emergency_service.mark_safe(
            connection, participant_id, bool(payload.get("safe", True)), _actor_name(connection, client_id),
            payload.get("assembly_point", ""), payload.get("team", ""),
        ))

    @app.get("/api/emergency/export")
    def api_emergency_export():
        connection = get_connection()
        require_role(connection, MUTATING_ROLES)
        output = emergency_service.export_workbook(connection, request.args.get("incident_id", ""))
        return send_file(
            output, as_attachment=True, download_name="EventHub-calamiteitenregistratie.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/api/health")
    def api_health():
        return jsonify({"status": "ok"})

    @app.get("/service-worker.js")
    def service_worker():
        return app.send_static_file("js/service-worker.js"), 200, {"Content-Type": "application/javascript", "Service-Worker-Allowed": "/"}

    # ---- Clients -----------------------------------------------------------
    def _device_type_from_request(submitted: str = "") -> str:
        allowed = {
            "iPhone", "iPad", "Android-telefoon", "Android-tablet",
            "Windows-pc", "Mac", "Chromebook", "Linux-apparaat",
            "Onbekend apparaat",
        }
        submitted = (submitted or "").strip()
        if submitted in allowed:
            return submitted
        ua = request.headers.get("User-Agent", "")
        ua_lower = ua.lower()
        if "ipad" in ua_lower:
            return "iPad"
        if "iphone" in ua_lower or "ipod" in ua_lower:
            return "iPhone"
        if "android" in ua_lower:
            return "Android-telefoon" if "mobile" in ua_lower else "Android-tablet"
        if "windows" in ua_lower:
            return "Windows-pc"
        if "cros" in ua_lower:
            return "Chromebook"
        if "macintosh" in ua_lower or "mac os x" in ua_lower:
            return "Mac"
        if "linux" in ua_lower:
            return "Linux-apparaat"
        return "Onbekend apparaat"

    @app.post("/api/clients/register")
    def api_register_client():
        connection = get_connection()
        payload = request.get_json(silent=True) or {}
        client_name = (payload.get("client_name") or "").strip() or "Onbekend apparaat"
        client_type = _device_type_from_request(payload.get("client_type", ""))
        # Een browserclient start altijd zonder mutatierechten. Een bestaande
        # eventmanager of beheerder wijst daarna zo nodig een hogere rol toe.
        role = "viewer"
        submitted_code = (payload.get("event_code") or "").strip()
        if not session_service.verify_event_code(connection, submitted_code):
            raise ApiError("Onjuiste sessiecode.", 401)
        ip_address = request.remote_addr or ""
        client = client_service.register_client(connection, event_id, client_name, client_type,
                                                 ip_address, role)
        return jsonify(client), 201

    @app.post("/api/clients/<client_id>/heartbeat")
    def api_client_heartbeat(client_id: str):
        if request.headers.get("X-Client-Id") != client_id:
            raise ApiError("Ongeldige client voor heartbeat.", 401)
        connection = get_connection()
        if not client_service.heartbeat(connection, client_id):
            raise ApiError("Deze client is door de beheerder afgemeld.", 401)
        return jsonify({"ok": True})

    @app.delete("/api/clients/<client_id>")
    def api_client_disconnect(client_id: str):
        if request.headers.get("X-Client-Id") != client_id:
            raise ApiError("Ongeldige client voor uitloggen.", 401)
        connection = get_connection()
        client_service.disconnect_client(connection, client_id)
        return jsonify({"ok": True})

    @app.patch("/api/clients/<client_id>/preferences")
    def api_client_preferences(client_id: str):
        if request.headers.get("X-Client-Id") != client_id:
            raise ApiError("U kunt alleen de instellingen van dit apparaat aanpassen.", 401)
        connection = get_connection()
        payload = request.get_json(silent=True) or {}
        try:
            return jsonify(client_service.update_own_preferences(
                connection, event_id, client_id,
                payload.get("client_name", ""), payload.get("role", ""),
            ))
        except ValueError as exc:
            raise ApiError(str(exc), 400)

    @app.get("/api/clients")
    def api_list_clients():
        connection = get_connection()
        return jsonify(client_service.list_clients(connection, event_id))

    @app.get("/api/admin/clients")
    def api_manage_clients():
        connection = get_connection()
        require_role(connection, MUTATING_ROLES)
        return jsonify(client_service.list_clients(connection, event_id))

    @app.delete("/api/admin/clients/<client_id>")
    def api_kick_client(client_id: str):
        connection = get_connection(); admin_id = require_role(connection, MUTATING_ROLES)
        actor_role = current_client_role(connection)
        target = connection.execute(
            "SELECT role FROM client_session WHERE id=? AND event_id=?", (client_id, event_id)
        ).fetchone()
        if not target:
            raise ApiError("Client niet gevonden.", 404)
        if client_id == admin_id:
            raise ApiError("U kunt uw eigen actieve client niet verwijderen.", 400)
        if actor_role == "event_manager" and target["role"] in {"event_manager", "admin"}:
            raise ApiError("Een eventmanager kan geen eventmanager of beheerder verwijderen.", 403)
        if not client_service.kick_client(connection, event_id, client_id, admin_id):
            raise ApiError("Client niet gevonden.", 404)
        return jsonify({"ok": True})

    @app.patch("/api/admin/clients/<client_id>/role")
    def api_change_client_role(client_id: str):
        connection = get_connection(); admin_id = require_role(connection, MUTATING_ROLES)
        payload = request.get_json(silent=True) or {}
        requested_role = payload.get("role", "")
        actor_role = current_client_role(connection)
        target = connection.execute(
            "SELECT role FROM client_session WHERE id=? AND event_id=?", (client_id, event_id)
        ).fetchone()
        if not target:
            raise ApiError("Client niet gevonden.", 404)
        if client_id == admin_id:
            raise ApiError("U kunt uw eigen actieve beheerrol niet aanpassen.", 400)
        if actor_role == "event_manager":
            if target["role"] in {"event_manager", "admin"} or requested_role not in {"viewer", "checkin"}:
                raise ApiError("Een eventmanager kan alleen Viewers en Check-in-clients beheren.", 403)
        try: return jsonify(client_service.set_role(connection, event_id, client_id, requested_role, admin_id))
        except ValueError as exc: raise ApiError(str(exc), 400)

    # ---- Participants --------------------------------------------------------
    @app.get("/api/participants")
    def api_list_participants():
        connection = get_connection()
        require_role(connection, READ_ROLES)
        query = request.args.get("q", "")
        attendance = request.args.get("attendance", "")
        limit = min(int(request.args.get("limit", 500)), 2000)
        return jsonify(participant_service.list_participants(connection, event_id, query, attendance, limit))

    @app.get("/api/participants/search")
    def api_search_participants():
        connection = get_connection()
        require_role(connection, READ_ROLES)
        query = request.args.get("q", "")
        limit = min(int(request.args.get("limit", 1000)), 2000)
        return jsonify(participant_service.list_participants(connection, event_id, query, limit=limit))

    @app.post("/api/participants/walkin")
    def api_add_walkin():
        connection = get_connection()
        client_id = require_role(connection, MUTATING_ROLES)
        require_not_frozen(connection)
        require_checkin_open(connection)
        payload = request.get_json(silent=True) or {}
        row = connection.execute("SELECT client_name FROM client_session WHERE id=?", (client_id,)).fetchone()
        try:
            participant = participant_service.add_walkin(
                connection, event_id, payload.get("name", ""), payload.get("phone", ""),
                client_id, row["client_name"] if row else ""
            )
        except ValueError as exc:
            raise ApiError(str(exc), 400)
        return jsonify({"participant": participant}), 201

    @app.get("/api/participants/<participant_id>")
    def api_get_participant(participant_id: str):
        connection = get_connection()
        require_role(connection, READ_ROLES)
        return jsonify(participant_service.get_participant(connection, participant_id))

    @app.patch("/api/participants/<participant_id>")
    def api_update_participant(participant_id: str):
        connection = get_connection()
        client_id = require_role(connection, MUTATING_ROLES)
        changes = request.get_json(silent=True) or {}
        return jsonify(participant_service.update_participant(connection, participant_id, changes, client_id))

    @app.post("/api/participants/<participant_id>/checkin")
    def api_checkin(participant_id: str):
        connection = get_connection()
        client_id = require_role(connection, CHECKIN_ROLES)
        require_not_frozen(connection)
        require_checkin_open(connection)
        row = connection.execute("SELECT client_name FROM client_session WHERE id = ?",
                                  (client_id,)).fetchone()
        client_name = row["client_name"] if row else ""
        result = participant_service.check_in(connection, participant_id, client_id, client_name,
                                               request.headers.get("X-Operation-Id"))
        status = 200 if result.get("already_checked_in") or result.get("already_processed") else 201
        return jsonify(result), status

    @app.post("/api/participants/<participant_id>/checkout")
    def api_checkout(participant_id: str):
        connection = get_connection()
        client_id = require_role(connection, CHECKIN_ROLES)
        require_not_frozen(connection)
        row = connection.execute("SELECT client_name FROM client_session WHERE id = ?",
                                  (client_id,)).fetchone()
        client_name = row["client_name"] if row else ""
        if session_service.freeze_state(connection)["checkout_required"]:
            result = participant_service.check_out(connection, participant_id, client_id, client_name,
                                                    request.headers.get("X-Operation-Id"))
        else:
            result = participant_service.undo_check_in(connection, participant_id, client_id, client_name,
                                                       request.headers.get("X-Operation-Id"))
        return jsonify(result)

    @app.post("/api/participants/<participant_id>/undo")
    def api_undo_checkin(participant_id: str):
        connection = get_connection(); client_id = require_role(connection, CHECKIN_ROLES)
        require_not_frozen(connection); require_checkin_open(connection)
        row = connection.execute("SELECT client_name FROM client_session WHERE id=?", (client_id,)).fetchone()
        return jsonify(participant_service.undo_check_in(connection, participant_id, client_id,
                       row["client_name"] if row else "", request.headers.get("X-Operation-Id")))

    # ---- Import --------------------------------------------------------------
    def _validate_upload(file_storage) -> tuple[Path, str]:
        original_name = secure_filename(file_storage.filename or "")
        suffix = Path(original_name).suffix.lower()
        if not original_name or suffix not in ALLOWED_IMPORT_EXTENSIONS:
            raise ApiError("Alleen .xlsx, .xlsm of .xls bestanden zijn toegestaan.", 400)
        import_dir = events_directory() / event_id / "imports"
        import_dir.mkdir(parents=True, exist_ok=True)
        target = import_dir / f"{uuid.uuid4()}{suffix}"
        file_storage.save(target)
        return target, original_name

    @app.post("/api/import/preview")
    def api_import_preview():
        connection = get_connection()
        require_role(connection, MUTATING_ROLES)
        if "file" not in request.files:
            raise ApiError("Geen bestand meegestuurd.", 400)
        stored_path, original_name = _validate_upload(request.files["file"])
        existing = participant_service.list_participants(connection, event_id, limit=5000)
        try:
            preview = importer.preview_import(stored_path, existing_participants=existing)
        except ValueError as exc:
            stored_path.unlink(missing_ok=True)
            raise ApiError(str(exc), 400)
        preview["file_name"] = original_name
        preview["import_token"] = stored_path.stem
        preview.pop("records", None)  # not needed client-side; kept server-side via the token
        logger.info("Importvoorbeeld gemaakt: %s (%d rijen)", preview["file_name"], preview["row_count"])
        return jsonify(preview)

    @app.post("/api/import/commit")
    def api_import_commit():
        connection = get_connection()
        client_id = require_role(connection, MUTATING_ROLES)
        payload = request.get_json(silent=True) or {}
        import_token = payload.get("import_token", "")
        if not import_token:
            raise ApiError("import_token ontbreekt.", 400)
        import_dir = events_directory() / event_id / "imports"
        matches = list(import_dir.glob(f"{secure_filename(import_token)}.*"))
        if not matches:
            raise ApiError("Importbestand niet gevonden (mogelijk verlopen); upload opnieuw.", 404)
        stored_path = matches[0]
        preview = importer.preview_import(stored_path)
        rows = importer.records_to_participants(preview["records"], event_id)
        count = participant_service.add_participants(connection, event_id, rows, client_id)
        stored_path.unlink(missing_ok=True)
        return jsonify({"imported": count})

    # ---- Statistics ------------------------------------------------------------
    def _include_introducees() -> bool:
        return request.args.get("include_introducees", "true").lower() != "false"

    def _inside_only() -> bool:
        return request.args.get("inside_only", "false").lower() == "true"

    @app.get("/api/statistics/overview")
    def api_stats_overview():
        connection = get_connection()
        return jsonify(statistics_service.overview(connection, event_id, _include_introducees()))

    @app.get("/api/statistics/attendance")
    def api_stats_attendance():
        connection = get_connection()
        return jsonify(statistics_service.attendance_timeline(connection, event_id))

    @app.get("/api/statistics/<dimension>")
    def api_stats_dimension(dimension: str):
        connection = get_connection()
        if dimension == "clients":
            return jsonify(statistics_service.client_checkin_counts(connection, event_id))
        try:
            return jsonify(statistics_service.breakdown_by_dimension(
                connection, event_id, dimension, _include_introducees(), _inside_only()))
        except ValueError as exc:
            raise ApiError(str(exc), 404)

    # ---- Live updates (SSE) -----------------------------------------------------
    @app.get("/api/events/stream")
    def api_events_stream():
        subscriber_id, subscriber_queue = hub.subscribe()

        def generate():
            yield from hub.stream(subscriber_id, subscriber_queue)

        return Response(stream_with_context(generate()), mimetype="text/event-stream",
                         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ---- Pages -----------------------------------------------------------------
    @app.get("/")
    def page_connect():
        connection = get_connection()
        session = session_service.get_session(connection)
        return render_template("connect.html", event=session)

    @app.get("/dashboard")
    def page_dashboard():
        connection = get_connection()
        session = session_service.get_session(connection)
        return render_template("dashboard.html", event=session, fullscreen=False)

    @app.get("/dashboard/fullscreen")
    def page_dashboard_fullscreen():
        connection = get_connection()
        session = session_service.get_session(connection)
        return render_template("dashboard.html", event=session, fullscreen=True)

    return app
