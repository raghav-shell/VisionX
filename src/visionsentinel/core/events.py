"""Scan event log (the operational timeline shown while a scan runs)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from ..contracts import ScanEvent


class EventLog:
    def __init__(self, on_event: Callable[[ScanEvent], None] | None = None) -> None:
        self._start = time.monotonic()
        self._lock = threading.Lock()
        self._events: list[ScanEvent] = []
        self._on_event = on_event

    def emit(self, message: str, *, level: str = "info", detector_id: str | None = None) -> ScanEvent:
        with self._lock:
            event = ScanEvent(seq=len(self._events) + 1, t_ms=int((time.monotonic() - self._start) * 1000),
                              level=level, message=message, detector_id=detector_id)
            self._events.append(event)
        if self._on_event is not None:
            self._on_event(event)
        return event

    def stage(self, message: str) -> ScanEvent:
        return self.emit(message, level="stage")

    @property
    def events(self) -> list[ScanEvent]:
        with self._lock:
            return list(self._events)
