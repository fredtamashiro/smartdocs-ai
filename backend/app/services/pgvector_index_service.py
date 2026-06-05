import hashlib
import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text

from app.config import get_settings
from app.database.database import SessionLocal

DB_CHUNKS_URI_PREFIX = "db://chunks/"
DB_ENRICHED_CHUNKS_URI_PREFIX = "db://enriched_chunks/"
OPENAI_API_KEY_PLACEHOLDER = "sua_chave_aqui"


def load_chunks_from_json(chunks_file: str) -> dict[str, Any]:
    if chunks_file.startswith(DB_CHUNKS_URI_PREFIX):
        document_id = chunks_file.removeprefix(DB_CHUNKS_URI_PREFIX)
        return load_chunks_from_db(document_id)

    path = Path(chunks_file)

    if not path.exists():
        raise ValueError("Arquivo de chunks nao encontrado.")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_chunks_from_db(document_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        document_row = db.execute(
            text(
                """
                SELECT id, file_path, total_chunks
                FROM smartdocs.documents
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).fetchone()

        if document_row is None:
            raise ValueError("Documento de chunks nao encontrado no banco.")

        chunk_rows = db.execute(
            text(
                """
                SELECT
                    chunk_index,
                    page,
                    content,
                    char_count,
                    chunk_strategy,
                    metadata
                FROM smartdocs.chunks
                WHERE document_id = CAST(:document_id AS UUID)
                ORDER BY chunk_index ASC
                """
            ),
            {"document_id": document_id},
        ).fetchall()

    document = document_row._mapping
    chunks = []

    for row in chunk_rows:
        chunk = row._mapping
        chunks.append(
            {
                "chunk_index": chunk["chunk_index"],
                "page": chunk["page"],
                "content": chunk["content"],
                "char_count": chunk["char_count"],
                "chunk_strategy": chunk["chunk_strategy"],
                "metadata": chunk["metadata"] or {},
            }
        )

    return {
        "document_id": str(document["id"]),
        "source_file_path": document["file_path"],
        "chunk_strategy": "recursive_character",
        "total_chunks": document["total_chunks"] or len(chunks),
        "chunks": chunks,
    }


def load_enriched_chunks_payload(enriched_chunks_file: str) -> dict[str, Any]:
    if enriched_chunks_file.startswith(DB_ENRICHED_CHUNKS_URI_PREFIX):
        document_id = enriched_chunks_file.removeprefix(
            DB_ENRICHED_CHUNKS_URI_PREFIX
        ).split("/", maxsplit=1)[0]
        return load_enriched_chunks_from_db(document_id)

    path = Path(enriched_chunks_file)

    if not path.exists():
        raise ValueError("Arquivo de chunks enriquecidos nao encontrado.")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_enriched_chunks_from_db(document_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        document_row = db.execute(
            text(
                """
                SELECT
                    id,
                    file_path,
                    chunks_file,
                    total_chunks,
                    theme_id,
                    theme_name
                FROM smartdocs.documents
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).fetchone()

        if document_row is None:
            raise ValueError("Documento enriquecido nao encontrado no banco.")

        enriched_rows = db.execute(
            text(
                """
                SELECT
                    ec.chunk_index,
                    ec.page,
                    ec.content,
                    c.char_count,
                    c.chunk_strategy,
                    ec.is_valid,
                    ec.quality_score,
                    ec.title,
                    ec.summary,
                    ec.category,
                    ec.keywords,
                    ec.possible_questions,
                    ec.warnings,
                    ec.embedding_content,
                    ec.metadata
                FROM smartdocs.enriched_chunks ec
                LEFT JOIN smartdocs.chunks c
                    ON c.document_id = ec.document_id
                    AND c.chunk_index = ec.chunk_index
                WHERE ec.document_id = CAST(:document_id AS UUID)
                ORDER BY ec.chunk_index ASC
                """
            ),
            {"document_id": document_id},
        ).fetchall()

    document = document_row._mapping
    chunks = []

    for row in enriched_rows:
        chunk = row._mapping
        content = chunk["content"] or ""
        chunks.append(
            {
                "chunk_index": chunk["chunk_index"],
                "page": chunk["page"],
                "content": content,
                "char_count": chunk["char_count"] or len(content),
                "chunk_strategy": chunk["chunk_strategy"] or "unknown",
                "enrichment": {
                    "is_valid": chunk["is_valid"],
                    "quality_score": float(chunk["quality_score"] or 0),
                    "title": chunk["title"],
                    "summary": chunk["summary"],
                    "category": chunk["category"],
                    "keywords": chunk["keywords"] or [],
                    "possible_questions": chunk["possible_questions"] or [],
                    "warnings": chunk["warnings"] or [],
                },
                "embedding_content": chunk["embedding_content"],
                "metadata": chunk["metadata"] or {},
            }
        )

    return {
        "document_id": str(document["id"]),
        "source_file_path": document["file_path"],
        "original_chunks_file": document["chunks_file"],
        "total_original_chunks": document["total_chunks"] or len(chunks),
        "total_enriched_chunks": len(chunks),
        "enrichment_mode": "full",
        "chunks": chunks,
        "theme_id": document["theme_id"],
        "theme_name": document["theme_name"],
    }


def validate_openai_api_key() -> str:
    try:
        settings = get_settings()
    except Exception as error:
        raise ValueError(
            "OPENAI_API_KEY nao configurada. Defina uma chave valida em backend/.env."
        ) from error

    api_key = settings.openai_api_key

    if not api_key or api_key == OPENAI_API_KEY_PLACEHOLDER:
        raise ValueError(
            "OPENAI_API_KEY nao configurada. Defina uma chave valida em backend/.env."
        )

    return api_key


def create_documents_from_enriched_chunks(
    enriched_payload: dict[str, Any],
) -> tuple[list[Document], list[dict[str, Any]]]:
    document_id = enriched_payload["document_id"]
    chunks = enriched_payload.get("chunks", [])
    min_quality_score = get_settings().min_enriched_chunk_quality_score
    documents = []
    skipped_chunks = []

    for chunk in chunks:
        enrichment = chunk.get("enrichment", {})
        is_valid = enrichment.get("is_valid", True)
        quality_score = float(enrichment.get("quality_score", 0))
        embedding_content = (chunk.get("embedding_content") or "").strip()

        if is_valid is False:
            skipped_chunks.append(
                {
                    "chunk_index": chunk.get("chunk_index"),
                    "page": chunk.get("page"),
                    "reason": "Chunk marcado como invalido no enriquecimento.",
                }
            )
            continue

        if quality_score < min_quality_score:
            skipped_chunks.append(
                {
                    "chunk_index": chunk.get("chunk_index"),
                    "page": chunk.get("page"),
                    "reason": (
                        "quality_score abaixo do minimo "
                        f"({quality_score} < {min_quality_score})."
                    ),
                }
            )
            continue

        if not embedding_content:
            skipped_chunks.append(
                {
                    "chunk_index": chunk.get("chunk_index"),
                    "page": chunk.get("page"),
                    "reason": "embedding_content vazio ou invalido.",
                }
            )
            continue

        documents.append(
            Document(
                page_content=embedding_content,
                metadata={
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "page": chunk["page"],
                },
            )
        )

    return documents, skipped_chunks


def index_enriched_chunks_in_pgvector(enriched_chunks_file: str) -> dict[str, Any]:
    enriched_payload = load_enriched_chunks_payload(enriched_chunks_file)
    chunks = enriched_payload.get("chunks", [])

    if not chunks:
        raise ValueError("Nenhum chunk enriquecido encontrado para indexacao.")

    document_id = enriched_payload["document_id"]
    settings = get_settings()
    api_key = validate_openai_api_key()

    embeddings = OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        openai_api_key=api_key,
    )

    documents, skipped_chunks = create_documents_from_enriched_chunks(
        enriched_payload
    )

    try:
        embedding_result = save_embeddings_in_database(
            document_id=document_id,
            documents=documents,
            embeddings=embeddings,
            model=settings.openai_embedding_model,
        )
    except Exception as error:
        raise ValueError(
            f"Falha ao indexar chunks enriquecidos no pgvector: {error}"
        ) from error

    collection_name = f"pgvector_{document_id}"

    return {
        "document_id": document_id,
        "collection_name": collection_name,
        "retrieval_backend": "pgvector",
        "total_chunks": len(chunks),
        "total_enriched_chunks": len(chunks),
        "total_indexed_documents": embedding_result["total_embeddings"],
        "total_embeddings": embedding_result["total_embeddings"],
        "total_skipped_chunks": len(skipped_chunks)
        + embedding_result["total_skipped_chunks"],
        "total_documents": embedding_result["total_embeddings"],
        "skipped_chunks": skipped_chunks + embedding_result["skipped_chunks"],
    }


def save_embeddings_in_database(
    document_id: str,
    documents: list[Document],
    embeddings: OpenAIEmbeddings,
    model: str,
) -> dict[str, Any]:
    result = {
        "total_embeddings": 0,
        "total_skipped_chunks": 0,
        "skipped_chunks": [],
    }

    if not documents:
        return result

    with SessionLocal() as db:
        db.execute(
            text(
                """
                DELETE FROM smartdocs.embeddings
                WHERE document_id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        )

        insert_query = text(
            """
            INSERT INTO smartdocs.embeddings (
                id,
                document_id,
                enriched_chunk_id,
                embedding,
                model
            )
            SELECT
                CAST(:id AS UUID),
                CAST(:document_id AS UUID),
                ec.id,
                CAST(:embedding AS vector),
                :model
            FROM smartdocs.enriched_chunks ec
            WHERE ec.document_id = CAST(:document_id AS UUID)
              AND ec.chunk_index = :chunk_index
            """
        )

        for document in documents:
            chunk_index = document.metadata.get("chunk_index")
            page = document.metadata.get("page")

            try:
                if not document.page_content.strip():
                    raise ValueError("embedding_content vazio ou invalido.")

                vector = embeddings.embed_query(document.page_content)
                deterministic_hash = hashlib.md5(
                    (
                        document_id
                        + str(chunk_index)
                        + model
                    ).encode("utf-8")
                ).hexdigest()
                deterministic_id = (
                    f"{deterministic_hash[:8]}-"
                    f"{deterministic_hash[8:12]}-"
                    f"{deterministic_hash[12:16]}-"
                    f"{deterministic_hash[16:20]}-"
                    f"{deterministic_hash[20:]}"
                )

                with db.begin_nested():
                    db.execute(
                        insert_query,
                        {
                            "id": deterministic_id,
                            "document_id": document_id,
                            "chunk_index": chunk_index,
                            "embedding": f"[{','.join(str(value) for value in vector)}]",
                            "model": model,
                        },
                    )
                result["total_embeddings"] += 1
            except Exception as error:
                result["total_skipped_chunks"] += 1
                result["skipped_chunks"].append(
                    {
                        "chunk_index": chunk_index,
                        "page": page,
                        "reason": (
                            "Erro ao gerar ou persistir embedding: "
                            f"{error}"
                        ),
                    }
                )

        db.commit()

    return result
