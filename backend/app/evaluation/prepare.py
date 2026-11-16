"""Idempotently load synthetic chunks into the existing pgvector schema."""

from uuid import NAMESPACE_URL, uuid5

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import text

from app.config import get_settings
from app.database.database import SessionLocal
from app.evaluation.dataset import document_id
from app.services.document_registry_service import register_document
from app.services.pgvector_index_service import save_embeddings_in_database, validate_openai_api_key


def prepare_local_documents(dataset: dict) -> list[dict]:
    settings = get_settings()
    if settings.app_env.lower() not in {"local", "development", "test"}:
        raise ValueError("Preparação de avaliação permitida apenas em ambiente local/development/test")

    prepared = []
    for document in dataset["documents"]:
        doc_id = document_id(dataset, document["ref"])
        chunks = document["chunks"]
        register_document({
            "document_id": doc_id,
            "collection_name": f"pgvector_{doc_id}",
            "original_filename": f"{document['ref']}.synthetic.txt",
            "stored_filename": f"{document['ref']}.synthetic.txt",
            "retrieval_mode": "pgvector",
            "theme_id": "generic_pdf",
            "theme_name": "PDF genérico",
            "total_pages": len(chunks),
            "total_chars": sum(len(chunk["text"]) for chunk in chunks),
            "total_chunks": len(chunks),
            "document_summary": document["title"],
            "status": "evaluation",
        })
        with SessionLocal() as db:
            for index, chunk in enumerate(chunks):
                chunk_id = str(uuid5(NAMESPACE_URL, f"{doc_id}/chunk/{index}"))
                enriched_id = str(uuid5(NAMESPACE_URL, f"{doc_id}/enriched/{index}"))
                db.execute(text("""
                    INSERT INTO smartdocs.chunks (id, document_id, chunk_index, page, content, char_count, chunk_strategy)
                    VALUES (CAST(:id AS uuid), CAST(:document_id AS uuid), :chunk_index, :page, :content, :char_count, 'synthetic_eval')
                    ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                        content = EXCLUDED.content, char_count = EXCLUDED.char_count, page = EXCLUDED.page
                """), {"id": chunk_id, "document_id": doc_id, "chunk_index": index,
                       "page": chunk["page"], "content": chunk["text"], "char_count": len(chunk["text"])})
                db.execute(text("""
                    INSERT INTO smartdocs.enriched_chunks
                        (id, document_id, chunk_id, chunk_index, page, content, embedding_content,
                         is_valid, quality_score, title, summary)
                    VALUES (CAST(:id AS uuid), CAST(:document_id AS uuid), CAST(:chunk_id AS uuid),
                            :chunk_index, :page, :content, :embedding_content, TRUE, 1.0, :title, :summary)
                    ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                        content = EXCLUDED.content, embedding_content = EXCLUDED.embedding_content,
                        page = EXCLUDED.page, title = EXCLUDED.title, summary = EXCLUDED.summary,
                        is_valid = TRUE, quality_score = 1.0
                """), {"id": enriched_id, "document_id": doc_id, "chunk_id": chunk_id,
                       "chunk_index": index, "page": chunk["page"], "content": chunk["text"],
                       "embedding_content": chunk["text"], "title": document["title"],
                       "summary": chunk["text"][:200]})
            db.commit()

        with SessionLocal() as db:
            existing = db.execute(text("""
                SELECT COUNT(*) FROM smartdocs.embeddings
                WHERE document_id = CAST(:document_id AS uuid) AND model = :model
            """), {"document_id": doc_id, "model": settings.openai_embedding_model}).scalar_one()
        if existing == len(chunks):
            prepared.append({"document": document["ref"], "chunks": len(chunks), "embedding_status": "reused"})
            continue

        embeddings = OpenAIEmbeddings(model=settings.openai_embedding_model, openai_api_key=validate_openai_api_key())
        from langchain_core.documents import Document
        documents = [Document(page_content=chunk["text"], metadata={"chunk_index": index, "page": chunk["page"]})
                     for index, chunk in enumerate(chunks)]
        result = save_embeddings_in_database(doc_id, documents, embeddings, settings.openai_embedding_model)
        if result["total_embeddings"] != len(chunks):
            raise RuntimeError(f"Indexação sintética incompleta: {document['ref']}")
        prepared.append({"document": document["ref"], "chunks": len(chunks), "embedding_status": "created"})
    return prepared


def assert_prepared(dataset: dict) -> None:
    """Avoid evaluating empty retrieval due to a forgotten preparation step."""
    with SessionLocal() as db:
        for document in dataset["documents"]:
            doc_id = document_id(dataset, document["ref"])
            count = db.execute(text("""
                SELECT COUNT(*) FROM smartdocs.embeddings
                WHERE document_id = CAST(:document_id AS uuid) AND model = :model
            """), {"document_id": doc_id, "model": get_settings().openai_embedding_model}).scalar_one()
            if count != len(document["chunks"]):
                raise RuntimeError(f"Documento sintético não preparado: {document['ref']}")
