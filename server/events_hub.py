"""Live-update broadcast hub.

The spec asks for WebSockets. This environment cannot install/verify
`websockets`/`flask-sock`/ASGI packages (no network access during
development), so v1 uses **Server-Sent Events (SSE)** instead: a plain,
dependency-free, one-way push channel built on standard HTTP that every
modern browser (including mobile Safari/Chrome) supports natively via
`EventSource`, and that degrades gracefully on a LAN with no internet
access (no CDN, no extra protocol handshake).

The event *names* and *payloads* match the spec (participant_created,
participant_updated, participant_checked_in, participant_checked_out,
statistics_updated, client_connected, client_disconnected), so swapping
the transport for real WebSockets later (e.g. once FastAPI/uvicorn can
be added on the build machine) only touches this file and the two lines
in web/app.py that expose the stream endpoint — every publisher call
site (services/*.py) stays the same.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Iterator

from .logging_setup import get_logger

logger = get_logger("events_hub")


class EventHub:
    def __init__(self):
        self._subscribers: dict[str, "queue.Queue[str]"] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def subscribe(self) -> tuple[str, "queue.Queue[str]"]:
        with self._lock:
            self._counter += 1
            subscriber_id = f"sub-{self._counter}"
            subscriber_queue: "queue.Queue[str]" = queue.Queue(maxsize=200)
            self._subscribers[subscriber_id] = subscriber_queue
        return subscriber_id, subscriber_queue

    def unsubscribe(self, subscriber_id: str) -> None:
        with self._lock:
            self._subscribers.pop(subscriber_id, None)

    def publish(self, event_type: str, payload: dict) -> None:
        message = json.dumps({"type": event_type, **payload}, ensure_ascii=False, default=str)
        with self._lock:
            subscribers = list(self._subscribers.items())
        for subscriber_id, subscriber_queue in subscribers:
            try:
                subscriber_queue.put_nowait(message)
            except queue.Full:
                logger.warning("SSE-subscriber %s loopt achter, oudste update overgeslagen.", subscriber_id)

    def stream(self, subscriber_id: str, subscriber_queue: "queue.Queue[str]") -> Iterator[str]:
        """Generator producing an SSE stream body, with periodic keep-alive comments."""
        try:
            yield "retry: 2000\n\n"
            while True:
                try:
                    message = subscriber_queue.get(timeout=15)
                    yield f"data: {message}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            pass
        finally:
            self.unsubscribe(subscriber_id)


# Process-wide singleton; one server process serves one event session.
hub = EventHub()
