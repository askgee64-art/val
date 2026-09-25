"""Immutable audit logger — Document 21 §4.12 / Master Spec §11.

Every significant action is appended. Updates and deletes are forbidden
both at the ORM layer and here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from val.config import get_settings
from val.db.models import AuditLog, Event


class AuditLogger:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._file_path = Path(self._settings.audit_dir) / "audit.jsonl"
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

    async def log(
        self,
        session: AsyncSession,
        *,
        org_id: str,
        actor_type: str,
        action: str,
        actor_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        emit_event: bool = True,
    ) -> AuditLog:
        entry = AuditLog(
            log_id=str(uuid4()),
            org_id=org_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc),
        )
        session.add(entry)

        # Dual-write to append-only JSONL for durability outside DB
        self._append_file(entry)

        if emit_event:
            session.add(
                Event(
                    event_id=str(uuid4()),
                    org_id=org_id,
                    event_type=f"audit.{action}",
                    payload={
                        "log_id": entry.log_id,
                        "actor_type": actor_type,
                        "actor_id": actor_id,
                        "action": action,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "details": details or {},
                    },
                    source="audit",
                )
            )

        return entry

    def _append_file(self, entry: AuditLog) -> None:
        record = {
            "log_id": entry.log_id,
            "org_id": entry.org_id,
            "actor_type": entry.actor_type,
            "actor_id": entry.actor_id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "details": entry.details,
            "ip_address": entry.ip_address,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")


_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger
