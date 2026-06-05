from typing import Any
from uuid import uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.database.database import SessionLocal

PROJECT_SMARTDOCS = "smartdocs"
EVENT_CHAT_QUESTION = "chat_question"
EVENT_RATE_LIMIT_BLOCKED = "rate_limit_blocked"
EVENT_SMART_INGEST_STARTED = "smart_ingest_started"
EVENT_SMART_INGEST_COMPLETED = "smart_ingest_completed"
EVENT_DOCUMENT_DELETED = "document_deleted"


def serialize_usage_log(row) -> dict[str, Any]:
    mapping = row._mapping
    created_at = mapping["created_at"]

    return {
        "id": str(mapping["id"]),
        "project": mapping["project"],
        "event_type": mapping["event_type"],
        "ip_address": mapping["ip_address"],
        "user_id": str(mapping["user_id"]) if mapping["user_id"] else None,
        "document_id": (
            str(mapping["document_id"]) if mapping["document_id"] else None
        ),
        "metadata": mapping["metadata"] or {},
        "created_at": created_at.isoformat() if created_at else None,
    }


def create_usage_log(
    event_type: str,
    ip_address: str | None = None,
    user_id: str | None = None,
    document_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    project: str = PROJECT_SMARTDOCS,
) -> dict[str, Any]:
    query = text(
        """
        INSERT INTO shared.usage_logs (
            id,
            project,
            event_type,
            ip_address,
            user_id,
            document_id,
            metadata
        )
        VALUES (
            CAST(:id AS UUID),
            :project,
            :event_type,
            :ip_address,
            CAST(NULLIF(:user_id, '') AS UUID),
            CAST(NULLIF(:document_id, '') AS UUID),
            :metadata
        )
        RETURNING
            id,
            project,
            event_type,
            ip_address,
            user_id,
            document_id,
            metadata,
            created_at
        """
    ).bindparams(bindparam("metadata", type_=JSONB))

    with SessionLocal() as db:
        row = db.execute(
            query,
            {
                "project": project,
                "id": str(uuid4()),
                "event_type": event_type,
                "ip_address": ip_address,
                "user_id": user_id or "",
                "document_id": document_id or "",
                "metadata": metadata or {},
            },
        ).fetchone()
        db.commit()

    return serialize_usage_log(row)


def list_usage_logs(limit: int = 50) -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    project,
                    event_type,
                    ip_address,
                    user_id,
                    document_id,
                    metadata,
                    created_at
                FROM shared.usage_logs
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).fetchall()

    return [serialize_usage_log(row) for row in rows]
