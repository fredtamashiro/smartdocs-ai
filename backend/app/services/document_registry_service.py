from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.database.database import SessionLocal


def serialize_document(row) -> dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    created_at = mapping["created_at"]
    updated_at = mapping["updated_at"]

    return {
        "document_id": str(mapping["id"]),
        "collection_name": mapping["collection_name"],
        "original_filename": mapping["original_filename"],
        "stored_filename": mapping["stored_filename"],
        "file_path": mapping["file_path"],
        "storage_url": mapping["storage_url"],
        "chunks_file": mapping["chunks_file"],
        "enriched_chunks_file": mapping["enriched_chunks_file"],
        "enriched_collection_name": mapping["enriched_collection_name"],
        "retrieval_mode": mapping["retrieval_mode"],
        "theme_id": mapping["theme_id"],
        "theme_name": mapping["theme_name"],
        "total_pages": mapping["total_pages"] or 0,
        "total_chars": mapping["total_chars"] or 0,
        "total_chunks": mapping["total_chunks"] or 0,
        "document_summary": mapping["document_summary"],
        "document_type": mapping["document_type"],
        "main_topics": mapping["main_topics"] or [],
        "suggested_questions": mapping["suggested_questions"] or [],
        "summary_limitations": mapping["summary_limitations"] or [],
        "status": mapping["status"],
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


DOCUMENT_COLUMNS = """
    id,
    collection_name,
    original_filename,
    stored_filename,
    file_path,
    storage_url,
    chunks_file,
    enriched_chunks_file,
    enriched_collection_name,
    retrieval_mode,
    theme_id,
    theme_name,
    total_pages,
    total_chars,
    total_chunks,
    document_summary,
    document_type,
    main_topics,
    suggested_questions,
    summary_limitations,
    status,
    created_at,
    updated_at
"""


def list_registered_documents() -> list[dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            text(
                f"""
                SELECT {DOCUMENT_COLUMNS}
                FROM smartdocs.documents
                WHERE status = 'active'
                ORDER BY created_at DESC
                """
            )
        ).fetchall()

    return [serialize_document(row) for row in rows]


def register_document(document_payload: dict[str, Any]) -> dict[str, Any]:
    query = text(
        f"""
        INSERT INTO smartdocs.documents (
            id,
            collection_name,
            original_filename,
            stored_filename,
            file_path,
            storage_url,
            chunks_file,
            enriched_chunks_file,
            enriched_collection_name,
            retrieval_mode,
            theme_id,
            theme_name,
            total_pages,
            total_chars,
            total_chunks,
            document_summary,
            document_type,
            main_topics,
            suggested_questions,
            summary_limitations,
            status
        )
        VALUES (
            CAST(:document_id AS UUID),
            :collection_name,
            :original_filename,
            :stored_filename,
            :file_path,
            :storage_url,
            :chunks_file,
            :enriched_chunks_file,
            :enriched_collection_name,
            :retrieval_mode,
            :theme_id,
            :theme_name,
            :total_pages,
            :total_chars,
            :total_chunks,
            :document_summary,
            :document_type,
            :main_topics,
            :suggested_questions,
            :summary_limitations,
            :status
        )
        ON CONFLICT (id) DO UPDATE SET
            collection_name = EXCLUDED.collection_name,
            original_filename = EXCLUDED.original_filename,
            stored_filename = EXCLUDED.stored_filename,
            file_path = EXCLUDED.file_path,
            storage_url = EXCLUDED.storage_url,
            chunks_file = EXCLUDED.chunks_file,
            enriched_chunks_file = EXCLUDED.enriched_chunks_file,
            enriched_collection_name = EXCLUDED.enriched_collection_name,
            retrieval_mode = EXCLUDED.retrieval_mode,
            theme_id = EXCLUDED.theme_id,
            theme_name = EXCLUDED.theme_name,
            total_pages = EXCLUDED.total_pages,
            total_chars = EXCLUDED.total_chars,
            total_chunks = EXCLUDED.total_chunks,
            document_summary = EXCLUDED.document_summary,
            document_type = EXCLUDED.document_type,
            main_topics = EXCLUDED.main_topics,
            suggested_questions = EXCLUDED.suggested_questions,
            summary_limitations = EXCLUDED.summary_limitations,
            status = EXCLUDED.status,
            updated_at = NOW()
        RETURNING {DOCUMENT_COLUMNS}
        """
    ).bindparams(
        bindparam("main_topics", type_=JSONB),
        bindparam("suggested_questions", type_=JSONB),
        bindparam("summary_limitations", type_=JSONB),
    )

    with SessionLocal() as db:
        row = db.execute(
            query,
            {
                "document_id": document_payload["document_id"],
                "collection_name": document_payload.get("collection_name"),
                "original_filename": document_payload["original_filename"],
                "stored_filename": document_payload["stored_filename"],
                "file_path": document_payload.get("file_path"),
                "storage_url": document_payload.get("storage_url"),
                "chunks_file": document_payload.get("chunks_file"),
                "enriched_chunks_file": document_payload.get(
                    "enriched_chunks_file"
                ),
                "enriched_collection_name": document_payload.get(
                    "enriched_collection_name"
                ),
                "retrieval_mode": document_payload.get("retrieval_mode", "pgvector"),
                "theme_id": document_payload.get("theme_id"),
                "theme_name": document_payload.get("theme_name"),
                "total_pages": document_payload.get("total_pages", 0),
                "total_chars": document_payload.get("total_chars", 0),
                "total_chunks": document_payload.get("total_chunks", 0),
                "document_summary": document_payload.get("document_summary"),
                "document_type": document_payload.get("document_type"),
                "main_topics": document_payload.get("main_topics", []),
                "suggested_questions": document_payload.get(
                    "suggested_questions",
                    [],
                ),
                "summary_limitations": document_payload.get(
                    "summary_limitations",
                    [],
                ),
                "status": document_payload.get("status", "active"),
            },
        ).fetchone()
        db.commit()

    return serialize_document(row)


def find_registered_document_by_id(document_id: str) -> dict[str, Any] | None:
    with SessionLocal() as db:
        row = db.execute(
            text(
                f"""
                SELECT {DOCUMENT_COLUMNS}
                FROM smartdocs.documents
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).fetchone()

    if row is None:
        return None

    return serialize_document(row)


def delete_registered_document(document_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        row = db.execute(
            text(
                f"""
                DELETE FROM smartdocs.documents
                WHERE id = CAST(:document_id AS UUID)
                RETURNING {DOCUMENT_COLUMNS}
                """
            ),
            {"document_id": document_id},
        ).fetchone()
        db.commit()

    if row is None:
        raise ValueError("Documento não encontrado.")

    return serialize_document(row)


def delete_document_from_database(document_id: str) -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                DELETE FROM smartdocs.documents
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        )
        db.commit()


def update_registered_document(
    document_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    allowed_fields = {
        "collection_name",
        "original_filename",
        "stored_filename",
        "file_path",
        "storage_url",
        "chunks_file",
        "enriched_chunks_file",
        "enriched_collection_name",
        "retrieval_mode",
        "theme_id",
        "theme_name",
        "total_pages",
        "total_chars",
        "total_chunks",
        "document_summary",
        "document_type",
        "main_topics",
        "suggested_questions",
        "summary_limitations",
        "status",
    }
    safe_updates = {
        key: value
        for key, value in updates.items()
        if key in allowed_fields
    }

    if not safe_updates:
        current_document = find_registered_document_by_id(document_id)

        if current_document is None:
            raise ValueError("Documento não encontrado.")

        return current_document

    assignments = []
    parameters: dict[str, Any] = {"document_id": document_id}

    for field, value in safe_updates.items():
        assignments.append(f"{field} = :{field}")
        parameters[field] = value

    query = text(
        f"""
        UPDATE smartdocs.documents
        SET
            {", ".join(assignments)},
            updated_at = NOW()
        WHERE id = CAST(:document_id AS UUID)
        RETURNING {DOCUMENT_COLUMNS}
        """
    ).bindparams(
        bindparam("main_topics", type_=JSONB, required=False),
        bindparam("suggested_questions", type_=JSONB, required=False),
        bindparam("summary_limitations", type_=JSONB, required=False),
    )

    with SessionLocal() as db:
        row = db.execute(query, parameters).fetchone()
        db.commit()

    if row is None:
        raise ValueError("Documento não encontrado.")

    return serialize_document(row)
