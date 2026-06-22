from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    request_id: str
    stage: str
    outcome: str
    reason: str
    details: dict[str, Any]


class AuditLog:
    """Small in-memory audit sink. Replace with OpenTelemetry/SIEM in production."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(
        self,
        *,
        request_id: str,
        stage: str,
        outcome: str,
        reason: str,
        **details: Any,
    ) -> None:
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request_id,
            stage=stage,
            outcome=outcome,
            reason=reason,
            details=details,
        )
        with self._lock:
            self._events.append(event)

    def list_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(event) for event in self._events]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
